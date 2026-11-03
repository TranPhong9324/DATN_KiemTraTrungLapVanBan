"""Đánh giá ngưỡng cảnh báo và Recall@k cho lexical/SBERT + FAISS.

Chạy từ thư mục gốc: python -m evaluation.evaluate
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path
from app.services.checker import cosine, features

ROOT = Path(__file__).resolve().parent.parent


def read_jsonl(path: Path) -> list[dict]:
    with path.open(encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def confusion(labels: list[int], scores: list[float], threshold: float) -> dict[str, int]:
    result = Counter(tp=0, fp=0, fn=0, tn=0)
    for label, score in zip(labels, scores):
        predicted = int(score >= threshold)
        result[{(1, 1): "tp", (0, 1): "fp", (1, 0): "fn", (0, 0): "tn"}[(label, predicted)]] += 1
    return dict(result)


def metrics(labels: list[int], scores: list[float], threshold: float) -> dict:
    matrix = confusion(labels, scores, threshold)
    tp, fp, fn, tn = (matrix[key] for key in ("tp", "fp", "fn", "tn"))
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return {
        "threshold": round(threshold, 2), "precision": round(precision, 4),
        "recall": round(recall, 4), "f1": round(f1, 4),
        "accuracy": round((tp + tn) / len(labels), 4) if labels else 0.0,
        "confusion_matrix": matrix,
    }


def select_threshold(labels: list[int], scores: list[float]) -> dict:
    """Chọn trên lưới 0.00..1.00; hòa F1 thì ưu tiên precision rồi ngưỡng cao."""
    candidates = [metrics(labels, scores, step / 100) for step in range(101)]
    return max(candidates, key=lambda item: (item["f1"], item["precision"], item["threshold"]))


def prepare_semantic(text: str) -> str:
    from preprocessor import clean_text, normalize_unicode, tokenize_words
    return tokenize_words(clean_text(normalize_unicode(text)))


def pair_scores(pairs: list[dict], engine: str, model_name: str) -> list[float]:
    if engine == "lexical":
        return [float(cosine(features(row["query"]), features(row["candidate"]))) for row in pairs]
    from vector_store import VectorStore
    store = VectorStore(model_name=model_name, local_files_only=True)
    texts = [prepare_semantic(row[key]) for row in pairs for key in ("query", "candidate")]
    vectors = store.encode(texts)
    return [float(vectors[index] @ vectors[index + 1]) for index in range(0, len(vectors), 2)]


def ranked_lexical(query: str, corpus: list[dict]) -> list[str]:
    vector = features(query)
    return [row["id"] for row in sorted(corpus, key=lambda row: -cosine(vector, features(row["text"])))]


def recall_at_k(rankings: list[list[str]], relevant: list[set[str]], values=(1, 3, 5)) -> dict[str, float]:
    output = {}
    for k in values:
        recalls = [len(set(ranking[:k]) & expected) / len(expected) for ranking, expected in zip(rankings, relevant)]
        output[f"recall@{k}"] = round(sum(recalls) / len(recalls), 4) if recalls else 0.0
    return output


def retrieval_scores(corpus: list[dict], queries: list[dict], model_name: str) -> dict:
    lexical = [ranked_lexical(row["text"], corpus) for row in queries]
    from vector_store import VectorStore
    store = VectorStore(model_name=model_name, local_files_only=True)
    store.add_chunks([
        {"chunk_id": row["id"], "tokenized_text": prepare_semantic(row["text"]), "text": row["text"]}
        for row in corpus
    ])
    semantic = [
        [hit["chunk_id"] for hit in store.search(prepare_semantic(row["text"]), top_k=len(corpus))]
        for row in queries
    ]
    output = {}
    for engine, rankings in (("lexical", lexical), ("semantic_faiss", semantic)):
        output[engine] = {}
        for split in ("validation", "test", "all"):
            indexes = [i for i, row in enumerate(queries) if split == "all" or row["split"] == split]
            output[engine][split] = recall_at_k(
                [rankings[i] for i in indexes], [set(queries[i]["relevant_ids"]) for i in indexes]
            )
    return output


def render_report(result: dict) -> str:
    lines = [
        "# Kết quả hiệu chỉnh ngưỡng ban đầu", "",
        "> Đây là phép đo trên tập gán nhãn khởi đầu có kiểm soát. Ngưỡng cần được đo lại trên báo cáo thật do giảng viên gán nhãn trước khi nghiệm thu.", "",
        f"- Mô hình semantic: `{result['model']}`", f"- Số cặp: {result['dataset']['pairs']} (validation: {result['dataset']['validation']}, test: {result['dataset']['test']})",
        f"- Kho truy xuất: {result['dataset']['corpus']} đoạn; {result['dataset']['queries']} truy vấn", "",
    ]
    for engine in ("lexical", "semantic"):
        block = result["classification"][engine]
        lines += [f"## {engine}", "", f"Ngưỡng được chọn **chỉ bằng validation**: `{block['selected_threshold']:.2f}`.", "",
                  "| Tập | Precision | Recall | F1 | TP | FP | FN | TN |", "|---|---:|---:|---:|---:|---:|---:|---:|"]
        for split in ("validation", "test"):
            m = block[split]; c = m["confusion_matrix"]
            lines.append(f"| {split} | {m['precision']:.4f} | {m['recall']:.4f} | {m['f1']:.4f} | {c['tp']} | {c['fp']} | {c['fn']} | {c['tn']} |")
        lines.append("")
    lines += ["## Recall@k", "", "| Bộ máy | Tập | R@1 | R@3 | R@5 |", "|---|---|---:|---:|---:|"]
    for engine, splits in result["retrieval"].items():
        for split, values in splits.items():
            lines.append(f"| {engine} | {split} | {values['recall@1']:.4f} | {values['recall@3']:.4f} | {values['recall@5']:.4f} |")
    lines += ["", "## Cách đọc ma trận nhầm lẫn", "", "- TP: cảnh báo đúng; FP: cảnh báo nhầm; FN: bỏ sót; TN: không cảnh báo đúng.", "- Precision cao giúp giảm cảnh báo nhầm; recall cao giúp giảm bỏ sót; F1 cân bằng hai mục tiêu.", "- Recall@k đo tỷ lệ tài liệu liên quan xuất hiện trong k kết quả đầu của bước FAISS; chỉ số này độc lập với ngưỡng cảnh báo.", ""]
    return "\n".join(lines)


def evaluate(pairs_path: Path, corpus_path: Path, queries_path: Path, output_dir: Path, model_name: str) -> dict:
    pairs, corpus, queries = read_jsonl(pairs_path), read_jsonl(corpus_path), read_jsonl(queries_path)
    result = {
        "schema_version": 1, "model": model_name,
        "dataset": {"pairs": len(pairs), "validation": sum(r["split"] == "validation" for r in pairs), "test": sum(r["split"] == "test" for r in pairs), "corpus": len(corpus), "queries": len(queries)},
        "classification": {},
    }
    details = []
    for engine in ("lexical", "semantic"):
        scores = pair_scores(pairs, engine, model_name)
        validation_indexes = [i for i, row in enumerate(pairs) if row["split"] == "validation"]
        selected = select_threshold([pairs[i]["label"] for i in validation_indexes], [scores[i] for i in validation_indexes])
        threshold = selected["threshold"]
        result["classification"][engine] = {"selected_threshold": threshold}
        for split in ("validation", "test"):
            indexes = [i for i, row in enumerate(pairs) if row["split"] == split]
            result["classification"][engine][split] = metrics([pairs[i]["label"] for i in indexes], [scores[i] for i in indexes], threshold)
        for row, score in zip(pairs, scores):
            details.append({"engine": engine, "id": row["id"], "split": row["split"], "category": row["category"], "label": row["label"], "score": round(score, 6), "predicted": int(score >= threshold)})
    result["retrieval"] = retrieval_scores(corpus, queries, model_name)
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "metrics.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    (output_dir / "pair_predictions.json").write_text(json.dumps(details, ensure_ascii=False, indent=2), encoding="utf-8")
    (output_dir / "REPORT.md").write_text(render_report(result), encoding="utf-8")
    return result


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="Hiệu chỉnh ngưỡng lexical và semantic")
    parser.add_argument("--pairs", type=Path, default=ROOT / "evaluation" / "pairs.jsonl")
    parser.add_argument("--corpus", type=Path, default=ROOT / "evaluation" / "retrieval_corpus.jsonl")
    parser.add_argument("--queries", type=Path, default=ROOT / "evaluation" / "retrieval_queries.jsonl")
    parser.add_argument("--output", type=Path, default=ROOT / "evaluation" / "results")
    parser.add_argument("--model", default="keepitreal/vietnamese-sbert")
    args = parser.parse_args()
    result = evaluate(args.pairs, args.corpus, args.queries, args.output, args.model)
    print(render_report(result))


if __name__ == "__main__":
    main()
