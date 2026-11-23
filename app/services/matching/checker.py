"""Explicit lexical baseline and optional existing SBERT/FAISS integration."""
from collections import Counter
from math import sqrt
from threading import Lock
import re

from app.services.document.documents import normalize
from app.services.matching.shingles import NGRAM, ShingleIndex, covered_words, tokenize


class EngineUnavailable(RuntimeError):
    pass


def features(text):
    words = re.findall(r"\w+", normalize(text))
    # Unigrams + bigrams, without external model downloads. This is NOT semantic.
    return Counter([("word", word) for word in words] + [("pair", a, b) for a, b in zip(words, words[1:])])


MIN_SHARED_WORDS = 4


def _words(text):
    return re.findall(r"[^\W_]+", normalize(text))


def shares_phrase(first, second, n=MIN_SHARED_WORDS):
    """Hai đoạn có chung ít nhất một cụm n từ liên tiếp (không phân biệt hoa/thường, dấu câu) hay không.

    Điểm cosine từ vựng chỉ đo mức dùng chung từ ngữ nên hai văn bản khác chủ đề vẫn đạt ~0,07-0,12 nhờ các từ phổ biến
    ("và", "của", "trong"...). Cảnh báo "trùng khớp từ vựng" vì vậy phải có bằng chứng là cụm từ trùng nguyên văn, cùng quy tắc
    với phần tô đậm trên giao diện. Đoạn dưới 3 từ (tiêu đề, nhãn) chỉ tính khi hai đoạn giống hệt nhau."""
    a, b = _words(first), _words(second)
    if not a or not b:
        return False
    if min(len(a), len(b)) < 3:
        return a == b
    n = min(n, len(a), len(b))
    grams = {tuple(b[i:i + n]) for i in range(len(b) - n + 1)}
    return any(tuple(a[i:i + n]) in grams for i in range(len(a) - n + 1))


def cosine(left, right):
    denominator = sqrt(sum(v * v for v in left.values()) * sum(v * v for v in right.values()))
    return sum(v * right.get(k, 0) for k, v in left.items()) / denominator if denominator else 0.0


EXCLUDED_SECTIONS = (
    "mục lục", "danh mục bảng", "danh mục hình", "tài liệu tham khảo",
    "tham khảo", "bibliography", "references", "table of contents",
)
BOILERPLATE_PATTERNS = (
    "cộng hòa xã hội chủ nghĩa việt nam", "độc lập tự do hạnh phúc",
    "lời cam đoan", "em xin cam đoan", "chúng tôi xin cam đoan",
    "ý kiến của giảng viên hướng dẫn", "nhận xét của giảng viên",
)


def exclusion_reason(item):
    """Trả lý do bỏ qua các phần không nên tham gia đối chiếu, nếu có."""
    text = normalize(item.get("text", ""))
    section = normalize(item.get("location", {}).get("section") or "")
    if any(section == title or section.startswith(title + " ") for title in EXCLUDED_SECTIONS):
        return "excluded_section"
    if text in EXCLUDED_SECTIONS:
        return "excluded_heading"
    lines = [line.strip() for line in item.get("text", "").splitlines() if line.strip()]
    dot_leaders = sum(bool(re.search(r"\.{3,}\s*\d+\s*$", line)) for line in lines)
    if len(lines) >= 3 and dot_leaders >= max(2, len(lines) // 2):
        return "table_of_contents"
    if len(text.split()) <= 35 and any(pattern in text for pattern in BOILERPLATE_PATTERNS):
        return "boilerplate"
    return None


def filter_chunks(items):
    kept, ignored = [], Counter()
    for item in items:
        reason = exclusion_reason(item)
        if reason:
            ignored[reason] += 1
        else:
            kept.append(item)
    return kept, dict(ignored)


class Checker:
    def __init__(self, settings):
        self.settings = settings
        self._lock = Lock()
        self._store = None
        self._signature = None
        self._indexes = {}

    def _lexical_index(self, references):
        """Chỉ mục cụm từ của kho; dựng một lần rồi dùng lại cho các lần kiểm tra có cùng kho (giữ vài kho gần nhất)."""
        signature = tuple(item["id"] for item in references)
        with self._lock:
            index = self._indexes.get(signature)
            if index is None:
                index = ShingleIndex(references)
                self._indexes[signature] = index
                while len(self._indexes) > 4:
                    self._indexes.pop(next(iter(self._indexes)))
            return index

    def search(self, queries, references, engine, top_k=3):
        if engine == "lexical":
            index = self._lexical_index(references)
            return [[(item, min(1.0, score)) for item, score, _ in index.search(query["text"], top_k)] for query in queries]
        if engine != "semantic" or not self.settings.enable_semantic:
            raise EngineUnavailable("Chế độ ngữ nghĩa chưa bật. Cài requirements.txt, đặt ENABLE_SEMANTIC=true trong .env và khởi động lại web.")
        with self._lock:
            try:
                from app.document_processing.vector_store import VectorStore
                from app.document_processing.preprocessor import normalize_unicode, clean_text, tokenize_words

                def prepare(text):
                    return tokenize_words(clean_text(normalize_unicode(text)))

                signature = (self.settings.semantic_model, tuple(item["id"] for item in references))
                if signature != self._signature:
                    # The model is downloaded/cached during setup. Runtime checks must
                    # not hang on Hugging Face retries when the machine is offline.
                    store = VectorStore(
                        model_name=self.settings.semantic_model,
                        local_files_only=True,
                    )
                    store.add_chunks([{**item, "chunk_id": item["id"], "tokenized_text": prepare(item["text"])} for item in references])
                    self._store, self._signature = store, signature
                return [[(item, item["similarity_score"]) for item in self._store.search(prepare(query["text"]), top_k)] for query in queries]
            except Exception as error:
                raise EngineUnavailable("Không chạy được SBERT/FAISS. Kiểm tra cài đặt requirements.txt, model cache và bộ nhớ; không có kết quả ngữ nghĩa được tạo.") from error


def _merge_location(first, last):
    result = dict(first)
    result["end_label"] = last.get("label")
    result["end_page"] = last.get("page")
    result["end_block"] = last.get("block")
    result["end"] = last.get("end")
    return result


def _group_matches(matches, engine, max_alerts=1000, max_per_source=1000):
    """Gộp ánh xạ liền nhau và giới hạn cảnh báo trùng ý trên cùng nguồn."""
    groups = []
    ordered = sorted(matches, key=lambda row: (row["source_document_id"], row["query_ordinal"], row["source_ordinal"], -row["score"]))
    for match in ordered:
        previous = groups[-1] if groups else None
        adjacent = previous and previous["source_document_id"] == match["source_document_id"] \
            and match["query_ordinal"] == previous["query_ordinals"][-1] + 1 \
            and match["source_ordinal"] in {previous["source_ordinals"][-1], previous["source_ordinals"][-1] + 1}
        if adjacent:
            previous["query_chunk_ids"].append(match["query_chunk_id"])
            previous["source_chunk_ids"].append(match["source_chunk_id"])
            previous["query_ordinals"].append(match["query_ordinal"])
            previous["source_ordinals"].append(match["source_ordinal"])
            previous["query_text"] += "\n" + match["query_text"]
            if match["source_chunk_id"] != previous["source_chunk_ids"][-2]:
                previous["source_text"] += "\n" + match["source_text"]
            previous["query_location"] = _merge_location(previous["query_location"], match["query_location"])
            previous["source_location"] = _merge_location(previous["source_location"], match["source_location"])
            previous["scores"].append(match["score"])
            previous["score"] = max(previous["score"], match["score"])
            previous["chunk_count"] += 1
        else:
            groups.append({
                **match, "query_chunk_ids": [match["query_chunk_id"]],
                "source_chunk_ids": [match["source_chunk_id"]],
                "query_ordinals": [match["query_ordinal"]], "source_ordinals": [match["source_ordinal"]],
                "scores": [match["score"]], "chunk_count": 1,
                "alert_type": "semantic_similarity" if engine == "semantic" else "lexical_overlap",
                "alert_label": "Tương đồng ngữ nghĩa" if engine == "semantic" else "Trùng khớp từ vựng",
            })
    for group in groups:
        group["average_score"] = round(sum(group.pop("scores")) / group["chunk_count"], 6)
    groups.sort(key=lambda row: (-row["chunk_count"], -row["score"], row["query_ordinal"]))
    selected, per_source = [], Counter()
    for group in groups:
        source_id = group["source_document_id"]
        if len(selected) >= max_alerts or per_source[source_id] >= max_per_source:
            continue
        per_source[source_id] += 1
        selected.append(group)
    selected.sort(key=lambda row: (row["query_ordinal"], -row["score"], row["source_filename"]))
    for number, group in enumerate(selected, 1):
        group["alert_number"] = number
    return selected, len(groups) - len(selected)


SIMILARITY_DEFINITION = (
    "Tỷ lệ số từ của bài nằm trong các cụm 4 từ liên tiếp trùng nguyên văn với nguồn đối chiếu (không tính cụm chỉ gồm từ chức năng). "
    "Chỉ phản ánh chép nguyên văn hoặc sửa nhẹ; diễn đạt lại không được phát hiện ở chế độ từ vựng, và đây không phải kết luận đạo văn."
)


def _word_level(queries, raw_matches, source_list):
    """Tính mức trùng ở cấp TỪ (chính xác hơn tỷ lệ ký tự của cả đoạn): hợp các từ trùng nguyên văn trên mọi nguồn.

    Ghi thêm vào từng nguồn: matched_words (số từ của bài trùng với riêng nguồn đó) và word_coverage (% trên tổng số từ của bài)."""
    tokens = {query["id"]: tokenize(query["text"]) for query in queries}
    total = sum(len(words) for words in tokens.values())
    union: dict[str, set] = {}
    per_source: dict[str, int] = {}
    seen: dict[str, dict[str, set]] = {}
    for match in raw_matches:
        qid, doc = match["query_chunk_id"], match["source_document_id"]
        covered = covered_words(tokens[qid], tokenize(match["source_text"]))
        union.setdefault(qid, set()).update(covered)
        seen.setdefault(doc, {}).setdefault(qid, set()).update(covered)
    for doc, by_query in seen.items():
        per_source[doc] = sum(len(words) for words in by_query.values())
    for source in source_list:
        count = per_source.get(source["document_id"], 0)
        source["matched_words"] = count
        source["word_coverage"] = round(count / total * 100, 2) if total else 0.0
    covered_total = sum(len(words) for words in union.values())
    return {"index": round(covered_total / total * 100, 2) if total else None, "covered_words": covered_total, "total_words": total}


def make_report(document, queries, references, rankings, engine, threshold, model, threshold_calibrated=False, ignored=None, original_query_count=None, original_queries=None, max_alerts=1000, max_per_source=1000):
    raw_matches, flagged, sources = [], set(), {}
    for query, candidates in zip(queries, rankings):
        # Một query chỉ giữ kết quả tốt nhất trên mỗi tài liệu nguồn.
        best_per_document = {}
        for source, score in candidates:
            if score < threshold:
                continue
            if engine == "lexical" and not shares_phrase(query["text"], source["text"]):
                continue  # điểm vượt ngưỡng chỉ nhờ các từ phổ biến, không có cụm từ trùng nào để chỉ ra
            current = best_per_document.get(source["document_id"])
            if current is None or score > current[1]:
                best_per_document[source["document_id"]] = (source, score)
        for source, score in best_per_document.values():
            flagged.add(query["id"])
            raw_matches.append({
                "query_chunk_id": query["id"], "query_text": query["text"], "query_location": query["location"],
                "query_ordinal": query.get("ordinal", 0),
                "source_document_id": source["document_id"], "source_filename": source["filename"],
                "source_chunk_id": source["id"], "source_text": source["text"], "source_location": source["location"],
                "source_ordinal": source.get("ordinal", 0),
                "score": round(float(score), 6),
            })
            entry = sources.setdefault(source["document_id"], {"document_id": source["document_id"], "filename": source["filename"], "best_score": 0.0, "query_ids": set(), "matched_characters": 0})
            entry["best_score"] = max(entry["best_score"], float(score))
            if query["id"] not in entry["query_ids"]:
                entry["matched_characters"] += len(query["text"])
            entry["query_ids"].add(query["id"])
    total = sum(len(item["text"]) for item in queries)
    marked = sum(len(item["text"]) for item in queries if item["id"] in flagged)
    source_list = [{"document_id": source["document_id"], "filename": source["filename"], "best_score": round(source["best_score"], 6), "matched_chunks": len(source["query_ids"]), "matched_characters": source["matched_characters"]} for source in sources.values()]
    source_list.sort(key=lambda source: (-source["matched_characters"], -source["matched_chunks"], -source["best_score"], source["filename"]))
    for rank, source in enumerate(source_list, 1):
        source["rank"] = rank
        source["coverage"] = round(source["matched_characters"] / total * 100, 2) if total else 0.0
    matches, suppressed = _group_matches(raw_matches, engine, max_alerts, max_per_source)
    word_stats = _word_level(queries, raw_matches, source_list) if engine == "lexical" else None
    ignored = ignored or {"queries": {}, "references": {}}
    alerts_by_chunk = {}
    scores_by_chunk = {}
    for match in matches:
        for chunk_id in match["query_chunk_ids"]:
            alerts_by_chunk.setdefault(chunk_id, []).append(match["alert_number"])
            scores_by_chunk[chunk_id] = max(scores_by_chunk.get(chunk_id, 0.0), match["score"])
    document_chunks = []
    for query in sorted(original_queries or queries, key=lambda row: row.get("ordinal", 0)):
        document_chunks.append({
            "id": query["id"], "ordinal": query.get("ordinal", 0), "text": query["text"],
            "location": query["location"], "alert_numbers": alerts_by_chunk.get(query["id"], []),
            "max_score": round(scores_by_chunk.get(query["id"], 0.0), 6),
            "ignored": exclusion_reason(query),
        })
    return {
        "schema_version": 3, "filename": document.filename, "document_id": document.id,
        "engine": engine, "model": model if engine == "semantic" else "word-4gram-verbatim-v2",
        "alert_type": "semantic_similarity" if engine == "semantic" else "lexical_overlap",
        "alert_label": "Tương đồng ngữ nghĩa" if engine == "semantic" else "Trùng khớp từ vựng",
        "min_shared_words": MIN_SHARED_WORDS if engine == "lexical" else None,
        "threshold": threshold, "threshold_calibrated": threshold_calibrated, "chunking": "nonoverlapping-block-chars-v1",
        "coverage": round(marked / total * 100, 2) if total else None,
        **({"similarity_index": word_stats["index"], "similarity_definition": SIMILARITY_DEFINITION} if word_stats else {}),
        "coverage_definition": "Tỷ lệ ký tự thuộc các đoạn có cảnh báo trên nội dung đủ điều kiện đối chiếu; không phải phần trăm đạo văn.",
        "total_chunks": original_query_count if original_query_count is not None else len(queries),
        "eligible_chunks": len(queries), "matched_chunks": len(flagged),
        "reference_documents": len({item["document_id"] for item in references}),
        "reference_chunk_ids": [item["id"] for item in references],
        "ignored_chunks": ignored, "suppressed_alerts": suppressed,
        "alert_limits": {"per_source": max_per_source, "per_report": max_alerts},
        "warnings": document.warnings, "sources": source_list, "matches": matches,
        "document_chunks": document_chunks,
    }
