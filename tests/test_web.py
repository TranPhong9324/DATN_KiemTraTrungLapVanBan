import re
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
        entry = client.get("/")
        assert 'id="root"' in entry.text
        for asset in re.findall(r'(?:src|href)="(/assets/[^"]+)"', entry.text):
            assert client.get(asset).status_code == 200
        assert client.get("/static/doc-preview.css").status_code == 200
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
    assert report["coverage"] == 0
    assert report["matched_chunks"] == 0
    assert report["matches"] == []
    assert report["excluded_self_document_ids"] == [reference.json()["id"]]
    assert report["document_id"] != reference.json()["id"]
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


def test_unrelated_report_is_archived_after_comparison_without_self_match(web):
    client, _, _ = web
    upload(client, "/api/references")
    result = upload(client, "/api/checks", make_docx(OTHER)).json()
    assert result["coverage"] == 0
    assert result["matches"] == []
    assert result["reference_archive"]["status"] == "added"
    assert client.get("/api/stats").json()["references"] == 2
    archived_id = result["reference_archive"]["document_id"]
    assert archived_id not in {source["document_id"] for source in result["sources"]}
    documents = client.get("/api/documents?role=reference").json()
    assert any(doc["id"] == archived_id for doc in documents)
    content = client.get(f"/api/documents/{archived_id}/file").content
    repeated = upload(client, "/api/checks", content, name="renamed.docx").json()
    assert repeated["reference_archive"] == {"status": "existing", "document_id": archived_id}
    assert repeated["coverage"] == 0
    assert repeated["matches"] == []
    assert repeated["excluded_self_document_ids"] == [archived_id]
    assert client.get("/api/stats").json()["references"] == 2


def test_multiple_sources_do_not_double_count_coverage(web):
    client, _, _ = web
    upload(client, "/api/references", make_docx(TEXT, TEXT), name="a.docx")
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
    assert report["coverage"] == 0
    assert report["matches"] == []
    assert report["excluded_self_document_ids"]
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
    upload(client, "/api/references", make_docx(TEXT, OTHER))
    from app.services.checker import EngineUnavailable
    def fail(*args):
        raise EngineUnavailable("Model unavailable")
    monkeypatch.setattr(app.state.checker, "search", fail)
    assert upload(client, "/api/checks").status_code == 503
    with app.state.database.session() as session:
        assert session.scalar(select(func.count(Document.id))) == 1
        assert session.scalar(select(func.count(Check.id))) == 0
    assert len(list(settings.upload_dir.iterdir())) == 1


def test_omitted_engine_and_threshold_follow_configuration(web, monkeypatch):
    from dataclasses import replace
    from app.services.checker import Checker
    _, original_app, settings = web
    configured = replace(settings, enable_semantic=True, semantic_threshold=0.73)
    app = create_app(configured, original_app.state.database)
    lexical = Checker(settings)
    selected = []
    def search(queries, references, engine):
        selected.append(engine)
        return lexical.search(queries, references, "lexical")
    # This test verifies API routing/defaults; it does not claim to test the model.
    monkeypatch.setattr(app.state.checker, "search", search)
    with TestClient(app) as client:
        upload(client, "/api/references", make_docx(TEXT, OTHER))
        response = upload(client, "/api/checks")
        assert response.status_code == 201, response.text
        assert selected == ["semantic"]
        assert response.json()["engine"] == "semantic"
        assert response.json()["threshold"] == 0.73
        explicit = upload(client, "/api/checks", engine="lexical", threshold="0.91")
        assert explicit.status_code == 201
        assert selected[-1] == "lexical"
        assert explicit.json()["threshold"] == 0.91

def test_internet_batches_cover_all_chunks_without_confirmation_and_persist(web):
    from dataclasses import replace
    from test_internet import FakeSerper
    client, original_app, settings = web
    upload(client, "/api/references")
    app = create_app(replace(settings, serper_max_queries=2), original_app.state.database)
    provider = FakeSerper()
    app.state.serper = provider
    paragraphs = [f"Đoạn {i} trình bày chức năng hệ thống xử lý văn bản và tìm kiếm nội dung tương đồng trong báo cáo." for i in range(5)]
    with TestClient(app) as test_client:
        response = upload(test_client, "/api/checks", make_docx(*paragraphs))
        assert response.status_code == 201, response.text
        report = response.json()
        assert provider.calls == []  # Save internal results before continuation batches.
        assert report["internet_search"]["searched_chunks"] == 0
        endpoint = f'/api/checks/{report["id"]}/internet/continue'
        assert provider.calls == []
        first = test_client.post(endpoint).json()
        assert first["internet_search"]["searched_chunks"] == 2
        assert first["internet_search"]["pending_chunks"] == 3
        saved = test_client.get(f'/api/checks/{report["id"]}').json()
        assert saved["internet_search"]["searched_chunks"] == 2
        second = test_client.post(endpoint).json()
        final = test_client.post(endpoint).json()
        assert second["internet_search"]["searched_chunks"] == 4
        assert final["internet_search"]["complete"]
        assert [item["ordinal"] for item in final["internet_search"]["queries"]] == list(range(5))
        assert len(provider.calls) == 5
        test_client.post(endpoint)
        assert len(provider.calls) == 5

def test_internet_error_progress_survives_reload_and_resumes_without_repeating_successes(web):
    from dataclasses import replace
    from test_internet import FakeSerper
    client, original_app, settings = web
    upload(client, "/api/references")
    app = create_app(replace(settings, serper_max_queries=3), original_app.state.database)
    provider = FakeSerper(fail_on=2)
    app.state.serper = provider
    content = make_docx(*[f"Đoạn {i} mô tả chức năng kiểm tra văn bản trong hệ thống quản lý báo cáo của trường." for i in range(3)])
    with TestClient(app) as test_client:
        report = upload(test_client, "/api/checks", content).json()
        endpoint = f'/api/checks/{report["id"]}/internet/continue'
        failed = test_client.post(endpoint).json()
        assert failed["internet_search"]["status"] == "error"
        assert failed["internet_search"]["searched_chunks"] == 1
        saved = test_client.get(f'/api/checks/{report["id"]}').json()
        assert saved["internet_search"]["searched_chunks"] == 1
        provider.fail_on = None
        final = test_client.post(endpoint).json()
        assert final["internet_search"]["complete"]
        assert len(final["internet_search"]["queries"]) == 3
        assert len(provider.calls) == 4  # Three successes and one failed request.


def test_reference_capacity_does_not_discard_successful_check(web):
    from dataclasses import replace
    client, original_app, settings = web
    upload(client, "/api/references")
    with TestClient(create_app(replace(settings, max_reference_chunks=1), original_app.state.database)) as limited:
        result = upload(limited, "/api/checks", make_docx(OTHER))
        assert result.status_code == 201
        report = result.json()
        assert report["reference_archive"]["status"] == "capacity_reached"
        assert report["warnings"]
        assert limited.get("/api/stats").json()["references"] == 1
        assert limited.get(f'/api/checks/{report["id"]}').status_code == 200


def test_same_file_is_skipped_but_other_sources_are_still_compared(web):
    client, _, _ = web
    content = make_docx(TEXT)
    own = upload(client, "/api/references", content, name="original.docx").json()
    other = upload(client, "/api/references", make_docx(TEXT, OTHER), name="other.docx").json()
    report = upload(client, "/api/checks", content, name="renamed.docx").json()
    assert report["excluded_self_document_ids"] == [own["id"]]
    assert report["coverage"] == 100
    assert {match["source_document_id"] for match in report["matches"]} == {other["id"]}
    own_chunks = {chunk["id"] for chunk in report["document_chunks"]}
    assert not own_chunks.intersection(report["reference_chunk_ids"])
    assert report["reference_documents"] == 1
    assert client.get("/api/stats").json()["references"] == 2
