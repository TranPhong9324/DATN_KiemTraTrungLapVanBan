from contextlib import asynccontextmanager
from pathlib import Path
from threading import BoundedSemaphore
from time import perf_counter
from typing import Literal
from urllib.parse import urlsplit
from uuid import uuid4
import logging

from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from starlette.middleware.trustedhost import TrustedHostMiddleware

from app.config import ROOT, Settings
from app.db import Database
from app.models import Check, Chunk, Document
from app.services.checker import Checker, EngineUnavailable, cosine, features, filter_chunks, make_report
from app.services.documents import DocumentError, extract_chunks, file_hash, safe_filename, validate_file
from app.services.serper import SerperClient, SerperError, web_query_from_text

logger = logging.getLogger(__name__)


def create_app(settings: Settings | None = None, database=None):
    settings = settings or Settings.load()
    database = database or (Database(settings.database_url) if settings.database_url else None)
    checker = Checker(settings)
    processing = BoundedSemaphore(1)  # Initial single-process/local deployment.

    @asynccontextmanager
    async def lifespan(app):
        settings.upload_dir.mkdir(parents=True, exist_ok=True)
        yield
        if database:
            database.engine.dispose()

    app = FastAPI(title="Đối chiếu báo cáo đồ án", version="0.1.0", lifespan=lifespan)
    app.state.settings = settings
    app.state.database = database
    app.state.checker = checker
    app.state.serper = SerperClient(settings.serper_api_key, settings.serper_timeout) if settings.serper_api_key else None
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=["127.0.0.1", "localhost", "[::1]", "testserver"])

    @app.middleware("http")
    async def local_guard(request: Request, call_next):
        if request.method in {"POST", "PUT", "PATCH", "DELETE"}:
            origin = request.headers.get("origin")
            if origin and urlsplit(origin).netloc != request.headers.get("host"):
                return JSONResponse({"detail": "Yêu cầu phải gửi từ chính trang web đang mở."}, status_code=403)
            try:
                length = int(request.headers.get("content-length", "0"))
            except ValueError:
                return JSONResponse({"detail": "Content-Length không hợp lệ."}, status_code=400)
            if length > settings.max_upload_mb * 1024 * 1024 + 64 * 1024:
                return JSONResponse({"detail": f"Chỉ nhận tệp tối đa {settings.max_upload_mb} MB."}, status_code=413)
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "same-origin"
        if request.url.path not in {"/docs", "/redoc", "/docs/oauth2-redirect"}:
            frame_ancestors = "'self'" if request.url.path.startswith("/api/documents/") and request.url.path.endswith("/preview") else "'none'"
            response.headers["Content-Security-Policy"] = f"default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'; frame-ancestors {frame_ancestors}; base-uri 'self'; form-action 'self'"
        if request.url.path.startswith("/api/"):
            response.headers["Cache-Control"] = "no-store"
        return response

    @app.exception_handler(SQLAlchemyError)
    async def database_error(request, error):
        logger.warning("Database operation failed (%s)", type(error).__name__)
        return JSONResponse({"detail": "PostgreSQL chưa sẵn sàng. Kiểm tra .env và chạy python -m app.db init."}, status_code=503)

    def require_db():
        if database is None:
            raise HTTPException(503, "Chưa cấu hình PostgreSQL. Điền .env theo .env.example rồi khởi động lại web.")
        return database

    def reference_rows(session):
        rows = session.execute(
            select(Chunk, Document.filename).join(Document, Chunk.document_id == Document.id)
            .where(Document.role == "reference").order_by(Document.id, Chunk.ordinal)
            .limit(settings.max_reference_chunks + 1)
        ).all()
        if len(rows) > settings.max_reference_chunks:
            raise HTTPException(409, "Kho vượt giới hạn bản thử nghiệm. Cần tăng giới hạn hoặc nâng cấp cơ chế lập chỉ mục.")
        return [{"id": chunk.id, "ordinal": chunk.ordinal, "text": chunk.text, "location": chunk.location, "document_id": chunk.document_id, "filename": name} for chunk, name in rows]

    def process_upload(upload, role, engine="semantic", threshold=0.68):
        db = require_db()
        if role == "submission" and engine not in {"lexical", "semantic"}:
            raise HTTPException(422, "Chế độ kiểm tra không hợp lệ.")
        if role == "submission" and engine == "semantic" and not settings.enable_semantic:
            raise HTTPException(503, "Chưa bật chế độ ngữ nghĩa. Cài requirements.txt và đặt ENABLE_SEMANTIC=true trong .env.")
        if not processing.acquire(blocking=False):
            raise HTTPException(409, "Một tài liệu khác đang được xử lý. Vui lòng thử lại khi hoàn tất.")
        saved_path, committed = None, False
        started = perf_counter()
        try:
            name = safe_filename(upload.filename or "")
            suffix = Path(name).suffix.lower()
            if suffix not in {".pdf", ".docx"}:
                raise HTTPException(415, "Chỉ hỗ trợ PDF và DOCX.")
            with db.session() as session:
                references = reference_rows(session) if role == "submission" else []
                if role == "submission" and not references:
                    raise HTTPException(409, "Kho tham chiếu đang trống. Hãy thêm ít nhất một tài liệu nguồn trước khi kiểm tra.")
                settings.upload_dir.mkdir(parents=True, exist_ok=True)
                stored_name = f"{uuid4()}{suffix}"
                saved_path = settings.upload_dir / stored_name
                size = 0
                with saved_path.open("xb") as target:
                    while block := upload.file.read(1024 * 1024):
                        size += len(block)
                        if size > settings.max_upload_mb * 1024 * 1024:
                            raise HTTPException(413, f"Tệp vượt giới hạn {settings.max_upload_mb} MB.")
                        target.write(block)
                validate_file(saved_path, suffix, settings.max_upload_mb * 1024 * 1024)
                digest = file_hash(saved_path)
                if role == "reference" and session.scalar(select(Document.id).where(Document.reference_hash == digest)):
                    raise HTTPException(409, "Tài liệu này đã có trong kho tham chiếu, kể cả khi đổi tên tệp.")
                extracted = extract_chunks(saved_path, settings)
                if role == "reference":
                    count = session.scalar(select(func.count(Chunk.id)).join(Document).where(Document.role == "reference")) or 0
                    if count + len(extracted.chunks) > settings.max_reference_chunks:
                        raise HTTPException(409, "Kho tham chiếu đã đạt giới hạn số đoạn của bản thử nghiệm.")
                document = Document(
                    id=str(uuid4()), filename=name, file_type=suffix[1:], role=role,
                    sha256=digest, reference_hash=digest if role == "reference" else None,
                    stored_name=stored_name, size_bytes=size, warnings=extracted.warnings,
                )
                for ordinal, chunk in enumerate(extracted.chunks):
                    document.chunks.append(Chunk(id=str(uuid4()), ordinal=ordinal, text=chunk["text"], location=chunk["location"]))
                session.add(document)
                session.flush()
                if role == "reference":
                    result = {"id": document.id, "filename": name, "chunks": len(document.chunks), "warnings": document.warnings}
                else:
                    all_queries = [{"id": chunk.id, "ordinal": chunk.ordinal, "text": chunk.text, "location": chunk.location} for chunk in document.chunks]
                    queries, ignored_queries = filter_chunks(all_queries)
                    eligible_references, ignored_references = filter_chunks(references)
                    if not queries:
                        raise HTTPException(422, "Tài liệu chỉ chứa mục lục, tài liệu tham khảo hoặc nội dung mẫu; không còn đoạn phù hợp để kiểm tra.")
                    if not eligible_references:
                        raise HTTPException(409, "Kho nguồn không còn đoạn phù hợp sau khi loại mục lục, tài liệu tham khảo và nội dung mẫu.")
                    rankings = checker.search(queries, eligible_references, engine)
                    configured_threshold = settings.semantic_threshold if engine == "semantic" else settings.lexical_threshold
                    result = make_report(
                        document, queries, eligible_references, rankings, engine, threshold,
                        settings.semantic_model,
                        threshold_calibrated=abs(threshold - configured_threshold) < 1e-9,
                        ignored={"queries": ignored_queries, "references": ignored_references},
                        original_query_count=len(all_queries),
                        original_queries=all_queries,
                        max_alerts=settings.max_alerts_per_report,
                        max_per_source=settings.max_alerts_per_source,
                    )
                    result["chunk_chars"] = settings.chunk_chars
                    result["elapsed_seconds"] = round(perf_counter() - started, 3)
                    result["internet_search"] = search_internet(queries, rankings)
                    check_id = str(uuid4())
                    result["id"] = check_id
                    session.add(Check(id=check_id, document_id=document.id, engine=engine, threshold=threshold, coverage=result["coverage"], report=result))
                session.commit()
                committed = True
                return result
        except DocumentError as error:
            raise HTTPException(422, str(error)) from error
        except EngineUnavailable as error:
            raise HTTPException(503, str(error)) from error
        except IntegrityError as error:
            raise HTTPException(409, "Tài liệu nguồn đã tồn tại hoặc dữ liệu thay đổi trong lúc xử lý. Hãy tải lại danh sách.") from error
        finally:
            if saved_path and not committed:
                saved_path.unlink(missing_ok=True)
            upload.file.close()
            processing.release()

    def search_internet(queries, rankings):
        """Search Internet only after the internal checker has ranked all chunks."""
        if app.state.serper is None:
            return {"enabled": False, "provider": "serper", "queries": [], "matches": [], "warning": "Chưa cấu hình SERPER_API_KEY."}
        ranked = []
        for query, candidates in zip(queries, rankings):
            local_score = max((float(score) for _, score in candidates), default=0.0)
            ranked.append((local_score, len(query.get("text", "")), query))
        ranked.sort(key=lambda row: (-row[0], -row[1], row[2].get("ordinal", 0)))
        searches, matches = [], []
        for local_score, _, query in ranked:
            if len(searches) >= settings.serper_max_queries:
                break
            phrase = web_query_from_text(query.get("text", ""))
            if not phrase:
                continue
            try:
                payload = app.state.serper.search(phrase, num=settings.serper_max_results)
            except SerperError as error:
                return {"enabled": True, "provider": "serper", "queries": searches, "matches": matches, "warning": str(error)}
            searches.append({"query_id": query["id"], "ordinal": query.get("ordinal", 0), "text": query["text"], "phrase": phrase, "local_score": round(local_score, 6), "result_count": len(payload["organic"])})
            for item in payload["organic"]:
                comparison = f'{item.get("title", "")} {item.get("snippet", "")}'
                web_score = cosine(features(query["text"]), features(comparison))
                matches.append({
                    **item, "query_id": query["id"], "query_ordinal": query.get("ordinal", 0),
                    "query_text": query["text"], "web_score": round(web_score, 6),
                    "candidate": web_score >= settings.serper_similarity_threshold,
                })
        matches.sort(key=lambda item: (-item["candidate"], -item["web_score"], item["query_ordinal"], item.get("position") or 0))
        return {"enabled": True, "provider": "serper", "queries": searches, "matches": matches, "warning": None}

    @app.get("/api/health")
    def health():
        state, detail = "not_configured", "Điền thông tin PostgreSQL vào .env rồi khởi động lại web."
        if database:
            try:
                database.verify()
                state, detail = "ready", "PostgreSQL đã kết nối."
            except Exception:
                state, detail = "unavailable", "Chưa kết nối được PostgreSQL hoặc chưa có bảng. Kiểm tra .env rồi chạy python -m app.db init."
        if settings.enable_ocr:
            from app.services.ocr import ocr_status
            ocr = {"enabled": True, **ocr_status(settings.tesseract_cmd, settings.ocr_language)}
        else:
            ocr = {"enabled": False, "available": False, "detail": "OCR đang tắt trong cấu hình.", "languages": []}
        return {
            "database": state, "detail": detail, "max_upload_mb": settings.max_upload_mb,
            "semantic_enabled": settings.enable_semantic,
            "thresholds": {"lexical": settings.lexical_threshold, "semantic": settings.semantic_threshold},
            "alert_limits": {"per_source": settings.max_alerts_per_source, "per_report": settings.max_alerts_per_report},
            "ocr": ocr,
            "serper_configured": app.state.serper is not None,
        }

    @app.post("/api/web-search")
    def web_search(payload: dict):
        if app.state.serper is None:
            raise HTTPException(503, "Chưa cấu hình SERPER_API_KEY trong .env. Khởi động lại web sau khi thêm key.")
        query = payload.get("query") if isinstance(payload, dict) else None
        if not isinstance(query, str) or not query.strip():
            raise HTTPException(422, "Cần nhập cụm từ hoặc câu cần tìm.")
        try:
            return app.state.serper.search(query, num=payload.get("num", settings.serper_max_results))
        except (SerperError, ValueError) as error:
            raise HTTPException(502, str(error)) from error

    @app.get("/api/documents")
    def documents(role: Literal["reference", "submission"] | None = None):
        with require_db().session() as session:
            statement = select(Document, func.count(Chunk.id)).outerjoin(Chunk)
            if role:
                statement = statement.where(Document.role == role)
            rows = session.execute(statement.group_by(Document.id).order_by(Document.created_at.desc()).limit(100)).all()
            return [{"id": doc.id, "filename": doc.filename, "role": doc.role, "file_type": doc.file_type, "chunks": count, "size_bytes": doc.size_bytes, "warnings": doc.warnings, "created_at": doc.created_at.isoformat()} for doc, count in rows]

    @app.get("/api/stats")
    def stats():
        with require_db().session() as session:
            return {
                "references": session.scalar(select(func.count(Document.id)).where(Document.role == "reference")),
                "reference_chunks": session.scalar(select(func.count(Chunk.id)).join(Document).where(Document.role == "reference")),
                "checks": session.scalar(select(func.count(Check.id))),
            }

    @app.post("/api/references", status_code=201)
    def add_reference(file: UploadFile = File(...)):
        return process_upload(file, "reference")

    @app.post("/api/checks", status_code=201)
    def check_document(file: UploadFile = File(...), engine: str = Form("semantic"), threshold: float = Form(0.68, gt=0, le=1)):
        return process_upload(file, "submission", engine, threshold)

    @app.get("/api/checks")
    def checks():
        with require_db().session() as session:
            return [{"id": check.id, "filename": name, "engine": check.engine, "coverage": check.coverage, "created_at": check.created_at.isoformat()} for check, name in session.execute(select(Check, Document.filename).join(Document).order_by(Check.created_at.desc()).limit(100))]

    @app.get("/api/checks/{check_id}")
    def report(check_id: str):
        with require_db().session() as session:
            check = session.get(Check, check_id)
            if not check:
                raise HTTPException(404, "Không tìm thấy kết quả kiểm tra.")
            return check.report

    @app.get("/api/documents/{document_id}/file")
    def download(document_id: str):
        with require_db().session() as session:
            document = session.get(Document, document_id)
            if not document:
                raise HTTPException(404, "Không tìm thấy tài liệu.")
            target = (settings.upload_dir / document.stored_name).resolve()
            if target.parent != settings.upload_dir.resolve() or not target.is_file():
                raise HTTPException(404, "Tệp gốc không còn trong kho lưu trữ.")
            return FileResponse(target, filename=document.filename, media_type="application/octet-stream")

    @app.get("/api/documents/{document_id}/preview")
    def preview(document_id: str):
        from app.services.preview import PreviewError, render_docx_html
        with require_db().session() as session:
            document = session.get(Document, document_id)
            if not document:
                raise HTTPException(404, "Không tìm thấy tài liệu.")
            source = settings.upload_dir / document.stored_name
            if document.file_type == "pdf":
                target = source.resolve()
                if target.parent != settings.upload_dir.resolve() or not target.is_file():
                    raise HTTPException(404, "Tệp gốc không còn trong kho lưu trữ.")
                return FileResponse(target, media_type="application/pdf", headers={"Content-Disposition": "inline"})
            try:
                return HTMLResponse(render_docx_html(source, settings.upload_dir, document.filename))
            except PreviewError as error:
                raise HTTPException(503, str(error)) from error

    app.mount("/static", StaticFiles(directory=ROOT / "frontend"), name="static")

    @app.get("/", include_in_schema=False)
    def index():
        return FileResponse(ROOT / "frontend" / "index.html")

    return app


app = create_app()
