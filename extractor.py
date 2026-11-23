"""
Module trích xuất văn bản thô từ file PDF và DOCX.

Hỗ trợ:
- PDF: dùng pdfplumber (đọc text theo từng trang, giữ thứ tự)
- DOCX: dùng python-docx (đọc theo từng paragraph, giữ heading style)

Nếu PDF là bản scan (không có text layer), hàm sẽ trả về cảnh báo
để pipeline có thể chuyển sang bước OCR (sẽ bổ sung ở giai đoạn 8 - OCR tùy chọn).
"""

from pathlib import Path
from typing import List, Dict
import pdfplumber
import docx


class ExtractionResult:
    """Đóng gói kết quả trích xuất của 1 file."""

    def __init__(self, filename: str, file_type: str):
        self.filename = filename
        self.file_type = file_type
        self.pages: List[Dict] = []   # mỗi phần tử: {"page": int, "text": str}
        self.warnings: List[str] = []

    def full_text(self) -> str:
        return "\n".join(p["text"] for p in self.pages if p["text"])

    def to_dict(self) -> Dict:
        return {
            "filename": self.filename,
            "file_type": self.file_type,
            "pages": self.pages,
            "warnings": self.warnings,
        }


def extract_pdf(file_path: str) -> ExtractionResult:
    """Trích xuất text từ PDF, giữ thông tin số trang để phục vụ trích dẫn nguồn sau này."""
    path = Path(file_path)
    result = ExtractionResult(filename=path.name, file_type="pdf")

    with pdfplumber.open(file_path) as pdf:
        for i, page in enumerate(pdf.pages, start=1):
            text = page.extract_text() or ""
            if not text.strip():
                result.warnings.append(
                    f"Trang {i}: không trích được text (có thể là ảnh scan, cần OCR)."
                )
            result.pages.append({"page": i, "text": text})

    if not result.full_text().strip():
        result.warnings.append(
            "Toàn bộ file không có text layer. Đề xuất chạy qua module OCR."
        )

    return result


def extract_docx(file_path: str) -> ExtractionResult:
    """Trích xuất text từ DOCX theo từng đoạn (paragraph), giữ style heading để hỗ trợ chia mục."""
    path = Path(file_path)
    result = ExtractionResult(filename=path.name, file_type="docx")

    document = docx.Document(file_path)
    page_text = []
    for para in document.paragraphs:
        text = para.text.strip()
        if not text:
            continue
        style = para.style.name if para.style is not None else "Normal"
        style_name = style.lower() if isinstance(style, str) else ""
        prefix = f"[{style}] " if style_name.startswith("heading") else ""
        page_text.append(prefix + text)

    # DOCX không có khái niệm "trang" rõ ràng khi đọc bằng python-docx,
    # nên gom toàn bộ vào "page" số 1 và để bước preprocessing chia đoạn.
    result.pages.append({"page": 1, "text": "\n".join(page_text)})

    if not result.full_text().strip():
        result.warnings.append("File DOCX rỗng hoặc không đọc được nội dung.")

    return result


def extract(file_path: str) -> ExtractionResult:
    """Hàm điều phối: tự nhận diện loại file và gọi hàm trích xuất tương ứng."""
    suffix = Path(file_path).suffix.lower()
    if suffix == ".pdf":
        return extract_pdf(file_path)
    elif suffix == ".docx":
        return extract_docx(file_path)
    else:
        raise ValueError(f"Định dạng file không được hỗ trợ: {suffix}")


if __name__ == "__main__":
    import sys
    import json

    if len(sys.argv) != 2:
        print("Cách dùng: python extractor.py <đường_dẫn_file.pdf|.docx>")
        sys.exit(1)

    res = extract(sys.argv[1])
    print(json.dumps(res.to_dict(), ensure_ascii=False, indent=2))
