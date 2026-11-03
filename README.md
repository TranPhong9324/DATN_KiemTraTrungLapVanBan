# Hệ thống kiểm tra và cảnh báo trùng lặp báo cáo đồ án

## Web tải tài liệu và kiểm tra trùng lặp

Đã có bản web cục bộ: thêm PDF/DOCX vào kho tham chiếu, tải báo cáo để kiểm tra, xem đoạn đối chiếu và lưu lịch sử trong PostgreSQL.

**Hướng dẫn đầy đủ:** [Chạy web và kết nối PostgreSQL](docs/WEB_POSTGRESQL.md).

```powershell
# Nếu chưa có môi trường, chạy python -m venv .venv trước
.\.venv\Scripts\python.exe -m pip install -r requirements-web.txt
# Tạo database/tài khoản và điền .env theo hướng dẫn trước khi chạy init
.\.venv\Scripts\python.exe -m app.db init
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Mở **http://127.0.0.1:8000**. Mặc định dùng so khớp từ vựng; ngữ nghĩa SBERT/FAISS là chế độ tùy chọn cần cài thêm bộ ML và bật cấu hình. PDF scan được nối với Tesseract OCR; cần cài Tesseract và `vie.traineddata` theo `docs/OCR_PDF.md`. Bản này chưa có đăng nhập và chỉ phục vụ thử nghiệm cục bộ.

## Kế hoạch triển khai và tiếp tục với AI

- [Kế hoạch triển khai G0–G9](KE_HOACH_TRIEN_KHAI.md): công việc, đầu ra, tiêu chí nghiệm thu và bước tiếp theo của từng giai đoạn.
- [Tiến độ dành cho AI](TIEN_DO_AI.md): trạng thái hiện tại, nhiệm vụ kế tiếp và bằng chứng bàn giao giữa các phiên.
- [Thiết kế lấy tài liệu nguồn bằng API miễn phí](docs/WEB_SOURCE_API.md): OpenAlex/Crossref/Unpaywall, Tavily tùy chọn, lọc Open Access và nhập vào kho `reference`.

Kế hoạch mới đã đối chiếu mã nguồn ngày 19/09/2026. Phần hướng dẫn Module 1 bên dưới là tài liệu cũ; `vector_store.py` đã có trong dự án, còn việc kiểm chứng baseline được lên lịch ở G0.

Đây là module đầu tiên của hệ thống kiểm tra & cảnh báo trùng lặp trong báo cáo đồ án,
tương ứng với mốc **"Xây chức năng tách/trích PDF-DOCX, tiền xử lý/chia đoạn"** trong kế hoạch.

## Cấu trúc

```
plagiarism_system/
├── extractor.py      # Trích xuất text thô từ PDF (pdfplumber) và DOCX (python-docx)
├── preprocessor.py   # Chuẩn hóa Unicode, làm sạch, tách câu, tách từ tiếng Việt, chia chunk
├── pipeline.py        # Điều phối: quét thư mục -> trích xuất -> tiền xử lý -> xuất JSON
├── requirements.txt
└── data/reports/      # (thư mục chứa file PDF/DOCX cần kiểm tra)
```

## Cài đặt

```bash
pip install -r requirements.txt
```

## Cách chạy

```bash
python pipeline.py <thư_mục_chứa_file_pdf_docx> <đường_dẫn_json_đầu_ra>

# Ví dụ:
python pipeline.py ./data/reports ./output/chunks.json
```

Kết quả: file `chunks.json` chứa danh sách các đoạn văn bản (chunk) đã được:
- Chuẩn hóa Unicode (NFC)
- Làm sạch nhiễu (số trang, dòng phân cách...)
- Tách câu
- Tách từ tiếng Việt (ví dụ: `"học sinh"` → `"học_sinh"`)
- Gắn `chunk_id`, `source_file`, `page` để truy vết nguồn khi phát hiện trùng lặp

Mỗi file cũng chạy độc lập để test/debug nhanh:
```bash
python extractor.py file.pdf
python preprocessor.py file.docx
```

## Vì sao thiết kế như vậy?

- **Giữ số trang / vị trí (`page`, `chunk_id`)**: để khi phát hiện trùng lặp, hệ thống
  chỉ đúng vị trí trong tài liệu gốc — cần thiết cho báo cáo cảnh báo ở giai đoạn sau.
- **Tách riêng `raw_text` và `tokenized_text`**: `tokenized_text` (đã tách từ) dùng cho
  các phương pháp dựa trên từ (TF-IDF, n-gram, Winnowing); `raw_text` giữ nguyên để hiển
  thị lại cho người dùng trong giao diện báo cáo.
- **Chunk theo `max_chars` (mặc định 500)**: đơn vị so sánh không quá dài (mất độ chính xác
  embedding) và không quá ngắn (mất ngữ cảnh) — tham số này bạn có thể tinh chỉnh khi
  đánh giá ở giai đoạn 8 (đánh giá chỉ số/hiệu năng).
- **OCR PDF scan/hỗn hợp**: giữ text layer và chỉ gọi Tesseract cho trang không đọc được chữ; lưu phương pháp trích xuất và lỗi theo trang.

## Bước tiếp theo (giai đoạn 14/09 – 20/09)

`chunks.json` sinh ra từ module này chính là input cho bước **vector hóa bằng PhoBERT/SBERT**
và **xây kho vector (FAISS/Qdrant)**. Mỗi chunk sẽ được encode thành 1 vector embedding,
lưu kèm `chunk_id` để truy vết ngược lại văn bản gốc khi tìm được đoạn tương đồng.

Gợi ý bước kế tiếp:
1. Load `chunks.json`
2. Dùng model PhoBERT/SBERT tiếng Việt để encode `tokenized_text` (hoặc `raw_text` nếu dùng
   model dạng SentenceTransformer đã tự tokenize) thành vector
3. Lưu vector + metadata vào FAISS index
4. Viết hàm `search(query_chunk, top_k)` trả về các chunk tương đồng nhất kèm điểm cosine similarity

Mình có thể xây tiếp phần này khi bạn sẵn sàng.
