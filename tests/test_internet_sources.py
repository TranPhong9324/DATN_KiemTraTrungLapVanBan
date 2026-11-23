"""Nguồn Internet tự lưu vào CSDL. Không dùng mạng thật: Serper và việc tải trang đều được giả lập."""
from sqlalchemy import func, select
from sqlalchemy import text as sql
from fastapi.testclient import TestClient
import pytest

from app.config import Settings
from app.main import create_app
from app.models import Chunk, Document
from app.services.web import web_sources
from app.services.web.webpages import (
    WebFetchError, WebPage, assert_public_host, canonical_url, fetch_page, html_to_text, text_to_chunks,
)
from conftest import ADMIN_EMAIL, login, make_docx, make_user

TEXT = "Hệ thống tự động kiểm tra và cảnh báo trùng lặp văn bản trong báo cáo đồ án. Nội dung được chia thành từng đoạn để đối chiếu với kho tài liệu tham chiếu."
OTHER = "Cây cà phê sinh trưởng trên đất đỏ bazan. Nông dân thu hoạch quả chín và phơi khô hạt dưới ánh nắng."
URL = "https://example.org/bai-viet"


class FakeSerper:
    """Trả về kết quả cố định; ghi lại số lần gọi."""
    def __init__(self, links=(URL + "?utm_source=fb",), snippet=None):
        self.links, self.calls, self.snippet = list(links), 0, snippet or TEXT

    def search(self, query, num=10):
        self.calls += 1
        return {"query": query, "provider": "serper", "organic": [
            {"position": i, "title": f"Bài viết {i}", "link": link, "snippet": self.snippet, "date": None, "source": None}
            for i, link in enumerate(self.links, 1)]}


def page(text=TEXT, url=URL, title="Trang đã lưu"):
    chunks = [{"text": text, "location": {"page": None, "block": 1, "label": "Đoạn 1 của trang web"}}]
    return WebPage(url=url, title=title, chunks=chunks, size_bytes=len(text), content_hash="h" + str(abs(hash(text))), warnings=[])


@pytest.fixture
def net(web, monkeypatch):
    """(client, app, calls): Serper giả + trình tải trang giả. calls['fetch'] ghi lại các địa chỉ đã tải."""
    client, app, settings = web
    app.state.serper = FakeSerper()
    calls = {"fetch": [], "pages": {URL: page()}}

    def fake_fetch(urls, settings, **kwargs):
        calls["fetch"] += list(urls)
        return {u: calls["pages"].get(u, WebFetchError("Trang web trả về mã lỗi HTTP 404.", 502)) for u in urls}

    monkeypatch.setattr(web_sources, "fetch_pages", fake_fetch)
    return client, app, calls


def check(client, text=TEXT, engine="lexical"):
    response = client.post("/api/checks", files={"file": ("baocao.docx", make_docx(text))}, data={"engine": engine, "threshold": "0.3"})
    assert response.status_code == 201, response.text
    return response.json()


def add_reference(client, text=OTHER):
    assert client.post("/api/references", files={"file": ("kho.docx", make_docx(text))}).status_code == 201


def web_docs(app):
    with app.state.database.session() as session:
        return session.execute(select(Document).where(Document.role == "web")).scalars().all()


# ---- lưu và đối chiếu toàn văn --------------------------------------------------------------------------------------

def test_page_is_fetched_saved_and_compared_in_full(net):
    client, app, calls = net
    add_reference(client)
    report = check(client)
    assert calls["fetch"] == [URL]  # đã bỏ tham số theo dõi utm_*
    docs = web_docs(app)
    assert len(docs) == 1 and docs[0].source_url == URL and docs[0].filename == "Trang đã lưu" and docs[0].owner_id is None
    with app.state.database.session() as session:
        assert session.scalar(select(func.count(Chunk.id)).where(Chunk.document_id == docs[0].id)) == 1
    # Kết quả là so khớp toàn văn với bản đã lưu, gắn nhãn Internet và địa chỉ
    web_match = [m for m in report["matches"] if m.get("source_kind") == "web"]
    assert web_match and web_match[0]["source_url"] == URL and web_match[0]["source_text"] == TEXT
    assert report["coverage"] == 100
    assert any(s.get("kind") == "web" and s["url"] == URL for s in report["sources"])
    storage = report["internet_search"]["storage"]
    assert (storage["new"], storage["failed"]) == (1, 0)
    assert all(item.get("stored") for item in report["internet_search"]["matches"])
    stats = client.get("/api/stats").json()
    assert stats["web_sources"] == 1 and stats["web_chunks"] == 1 and stats["references"] == 1


def test_saved_page_is_reused_without_fetching_or_searching_again(net):
    client, app, calls = net
    add_reference(client)
    check(client)
    app.state.serper = FakeSerper(links=[])  # lần sau tìm kiếm không ra gì
    calls["fetch"].clear()
    report = check(client)
    assert calls["fetch"] == []
    assert report["coverage"] == 100 and any(m.get("source_kind") == "web" for m in report["matches"])
    assert len(web_docs(app)) == 1


def test_same_url_or_same_content_is_not_saved_twice(net):
    client, app, calls = net
    add_reference(client)
    check(client)
    check(client)
    assert len(web_docs(app)) == 1 and calls["fetch"] == [URL]  # lần hai thấy địa chỉ đã lưu nên không tải lại
    # Bản sao giống hệt nội dung ở địa chỉ khác: không thêm bản ghi
    mirror = "https://mirror.example.net/sao-chep"
    app.state.serper = FakeSerper(links=[mirror])
    calls["pages"][mirror] = page(url=mirror)
    calls["pages"][mirror].content_hash = web_docs(app)[0].sha256
    # đoạn chưa được kho giải thích hết (còn phần tự viết) nên mới tìm Internet; bài chép trọn vẹn đã có ở kho thì không tìm
    report = check(client, "Phần mở đầu do sinh viên tự viết hoàn toàn mới nói về một chủ đề rất khác biệt. " + TEXT)
    assert len(web_docs(app)) == 1
    assert report["internet_search"]["storage"]["existing"] >= 1


def test_internet_search_skips_chunks_already_explained_locally(net):
    client, app, calls = net
    add_reference(client)
    check(client)
    searched = app.state.serper.calls
    check(client)  # đã lưu trang ở lần trước nên đoạn này trùng 100% với kho -> không tốn thêm hạn mức tìm kiếm
    assert app.state.serper.calls == searched


def test_fetch_failure_does_not_break_the_check(net):
    client, app, calls = net
    add_reference(client)
    app.state.serper = FakeSerper(links=["https://example.org/khong-co"])
    report = check(client)
    assert web_docs(app) == []
    item = report["internet_search"]["matches"][0]
    assert not item.get("stored") and "404" in item["fetch_error"]
    assert report["internet_search"]["storage"]["failed"] == 1


def test_unexpected_fetch_exception_is_contained(net, monkeypatch):
    client, app, _ = net
    add_reference(client)
    def boom(*a, **k):
        raise RuntimeError("mạng hỏng")
    monkeypatch.setattr(web_sources, "fetch_pages", boom)
    report = check(client)
    assert report["internet_search"]["storage"]["failed"] == 1 and web_docs(app) == []


def test_only_suspicious_results_are_fetched_and_page_count_is_capped(net):
    client, app, calls = net
    add_reference(client)
    links = [f"https://example.org/trang-{i}" for i in range(10)]
    app.state.serper = FakeSerper(links=links)
    for link in links:
        calls["pages"][link] = page(text=TEXT + f" Bản số {link}", url=link, title=link)
    check(client)
    assert len(calls["fetch"]) == app.state.settings.web_max_pages_per_check == 6
    assert len(web_docs(app)) == 6


def test_auto_save_off_keeps_snippet_only(tmp_path, postgres_db, monkeypatch):
    settings = Settings(upload_dir=tmp_path / "u", jwt_secret="t" * 48, web_auto_save=False)
    app = create_app(settings, postgres_db)
    make_user(postgres_db, ADMIN_EMAIL, "admin")
    monkeypatch.setattr(web_sources, "fetch_pages", lambda *a, **k: pytest.fail("không được tải khi WEB_AUTO_SAVE=false"))
    with TestClient(app) as client:
        login(client)
        app.state.serper = FakeSerper()
        add_reference(client)
        report = check(client)
        assert web_docs(app) == [] and report["internet_search"]["storage"]["enabled"] is False
        assert report["internet_search"]["matches"] and not report["internet_search"]["matches"][0].get("stored")


def test_storage_cap_skips_new_pages(tmp_path, postgres_db, monkeypatch):
    settings = Settings(upload_dir=tmp_path / "u", jwt_secret="t" * 48, max_web_chunks=0)
    app = create_app(settings, postgres_db)
    make_user(postgres_db, ADMIN_EMAIL, "admin")
    monkeypatch.setattr(web_sources, "fetch_pages", lambda urls, s, **k: {u: page(url=u) for u in urls})
    with TestClient(app) as client:
        login(client)
        app.state.serper = FakeSerper()
        add_reference(client)
        report = check(client)
        assert web_docs(app) == [] and report["internet_search"]["storage"]["skipped"] == 1
        assert "MAX_WEB_CHUNKS" in report["internet_search"]["matches"][0]["fetch_error"]


def test_check_works_with_only_saved_web_pages_in_corpus(net):
    client, app, _ = net
    add_reference(client)
    check(client)
    with app.state.database.session() as session:  # kho tham chiếu trống, chỉ còn trang Internet
        for doc in session.execute(select(Document).where(Document.role == "reference")).scalars():
            session.delete(doc)
        session.commit()
    app.state.serper = FakeSerper(links=[])
    assert check(client)["coverage"] == 100


# ---- phân quyền -----------------------------------------------------------------------------------------------------

def test_user_sees_page_title_and_url_but_cannot_list_or_delete_web_sources(net):
    client, app, _ = net
    add_reference(client)
    make_user(app.state.database, "a@example.com", "user")
    other = TestClient(app)
    login(other, "a@example.com")
    report = check(other)  # người dùng thường chạy kiểm tra: trang vẫn được lưu và đối chiếu
    assert len(web_docs(app)) == 1
    match = next(m for m in report["matches"] if m.get("source_kind") == "web")
    assert match["source_url"] == URL and match["source_filename"] == "Trang đã lưu" and match["source_document_id"] is None
    assert not match.get("masked") and not match.get("redacted")
    assert all(s["document_id"] is None for s in report["sources"] if s.get("kind") == "web")
    doc_id = web_docs(app)[0].id
    assert other.get("/api/documents?role=web").status_code == 403
    assert other.delete(f"/api/documents/{doc_id}").status_code == 403
    assert other.get(f"/api/documents/{doc_id}/file").status_code == 404
    assert other.get(f"/api/documents/{doc_id}/preview").status_code == 404
    assert "web_sources" not in other.get("/api/stats").json()
    assert other.get("/api/documents").json()[0]["role"] == "submission"
    assert all(d["role"] == "submission" for d in other.get("/api/documents").json())
    # lịch sử của chính họ đọc lại giống hệt (đã lưu bản chụp)
    again = other.get(f'/api/checks/{report["id"]}').json()
    assert again["matches"][0]["source_url"] == URL and again["document_id"] == report["document_id"]


def test_admin_lists_and_deletes_saved_page_and_old_reports_survive(net):
    client, app, _ = net
    add_reference(client)
    report = check(client)
    listing = client.get("/api/documents?role=web").json()
    assert len(listing) == 1 and listing[0]["source_url"] == URL and listing[0]["chunks"] == 1
    assert client.delete(f"/api/documents/{listing[0]['id']}").status_code == 204
    assert web_docs(app) == []
    with app.state.database.session() as session:
        assert session.scalar(select(func.count(Chunk.id)).join(Document).where(Document.role == "web")) == 0
    assert client.get(f'/api/checks/{report["id"]}').json()["matches"][0]["source_text"] == TEXT
    # chỉ xóa được nguồn Internet, không xóa tài liệu kho hay bài nộp
    refs = client.get("/api/documents?role=reference").json()
    assert client.delete(f"/api/documents/{refs[0]['id']}").status_code == 404
    assert client.delete(f"/api/documents/{report['document_id']}").status_code == 404
    assert client.delete("/api/documents/khong-ton-tai").status_code == 404


def test_old_database_gets_source_url_column(postgres_db):
    with postgres_db.engine.begin() as connection:
        connection.execute(sql("ALTER TABLE documents DROP COLUMN source_url"))
    postgres_db.initialize()
    postgres_db.initialize()  # chạy lại vẫn an toàn
    with postgres_db.engine.connect() as connection:
        assert connection.scalar(sql("SELECT count(*) FROM information_schema.columns WHERE table_name='documents' AND column_name='source_url' AND table_schema=current_schema()")) == 1


# ---- bộ tải trang (không dùng mạng thật) ----------------------------------------------------------------------------

def test_canonical_url_removes_tracking_and_rejects_bad_schemes():
    assert canonical_url("HTTPS://Example.ORG:443/a?utm_source=x&id=2#top") == "https://example.org/a?id=2"
    for bad in ("ftp://a.com/x", "javascript:alert(1)", "https://user:pw@a.com/", "https://a.com:8080/", "http://", "", "http://[abc", "http://[::1", "https://a.com/\ud800", "http://a.com:abc/"):
        with pytest.raises(WebFetchError):
            canonical_url(bad)


def test_private_addresses_are_refused():
    for url in ("http://127.0.0.1/", "http://10.0.0.5/x", "http://169.254.169.254/latest/meta-data", "http://[::1]/", "http://192.168.1.1/"):
        with pytest.raises(WebFetchError):
            assert_public_host(url)
    with pytest.raises(WebFetchError):  # tên miền phân giải ra địa chỉ nội bộ
        assert_public_host("http://noi-bo.example/", resolver=lambda host, port: ["10.1.2.3"])
    assert_public_host("https://example.org/", resolver=lambda host, port: ["93.184.216.34"])


class FakeResponse:
    def __init__(self, status=200, body=b"", kind="text/html; charset=utf-8", location=None):
        self.status_code, self._body, self.headers = status, body, {"Content-Type": kind}
        if location:
            self.headers["Location"] = location
        self.is_redirect = status in {301, 302, 307, 308}
        self.raw = None

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def iter_content(self, size):
        yield self._body


class FakeSession:
    def __init__(self, responses):
        self.responses, self.requested, self.max_redirects = responses, [], 5

    def get(self, url, **kwargs):
        self.requested.append(url)
        return self.responses[len(self.requested) - 1]

    def close(self):
        pass


PUBLIC = lambda host, port: ["93.184.216.34"]  # noqa: E731
HTML = ("<html><head><title>Quy chế đấu giá</title></head><body><nav>Trang chủ Giới thiệu Liên hệ Tin tức</nav><script>var x=1;</script>"
        f"<article><h1>Quy chế đấu giá</h1><p>{TEXT}</p><p>{OTHER}</p></article><footer>Bản quyền thuộc về công ty đấu giá hợp danh</footer></body></html>")


def test_fetch_page_extracts_main_text_and_follows_safe_redirect():
    session = FakeSession([FakeResponse(301, location="/moi"), FakeResponse(body=HTML.encode())])
    result = fetch_page("https://example.org/cu", Settings(), session=session, resolver=PUBLIC)
    assert result.url == "https://example.org/moi" and result.title == "Quy chế đấu giá"
    joined = " ".join(chunk["text"] for chunk in result.chunks)
    assert TEXT in joined and "var x" not in joined and "Liên hệ" not in joined and "Bản quyền" not in joined


def test_redirect_to_private_address_and_bad_content_are_refused():
    with pytest.raises(WebFetchError):
        fetch_page("https://example.org/a", Settings(), session=FakeSession([FakeResponse(302, location="http://127.0.0.1/admin")]),
                   resolver=lambda host, port: ["93.184.216.34"])
    with pytest.raises(WebFetchError, match="HTML"):
        fetch_page("https://example.org/a", Settings(), session=FakeSession([FakeResponse(body=b"\x00", kind="application/zip")]), resolver=PUBLIC)
    with pytest.raises(WebFetchError, match="HTTP 404"):
        fetch_page("https://example.org/a", Settings(), session=FakeSession([FakeResponse(404)]), resolver=PUBLIC)
    with pytest.raises(WebFetchError, match="không có đủ văn bản"):
        fetch_page("https://example.org/a", Settings(), session=FakeSession([FakeResponse(body=b"<html><body><p>ngan</p></body></html>")]), resolver=PUBLIC)


def test_html_to_text_and_chunking():
    title, body, _ = html_to_text(HTML)
    assert title == "Quy chế đấu giá" and TEXT in body
    chunks = text_to_chunks("\n".join([TEXT, OTHER, TEXT + " thêm"]), 200)
    assert all(len(c["text"]) <= 200 for c in chunks) and chunks


def test_user_still_sees_old_report_after_admin_deletes_the_web_source(net):
    client, app, _ = net
    add_reference(client)
    make_user(app.state.database, "a@example.com", "user")
    other = TestClient(app)
    login(other, "a@example.com")
    report = check(other)
    assert client.delete(f"/api/documents/{web_docs(app)[0].id}").status_code == 204
    again = other.get(f'/api/checks/{report["id"]}').json()
    match = next(m for m in again["matches"] if m.get("source_kind") == "web")
    assert match["source_text"] == TEXT and match["source_url"] == URL and match["source_filename"] == "Trang đã lưu"
    assert not match.get("redacted") and again["redacted_sources"] == 0


# ---- độ bền: lỗi không được thành "500" trống ------------------------------------------------------------------------

def test_pdf_text_with_nul_control_and_lone_surrogate_is_cleaned_and_checked(net, monkeypatch):
    """PDF có font thiếu bảng ánh xạ hay sinh NUL/ký tự lạ; trước đây làm hỏng việc lưu hoặc trả lỗi 500."""
    from types import SimpleNamespace
    from app.services.document import documents
    from conftest import make_pdf
    client, app, _ = net
    add_reference(client)
    dirty = "Hệ thống tự động kiểm tra\x00 và cảnh báo trùng lặp\x07 văn bản trong báo cáo đồ án.\ud800 Nội dung được chia thành từng đoạn để đối chiếu với kho tài liệu tham chiếu."

    class Page:
        def extract_text(self):
            return dirty

    class Pdf:
        pages = [Page()]
        def __enter__(self): return self
        def __exit__(self, *exc): return False

    monkeypatch.setattr(documents, "pdfplumber", SimpleNamespace(open=lambda path: Pdf()))
    response = client.post("/api/checks", files={"file": ("hop dong.pdf", make_pdf(["x"]), "application/pdf")}, data={"engine": "lexical", "threshold": "0.3"})
    assert response.status_code == 201, response.text
    text = " ".join(chunk["text"] for chunk in response.json()["document_chunks"])
    assert "\x00" not in text and "\x07" not in text and "\ud800" not in text and "kiểm tra và cảnh báo" in text
    assert response.json()["coverage"] == 100


def test_internet_failures_never_break_the_check(net, monkeypatch):
    client, app, _ = net
    add_reference(client)

    class Broken:
        def search(self, *a, **k):
            raise RuntimeError("Serper trả dữ liệu lạ")

    app.state.serper = Broken()
    report = check(client)
    assert report["coverage"] is not None and "lỗi nội bộ" in report["internet_search"]["warning"]
    app.state.serper = FakeSerper()
    monkeypatch.setattr(web_sources, "save_internet_sources", lambda *a, **k: (_ for _ in ()).throw(KeyError("lỗi lạ")))
    from app import main
    monkeypatch.setattr(main, "save_internet_sources", web_sources.save_internet_sources)
    report = check(client)
    assert report["internet_search"]["storage"]["error"] and web_docs(app) == []


def test_very_long_page_title_is_truncated_not_a_database_error(net):
    client, app, calls = net
    add_reference(client)
    calls["pages"][URL] = page(title="Tiêu đề rất dài " * 40 + "\x00")
    report = check(client)
    docs = web_docs(app)
    assert len(docs) == 1 and len(docs[0].filename) <= 255 and "\x00" not in docs[0].filename
    assert report["internet_search"]["storage"]["new"] == 1


def test_unexpected_error_gives_a_coded_message_and_a_log(net, monkeypatch, caplog):
    from app import main
    client, app, _ = net
    add_reference(client)
    monkeypatch.setattr(app.state.checker, "search", lambda *a, **k: (_ for _ in ()).throw(ValueError("hỏng")))
    with caplog.at_level("ERROR"):
        response = client.post("/api/checks", files={"file": ("a.docx", make_docx(TEXT))}, data={"engine": "lexical"})
    assert response.status_code == 500
    detail = response.json()["detail"]
    assert "ValueError" in detail and "mã " in detail
    import re
    code = re.search(r"mã ([0-9a-f]{8})", detail).group(1)
    assert any(code in record.getMessage() for record in caplog.records)
    assert client.post("/api/checks", files={"file": ("b.docx", make_docx(TEXT))}, data={"engine": "lexical"}).status_code == 500  # không kẹt khóa xử lý


def test_search_result_sharing_only_a_common_phrase_is_not_suspect(net):
    client, app, calls = net
    add_reference(client)
    # kết quả chỉ trùng một cụm 4 từ phổ thông ("hệ thống tự động kiểm") với đoạn của bài: không phải nghi vấn, không tải trang
    app.state.serper = FakeSerper(snippet="Giới thiệu hệ thống tự động kiểm soát nhiệt độ cho nhà kính trồng rau sạch.")
    report = check(client)
    items = report["internet_search"]["matches"]
    assert items and not any(item["candidate"] for item in items)
    assert calls["fetch"] == [] and web_docs(app) == []
    assert all(0 <= item["web_score"] < 0.3 for item in items)


def test_search_result_with_long_verbatim_run_is_suspect_and_scored_as_ratio(net):
    client, app, calls = net
    add_reference(client)
    report = check(client)
    item = report["internet_search"]["matches"][0]
    assert item["candidate"] and item["matched_words"] >= 8 and item["web_score"] == 1.0


def test_stale_cosine_threshold_in_env_is_ignored(monkeypatch):
    monkeypatch.setenv("LEXICAL_THRESHOLD", "0.08")
    monkeypatch.delenv("VERBATIM_THRESHOLD", raising=False)
    assert Settings.load().lexical_threshold == 0.30
    monkeypatch.setenv("VERBATIM_THRESHOLD", "0.4")
    assert Settings.load().lexical_threshold == 0.4


def test_page_wrapped_in_form_and_unclosed_options_still_yield_text():
    from app.services.web.webpages import html_to_text
    body = "Đây là một đoạn văn dài hơn mười từ nằm trong trang web có bọc thẻ form kiểu WebForms. " * 3
    assert len(html_to_text(f"<html><body><form><div><p>{body}</p></div></form></body></html>")[1]) > 100
    page = f"<nav><select><option>a<option>b</select></nav><p>{body}</p><footer><p>{'chân trang không lấy vì thuộc phần cuối của trang web này ' * 2}</p></footer>"
    text = html_to_text(page)[1]
    assert "đoạn văn dài" in text and "chân trang" not in text


def test_unexpected_fetch_error_is_logged_and_names_the_exception(caplog, monkeypatch):
    from app.services.web import webpages
    def boom(url, settings, **kwargs):
        raise UnicodeError("x")
    monkeypatch.setattr(webpages, "fetch_page", boom)
    result = webpages.fetch_pages(["https://example.com/a"], Settings.load())["https://example.com/a"]
    assert "UnicodeError" in str(result)
    assert any("Không xử lý được trang web" in record.getMessage() and record.exc_info for record in caplog.records)
