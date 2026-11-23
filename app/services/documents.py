"""Bounded extraction with real PDF pages and structural DOCX locations."""
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from zipfile import BadZipFile, ZipFile
import re
import unicodedata

import docx
from docx.table import Table
import pdfplumber

from app.config import Settings


class DocumentError(ValueError):
    pass


@dataclass
class Extracted:
    chunks: list[dict]
    warnings: list[str]


def safe_filename(name: str) -> str:
    name = re.split(r"[/\\]", name)[-1]
    name = "".join(c for c in name if ord(c) >= 32).strip()
    return name[:255] or "document"


def validate_file(path: Path, suffix: str, max_bytes: int):
    if path.stat().st_size == 0:
        raise DocumentError("Tệp rỗng. Vui lòng chọn PDF hoặc DOCX có nội dung.")
    if suffix == ".pdf":
        with path.open("rb") as file:
            if not file.read(1024).lstrip().startswith(b"%PDF-"):
                raise DocumentError("Nội dung tệp không đúng định dạng PDF.")
    elif suffix == ".docx":
        try:
            with ZipFile(path) as archive:
                entries = archive.infolist()
                names = {entry.filename for entry in entries}
                if not {"[Content_Types].xml", "word/document.xml"}.issubset(names):
                    raise DocumentError("Tệp không phải tài liệu DOCX hợp lệ.")
                if len(entries) > 5000 or sum(entry.file_size for entry in entries) > max_bytes * 10:
                    raise DocumentError("DOCX vượt giới hạn kích thước giải nén.")
                if any(entry.flag_bits & 1 for entry in entries):
                    raise DocumentError("Chưa hỗ trợ DOCX được mã hóa.")
        except BadZipFile as error:
            raise DocumentError("Tệp DOCX bị hỏng.") from error
    else:
        raise DocumentError("Chỉ hỗ trợ tệp .pdf và .docx.")


def split_block(text: str, location: dict, max_chars: int) -> list[dict]:
    # Non-overlapping ranges in the original extracted block, before normalization.
    chunks = []
    start = 0
    while start < len(text):
        end = min(start + max_chars, len(text))
        if end < len(text):
            boundary = text.rfind(" ", start + max_chars // 2, end)
            if boundary > start:
                end = boundary
        raw = text[start:end]
        if raw.strip():
            chunks.append({"text": raw, "location": {**location, "start": start, "end": end}})
        start = end
    return chunks


def extract_chunks(path: Path, settings: Settings, ocr_engine=None) -> Extracted:
    chunks, warnings = [], []

    def add(text, location):
        chunks.extend(split_block(text, location, settings.chunk_chars))
        if len(chunks) > settings.max_chunks:
            raise DocumentError(f"Tài liệu vượt giới hạn {settings.max_chunks} đoạn xử lý.")

    try:
        if path.suffix == ".pdf":
            ocr_pages = 0
            with pdfplumber.open(path) as pdf:
                if len(pdf.pages) > settings.max_pages:
                    raise DocumentError(f"PDF vượt giới hạn {settings.max_pages} trang.")
                for number, page in enumerate(pdf.pages, 1):
                    text = page.extract_text() or ""
                    method = "text_layer"
                    if len(normalize(text)) < settings.ocr_min_text_chars:
                        if not settings.enable_ocr:
                            warnings.append(f"Trang {number} không đủ văn bản và OCR đang tắt.")
                            continue
                        if ocr_pages >= settings.max_ocr_pages:
                            warnings.append(f"Trang {number} bị bỏ qua vì vượt giới hạn {settings.max_ocr_pages} trang OCR.")
                            continue
                        if ocr_engine is None:
                            from app.services.ocr import TesseractOCR
                            ocr_engine = TesseractOCR(settings.tesseract_cmd, settings.ocr_language, settings.ocr_page_timeout)
                        ocr_pages += 1
                        try:
                            image = page.to_image(resolution=settings.ocr_dpi, antialias=True).original
                            text = ocr_engine.recognize(image)
                            method = "ocr"
                            if text.strip():
                                warnings.append(f"Trang {number} được đọc bằng Tesseract OCR ({settings.ocr_language}).")
                            else:
                                warnings.append(f"Trang {number} OCR không nhận dạng được văn bản.")
                        except Exception as error:
                            from app.services.ocr import OCRError, OCRUnavailable
                            if not isinstance(error, (OCRError, OCRUnavailable)):
                                raise
                            warnings.append(f"Trang {number} OCR lỗi: {error}")
                            continue
                    add(text, {"page": number, "block": number, "label": f"Trang {number}", "extraction_method": method})
        else:
            document = docx.Document(path)
            section = ""
            for number, block in enumerate(document.iter_inner_content(), 1):
                if isinstance(block, Table):
                    text = "\n".join(" | ".join(cell.text for cell in row.cells) for row in block.rows)
                    label = f"Bảng / khối {number}"
                else:
                    text = block.text
                    if block.style and block.style.name.lower().startswith("heading"):
                        section = text
                    label = f"Đoạn / khối {number}"
                add(text, {"page": None, "block": number, "section": section, "label": label})
    except DocumentError:
        raise
    except Exception as error:
        raise DocumentError("Không đọc được tài liệu. Kiểm tra tệp bị hỏng, đặt mật khẩu hoặc định dạng không được hỗ trợ.") from error
    if not chunks:
        detail = " ".join(warnings[:3])
        raise DocumentError("Không có văn bản để kiểm tra sau trích xuất/OCR." + (f" {detail}" if detail else ""))
    return Extracted(chunks, warnings)


def normalize(text: str) -> str:
    return re.sub(r"\s+", " ", unicodedata.normalize("NFC", text)).strip().lower()


def file_hash(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as file:
        for block in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()
