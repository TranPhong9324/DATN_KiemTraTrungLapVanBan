"""Tesseract OCR adapter with bounded subprocess execution."""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from tempfile import TemporaryDirectory
import shutil
import subprocess


class OCRUnavailable(RuntimeError):
    pass


class OCRError(RuntimeError):
    pass


class TesseractOCR:
    def __init__(self, command="tesseract", language="vie+eng", timeout=30):
        self.command = command
        self.language = language
        self.timeout = timeout

    def executable(self) -> str:
        explicit = Path(self.command)
        resolved = str(explicit) if explicit.is_file() else shutil.which(self.command)
        if not resolved:
            raise OCRUnavailable(
                "Chưa tìm thấy Tesseract OCR. Cài Tesseract, bộ ngôn ngữ vie.traineddata, "
                "sau đó đặt TESSERACT_CMD trong .env nếu chương trình không nằm trong PATH."
            )
        return resolved

    def languages(self) -> set[str]:
        try:
            result = subprocess.run(
                [self.executable(), "--list-langs"], capture_output=True, text=True,
                encoding="utf-8", errors="replace", timeout=10, check=True,
            )
        except OCRUnavailable:
            raise
        except (subprocess.SubprocessError, OSError) as error:
            raise OCRUnavailable("Không đọc được danh sách ngôn ngữ của Tesseract.") from error
        return {line.strip() for line in result.stdout.splitlines()[1:] if line.strip()}

    def validate(self):
        installed = self.languages()
        required = {code for code in self.language.split("+") if code}
        missing = required - installed
        if missing:
            raise OCRUnavailable(
                "Tesseract thiếu dữ liệu ngôn ngữ: " + ", ".join(sorted(missing))
                + ". Cần cài vie.traineddata để OCR tiếng Việt."
            )

    def recognize(self, image) -> str:
        self.validate()
        with TemporaryDirectory(prefix="document-ocr-") as directory:
            image_path = Path(directory) / "page.png"
            image.save(image_path, format="PNG")
            try:
                result = subprocess.run(
                    [self.executable(), str(image_path), "stdout", "-l", self.language,
                     "--oem", "1", "--psm", "6"],
                    capture_output=True, text=True, encoding="utf-8", errors="replace",
                    timeout=self.timeout, check=False,
                )
            except subprocess.TimeoutExpired as error:
                raise OCRError(f"Tesseract vượt quá {self.timeout} giây cho một trang.") from error
            except OSError as error:
                raise OCRError("Không thể chạy tiến trình Tesseract.") from error
            if result.returncode:
                detail = (result.stderr or "Tesseract trả lỗi không xác định.").strip()
                raise OCRError(detail[:500])
            return result.stdout.strip()


@lru_cache(maxsize=8)
def ocr_status(command: str, language: str) -> dict:
    engine = TesseractOCR(command, language)
    try:
        engine.validate()
        return {"available": True, "detail": f"Tesseract sẵn sàng ({language}).", "languages": sorted(engine.languages())}
    except OCRUnavailable as error:
        return {"available": False, "detail": str(error), "languages": []}
