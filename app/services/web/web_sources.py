"""Tự lưu nguồn Internet vào CSDL.

Luồng một lần kiểm tra (xem process_upload trong app/main.py):
  1. Đối chiếu với kho tham chiếu + các trang Internet ĐÃ lưu từ trước (offline, không tốn hạn mức tìm kiếm).
  2. Tìm kiếm Internet (Serper) cho các đoạn đáng ngờ nhất.
  3. Với các kết quả nghi vấn chưa có trong CSDL: tải toàn văn (app/services/webpages.py, có chống SSRF), tách đoạn,
     lưu thành Document(role="web") + Chunk. Địa chỉ trang đã chuẩn hóa là duy nhất nên không lưu trùng.
  4. Đối chiếu báo cáo với các đoạn vừa lưu: kết quả là so khớp toàn văn, không chỉ đoạn trích của công cụ tìm kiếm.
Lần kiểm tra sau gặp lại trang đó sẽ dùng bản đã lưu ngay ở bước 1.
Bản lưu là ảnh chụp tại thời điểm tải; trang gốc đổi nội dung sau đó không làm đổi các báo cáo đã có.
"""
from __future__ import annotations

from uuid import uuid4
import logging

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from app.models import Chunk, Document
from app.services.document.documents import clean_extracted_text
from app.services.web.webpages import WebFetchError, canonical_url, fetch_pages

logger = logging.getLogger(__name__)
MAX_URL_BYTES = 2000  # chỉ mục duy nhất của PostgreSQL không nhận khóa quá lớn


def _rows(chunks, title, url):
    return [{"id": c.id, "ordinal": c.ordinal, "text": c.text, "location": c.location, "document_id": c.document_id,
             "filename": title, "kind": "web", "url": url} for c in chunks]


def web_rows(session, limit: int) -> list[dict]:
    """Các đoạn của mọi trang Internet đã lưu, cùng dạng với đoạn của kho tham chiếu."""
    rows = session.execute(
        select(Chunk, Document.filename, Document.source_url).join(Document, Chunk.document_id == Document.id)
        .where(Document.role == "web").order_by(Document.created_at.desc(), Document.id, Chunk.ordinal).limit(limit)
    ).all()
    return [row for chunk, title, url in rows for row in _rows([chunk], title, url)]


def _canon(link):
    try:
        value = canonical_url(link)
    except WebFetchError:
        return None
    return value if len(value.encode("utf-8")) <= MAX_URL_BYTES else None


def save_internet_sources(session, settings, internet: dict, fetch=None):
    """Tải và lưu các trang nghi vấn trong kết quả tìm kiếm `internet`.

    Trả (các đoạn của trang MỚI lưu, tóm tắt). Đồng thời gắn vào từng kết quả tìm kiếm:
      stored=True      trang đã nằm trong CSDL (đã được đối chiếu toàn văn) -> giao diện không cần hiện đoạn trích ngắn;
      fetch_error=...  lý do không tải/lưu được, để người dùng biết kết quả đó chỉ là đoạn trích.
    Lỗi mạng hoặc trang lạ chỉ làm trang đó thất bại, không làm hỏng lần kiểm tra."""
    fetch = fetch or fetch_pages
    summary = {"enabled": bool(settings.web_auto_save), "new": 0, "existing": 0, "failed": 0, "skipped": 0, "pages": []}
    matches = internet.get("matches") or []
    if not settings.web_auto_save or not matches:
        internet["storage"] = summary
        return [], summary
    canon_of = {id(item): _canon(item.get("link", "")) for item in matches}
    urls = {url for url in canon_of.values() if url}
    existing = {}
    if urls:
        existing = {url: (doc_id, title) for doc_id, url, title in session.execute(
            select(Document.id, Document.source_url, Document.filename).where(Document.role == "web", Document.source_url.in_(urls)))}
    # Chỉ tải các kết quả nghi vấn (đủ giống đoạn trích), chưa có trong CSDL, theo thứ tự xếp hạng, tối đa N trang mới.
    wanted: list[str] = []
    for item in matches:
        url = canon_of[id(item)]
        if url and item.get("candidate") and url not in existing and url not in wanted and len(wanted) < settings.web_max_pages_per_check:
            wanted.append(url)
    remaining = settings.max_web_chunks - (session.scalar(select(func.count(Chunk.id)).join(Document).where(Document.role == "web")) or 0)
    outcome: dict[str, dict] = {}
    new_rows: list[dict] = []
    try:
        fetched = fetch(wanted, settings) if wanted else {}
    except Exception:  # noqa: BLE001 - mạng/hệ thống lỗi bất ngờ: bỏ qua bước lưu, vẫn trả kết quả đối chiếu
        logger.exception("Không tải được nguồn Internet")
        fetched = {url: WebFetchError("Không tải được trang web.", 502) for url in wanted}
    for url in wanted:
        page = fetched.get(url)
        if not hasattr(page, "chunks"):
            message = str(page) if page is not None else "Không tải được trang web."
            outcome[url] = {"status": "failed", "error": message}
            continue
        final = _canon(page.url) or url
        same = session.execute(select(Document.id, Document.filename).where(
            Document.role == "web", (Document.source_url == final) | (Document.sha256 == page.content_hash)).limit(1)).first()
        if same:  # cùng địa chỉ sau chuyển hướng, hoặc bản sao nội dung giống hệt ở địa chỉ khác
            outcome[url] = {"status": "existing", "title": same[1], "chunks": len(page.chunks)}
            continue
        if len(page.chunks) > remaining:
            outcome[url] = {"status": "skipped", "error": "Kho nguồn Internet đã đạt giới hạn số đoạn (MAX_WEB_CHUNKS).", "title": page.title}
            continue
        document = Document(
            id=str(uuid4()), filename=clean_extracted_text(page.title or final)[:255] or final[:255], file_type="web", role="web", sha256=page.content_hash,
            reference_hash=None, stored_name="", source_url=final, size_bytes=page.size_bytes, warnings=page.warnings, owner_id=None,
        )
        for ordinal, chunk in enumerate(page.chunks):
            document.chunks.append(Chunk(id=str(uuid4()), ordinal=ordinal, text=chunk["text"], location=chunk["location"]))
        try:
            with session.begin_nested():  # savepoint: trùng địa chỉ không làm hỏng cả lần kiểm tra
                session.add(document)
        except IntegrityError:
            outcome[url] = {"status": "existing", "title": page.title, "chunks": len(page.chunks)}
            continue
        except SQLAlchemyError:  # savepoint đã hoàn tác: chỉ trang này không lưu được, phiên làm việc vẫn dùng tiếp
            logger.exception("Không lưu được trang Internet %s", final)
            outcome[url] = {"status": "failed", "error": "Không lưu được trang này vào cơ sở dữ liệu."}
            continue
        remaining -= len(page.chunks)
        new_rows += _rows(document.chunks, document.filename, final)
        outcome[url] = {"status": "saved", "title": document.filename, "chunks": len(document.chunks)}
    for item in matches:
        url = canon_of[id(item)]
        if url in existing:
            item["stored"] = True
        elif url in outcome:
            result = outcome[url]
            if result["status"] in {"saved", "existing"}:
                item["stored"] = True
            else:
                item["fetch_error"] = result.get("error", "Không lưu được trang này.")
    for url in wanted:
        result = outcome[url]
        summary["pages"].append({"url": url, **result})
        summary[{"saved": "new", "existing": "existing", "failed": "failed", "skipped": "skipped"}[result["status"]]] += 1
    summary["existing"] += len(existing)  # trang đã lưu từ trước và xuất hiện lại trong kết quả lần này
    internet["storage"] = summary
    return new_rows, summary


def annotate_web_sources(report: dict, corpus: list[dict]) -> dict:
    """Đánh dấu các nguồn của báo cáo là trang Internet (kèm địa chỉ) để giao diện phân biệt với kho tham chiếu."""
    info = {row["document_id"]: row["url"] for row in corpus if row.get("kind") == "web"}
    if not info:
        return report
    for match in report.get("matches", []):
        if match.get("source_document_id") in info:
            match.update(source_kind="web", source_url=info[match["source_document_id"]])
    for source in report.get("sources", []):
        if source.get("document_id") in info:
            source.update(kind="web", url=info[source["document_id"]])
    return report
