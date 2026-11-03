from types import SimpleNamespace

from app.services.checker import exclusion_reason, filter_chunks, make_report


def chunk(identifier, ordinal, text, document_id=None, section="Nội dung"):
    item = {
        "id": identifier, "ordinal": ordinal, "text": text,
        "location": {"block": ordinal + 1, "label": f"Đoạn {ordinal + 1}", "section": section},
    }
    if document_id:
        item.update(document_id=document_id, filename=f"{document_id}.docx")
    return item


def test_filters_contents_references_and_boilerplate():
    rows = [
        chunk("a", 0, "Chương 1 ........ 2\nChương 2 ........ 8\nChương 3 ........ 15"),
        chunk("b", 1, "Nguyễn Văn A, Giáo trình xử lý dữ liệu", section="Tài liệu tham khảo"),
        chunk("c", 2, "CỘNG HÒA XÃ HỘI CHỦ NGHĨA VIỆT NAM"),
        chunk("d", 3, "Nội dung phương pháp nghiên cứu của đề tài"),
    ]
    kept, ignored = filter_chunks(rows)
    assert [row["id"] for row in kept] == ["d"]
    assert ignored == {"table_of_contents": 1, "excluded_section": 1, "boilerplate": 1}


def test_report_merges_adjacent_chunks_deduplicates_and_ranks_sources():
    queries = [chunk("q0", 0, "nội dung thứ nhất"), chunk("q1", 1, "nội dung thứ hai")]
    source_a0 = chunk("a0", 0, "nguồn thứ nhất", "a")
    source_a1 = chunk("a1", 1, "nguồn thứ hai", "a")
    source_b0 = chunk("b0", 0, "nguồn phụ", "b")
    rankings = [
        [(source_a0, 0.9), (source_a1, 0.8), (source_b0, 0.7)],
        [(source_a1, 0.85)],
    ]
    report = make_report(SimpleNamespace(filename="query.docx", id="doc", warnings=[]), queries,
                         [source_a0, source_a1, source_b0], rankings, "semantic", 0.6, "model")
    assert report["schema_version"] == 3
    assert report["alert_type"] == "semantic_similarity"
    assert len(report["matches"]) == 2  # một cảnh báo gộp cho a, một cảnh báo cho b
    merged = next(row for row in report["matches"] if row["source_document_id"] == "a")
    assert merged["chunk_count"] == 2
    assert merged["query_chunk_ids"] == ["q0", "q1"]
    assert report["sources"][0]["document_id"] == "a"
    assert report["sources"][0]["rank"] == 1
    assert report["matched_chunks"] == 2
    assert report["matches"][0]["alert_number"] == 1
    assert report["document_chunks"][0]["alert_numbers"]


def test_lexical_and_semantic_alert_labels_are_distinct():
    query = chunk("q", 0, "một đoạn")
    source = chunk("s", 0, "một đoạn", "source")
    document = SimpleNamespace(filename="q.docx", id="qdoc", warnings=[])
    lexical = make_report(document, [query], [source], [[(source, 1.0)]], "lexical", 0.5, "model")
    semantic = make_report(document, [query], [source], [[(source, 1.0)]], "semantic", 0.5, "model")
    assert lexical["alert_label"] == "Trùng khớp từ vựng"
    assert semantic["alert_label"] == "Tương đồng ngữ nghĩa"


def test_alert_limit_can_reach_one_thousand():
    document = SimpleNamespace(filename="q.docx", id="qdoc", warnings=[])
    queries = [chunk(f"q{i}", i * 2, f"query {i}") for i in range(12)]
    sources = [chunk(f"s{i}", i * 2, f"source {i}", "source") for i in range(12)]
    rankings = [[(source, 0.9)] for source in sources]
    report = make_report(document, queries, sources, rankings, "lexical", 0.5, "model",
                         max_alerts=1000, max_per_source=1000)
    assert len(report["matches"]) == 12
    assert report["suppressed_alerts"] == 0
    assert report["alert_limits"] == {"per_source": 1000, "per_report": 1000}
