"""Đo chất lượng đối chiếu từ vựng ở mức đoạn văn bản, có đáp án sinh sẵn (lặp lại được, seed cố định).

    python -m evaluation.benchmark_docs

Dữ liệu: các đoạn văn tiếng Việt thật lấy từ tài liệu của dự án (docs/*.md, README, De_cuong.md). Chia thành
  - nhóm A: kho tham chiếu;  - nhóm B: đoạn cùng lĩnh vực nhưng KHÔNG có trong kho (phép thử khó: dùng chung từ vựng);
  - đoạn khác lĩnh vực (hợp đồng, pháp lý).
Bài nộp tổng hợp gồm các loại: chép nguyên văn, chép một nửa, sửa nhẹ (10% từ), sửa nhiều (30% từ), đảo thứ tự câu,
và các loại đúng (không chép). Nhãn dương khi >= 50% số từ có nguồn gốc từ kho.

Giao thức giống evaluation/evaluate.py: ngưỡng chọn CHỈ trên tập validation (tối đa F1), rồi giữ nguyên khi đo test.
Giới hạn: văn bản "sửa" ở đây là xóa/thay từ ngẫu nhiên, không phải diễn đạt lại bằng ngôn ngữ tự nhiên; khả năng phát hiện
diễn đạt lại được đo riêng trên các cặp trong evaluation/pairs.jsonl. Đây là phép đo tổng hợp, không thay thế báo cáo thật.
"""
from __future__ import annotations

import argparse
import json
import random
import re
import time
from pathlib import Path

from app.services.matching.checker import cosine, features, shares_phrase
from app.services.matching.shingles import ShingleIndex, covered_words, tokenize

ROOT = Path(__file__).resolve().parent.parent
SEED = 20261120
LEGAL = [
    "Bên A đồng ý chuyển nhượng và bên B đồng ý nhận chuyển nhượng quyền sử dụng đất theo các điều khoản của hợp đồng này, trong thời hạn quy định của pháp luật hiện hành.",
    "Giá chuyển nhượng được các bên thỏa thuận và thanh toán bằng chuyển khoản theo đúng tiến độ đã ghi trong hợp đồng, bên nhận chuyển nhượng chịu trách nhiệm nộp các khoản thuế và lệ phí theo quy định.",
    "Các bên cam kết thông tin đã ghi trong hợp đồng là đúng sự thật, tự đọc lại và đồng ý toàn bộ nội dung, ký vào từng trang và điểm chỉ vào trang cuối của hợp đồng này.",
    "Trong trường hợp có tranh chấp, các bên ưu tiên giải quyết bằng thương lượng, nếu không thương lượng được thì đưa ra Tòa án nhân dân có thẩm quyền để giải quyết theo quy định của pháp luật.",
    "Hợp đồng này có hiệu lực kể từ ngày ký và được lập thành bốn bản có giá trị pháp lý như nhau, mỗi bên giữ một bản để thực hiện đúng các nghĩa vụ đã cam kết.",
    "Bên chuyển nhượng bảo đảm quyền sử dụng đất không có tranh chấp, không bị kê biên để bảo đảm thi hành án và còn trong thời hạn sử dụng đất theo giấy chứng nhận đã được cấp.",
    "Công ty đấu giá hợp danh thông báo bán đấu giá tài sản gồm quyền sử dụng đất và công trình xây dựng gắn liền với đất, khách hàng đăng ký tham gia đấu giá nộp tiền đặt trước theo quy chế.",
    "Người tham gia đấu giá phải nộp hồ sơ hợp lệ trong thời hạn thông báo, trả giá theo bước giá quy định và chấp hành nghiêm quy chế cuộc đấu giá đã được công bố công khai.",
]
CATEGORIES = ["copy_full", "copy_half", "edit_light", "edit_heavy", "shuffle"]
RETAINED = {"copy_full": 1.0, "copy_half": 0.5, "edit_light": 0.9, "edit_heavy": 0.7, "shuffle": 1.0}


def words(text):
    return re.findall(r"[^\W_]+", text)


def load_pool() -> list[str]:
    seen, pool = set(), []
    for path in sorted((ROOT / "docs").glob("*.md")) + [ROOT / "README.md", ROOT / "De_cuong.md", ROOT / "evaluation" / "README.md"]:
        if not path.exists():
            continue
        for line in path.read_text(encoding="utf-8").splitlines():
            text = " ".join(re.sub(r"[`*#>|]|^\s*[-\d.]+\s+", " ", line).split())
            key = text.lower()
            if len(words(text)) >= 20 and not re.search(r"https?:|\\|\.py\b|\.env|->", text) and sum(c.isalpha() for c in text) / len(text) > 0.7 and key not in seen:
                seen.add(key)
                pool.append(text)
    return pool


def perturb(text, rate, vocabulary, rng):
    """Xóa hoặc thay ngẫu nhiên `rate` số từ bằng từ khác trong kho từ vựng (mô phỏng sửa chữa thủ công)."""
    out = []
    for word in text.split():
        roll = rng.random()
        if roll < rate / 2:
            continue
        out.append(rng.choice(vocabulary) if roll < rate else word)
    return " ".join(out)


def build(rng):
    pool = load_pool()
    rng.shuffle(pool)
    half = len(pool) // 2
    sources, others = pool[:half], pool[half:]
    vocabulary = sorted({w.lower() for p in pool for w in words(p)})
    source_grams = set()
    for text in sources:
        tokens = tokenize(text)
        source_grams.update(tuple(tokens[i:i + 5]) for i in range(len(tokens) - 4))
    # Đoạn cùng lĩnh vực chỉ giữ nếu thật sự không chép kho (không chung cụm 5 từ nào) để nhãn âm đáng tin.
    negatives = [t for t in others if not any(tuple(tokenize(t)[i:i + 5]) in source_grams for i in range(max(0, len(tokenize(t)) - 4)))]
    refs = [{"id": f"s{i}", "text": t, "ordinal": i, "filename": "kho.docx", "location": {}} for i, t in enumerate(sources)]
    rows = []
    for i, text in enumerate(sources):
        category = CATEGORIES[i % len(CATEGORIES)]
        w = text.split()
        if category == "copy_full":
            made = text
        elif category == "copy_half":
            filler = rng.choice(negatives).split()
            made = " ".join(w[: len(w) // 2] + filler[: len(w) - len(w) // 2])
        elif category == "edit_light":
            made = perturb(text, 0.10, vocabulary, rng)
        elif category == "edit_heavy":
            made = perturb(text, 0.30, vocabulary, rng)
        else:
            sentences = re.split(r"(?<=[.;:])\s+", text)
            made = " ".join(reversed(sentences)) if len(sentences) > 1 else " ".join(w[len(w) // 2:] + w[: len(w) // 2])
        rows.append({"text": made, "category": category, "label": 1, "source": f"s{i}"})
    for text in negatives:
        rows.append({"text": text, "category": "neg_domain", "label": 0, "source": None})
    for text in LEGAL * 3:
        rows.append({"text": perturb(text, 0.0, vocabulary, rng) if False else text, "category": "neg_unrelated", "label": 0, "source": None})
    # validation / test chia theo chỉ số xen kẽ; nguồn ở mỗi nửa vẫn nằm trong cùng kho (kho dùng chung)
    for i, row in enumerate(rows):
        row["split"] = "validation" if i % 2 == 0 else "test"
        row["id"] = f"q{i}"
    return refs, rows, vocabulary


# ---- các bộ máy -------------------------------------------------------------------------------------------------------

class CosineEngine:
    def __init__(self, refs, gated):
        self.refs, self.gated = refs, gated
        self.vectors = [features(r["text"]) for r in refs]

    def score(self, text):
        vector = features(text)
        ranked = sorted(((cosine(vector, v), r) for v, r in zip(self.vectors, self.refs)), key=lambda p: -p[0])[:3]
        if self.gated:
            ranked = [(s, r) for s, r in ranked if shares_phrase(text, r["text"])]
        return (ranked[0][0], ranked[0][1]["id"]) if ranked else (0.0, None)


class NgramEngine:
    def __init__(self, refs, n, min_content):
        self.index = ShingleIndex(refs, n, min_content)

    def score(self, text):
        best = self.index.search(text, top_k=1)
        return (best[0][1], best[0][0]["id"]) if best else (0.0, None)


def prf(labels, flags):
    tp = sum(1 for y, f in zip(labels, flags) if y and f)
    fp = sum(1 for y, f in zip(labels, flags) if not y and f)
    fn = sum(1 for y, f in zip(labels, flags) if y and not f)
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return {"precision": precision, "recall": recall, "f1": f1, "tp": tp, "fp": fp, "fn": fn}


def pick_threshold(labels, scores):
    best = None
    for k in range(1, 100):
        t = k / 100
        m = prf(labels, [s >= t for s in scores])
        key = (m["f1"], m["precision"], t)
        if best is None or key > best[0]:
            best = (key, t, m)
    return best[1], best[2]


def evaluate_engine(name, engine, rows, fixed_threshold=None):
    scored = [dict(row, **dict(zip(("score", "found"), engine.score(row["text"])))) for row in rows]
    val = [r for r in scored if r["split"] == "validation"]
    test = [r for r in scored if r["split"] == "test"]
    threshold, val_metrics = (fixed_threshold, None) if fixed_threshold is not None else pick_threshold([r["label"] for r in val], [r["score"] for r in val])
    flags = [r["score"] >= threshold for r in test]
    metrics = prf([r["label"] for r in test], flags)
    by_category = {}
    for category in CATEGORIES + ["neg_domain", "neg_unrelated"]:
        group = [(r, f) for r, f in zip(test, flags) if r["category"] == category]
        hit = sum(f for _, f in group)
        by_category[category] = hit / len(group) if group else 0.0  # dương: tỷ lệ bắt được; âm: tỷ lệ báo nhầm
    correct_source = [r["found"] == r["source"] for r, f in zip(test, flags) if r["label"] and f]
    return {"engine": name, "threshold": threshold, "validation": val_metrics, "test": metrics, "by_category": by_category,
            "top1_source_accuracy": sum(correct_source) / len(correct_source) if correct_source else 0.0}


def paraphrase_check(engines_for_pairs):
    """Các cặp có nhãn tay trong evaluation/pairs.jsonl: tỷ lệ cặp được báo theo từng loại."""
    rows = [json.loads(line) for line in (ROOT / "evaluation" / "pairs.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
    out = {}
    for name, (scorer, threshold) in engines_for_pairs.items():
        counts = {}
        for row in rows:
            counts.setdefault(row["category"], []).append(scorer(row["query"], row["candidate"]) >= threshold)
        out[name] = {category: sum(v) / len(v) for category, v in counts.items()}
    return out


def headline_error(refs, rows, rng, cosine_threshold):
    """Sai số của con số tổng: ghép các đoạn thành 'tài liệu' có tỷ lệ chép biết trước, so với ước lượng của từng cách tính."""
    positives = [r for r in rows if r["label"] and r["split"] == "test"]
    negatives = [r for r in rows if not r["label"] and r["split"] == "test"]
    index = ShingleIndex(refs)
    ref_by_id = {r["id"]: r for r in refs}
    errors = {"chunk_ratio_cosine": [], "chunk_ratio_ngram": [], "word_index_ngram": []}
    cosine_engine = CosineEngine(refs, gated=True)
    for _ in range(60):
        k = rng.randint(0, 12)
        doc = rng.sample(positives, min(k, len(positives))) + rng.sample(negatives, min(20 - k, len(negatives)))
        total = sum(len(words(r["text"])) for r in doc)
        truth = sum(RETAINED[r["category"]] * len(words(r["text"])) for r in doc if r["label"]) / total
        chars = sum(len(r["text"]) for r in doc)
        by_cos = sum(len(r["text"]) for r in doc if cosine_engine.score(r["text"])[0] >= cosine_threshold) / chars
        flagged = covered_total = 0
        flagged_chars = 0
        for r in doc:
            best = index.search(r["text"], top_k=1)
            if best:
                covered_total += best[0][2]
                if best[0][1] >= 0.25:
                    flagged_chars += len(r["text"])
        errors["chunk_ratio_cosine"].append(abs(by_cos - truth))
        errors["chunk_ratio_ngram"].append(abs(flagged_chars / chars - truth))
        errors["word_index_ngram"].append(abs(covered_total / total - truth))
    return {k: sum(v) / len(v) for k, v in errors.items()}


def speed(refs, rows, rng, size=10000):
    vocabulary = sorted({w.lower() for r in refs for w in words(r["text"])})
    big = [{"id": f"b{i}", "text": perturb(rng.choice(refs)["text"], 0.5, vocabulary, rng), "ordinal": i, "filename": "x", "location": {}} for i in range(size)]
    queries = [r["text"] for r in rows[:150]]
    start = time.perf_counter(); index = ShingleIndex(big); build_time = time.perf_counter() - start
    start = time.perf_counter(); [index.search(q, top_k=3) for q in queries]; ngram_time = time.perf_counter() - start
    small = big[:1500]
    vectors = [features(r["text"]) for r in small]
    start = time.perf_counter()
    for q in queries[:30]:
        v = features(q)
        sorted(((cosine(v, x), i) for i, x in enumerate(vectors)), reverse=True)[:3]
    cosine_time = (time.perf_counter() - start) / 30 * len(queries) * (size / len(small))
    return {"corpus_chunks": size, "queries": len(queries), "ngram_build_s": build_time, "ngram_search_s": ngram_time, "cosine_search_s_estimated": cosine_time}


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--output", type=Path, default=ROOT / "evaluation" / "results" / "BENCHMARK.md")
    args = parser.parse_args()
    rng = random.Random(SEED)
    refs, rows, vocabulary = build(rng)
    results = [
        evaluate_engine("cosine cũ (0,08, không ràng buộc)", CosineEngine(refs, False), rows, fixed_threshold=0.08),
        evaluate_engine("cosine + cụm 4 từ (bản trước)", CosineEngine(refs, True), rows, fixed_threshold=0.08),
    ]
    for n in (3, 4, 5):
        for mc in (0, 1, 2):
            results.append(evaluate_engine(f"n-gram n={n}, từ nội dung>={mc}", NgramEngine(refs, n, mc), rows))
    pairs = {}
    for r in results:
        if r["engine"].startswith("n-gram"):
            n = int(r["engine"].split("n=")[1][0]); mc = int(r["engine"].split(">=")[1])
            pairs[r["engine"]] = (lambda q, c, n=n, mc=mc: len(covered_words(tokenize(q), tokenize(c), n, mc)) / max(1, len(tokenize(q))), r["threshold"])
    pairs["cosine cũ (0,08, không ràng buộc)"] = (lambda q, c: cosine(features(q), features(c)), 0.08)
    pairs["cosine + cụm 4 từ (bản trước)"] = (lambda q, c: cosine(features(q), features(c)) if shares_phrase(q, c) else 0.0, 0.08)
    paraphrase = paraphrase_check(pairs)
    best = max((r for r in results if r["engine"].startswith("n-gram")), key=lambda r: (r["test"]["f1"], r["test"]["precision"]))
    headline = headline_error(refs, rows, random.Random(SEED + 1), 0.08)
    timing = speed(refs, rows, random.Random(SEED + 2))
    data = {"seed": SEED, "references": len(refs), "rows": len(rows), "results": results, "paraphrase_pairs": paraphrase, "headline_mae": headline, "speed": timing, "best_ngram": best["engine"]}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.with_suffix(".json").write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    lines = ["# Đo đối chiếu từ vựng trên dữ liệu tổng hợp có đáp án", "", f"Kho {len(refs)} đoạn, {len(rows)} đoạn bài nộp (test: {sum(r['split'] == 'test' for r in rows)}). Ngưỡng của các bộ máy n-gram chọn trên validation.", "",
             "| Bộ máy | Ngưỡng | Precision | Recall | F1 | Báo nhầm (cùng lĩnh vực) | Báo nhầm (khác lĩnh vực) | Bắt: chép nửa | sửa 30% |", "|---|---:|---:|---:|---:|---:|---:|---:|---:|"]
    for r in results:
        t, c = r["test"], r["by_category"]
        lines.append(f"| {r['engine']} | {r['threshold']:.2f} | {t['precision']:.3f} | {t['recall']:.3f} | {t['f1']:.3f} | {c['neg_domain']:.3f} | {c['neg_unrelated']:.3f} | {c['copy_half']:.2f} | {c['edit_heavy']:.2f} |")
    lines += ["", "## Tỷ lệ cặp được báo trên evaluation/pairs.jsonl (nhãn tay)", "", "| Bộ máy | chép nguyên văn | diễn đạt lại | cùng chủ đề | khác chủ đề |", "|---|---:|---:|---:|---:|"]
    for name, v in paraphrase.items():
        lines.append(f"| {name} | {v.get('direct_copy', 0):.2f} | {v.get('paraphrase', 0):.2f} | {v.get('same_topic', 0):.2f} | {v.get('unrelated', 0):.2f} |")
    lines += ["", "## Sai số tuyệt đối trung bình của con số tổng (so với tỷ lệ chép thật)", ""] + [f"- {k}: {v:.3f}" for k, v in headline.items()]
    lines += ["", "## Tốc độ", "", f"- Kho {timing['corpus_chunks']} đoạn, {timing['queries']} truy vấn: n-gram dựng chỉ mục {timing['ngram_build_s']:.1f}s + tìm {timing['ngram_search_s']:.1f}s; cosine ước tính {timing['cosine_search_s_estimated']:.0f}s."]
    args.output.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
