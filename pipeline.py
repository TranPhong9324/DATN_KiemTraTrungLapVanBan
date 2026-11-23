"""
Có 2 cách dùng:

1) BATCH THỦ CÔNG (dùng thư mục bất kỳ, giữ tương thích với script cũ):
       python pipeline.py <thư_mục_chứa_file> <file_json_đầu_ra>

2) QUY TRÌNH THEO CẤU TRÚC DỰ ÁN (khuyến nghị dùng cho DATN):
   Thả file PDF/DOCX mới cần xử lý vào  Data/file_xu_ly/
   Chạy:
       python pipeline.py --watch
   Với mỗi file trong Data/file_xu_ly/, hệ thống sẽ:
     - Trích xuất + tiền xử lý -> lưu file .json kết quả vào
       request/pdf/  (nếu là PDF) hoặc request/word/ (nếu là DOCX)
     - DI CHUYỂN (không xóa) file gốc sang Data/file_dxl/ để đánh dấu "đã xử lý"
   Nếu trùng tên file ở nơi đến, hệ thống tự thêm timestamp để không ghi đè.
"""

import json
import shutil
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List

from extractor import extract
from preprocessor import process_extraction

SUPPORTED_EXTENSIONS = {".pdf", ".docx"}

# --- Cấu trúc thư mục cố định của dự án DATN ---
BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "Data"
INPUT_DIR = DATA_DIR / "file_xu_ly"      # nơi thả file MỚI cần xử lý
PROCESSED_DIR = DATA_DIR / "file_dxl"    # nơi lưu file GỐC sau khi đã trích xuất (đã xử lý)
REQUEST_DIR = BASE_DIR / "request"       # nơi lưu kết quả trích xuất (.json)
REQUEST_SUBDIR_BY_EXT = {
    ".pdf": REQUEST_DIR / "pdf",
    ".docx": REQUEST_DIR / "word",
}


def _unique_destination(dest_dir: Path, filename: str) -> Path:
    """
    Nếu đã tồn tại file trùng tên ở thư mục đích, thêm hậu tố timestamp
    để KHÔNG bao giờ ghi đè lên file cũ.
    """
    dest = dest_dir / filename
    if not dest.exists():
        return dest
    stem, suffix = Path(filename).stem, Path(filename).suffix
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    return dest_dir / f"{stem}_{ts}{suffix}"


def process_single_file(file_path: Path, chunk_max_chars: int = 500) -> Dict:
    """
    Xử lý 1 file: trích xuất + tiền xử lý, sau đó:
      1. Lưu kết quả (json) vào request/pdf hoặc request/word tương ứng.
      2. Di chuyển (KHÔNG xóa) file gốc sang Data/file_dxl để đánh dấu đã xử lý.
    """
    file_path = Path(file_path)
    suffix = file_path.suffix.lower()

    extraction = extract(str(file_path))
    chunks = process_extraction(extraction, chunk_max_chars=chunk_max_chars)

    chunk_data = [
        {
            "chunk_id": c.chunk_id,
            "source_file": c.source_file,
            "page": c.page,
            "raw_text": c.raw_text,
            "tokenized_text": c.tokenized_text,
            "num_sentences": len(c.sentences),
        }
        for c in chunks
    ]

    # 1) Lưu kết quả trích xuất vào folder request tương ứng loại file
    request_subdir = REQUEST_SUBDIR_BY_EXT.get(suffix, REQUEST_DIR)
    request_subdir.mkdir(parents=True, exist_ok=True)
    output_json_path = _unique_destination(request_subdir, file_path.stem + ".json")
    with open(output_json_path, "w", encoding="utf-8") as f:
        json.dump(chunk_data, f, ensure_ascii=False, indent=2)

    # 2) Di chuyển (không xóa) file gốc sang thư mục "đã xử lý"
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    processed_path = _unique_destination(PROCESSED_DIR, file_path.name)
    shutil.move(str(file_path), str(processed_path))

    return {
        "file": file_path.name,
        "num_chunks": len(chunks),
        "warnings": extraction.warnings,
        "output_json": str(output_json_path),
        "moved_to": str(processed_path),
    }


def watch_and_process(chunk_max_chars: int = 500) -> Dict:
    """
    Quét thư mục Data/file_xu_ly một lần, xử lý toàn bộ file PDF/DOCX đang có
    trong đó. Gọi hàm này (hoặc chạy `python pipeline.py --watch`) mỗi khi
    có file mới được thêm vào Data/file_xu_ly.
    """
    INPUT_DIR.mkdir(parents=True, exist_ok=True)
    files = [
        f for f in INPUT_DIR.iterdir()
        if f.is_file() and f.suffix.lower() in SUPPORTED_EXTENSIONS
    ]

    summary = {"total_files": len(files), "processed": [], "errors": []}
    for f in files:
        try:
            summary["processed"].append(
                process_single_file(f, chunk_max_chars=chunk_max_chars)
            )
        except Exception as e:
            summary["errors"].append({"file": f.name, "error": str(e)})

    return summary


def run_pipeline(input_dir: str, output_file: str, chunk_max_chars: int = 500) -> Dict:
    input_path = Path(input_dir)
    if not input_path.exists():
        raise FileNotFoundError(f"Không tìm thấy thư mục: {input_dir}")

    files = [
        f for f in input_path.rglob("*")
        if f.suffix.lower() in SUPPORTED_EXTENSIONS and f.is_file()
    ]

    summary = {"total_files": len(files), "processed": [], "errors": []}
    all_chunks: List[Dict] = []

    for f in files:
        try:
            extraction = extract(str(f))
            chunks = process_extraction(extraction, chunk_max_chars=chunk_max_chars)

            for c in chunks:
                all_chunks.append({
                    "chunk_id": c.chunk_id,
                    "source_file": c.source_file,
                    "page": c.page,
                    "raw_text": c.raw_text,
                    "tokenized_text": c.tokenized_text,
                    "num_sentences": len(c.sentences),
                })

            summary["processed"].append({
                "file": f.name,
                "num_chunks": len(chunks),
                "warnings": extraction.warnings,
            })

        except Exception as e:
            summary["errors"].append({"file": f.name, "error": str(e)})

    output_path = Path(output_file)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as out:
        json.dump(all_chunks, out, ensure_ascii=False, indent=2)

    summary["total_chunks"] = len(all_chunks)
    summary["output_file"] = str(output_path)
    return summary


def _print_help():
    print(
        "Cách dùng:\n"
        "  python pipeline.py --watch\n"
        "      Xử lý toàn bộ file mới trong Data/file_xu_ly/, lưu kết quả vào\n"
        "      request/pdf hoặc request/word, và chuyển file gốc sang Data/file_dxl/.\n\n"
        "  python pipeline.py <thư_mục_input> <file_json_output>\n"
        "      (Chế độ cũ) Gom kết quả trích xuất của cả thư mục vào 1 file JSON duy nhất.\n"
    )


if __name__ == "__main__":
    if len(sys.argv) == 2 and sys.argv[1] == "--watch":
        result = watch_and_process()
        print(json.dumps(result, ensure_ascii=False, indent=2))
    elif len(sys.argv) == 3:
        result = run_pipeline(sys.argv[1], sys.argv[2])
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        _print_help()
        sys.exit(1)
