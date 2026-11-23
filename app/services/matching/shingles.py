"""Đối chiếu từ vựng theo cụm từ liên tiếp (word n-gram), thay cho cosine trên từng từ.

Vì sao: cosine unigram+bigram đo mức dùng chung từ ngữ, nên hai văn bản cùng chủ đề (hoặc chỉ cùng dùng "và", "của", "trong")
vẫn có điểm đáng kể, còn đoạn chỉ chép một phần thì bị pha loãng. Cách làm ở đây là cách của các công cụ phát hiện chép văn:
  1. Lập chỉ mục ngược từ mỗi cụm n từ liên tiếp tới các đoạn nguồn chứa nó -> tìm ứng viên nhanh, không so từng cặp.
  2. Điểm của một đoạn = tỷ lệ số từ của đoạn nằm trong cụm trùng nguyên văn với nguồn (0..1). Đây đúng là con số
     "Trùng nguyên văn X / Y từ" giao diện hiển thị, nên điểm, mức Cao/Trung bình/Thấp và phần tô đậm luôn khớp nhau.
  3. Cụm chỉ gồm từ chức năng ("của một số các"...) không được tính, để câu khuôn mẫu không tạo cảnh báo.
Không dùng mô hình học máy, không cần mạng. Đây vẫn là so khớp từ vựng, không phát hiện diễn đạt lại (việc của chế độ ngữ nghĩa).
"""
from __future__ import annotations

from collections import Counter
import re
import unicodedata

NGRAM = 4
MIN_CONTENT_WORDS = 2  # số từ nội dung tối thiểu trong một cụm để được tính
MAX_DOCUMENT_FREQUENCY = 200  # cụm xuất hiện ở quá nhiều đoạn nguồn là cụm phổ thông, bỏ qua để giữ tốc độ
CANDIDATES_PER_QUERY = 8

# Từ chức năng tiếng Việt thường gặp (đã chuẩn hóa chữ thường).
STOPWORDS = frozenset("""
và của là các một những được trong cho với có này để khi đã không từ theo như về tại hoặc cũng đó thì mà nên rất
sẽ đang bị bởi nếu vì do trên dưới ra vào lại còn đều chỉ cả nhiều ít hơn nhất rồi sau trước giữa ở ai gì nào
đây kia vậy thế sao hay mỗi mọi từng cùng đến tới qua lên xuống cần phải thể nhưng tuy nên cho biết
the of and to in is a for on that with as by at an be this are from or it
""".split())

_WORD = re.compile(r"[^\W_]+", re.UNICODE)


def tokenize(text: str) -> list[str]:
    return [word.lower() for word in _WORD.findall(unicodedata.normalize("NFC", text or ""))]


def _grams(tokens: list[str], n: int, min_content: int):
    """(vị trí, mã băm) của mọi cụm n từ có đủ từ nội dung."""
    out = []
    for i in range(len(tokens) - n + 1):
        window = tokens[i:i + n]
        if min_content and sum(word not in STOPWORDS for word in window) < min_content:
            continue
        out.append((i, hash(tuple(window))))
    return out


def covered_words(tokens: list[str], other: list[str], n: int = NGRAM, min_content: int = MIN_CONTENT_WORDS) -> set[int]:
    """Chỉ số các từ của `tokens` nằm trong một cụm n từ liên tiếp cũng có ở `other`."""
    if len(tokens) < n:  # đoạn ngắn hơn một cụm (tiêu đề, nhãn): chỉ tính khi giống hệt và đủ 3 từ
        return set(range(len(tokens))) if len(tokens) >= 3 and tokens == other else set()
    if len(other) < n:
        return set()
    theirs = {gram for _, gram in _grams(other, n, min_content)}
    mask: set[int] = set()
    for i, gram in _grams(tokens, n, min_content):
        if gram in theirs:
            mask.update(range(i, i + n))
    return mask


class ShingleIndex:
    """Chỉ mục ngược cụm từ -> đoạn nguồn. Dựng một lần cho mỗi kho, dùng lại cho mọi truy vấn."""

    def __init__(self, items: list[dict], n: int = NGRAM, min_content: int = MIN_CONTENT_WORDS):
        self.items, self.n, self.min_content = items, n, min_content
        self.tokens = [tokenize(item["text"]) for item in items]
        self.postings: dict[int, list[int]] = {}
        for index, tokens in enumerate(self.tokens):
            for gram in {gram for _, gram in _grams(tokens, n, min_content)}:
                self.postings.setdefault(gram, []).append(index)

    def search(self, text: str, top_k: int = 3, candidates: int = CANDIDATES_PER_QUERY):
        """Các đoạn nguồn trùng nhiều nhất với `text`: [(đoạn nguồn, điểm 0..1, số từ trùng)]."""
        tokens = tokenize(text)
        if len(tokens) < self.n:
            return [(item, score, words) for item, score, words in self._short(tokens, top_k)]
        votes: Counter = Counter()
        for _, gram in _grams(tokens, self.n, self.min_content):
            posting = self.postings.get(gram)
            if posting and len(posting) <= MAX_DOCUMENT_FREQUENCY:
                votes.update(posting)
        ranked = []
        for index, _ in votes.most_common(candidates):
            covered = covered_words(tokens, self.tokens[index], self.n, self.min_content)
            if covered:
                ranked.append((self.items[index], len(covered) / len(tokens), len(covered)))
        ranked.sort(key=lambda row: (-row[1], row[0]["id"]))
        return ranked[:top_k]

    def _short(self, tokens, top_k):
        """Đoạn ngắn hơn một cụm (tiêu đề, nhãn): chỉ tính khi giống hệt một đoạn nguồn và đủ 3 từ trở lên."""
        if len(tokens) < 3:
            return []
        return [(item, 1.0, len(tokens)) for item, other in zip(self.items, self.tokens) if other == tokens][:top_k]
