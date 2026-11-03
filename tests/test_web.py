import unicodedata

from fastapi.testclient import TestClient
from sqlalchemy import func, select

from app.config import Settings
from app.main import create_app
from app.models import Check, Document
from app.services.checker import cosine, features
from app.services.documents import extract_chunks, split_block
from conftest import make_docx, make_pdf

TEXT = "Hệ thống tự động kiểm tra và cảnh báo trùng lặp văn bản trong báo cáo đồ án. Nội dung được chia thành từng đoạn để đối chiếu với kho tài liệu tham chiếu."
OTHER = "Cây cà phê sinh trưởng trên đất đỏ bazan. Nông dân thu hoạch quả chín và phơi khô hạt dưới ánh nắng."


def upload(client, endpoint, content=None, name="baocao.docx", **data):
    return client.post(endpoint, files={"file": (name, content if content is not None else make_docx(TEXT))}, data=data)


def test_no_database_still_serves_setup(tmp_path):
    with TestClient(create_app(Settings(upload_dir=tmp_path))) as client:
        assert client.get("/").status_code == 200
        assert client.get("/static/app.js").status_code == 200
        assert client.get("/api/health").json()["database"] == "not_configured"
        assert upload(client, "/api/references").status_code == 503


def test_unicode_and_unrelated_lexical_scores():
    assert abs(cosine(features(TEXT), features(unicodedata.normalize("NFD", TEXT))) - 1) < 1e-9
    assert cosine(features(TEXT), features(OTHER)) < 0.65


def test_chunk_locations_are_exact_nonoverlapping():
    raw = "đồ án " * 300
    chunks = split_block(raw, {"page": 2}, 100)
    for chunk in chunks:
        location = chunk["location"]
        assert chunk["text"] == raw[location["start"]:location["end"]]
        assert len(chunk["text"]) <= 100
    assert "".join(chunk["text"] for chunk in chunks) == raw


def test_docx_keeps_structural_location_and_table(tmp_path):
    path = tmp_path / "sample.docx"
    path.write_bytes(make_docx(TEXT, table=True))
    result = extract_chunks(path, Settings())
    assert all(chunk["location"]["page"] is None for chunk in result.chunks)
    assert any("Đối chiếu ngữ nghĩa" in chunk["text"] for chunk in result.chunks)


def test_pdf_locations_and_partial_warning(tmp_path):
    path = tmp_path / "sample.pdf"
    path.write_bytes(make_pdf(["First page report", "", "Third page report"]))
    result = extract_chunks(path, Settings())
    assert [chunk["location"]["page"] for chunk in result.chunks] == [1, 3]
    assert "Trang 2" in result.warnings[0]


def test_postgres_roundtrip_and_persisted_history(web):
    client, app, settings = web
    assert client.get("/api/health").json()["database"] == "ready"
    original = make_docx(TEXT)
    reference = upload(client, "/api/references", original)
    assert reference.status_code == 201, reference.text
    response = upload(client, "/api/checks", original)
    assert response.status_code == 201, response.text
    report = response.json()
    assert report["coverage"] == 100
    assert report["matched_chunks"] == report["total_chunks"]
    assert report["matches"][0]["source_document_id"] == reference.json()["id"]
    assert report["document_id"] != reference.json()["id"]
    assert report["matches"][0]["source_location"]["page"] is None
    preview = client.get(f'/api/documents/{report["document_id"]}/preview')
    assert preview.status_code == 200
    assert "text/html" in preview.headers["content-type"]
    assert "frame-ancestors 'self'" in preview.headers["content-security-policy"]
    assert TEXT in preview.text
    assert client.get("/api/stats").json() == {"references": 1, "reference_chunks": 1, "checks": 1}
    # New application/connection context reads the saved PostgreSQL report.
    with TestClient(create_app(settings, app.state.database)) as restarted:
        assert restarted.get(f'/api/checks/{report["id"]}').json() == report
        assert len(restarted.get("/api/checks").json()) == 1
        assert restarted.get(f'/api/documents/{reference.json()["id"]}/file').content == original


def test_empty_reference_corpus_does_not_save_submission(web):
    client, app, settings = web
    assert upload(client, "/api/checks").status_code == 409
    assert client.get("/api/documents").json() == []
    assert list(settings.upload_dir.iterdir()) == []


def test_duplicate_reference_hash_and_same_filename_different_content(web):
    client, _, _ = web
    content = make_docx(TEXT)
    assert upload(client, "/api/references", content).status_code == 201
    assert upload(client, "/api/references", content, name="renamed.docx").status_code == 409
    assert upload(client, "/api/references", make_docx(OTHER)).status_code == 201
    assert client.get("/api/stats").json()["references"] == 2


def test_unrelated_report_no_matches_and_no_automatic_reference(web):
    client, _, _ = web
    upload(client, "/api/references")
    result = upload(client, "/api/checks", make_docx(OTHER)).json()
    assert result["coverage"] == 0
    assert result["matches"] == []
    assert client.get("/api/stats").json()["references"] == 1


def test_multiple_sources_do_not_double_count_coverage(web):
    client, _, _ = web
    upload(client, "/api/references", make_docx(TEXT), name="a.docx")
    upload(client, "/api/references", make_docx(TEXT, OTHER), name="b.docx")
    result = upload(client, "/api/checks").json()
    assert len(result["sources"]) == 2
    assert result["coverage"] == 100
    assert result["matched_chunks"] == 1


def test_invalid_empty_and_oversized_files_leave_no_records(web):
    client, _, settings = web
    for filename, content, expected in [("bad.pdf", b"not a pdf", 422), ("bad.docx", b"PK bad zip", 422), ("empty.docx", b"", 422), ("bad.exe", b"hello", 415), ("large.pdf", b"x" * (1024 * 1024 + 1), 413)]:
        response = upload(client, "/api/references", content, filename)
        assert response.status_code == expected, response.text
    assert client.get("/api/documents").json() == []
    assert list(settings.upload_dir.iterdir()) == []


def test_pdf_scan_is_not_zero_percent_success(web):
    client, _, _ = web
    upload(client, "/api/references")
    response = upload(client, "/api/checks", make_pdf([""]), name="scan.pdf")
    assert response.status_code == 422
    assert "OCR" in response.json()["detail"]
    assert client.get("/api/checks").json() == []


def test_pdf_upload_check_and_download(web):
    client, _, _ = web
    content = make_pdf(["Document duplicate checking system"])
    assert upload(client, "/api/references", content, name="source.pdf").status_code == 201
    report = upload(client, "/api/checks", content, name="query.pdf").json()
    assert report["coverage"] == 100
    assert report["matches"][0]["query_location"]["page"] == 1
    preview = client.get(f'/api/documents/{report["document_id"]}/preview')
    assert preview.status_code == 200
    assert preview.headers["content-type"] == "application/pdf"
    assert "frame-ancestors 'self'" in preview.headers["content-security-policy"]
    assert preview.content.startswith(b"%PDF-")


def test_semantic_disabled_and_invalid_threshold_are_explicit(web):
    client, _, _ = web
    upload(client, "/api/references")
    assert upload(client, "/api/checks", engine="semantic").status_code == 503
    assert upload(client, "/api/checks", threshold="1.2").status_code == 422
    assert upload(client, "/api/checks", threshold="nan").status_code == 422
    assert client.get("/api/checks").json() == []


def test_cross_origin_upload_rejected(web):
    client, _, _ = web
    response = client.post("/api/references", files={"file": ("a.docx", make_docx(TEXT))}, headers={"Origin": "https://example.com"})
    assert response.status_code == 403


def test_failed_check_rolls_back_and_removes_file(web, monkeypatch):
    client, app, settings = web
    upload(client, "/api/references")
    from app.services.checker import EngineUnavailable
    def fail(*args):
        raise EngineUnavailable("Model unavailable")
    monkeypatch.setattr(app.state.checker, "search", fail)
    assert upload(client, "/api/checks").status_code == 503
    with app.state.database.session() as session:
        assert session.scalar(select(func.count(Document.id))) == 1
        assert session.scalar(select(func.count(Check.id))) == 0
    assert len(list(settings.upload_dir.iterdir())) == 1
