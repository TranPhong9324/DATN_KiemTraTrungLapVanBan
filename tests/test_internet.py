from app.config import Settings
from app.services.internet import search_batch, search_state
from app.services.serper import SerperError, web_query_from_text


def queries(count=7):
    return [{"id": f"q{i}", "ordinal": i,
             "text": f"Đoạn {i} mô tả hệ thống quản lý dữ liệu báo cáo và kiểm tra nội dung tương đồng.",
             "location": {}} for i in range(count)]


class FakeSerper:
    def __init__(self, fail_on=None):
        self.calls = []
        self.fail_on = fail_on
    def search(self, phrase, **kwargs):
        self.calls.append(phrase)
        if self.fail_on is not None and len(self.calls) == self.fail_on:
            raise SerperError("API hết hạn mức")
        return {"organic": [{"title": "Nguồn đối chiếu", "snippet": phrase, "link": "https://example.org/source"}]}


def test_all_chunks_are_searched_in_order_across_batches_not_just_first_five():
    rows, client, settings = queries(), FakeSerper(), Settings()
    first = search_batch(list(reversed(rows)), None, client, settings)
    assert first["searched_chunks"] == 5 and first["pending_chunks"] == 2
    assert [row["query_id"] for row in first["queries"]] == [f"q{i}" for i in range(5)]
    final = search_batch(rows, first, client, settings)
    assert final["complete"] and final["searched_chunks"] == 7
    assert len(client.calls) == 7
    assert [row["query_id"] for row in final["queries"]] == [f"q{i}" for i in range(7)]
    assert search_batch(rows, final, client, settings)["complete"]
    assert len(client.calls) == 7


def test_error_keeps_saved_successes_and_retry_starts_at_failed_chunk():
    rows, settings = queries(), Settings(serper_max_queries=3)
    failed = search_batch(rows, None, FakeSerper(fail_on=3), settings)
    assert failed["status"] == "error" and failed["searched_chunks"] == 2
    assert failed["query_states"]["q2"]["status"] == "error"
    retry = FakeSerper()
    resumed = search_batch(rows, failed, retry, settings)
    assert retry.calls[0] == web_query_from_text(rows[2]["text"])
    assert resumed["searched_chunks"] == 5
    final = search_batch(rows, resumed, retry, settings)
    assert final["complete"]
    assert len({row["query_id"] for row in final["queries"]}) == 7


def test_legacy_nonconsecutive_results_are_preserved_and_gaps_are_filled():
    rows, client = queries(), FakeSerper()
    previous = {"queries": [{"query_id": "q4", "ordinal": 4}], "matches": [{"query_id": "q4", "title": "Existing"}]}
    result = search_batch(rows, previous, client, Settings(serper_max_queries=4))
    assert result["matches"][0] == previous["matches"][0]
    assert web_query_from_text(rows[4]["text"]) not in client.calls
    assert {row["query_id"] for row in result["queries"]} == {"q0", "q1", "q2", "q3", "q4"}


def test_short_chunks_are_reported_as_skipped_not_searched():
    rows = queries(1) + [{"id": "short", "ordinal": 1, "text": "Mục tiêu"}]
    result = search_batch(rows, None, FakeSerper(), Settings())
    assert result["complete"]
    assert result["total_chunks"] == 2
    assert result["searched_chunks"] == 1 and result["skipped_chunks"] == 1
    assert result["query_states"]["short"] == {"status": "skipped", "reason": "too_short"}


def test_disabled_search_does_not_claim_completion():
    result = search_state(queries(), None, False, 5)
    assert not result["enabled"] and not result["complete"]
    assert result["status"] == "disabled" and result["searched_chunks"] == 0


def test_only_highest_scoring_source_is_kept_for_each_chunk():
    class MultipleSources:
        def search(self, phrase, **kwargs):
            return {"organic": [
                {"title": "Unrelated", "snippet": "oranges bananas", "link": "https://low.example"},
                {"title": "", "snippet": queries(1)[0]["text"], "link": "https://best.example"},
                {"title": "Other", "snippet": "oranges", "link": "https://other.example"},
            ]}
    result = search_batch(queries(1), None, MultipleSources(), Settings())
    assert len(result["matches"]) == 1
    assert result["matches"][0]["link"] == "https://best.example"


def test_saved_results_keep_best_source_per_chunk_and_first_on_ties():
    previous = {"matches": [
        {"query_id": "q0", "web_score": 0.1},
        {"query_id": "q1", "web_score": 0.4},
        {"query_id": "q0", "web_score": 0.8, "title": "Best"},
        {"query_id": "q0", "web_score": 0.8, "title": "Tie"},
    ]}
    result = search_state(queries(2), previous, True, 5)
    assert result["matches"] == [previous["matches"][2], previous["matches"][1]]
