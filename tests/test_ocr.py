import pytest

from app.config import Settings
from app.services.documents import DocumentError, extract_chunks
from app.services.ocr import OCRError
from conftest import make_pdf


class FakeOCR:
    def __init__(self, outputs):
        self.outputs = iter(outputs)
        self.calls = 0

    def recognize(self, image):
        self.calls += 1
        assert image.width > 0 and image.height > 0
        value = next(self.outputs)
        if isinstance(value, Exception):
            raise value
        return value


def test_scanned_pdf_is_rendered_ocr_and_chunked(tmp_path):
    path = tmp_path / "scan.pdf"
    path.write_bytes(make_pdf([""]))
    ocr = FakeOCR(["Hệ thống nhận dạng văn bản tiếng Việt từ trang ảnh quét."])
    result = extract_chunks(path, Settings(ocr_min_text_chars=1), ocr)
    assert ocr.calls == 1
    assert result.chunks[0]["location"]["page"] == 1
    assert result.chunks[0]["location"]["extraction_method"] == "ocr"
    assert "Tesseract OCR" in result.warnings[0]


def test_mixed_pdf_only_ocrs_page_without_text(tmp_path):
    path = tmp_path / "mixed.pdf"
    path.write_bytes(make_pdf(["Text layer page", "", "Another text page"]))
    ocr = FakeOCR(["Nội dung chỉ có trong ảnh của trang thứ hai."])
    result = extract_chunks(path, Settings(ocr_min_text_chars=1), ocr)
    assert ocr.calls == 1
    assert [row["location"]["extraction_method"] for row in result.chunks] == ["text_layer", "ocr", "text_layer"]
    assert [row["location"]["page"] for row in result.chunks] == [1, 2, 3]


def test_ocr_page_limit_and_page_error_are_reported(tmp_path):
    path = tmp_path / "partial.pdf"
    path.write_bytes(make_pdf(["Kept text", "", ""]))
    ocr = FakeOCR([OCRError("ảnh quá nhiễu")])
    result = extract_chunks(path, Settings(ocr_min_text_chars=1, max_ocr_pages=1), ocr)
    assert len(result.chunks) == 1
    assert any("Trang 2 OCR lỗi" in warning for warning in result.warnings)
    # Lỗi cũng tiêu thụ một lần thử OCR; trang sau bị giới hạn.
    assert any("Trang 3" in warning for warning in result.warnings)


def test_scan_with_no_ocr_result_is_not_reported_as_zero_percent(tmp_path):
    path = tmp_path / "empty-scan.pdf"
    path.write_bytes(make_pdf([""]))
    with pytest.raises(DocumentError, match="sau trích xuất/OCR"):
        extract_chunks(path, Settings(ocr_min_text_chars=1), FakeOCR([""]))
