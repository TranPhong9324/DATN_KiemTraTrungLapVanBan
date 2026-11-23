"""Resumable Internet search in document order."""
from time import perf_counter

from app.services.checker import cosine, features
from app.services.serper import SerperError, web_query_from_text


def best_web_matches(matches):
    """Keep the highest-scoring web source per query; ties keep the first."""
    best = {}
    for row in matches:
        key = row.get("query_id")
        if key not in best or (row.get("web_score") or 0) > (best[key].get("web_score") or 0):
            best[key] = dict(row)
    return list(best.values())


def report_queries(report):
    return sorted(
        [row for row in report.get("document_chunks", []) if not row.get("ignored")],
        key=lambda row: row.get("ordinal", 0),
    )


def search_state(queries, previous, enabled, batch_size):
    previous = previous or {}
    ids = {row["id"] for row in queries}
    searches = [dict(row) for row in previous.get("queries", []) if row.get("query_id") in ids]
    states = {key: dict(value) for key, value in previous.get("query_states", {}).items()
              if key in ids and isinstance(value, dict)}
    for row in searches:
        states[row["query_id"]] = {"status": "searched"}
    for row in queries:
        if row["id"] not in states and not web_query_from_text(row.get("text", "")):
            states[row["id"]] = {"status": "skipped", "reason": "too_short"}
    searched = sum(states.get(row["id"], {}).get("status") == "searched" for row in queries)
    skipped = sum(states.get(row["id"], {}).get("status") == "skipped" for row in queries)
    remaining = len(queries) - searched - skipped
    warning = previous.get("warning") if previous.get("state_version") == 1 else None
    if not enabled:
        status, warning = "disabled", "Chưa cấu hình tìm nguồn Internet."
    elif not remaining:
        status, warning = "complete", None
    elif warning:
        status = "error"
    else:
        status = "pending"
    return {
        **previous, "state_version": 1, "enabled": enabled, "provider": "serper",
        "order": "document", "batch_size": batch_size,
        "total_chunks": len(queries), "searched_chunks": searched,
        "skipped_chunks": skipped, "processed_chunks": searched + skipped,
        "pending_chunks": remaining, "complete": enabled and remaining == 0,
        "status": status, "warning": warning, "query_states": states,
        "queries": searches, "matches": best_web_matches(previous.get("matches", [])),
        "resumable": bool(queries),
    }


def search_batch(queries, previous, client, settings):
    """Search the next batch; the frontend runs batches automatically after upload."""
    started = perf_counter()
    state = search_state(queries, previous, client is not None, settings.serper_max_queries)
    if client is None or state["complete"]:
        return state
    state["warning"] = None
    attempted = 0
    for query in sorted(queries, key=lambda row: row.get("ordinal", 0)):
        if state["query_states"].get(query["id"], {}).get("status") in {"searched", "skipped"}:
            continue
        if attempted >= settings.serper_max_queries:
            break
        phrase = web_query_from_text(query.get("text", ""))
        if not phrase:
            state["query_states"][query["id"]] = {"status": "skipped", "reason": "too_short"}
            continue
        attempted += 1
        try:
            payload = client.search(phrase, num=settings.serper_max_results)
        except SerperError as error:
            state["query_states"][query["id"]] = {"status": "error"}
            state["warning"] = str(error)
            break
        state["queries"].append({
            "query_id": query["id"], "ordinal": query.get("ordinal", 0),
            "text": query["text"], "phrase": phrase, "result_count": len(payload["organic"]),
            "cache_hit": payload.get("cache_hit", False),
        })
        state["query_states"][query["id"]] = {"status": "searched"}
        for item in payload["organic"]:
            comparison = f'{item.get("title", "")} {item.get("snippet", "")}'
            score = cosine(features(query["text"]), features(comparison))
            state["matches"].append({
                **item, "query_id": query["id"], "query_ordinal": query.get("ordinal", 0),
                "query_text": query["text"], "web_score": round(score, 6),
                "candidate": score >= settings.serper_similarity_threshold,
            })
    state["elapsed_seconds"] = round((previous or {}).get("elapsed_seconds", 0) + perf_counter() - started, 3)
    return search_state(queries, state, True, settings.serper_max_queries)
