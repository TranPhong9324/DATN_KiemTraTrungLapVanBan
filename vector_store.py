"""
vector_store.py
----------------
Xây dựng kho vector (vector store) từ các chunk đã tiền xử lý, dùng FAISS
để lưu trữ và tìm kiếm tương đồng ngữ nghĩa (semantic similarity search).

Module này hoàn thiện phần còn lại của giai đoạn 1 trong kế hoạch (17/08 - 13/09):
"lập kho vector và tìm kiếm cơ sở", nối tiếp ngay sau extractor.py + preprocessor.py.

Luồng xử lý:
    chunks (đọc từ request/pdf, request/word do pipeline.py sinh ra)
        --encode--> vector bằng Sentence-BERT tiếng Việt (nền PhoBERT)
        --lưu vào--> FAISS index (IndexFlatIP mô phỏng cosine similarity)
        --song song--> lưu metadata (chunk_id, source_file, page, raw_text)
                        để truy vết lại nội dung gốc khi tìm được kết quả tương đồng
"""

# pyright: reportMissingImports=false
# pyright: reportOptionalMemberAccess=false

import json
import pickle
import sys
from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict, List, Optional

_FAISS_IMPORT_ERROR: Optional[Exception] = None
_ST_IMPORT_ERROR: Optional[Exception] = None
_NP_IMPORT_ERROR: Optional[Exception] = None

if TYPE_CHECKING:
    import faiss
    import numpy as np
    from sentence_transformers import SentenceTransformer
else:
    try:
        import faiss
    except ModuleNotFoundError as exc:  # pragma: no cover - handled at runtime
        faiss = None
        _FAISS_IMPORT_ERROR = exc

    try:
        import numpy as np
    except ModuleNotFoundError as exc:  # pragma: no cover - handled at runtime
        np = None  # type: ignore[assignment]
        _NP_IMPORT_ERROR = exc

    try:
        from sentence_transformers import SentenceTransformer
    except ModuleNotFoundError as exc:  # pragma: no cover - handled at runtime
        SentenceTransformer = None  # type: ignore[assignment]
        _ST_IMPORT_ERROR = exc

BASE_DIR = Path(__file__).resolve().parent


def resolve_project_path(path: str | Path) -> str:
    """Resolve paths relative to the project root, not to the current working directory."""
    p = Path(path)
    if not p.is_absolute():
        p = BASE_DIR / p
    return str(p)

# Model SBERT tiếng Việt, huấn luyện trên nền PhoBERT, output vector 768 chiều.
# Model này được huấn luyện để nhận input đã TÁCH TỪ (word-segmented,
# nối bằng dấu "_") - khớp đúng với trường "tokenized_text" mà preprocessor.py
# đã sinh ra ở bước trước, nên không cần xử lý thêm gì trước khi encode.
DEFAULT_MODEL_NAME = "keepitreal/vietnamese-sbert"


class VectorStore:
    """
    Kho vector dựa trên FAISS, hỗ trợ:
      - add_chunks() / add_from_json_file() / add_from_directory(): nạp dữ liệu
      - search() / search_chunk(): tìm kiếm tương đồng ngữ nghĩa
      - save() / load(): lưu và khôi phục toàn bộ index + metadata xuống đĩa,
        tránh phải encode lại từ đầu mỗi lần khởi động hệ thống
    """

    def __init__(
        self,
        model_name: str = DEFAULT_MODEL_NAME,
        dim: Optional[int] = None,
        local_files_only: bool = False,
    ):
        self.model_name = model_name
        self.local_files_only = local_files_only
        self._model: Optional[Any] = None
        self.dim = dim
        self.index: Optional[Any] = None
        self.metadata: List[Dict] = []  # song song với thứ tự vector trong index

    # ------------------------------------------------------------------
    # Model (lazy-load)
    # ------------------------------------------------------------------
    @property
    def model(self) -> Any:
        """Chỉ tải model khi thực sự cần encode - tránh tốn thời gian/RAM
        nếu chỉ load lại index có sẵn từ đĩa để phục vụ tìm kiếm."""
        if SentenceTransformer is None:
            raise ModuleNotFoundError(
                "Thiếu dependency 'sentence-transformers'.\n"
                "Vui lòng chạy: python -m pip install -r requirements.txt"
            ) from _ST_IMPORT_ERROR

        if self._model is None:
            self._model = SentenceTransformer(
                self.model_name,
                local_files_only=self.local_files_only,
            )
            if self.dim is None:
                get_dimension = getattr(
                    self._model,
                    "get_embedding_dimension",
                    self._model.get_sentence_embedding_dimension,
                )
                self.dim = get_dimension()
        return self._model

    def encode(self, texts: List[str]) -> Any:
        """
        Encode danh sách văn bản thành ma trận vector đã chuẩn hóa L2 (đưa độ
        dài vector về 1). Đây là bước bắt buộc để dùng IndexFlatIP (tích vô
        hướng) mô phỏng đúng cosine similarity:

            cos(a, b) = (a . b) / (|a| * |b|)

        Khi |a| = |b| = 1, công thức trên rút gọn thành cos(a, b) = a . b,
        nên tích vô hướng trên vector đã chuẩn hóa CHÍNH LÀ cosine similarity -
        giúp FAISS tìm kiếm nhanh hơn so với việc tính cosine trực tiếp
        (phải chia chuẩn) cho từng cặp vector.
        """
        vectors = self.model.encode(texts, convert_to_numpy=True, show_progress_bar=False)
        vectors = np.asarray(vectors, dtype="float32")
        faiss.normalize_L2(vectors)
        return vectors

    # ------------------------------------------------------------------
    # Xây / nạp dữ liệu vào index
    # ------------------------------------------------------------------
    def _ensure_index(self):
        if faiss is None:
            raise ModuleNotFoundError(
                "Thiếu dependency 'faiss-cpu'.\n"
                "Vui lòng chạy: python -m pip install -r requirements.txt"
            ) from _FAISS_IMPORT_ERROR

        if self.index is None:
            if self.dim is None:
                _ = self.model  # ép load model để lấy số chiều vector
            self.index = faiss.IndexFlatIP(self.dim)

    def add_chunks(self, chunks: List[Dict]):
        """
        Thêm danh sách chunk (dict có 'tokenized_text', 'chunk_id',
        'source_file', 'page', 'raw_text' - đúng format do pipeline.py sinh ra)
        vào kho vector.
        """
        if not chunks:
            return
        self._ensure_index()
        texts = [c["tokenized_text"] for c in chunks]
        vectors = self.encode(texts)
        self.index.add(vectors)
        self.metadata.extend(chunks)

    def add_from_json_file(self, json_path: str):
        """Nạp trực tiếp 1 file .json (kết quả xuất ra từ pipeline.py)."""
        with open(json_path, "r", encoding="utf-8") as f:
            chunks = json.load(f)
        self.add_chunks(chunks)

    def add_from_directory(self, directory: str):
        """Nạp toàn bộ file .json trong 1 thư mục (vd: request/pdf, request/word)."""
        dir_path = Path(resolve_project_path(directory))
        if not dir_path.exists():
            return
        for path in sorted(dir_path.glob("*.json")):
            self.add_from_json_file(str(path))

    # ------------------------------------------------------------------
    # Tìm kiếm
    # ------------------------------------------------------------------
    def search(self, query_text: str, top_k: int = 5) -> List[Dict]:
        """
        Tìm top_k chunk trong kho có nội dung tương đồng ngữ nghĩa cao nhất
        với query_text. Trả về danh sách dict gồm metadata gốc + điểm
        similarity_score (từ 0 đến 1, càng gần 1 càng giống).
        """
        if self.index is None or self.index.ntotal == 0:
            return []

        query_vector = self.encode([query_text])
        k = min(top_k, self.index.ntotal)
        scores, indices = self.index.search(query_vector, k)

        results = []
        for score, idx in zip(scores[0], indices[0]):
            if idx == -1:
                continue
            item = dict(self.metadata[idx])
            item["similarity_score"] = float(score)
            results.append(item)
        return results

    def search_chunk(self, chunk: Dict, top_k: int = 5, exclude_same_file: bool = True) -> List[Dict]:
        """
        Biến thể của search() dùng để kiểm tra 1 chunk (thường thuộc bài báo
        cáo MỚI vừa nộp) có trùng với chunk nào đã có sẵn trong kho không.
        exclude_same_file=True để không so trùng với chính tài liệu chứa nó
        (tránh báo động giả một câu tự trùng với chính nó).
        """
        raw_results = self.search(chunk["tokenized_text"], top_k=top_k + 5)
        if exclude_same_file:
            raw_results = [
                r for r in raw_results if r.get("source_file") != chunk.get("source_file")
            ]
        return raw_results[:top_k]

    # ------------------------------------------------------------------
    # Lưu / khôi phục xuống đĩa
    # ------------------------------------------------------------------
    def save(self, index_path: str, metadata_path: str):
        """Lưu FAISS index + metadata xuống đĩa để tái sử dụng, không cần encode lại."""
        self._ensure_index()
        index_path = resolve_project_path(index_path)
        metadata_path = resolve_project_path(metadata_path)
        faiss.write_index(self.index, index_path)
        with open(metadata_path, "wb") as f:
            pickle.dump(
                {"metadata": self.metadata, "dim": self.dim, "model_name": self.model_name},
                f,
            )

    @classmethod
    def load(cls, index_path: str, metadata_path: str) -> "VectorStore":
        """Khôi phục kho vector đã lưu, KHÔNG cần tải lại model để encode."""
        index_path = resolve_project_path(index_path)
        metadata_path = resolve_project_path(metadata_path)
        with open(metadata_path, "rb") as f:
            data = pickle.load(f)
        store = cls(model_name=data["model_name"], dim=data["dim"])
        store.index = faiss.read_index(index_path)
        store.metadata = data["metadata"]
        return store


def build_default_store(
    request_dirs: Optional[List[str]] = None,
    index_path: str = "vector_store.index",
    metadata_path: str = "vector_store.meta.pkl",
) -> VectorStore:
    """
    Hàm tiện ích: xây kho vector từ các thư mục request/pdf, request/word
    (đúng theo cấu trúc dự án hiện tại) rồi lưu xuống đĩa.
    """
    if request_dirs is None:
        request_dirs = [
            str(BASE_DIR / "request" / "pdf"),
            str(BASE_DIR / "request" / "word"),
        ]

    store = VectorStore()
    for d in request_dirs:
        store.add_from_directory(d)
    store.save(index_path, metadata_path)
    return store


if __name__ == "__main__":
    index_path = str(BASE_DIR / "vector_store.index")
    metadata_path = str(BASE_DIR / "vector_store.meta.pkl")

    if len(sys.argv) < 2:
        print("Cách dùng:")
        print("  1) Xây kho vector từ request/pdf và request/word, lưu xuống đĩa:")
        print("       python vector_store.py build")
        print("  2) Xây kho vector rồi tìm thử ngay 1 câu truy vấn:")
        print('       python vector_store.py build "câu truy vấn thử"')
        print("  3) Chỉ tìm kiếm trên kho vector đã lưu sẵn (không xây lại):")
        print('       python vector_store.py search "câu truy vấn thử"')
        sys.exit(1)

    command = sys.argv[1]

    if command == "build":
        store = build_default_store(index_path=index_path, metadata_path=metadata_path)
        print(f"Đã lập kho vector với {store.index.ntotal} chunk. "
              f"Lưu tại {index_path} / {metadata_path}")
        if len(sys.argv) >= 3:
            query = sys.argv[2]
            for r in store.search(query, top_k=5):
                print(f"  [{r['similarity_score']:.4f}] {r['source_file']} "
                      f"(trang {r['page']}): {r['raw_text'][:80]}...")

    elif command == "search":
        if len(sys.argv) < 3:
            print("Cần truyền câu truy vấn. Ví dụ: python vector_store.py search \"...\"")
            sys.exit(1)
        store = VectorStore.load(index_path, metadata_path)
        query = sys.argv[2]
        for r in store.search(query, top_k=5):
            print(f"  [{r['similarity_score']:.4f}] {r['source_file']} "
                  f"(trang {r['page']}): {r['raw_text'][:80]}...")

    else:
        print(f"Lệnh không hợp lệ: {command}")
        sys.exit(1)
