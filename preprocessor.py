"""
preprocessor.py
---------------
Module tiền xử lý văn bản tiếng Việt sau khi trích xuất.
Đầu ra của module này là danh sách các "chunk" (đoạn văn bản đã chuẩn hóa),
sẵn sàng để đưa vào bước vector hóa bằng PhoBERT/SBERT ở giai đoạn tiếp theo.

Các bước xử lý:
1. Chuẩn hóa Unicode (NFC) - quan trọng với tiếng Việt vì có nhiều cách
   tổ hợp dấu khác nhau (dựng sẵn vs tổ hợp), nếu không chuẩn hóa sẽ làm
   sai lệch kết quả so khớp dù 2 câu nhìn giống hệt nhau.
2. Loại bỏ ký tự thừa, khoảng trắng dư, số trang, header/footer lặp lại.
3. Tách câu (sentence segmentation).
4. Tách từ tiếng Việt (word segmentation) bằng underthesea - cần thiết vì
   tiếng Việt là ngôn ngữ đơn lập, ranh giới từ không trùng khoảng trắng
   (vd: "học sinh" là 1 từ ghép gồm 2 tiếng).
5. Gộp câu thành đoạn (chunk) theo độ dài tối đa, làm đơn vị so sánh
   cho bước tìm kiếm tương đồng/phát hiện sao chép.
"""

import re
import unicodedata
from dataclasses import dataclass, field
from typing import List
from underthesea import sent_tokenize, word_tokenize


# Các mẫu thường gặp cần loại bỏ: số trang riêng lẻ, dòng chỉ có dấu gạch/chấm
NOISE_PATTERNS = [
    re.compile(r"^\s*\d+\s*$"),          # dòng chỉ có số trang
    re.compile(r"^[\-–—_.\s]{3,}$"),      # dòng chỉ có dấu phân cách
]


@dataclass
class TextChunk:
    """Một đơn vị văn bản sau xử lý, dùng làm input cho bước embedding."""
    chunk_id: str
    source_file: str
    page: int
    raw_text: str
    normalized_text: str
    tokenized_text: str  # đã tách từ, ví dụ: "học_sinh đi_học"
    sentences: List[str] = field(default_factory=list)


def normalize_unicode(text: str) -> str:
    """Chuẩn hóa về dạng NFC - bắt buộc trước khi so sánh văn bản tiếng Việt."""
    return unicodedata.normalize("NFC", text)


def clean_text(text: str) -> str:
    """Loại bỏ nhiễu: khoảng trắng thừa, dòng rác (số trang, dấu phân cách)."""
    lines = text.splitlines()
    cleaned_lines = []
    for line in lines:
        line = line.strip()
        if not line:
            continue
        if any(pattern.match(line) for pattern in NOISE_PATTERNS):
            continue
        cleaned_lines.append(line)
    text = " ".join(cleaned_lines)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def split_sentences(text: str) -> List[str]:
    """Tách câu tiếng Việt bằng underthesea."""
    if not text:
        return []
    return [s.strip() for s in sent_tokenize(text) if s.strip()]


def tokenize_words(text: str) -> str:
    """Tách từ tiếng Việt, nối các tiếng trong 1 từ ghép bằng dấu '_' (chuẩn underthesea)."""
    if not text:
        return ""

    tokens = word_tokenize(text, format="text")
    if isinstance(tokens, list):
        return " ".join(str(token) for token in tokens)
    return str(tokens)


def chunk_sentences(sentences: List[str], max_chars: int = 500) -> List[str]:
    """
    Gộp các câu liên tiếp thành đoạn (chunk) không vượt quá max_chars.
    Chunk vừa phải giúp bước embedding giữ được ngữ nghĩa cục bộ,
    đồng thời đủ nhỏ để định vị chính xác vị trí đoạn nghi vấn đạo văn.
    """
    chunks, current, current_len = [], [], 0
    for sent in sentences:
        if current_len + len(sent) > max_chars and current:
            chunks.append(" ".join(current))
            current, current_len = [], 0
        current.append(sent)
        current_len += len(sent)
    if current:
        chunks.append(" ".join(current))
    return chunks


def process_extraction(extraction_result, chunk_max_chars: int = 500) -> List[TextChunk]:
    """
    Nhận vào ExtractionResult (từ extractor.py), trả về danh sách TextChunk
    đã sẵn sàng cho bước vector hóa.
    """
    all_chunks: List[TextChunk] = []
    chunk_counter = 0

    for page_data in extraction_result.pages:
        page_num = page_data["page"]
        raw = page_data["text"]
        if not raw or not raw.strip():
            continue

        normalized = normalize_unicode(raw)
        cleaned = clean_text(normalized)
        sentences = split_sentences(cleaned)
        chunk_texts = chunk_sentences(sentences, max_chars=chunk_max_chars)

        for chunk_text in chunk_texts:
            chunk_counter += 1
            all_chunks.append(
                TextChunk(
                    chunk_id=f"{extraction_result.filename}_p{page_num}_c{chunk_counter}",
                    source_file=extraction_result.filename,
                    page=page_num,
                    raw_text=chunk_text,
                    normalized_text=chunk_text,
                    tokenized_text=tokenize_words(chunk_text),
                    sentences=split_sentences(chunk_text),
                )
            )

    return all_chunks


if __name__ == "__main__":
    import sys
    import json
    from extractor import extract

    if len(sys.argv) != 2:
        print("Cách dùng: python preprocessor.py <đường_dẫn_file.pdf|.docx>")
        sys.exit(1)

    extraction = extract(sys.argv[1])
    chunks = process_extraction(extraction)

    output = [
        {
            "chunk_id": c.chunk_id,
            "source_file": c.source_file,
            "page": c.page,
            "tokenized_text": c.tokenized_text,
            "num_sentences": len(c.sentences),
        }
        for c in chunks
    ]
    print(json.dumps(output, ensure_ascii=False, indent=2))
    print(f"\n--> Tổng số chunk tạo ra: {len(chunks)}")
