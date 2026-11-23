from app.config import Settings
from app.services.matching.checker import Checker, make_report
from app.services.matching.shingles import ShingleIndex, covered_words, tokenize

SOURCE = "Hợp đồng chuyển nhượng quyền sử dụng đất phải được lập thành văn bản và công chứng theo quy định của pháp luật hiện hành"


def ref(i, text):
    return {"id": f"r{i}", "document_id": f"d{i}", "filename": f"nguon{i}.docx", "text": text, "ordinal": 0, "location": {}}


def test_score_is_fraction_of_verbatim_words():
    index = ShingleIndex([ref(1, SOURCE)])
    copied = SOURCE + " " + "cụm từ hoàn toàn khác biệt về sau không hề liên quan gì nữa cả"
    (item, score, words), = index.search(copied)
    assert item["id"] == "r1" and words == len(tokenize(SOURCE))
    assert abs(score - words / len(tokenize(copied))) < 1e-9
    assert index.search(SOURCE)[0][1] == 1.0


def test_light_edits_still_found_but_same_topic_is_not():
    index = ShingleIndex([ref(1, SOURCE)])
    edited = SOURCE.replace("công chứng", "chứng thực").replace("hiện hành", "đang có hiệu lực")
    assert index.search(edited)[0][1] > 0.5
    same_topic = "Việc chuyển nhượng đất đai cần có văn bản, các bên nên công chứng để bảo đảm quyền lợi theo luật"
    assert index.search(same_topic) == []


def test_function_words_alone_do_not_create_a_match():
    boiler = "của các và những được trong cho với"
    index = ShingleIndex([ref(1, boiler + " " + boiler)])
    assert index.search(boiler + " " + boiler) == []


def test_short_text_only_when_identical():
    index = ShingleIndex([ref(1, "Kết quả chung"), ref(2, "Kết luận")])
    assert index.search("kết quả chung")[0][1] == 1.0
    assert index.search("Kết luận") == []  # dưới 3 từ
    assert index.search("Kết quả riêng") == []
    assert covered_words(tokenize("Kết quả chung"), tokenize("kết quả chung")) == {0, 1, 2}


def test_best_source_is_ranked_first():
    other = "Quy trình phát hiện trùng lặp so sánh từng đoạn văn bản nộp lên với kho tài liệu tham chiếu đã lưu"
    index = ShingleIndex([ref(1, other), ref(2, SOURCE)])
    assert index.search(SOURCE + " " + other[:30])[0][0]["id"] == "r2"


def test_checker_caches_index_per_corpus():
    checker = Checker(Settings.load())
    refs = [ref(1, SOURCE)]
    checker.search([{"id": "q", "text": SOURCE}], refs, "lexical")
    first = next(iter(checker._indexes.values()))
    checker.search([{"id": "q", "text": SOURCE}], list(refs), "lexical")
    assert next(iter(checker._indexes.values())) is first and len(checker._indexes) == 1
    for n in range(6):
        checker.search([{"id": "q", "text": SOURCE}], [ref(10 + n, SOURCE)], "lexical")
    assert len(checker._indexes) <= 4


class Doc:
    id, filename, warnings = "doc", "bai.docx", []


def test_report_has_word_level_similarity_index():
    filler = "Phần này do sinh viên tự viết hoàn toàn mới, trình bày kết quả chung trên bộ dữ liệu riêng của đề tài nghiên cứu"
    queries = [
        {"id": "q1", "ordinal": 0, "text": SOURCE, "location": {}},
        {"id": "q2", "ordinal": 1, "text": filler, "location": {}},
    ]
    refs = [ref(1, SOURCE)]
    rankings = Checker(Settings.load()).search(queries, refs, "lexical")
    report = make_report(Doc, queries, refs, rankings, "lexical", 0.3, "x")
    total = len(tokenize(SOURCE)) + len(tokenize(filler))
    assert report["model"] == "word-4gram-verbatim-v2"
    assert abs(report["similarity_index"] - round(len(tokenize(SOURCE)) / total * 100, 2)) < 0.01
    source = report["sources"][0]
    assert source["matched_words"] == len(tokenize(SOURCE))
    assert report["matched_chunks"] == 1 and report["document_chunks"][1]["alert_numbers"] == []


def test_partial_copy_flagged_even_when_chunk_is_mostly_original():
    original = "Nội dung hoàn toàn mới do tác giả viết ra để mô tả hệ thống và cách triển khai trên máy chủ của trường đại học " * 2
    mixed = original + SOURCE
    queries = [{"id": "q1", "ordinal": 0, "text": mixed, "location": {}}]
    refs = [ref(1, SOURCE)]
    rankings = Checker(Settings.load()).search(queries, refs, "lexical")
    score = rankings[0][0][1]
    assert 0.25 < score < 0.6
    report = make_report(Doc, queries, refs, rankings, "lexical", 0.25, "x")
    assert report["matched_chunks"] == 1 and report["similarity_index"] > 25


def test_web_query_uses_most_distinctive_window_not_the_opening():
    from app.services.web.serper import web_query_from_text
    text = ("Trong phần này chúng ta sẽ cùng nhau xem xét một số vấn đề như sau: thuật toán băm cụm từ liên tiếp dựng chỉ mục ngược "
            "giúp tăng tốc độ phát hiện trùng lặp văn bản")
    phrase = web_query_from_text(text)
    assert phrase.startswith('"') and phrase.endswith('"') and "trùng lặp văn bản" in phrase
    assert not phrase.startswith('"Trong phần này')
    assert web_query_from_text("quá ngắn để tìm") is None
