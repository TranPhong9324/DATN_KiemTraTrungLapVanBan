from contextlib import asynccontextmanager
from pathlib import Path
from threading import BoundedSemaphore
from time import perf_counter
from typing import Literal
from urllib.parse import urlsplit
from uuid import uuid4
import logging
import secrets

from fastapi import Depends, FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import func, select
from sqlalchemy.exc import DataError, IntegrityError, SQLAlchemyError
from starlette.middleware.trustedhost import TrustedHostMiddleware

from app.config import ROOT, Settings
from app.db import Database
from app.auth import build_router, current_user, require_roles
from app.models import Check, Chunk, Document, User
from app.permissions import can_view_document, document_visibility, may_read_reference, redact_report
from app.security import LoginLimiter
from app.services.matching.checker import Checker, EngineUnavailable, filter_chunks, make_report
from app.services.document.documents import DocumentError, extract_chunks, file_hash, safe_filename, validate_file
from app.services.matching.shingles import covered_words, tokenize
from app.services.web.serper import SerperClient, SerperError, web_query_from_text
from app.services.web.web_sources import annotate_web_sources, save_internet_sources, web_rows

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
    # Khóa ký JWT: lấy từ JWT_SECRET; nếu thiếu thì sinh ngẫu nhiên mỗi lần chạy (đăng nhập hết hiệu lực khi restart).
    if not settings.jwt_secret:
        logger.warning("JWT_SECRET chưa đặt: dùng khóa tạm thời, người dùng phải đăng nhập lại sau khi khởi động lại.")
    app.state.jwt_secret = settings.jwt_secret or secrets.token_urlsafe(48)
    app.state.login_limiter = LoginLimiter(settings.login_max_failures, settings.login_lockout_minutes * 60)
    app.state.password_limiter = LoginLimiter(settings.login_max_failures, settings.login_lockout_minutes * 60)  # đoán mật khẩu hiện tại
    app.state.register_limiter = LoginLimiter(settings.register_max_per_hour, 3600)
    app.include_router(build_router())
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
        elif request.url.path == "/" or request.url.path.startswith("/static/"):
            # no-cache = được lưu nhưng luôn hỏi lại máy chủ (ETag) trước khi dùng, để sửa giao diện có hiệu lực ngay.
            response.headers["Cache-Control"] = "no-cache"
        return response

    @app.exception_handler(DataError)
    async def data_error(request, error):
        logger.warning("Dữ liệu không lưu được vào PostgreSQL (%s)", type(error.orig).__name__ if getattr(error, "orig", None) else "DataError")
        return JSONResponse({"detail": "Nội dung có dữ liệu mà PostgreSQL không lưu được (ví dụ ký tự điều khiển hoặc chuỗi quá dài)."}, status_code=422)

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

    def process_upload(upload, role, owner_id, engine="semantic", threshold=0.68):
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
                web_corpus = web_rows(session, settings.max_web_chunks) if role == "submission" else []  # trang Internet đã lưu từ trước
                if role == "submission" and not references and not web_corpus:
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
                    stored_name=stored_name, size_bytes=size, warnings=extracted.warnings, owner_id=owner_id,
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
                    eligible_references, ignored_references = filter_chunks(references + web_corpus)
                    if not queries:
                        raise HTTPException(422, "Tài liệu chỉ chứa mục lục, tài liệu tham khảo hoặc nội dung mẫu; không còn đoạn phù hợp để kiểm tra.")
                    if not eligible_references:
                        raise HTTPException(409, "Kho nguồn không còn đoạn phù hợp sau khi loại mục lục, tài liệu tham khảo và nội dung mẫu.")
                    rankings = checker.search(queries, eligible_references, engine)
                    # Tìm Internet, tải toàn văn các trang nghi vấn và lưu vào CSDL; rồi đối chiếu thêm với các đoạn vừa lưu.
                    # Phần Internet chỉ là bổ sung: lỗi ở đây không được làm hỏng kết quả đối chiếu với kho.
                    try:
                        internet = search_internet(queries, rankings)
                    except Exception:  # noqa: BLE001
                        logger.exception("Tìm kiếm Internet gặp lỗi")
                        internet = {"enabled": True, "provider": "serper", "queries": [], "matches": [],
                                    "warning": "Không tìm được nguồn Internet do lỗi nội bộ (xem log máy chủ). Kết quả đối chiếu với kho vẫn đầy đủ."}
                    try:
                        new_web, _ = save_internet_sources(session, settings, internet)
                    except SQLAlchemyError:
                        raise
                    except Exception:  # noqa: BLE001
                        logger.exception("Lưu nguồn Internet gặp lỗi")
                        new_web = []
                        internet["storage"] = {"enabled": True, "new": 0, "existing": 0, "failed": 0, "skipped": 0, "pages": [], "error": "Không lưu được nguồn Internet."}
                    new_web, _ = filter_chunks(new_web)
                    if new_web:
                        extra = checker.search(queries, new_web, engine)
                        rankings = [sorted(old + new, key=lambda pair: -pair[1]) for old, new in zip(rankings, extra)]
                        eligible_references = eligible_references + new_web
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
                    annotate_web_sources(result, eligible_references)
                    result["internet_search"] = internet
                    check_id = str(uuid4())
                    result["id"] = check_id
                    session.add(Check(id=check_id, document_id=document.id, engine=engine, threshold=threshold, coverage=result.get("similarity_index", result["coverage"]), report=result))
                session.commit()
                committed = True
                return result
        except DocumentError as error:
            raise HTTPException(422, str(error)) from error
        except EngineUnavailable as error:
            raise HTTPException(503, str(error)) from error
        except IntegrityError as error:
            raise HTTPException(409, "Tài liệu nguồn đã tồn tại hoặc dữ liệu thay đổi trong lúc xử lý. Hãy tải lại danh sách.") from error
        except (HTTPException, SQLAlchemyError):
            raise
        except Exception as error:
            # Lỗi chưa lường trước: ghi đầy đủ traceback kèm mã để tra log, trả về thông báo có mã thay vì "500" trống.
            code = uuid4().hex[:8]
            logger.exception("Lỗi không mong đợi khi xử lý tài liệu (mã %s)", code)
            raise HTTPException(500, f"Lỗi nội bộ khi xử lý tài liệu ({type(error).__name__}, mã {code}). Xem log máy chủ theo mã này.") from error
        finally:
            if saved_path and not committed:
                saved_path.unlink(missing_ok=True)
            upload.file.close()
            processing.release()

    def search_internet(queries, rankings):
        """Search Internet only after the internal checker has ranked all chunks."""
        if app.state.serper is None:
            return {"enabled": False, "provider": "serper", "queries": [], "matches": [], "warning": "Chưa cấu hình SERPER_API_KEY."}
        # Ưu tiên các đoạn CHƯA được giải thích bằng kho/nguồn đã lưu (điểm cục bộ thấp): đoạn đã trùng nhiều với kho thì tìm
        # Internet chỉ tốn hạn mức. Trải đều trong bài thay vì dồn vào các đoạn đầu.
        pool = []
        for query, candidates in zip(queries, rankings):
            local_score = max((float(score) for _, score in candidates), default=0.0)
            if local_score < 0.8 and web_query_from_text(query.get("text", "")):
                pool.append((local_score, query))
        pool.sort(key=lambda row: row[1].get("ordinal", 0))
        limit = settings.serper_max_queries
        if len(pool) > limit:
            step = len(pool) / limit
            pool = [pool[int(i * step + step / 2)] for i in range(limit)]
        ranked = [(local_score, len(query.get("text", "")), query) for local_score, query in pool]
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
                # Cùng thước đo với đối chiếu nội bộ: số từ của đoạn nằm trong cụm trùng nguyên văn (>= 4 từ liên tiếp) với đoạn trích.
                # Chỉ khi có đủ từ trùng mới coi là nghi vấn (đáng tải toàn văn); một cụm 4 từ phổ thông không đủ.
                query_tokens = tokenize(query["text"])
                covered = len(covered_words(query_tokens, tokenize(comparison)))
                web_score = covered / len(query_tokens) if query_tokens else 0.0
                matches.append({
                    **item, "query_id": query["id"], "query_ordinal": query.get("ordinal", 0),
                    "query_text": query["text"], "web_score": round(web_score, 6), "matched_words": covered,
                    "candidate": covered >= settings.serper_min_words,
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
            from app.services.document.ocr import ocr_status
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
            "registration_enabled": settings.allow_registration,
        }

    @app.post("/api/web-search")
    def web_search(payload: dict, _: User = Depends(require_roles("admin"))):
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
    def documents(role: Literal["reference", "submission", "web"] | None = None, user: User = Depends(current_user)):
        if role in ("reference", "web") and not may_read_reference(user):
            raise HTTPException(403, "Chỉ quản trị viên được truy cập kho tham chiếu.")
        with require_db().session() as session:
            statement = select(Document, func.count(Chunk.id)).outerjoin(Chunk).where(document_visibility(user))
            if role:
                statement = statement.where(Document.role == role)
            rows = session.execute(statement.group_by(Document.id).order_by(Document.created_at.desc()).limit(100)).all()
            return [{"id": doc.id, "filename": doc.filename, "role": doc.role, "file_type": doc.file_type, "chunks": count, "size_bytes": doc.size_bytes, "warnings": doc.warnings, "source_url": doc.source_url, "created_at": doc.created_at.isoformat()} for doc, count in rows]

    @app.get("/api/stats")
    def stats(user: User = Depends(current_user)):
        with require_db().session() as session:
            if not may_read_reference(user):  # người dùng thường không biết quy mô kho
                return {"checks": session.scalar(select(func.count(Check.id)).join(Document, Check.document_id == Document.id).where(document_visibility(user)))}
            return {
                "references": session.scalar(select(func.count(Document.id)).where(Document.role == "reference")),
                "reference_chunks": session.scalar(select(func.count(Chunk.id)).join(Document).where(Document.role == "reference")),
                "web_sources": session.scalar(select(func.count(Document.id)).where(Document.role == "web")),
                "web_chunks": session.scalar(select(func.count(Chunk.id)).join(Document).where(Document.role == "web")),
                # Số lần kiểm tra chỉ tính các bài người dùng này được phép xem.
                "checks": session.scalar(select(func.count(Check.id)).join(Document, Check.document_id == Document.id).where(document_visibility(user))),
            }

    @app.delete("/api/documents/{document_id}", status_code=204)
    def delete_web_source(document_id: str, _: User = Depends(require_roles("admin"))):
        """Xóa một nguồn Internet đã lưu (các đoạn đi kèm xóa theo). Báo cáo đã tạo không đổi vì đã lưu nguyên văn đoạn trích."""
        with require_db().session() as session:
            document = session.get(Document, document_id)
            if not document or document.role != "web":
                raise HTTPException(404, "Không tìm thấy nguồn Internet.")
            session.delete(document)
            session.commit()

    @app.post("/api/references", status_code=201)
    def add_reference(file: UploadFile = File(...), user: User = Depends(require_roles("admin"))):
        return process_upload(file, "reference", user.id)

    @app.post("/api/checks", status_code=201)
    def check_document(file: UploadFile = File(...), engine: str = Form("semantic"), threshold: float = Form(0.68, gt=0, le=1), user: User = Depends(current_user)):
        result = process_upload(file, "submission", user.id, engine, threshold)
        # Báo cáo lưu trong CSDL là bản đầy đủ; người dùng thường nhận bản đã che ngay từ lần trả về đầu tiên,
        # giống hệt bản họ mở lại từ lịch sử.
        with require_db().session() as session:
            return redact_report(session, user, result)

    @app.get("/api/checks")
    def checks(user: User = Depends(current_user)):
        with require_db().session() as session:
            rows = session.execute(
                select(Check, Document.filename).join(Document, Check.document_id == Document.id)
                .where(document_visibility(user)).order_by(Check.created_at.desc()).limit(100)
            )
            return [{"id": check.id, "filename": name, "engine": check.engine, "coverage": check.coverage, "created_at": check.created_at.isoformat()} for check, name in rows]

    @app.get("/api/checks/{check_id}")
    def report(check_id: str, user: User = Depends(current_user)):
        with require_db().session() as session:
            check = session.get(Check, check_id)
            document = session.get(Document, check.document_id) if check else None
            # Không có quyền cũng trả 404 để không lộ việc kết quả đó có tồn tại.
            if not check or not document or not can_view_document(session, user, document):
                raise HTTPException(404, "Không tìm thấy kết quả kiểm tra.")
            return redact_report(session, user, check.report)

    @app.get("/api/documents/{document_id}/file")
    def download(document_id: str, user: User = Depends(current_user)):
        with require_db().session() as session:
            document = session.get(Document, document_id)
            if not document or not can_view_document(session, user, document):
                raise HTTPException(404, "Không tìm thấy tài liệu.")
            target = (settings.upload_dir / document.stored_name).resolve()
            if target.parent != settings.upload_dir.resolve() or not target.is_file():
                raise HTTPException(404, "Tệp gốc không còn trong kho lưu trữ.")
            return FileResponse(target, filename=document.filename, media_type="application/octet-stream")

    @app.get("/api/documents/{document_id}/preview")
    def preview(document_id: str, user: User = Depends(current_user)):
        from app.services.document.preview import PreviewError, render_docx_html
        with require_db().session() as session:
            document = session.get(Document, document_id)
            if not document or not can_view_document(session, user, document):
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

    app.mount("/static", StaticFiles(directory=ROOT / "frontend" / "static"), name="static")

    @app.get("/", include_in_schema=False)
    def index():
        return FileResponse(ROOT / "frontend" / "index.html")

    return app


app = create_app()
