from dataclasses import dataclass
import os
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import URL

ROOT = Path(__file__).resolve().parent.parent


@dataclass(frozen=True)
class Settings:
    database_url: str | URL | None = None
    upload_dir: Path = ROOT / "storage" / "uploads"
    max_upload_mb: int = 20
    max_pages: int = 200
    max_chunks: int = 2000
    max_reference_chunks: int = 10000
    chunk_chars: int = 700
    enable_semantic: bool = False
    semantic_model: str = "keepitreal/vietnamese-sbert"
    lexical_threshold: float = 0.08
    semantic_threshold: float = 0.68
    enable_ocr: bool = True
    tesseract_cmd: str = "tesseract"
    ocr_language: str = "vie+eng"
    ocr_dpi: int = 200
    max_ocr_pages: int = 30
    ocr_page_timeout: int = 30
    ocr_min_text_chars: int = 1
    max_alerts_per_source: int = 1000
    max_alerts_per_report: int = 1000
    serper_api_key: str | None = None
    serper_timeout: int = 20
    serper_max_results: int = 10
    serper_max_queries: int = 5
    serper_similarity_threshold: float = 0.08

    @classmethod
    def load(cls):
        load_dotenv(ROOT / ".env")
        url = os.getenv("DATABASE_URL") or None
        if not url and os.getenv("PGPASSWORD"):
            url = URL.create(
                "postgresql+psycopg", username=os.getenv("PGUSER", "document_checker"),
                password=os.environ["PGPASSWORD"], host=os.getenv("PGHOST", "127.0.0.1"),
                port=int(os.getenv("PGPORT", "5432")),
                database=os.getenv("PGDATABASE", "document_checker"),
            )
        return cls(
            database_url=url,
            upload_dir=(ROOT / os.getenv("UPLOAD_DIR", "storage/uploads")).resolve(),
            max_upload_mb=max(1, int(os.getenv("MAX_UPLOAD_MB", "20"))),
            max_pages=max(1, int(os.getenv("MAX_PAGES", "200"))),
            max_chunks=max(1, int(os.getenv("MAX_CHUNKS", "2000"))),
            max_reference_chunks=max(1, int(os.getenv("MAX_REFERENCE_CHUNKS", "10000"))),
            chunk_chars=max(100, int(os.getenv("CHUNK_CHARS", "700"))),
            enable_semantic=os.getenv("ENABLE_SEMANTIC", "false").lower() == "true",
            semantic_model=os.getenv("SEMANTIC_MODEL", "keepitreal/vietnamese-sbert"),
            lexical_threshold=float(os.getenv("LEXICAL_THRESHOLD", "0.08")),
            semantic_threshold=float(os.getenv("SEMANTIC_THRESHOLD", "0.68")),
            enable_ocr=os.getenv("ENABLE_OCR", "true").lower() == "true",
            tesseract_cmd=os.getenv("TESSERACT_CMD", "tesseract"),
            ocr_language=os.getenv("OCR_LANGUAGE", "vie+eng"),
            ocr_dpi=min(300, max(100, int(os.getenv("OCR_DPI", "200")))),
            max_ocr_pages=max(1, int(os.getenv("MAX_OCR_PAGES", "30"))),
            ocr_page_timeout=max(5, int(os.getenv("OCR_PAGE_TIMEOUT", "30"))),
            ocr_min_text_chars=max(1, int(os.getenv("OCR_MIN_TEXT_CHARS", "1"))),
            max_alerts_per_source=max(1, min(1000, int(os.getenv("MAX_ALERTS_PER_SOURCE", "1000")))),
            max_alerts_per_report=max(1, min(1000, int(os.getenv("MAX_ALERTS_PER_REPORT", "1000")))),
            serper_api_key=os.getenv("SERPER_API_KEY") or None,
            serper_timeout=max(5, min(60, int(os.getenv("SERPER_TIMEOUT_SECONDS", "20")))),
            serper_max_results=max(1, min(10, int(os.getenv("SERPER_MAX_RESULTS", "10")))),
            serper_max_queries=max(1, min(20, int(os.getenv("SERPER_MAX_QUERIES", "5")))),
            serper_similarity_threshold=max(0.0, min(1.0, float(os.getenv("SERPER_SIMILARITY_THRESHOLD", "0.08")))),
        )
