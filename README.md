# Hệ thống kiểm tra và cảnh báo trùng lặp nội dung tài liệu

## Web tải tài liệu và kiểm tra trùng lặp

Đã có bản web cục bộ: thêm PDF/DOCX vào kho tham chiếu, tải báo cáo để kiểm tra, xem đoạn đối chiếu và lưu lịch sử trong PostgreSQL.

Repository: https://github.com/TranPhong9324/DATN_KiemTraTrungLap

### Cài đặt nhanh

```powershell
git clone https://github.com/TranPhong9324/DATN_KiemTraTrungLap.git
cd DATN_KiemTraTrungLap
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements-web.txt
```

**Hướng dẫn đầy đủ:** [Chạy web và kết nối PostgreSQL](docs/WEB_POSTGRESQL.md).

```powershell
# Nếu chưa có môi trường, chạy python -m venv .venv trước
.\.venv\Scripts\python.exe -m pip install -r requirements-web.txt
# Tạo database/tài khoản và điền .env theo hướng dẫn trước khi chạy init
.\.venv\Scripts\python.exe -m app.db init
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Mở **http://127.0.0.1:8000**. Mặc định dùng so khớp từ vựng; ngữ nghĩa SBERT/FAISS là chế độ tùy chọn cần cài thêm bộ ML và bật cấu hình. PDF scan được nối với Tesseract OCR; cần cài Tesseract và `vie.traineddata` theo `docs/OCR_PDF.md`. Web có trang chủ công khai (đăng nhập/đăng ký) và 2 vai trò (người dùng / quản trị). Có `SERPER_API_KEY` thì hệ thống tìm thêm nguồn Internet, tải toàn văn các trang nghi vấn và tự lưu vào PostgreSQL để dùng lại (xem `docs/WEB_SOURCE_API.md`): đặt `JWT_SECRET` trong `.env`, chạy `python -m app.db init`, tạo quản trị đầu tiên bằng `python -m app.db create-user --email ... --name ... --role admin`. Chi tiết: [Xác thực và phân quyền](docs/PHAN_QUYEN.md). Bản này vẫn chỉ phục vụ thử nghiệm cục bộ.

Để chạy semantic matching, cài thêm `requirements.txt`. Không commit `.env`, mật khẩu PostgreSQL, khóa JWT hoặc API key.

## Kế hoạch triển khai và tiếp tục với AI

- [Kế hoạch triển khai G0–G9](KE_HOACH_TRIEN_KHAI.md): công việc, đầu ra, tiêu chí nghiệm thu và bước tiếp theo của từng giai đoạn.
- [Tiến độ dành cho AI](TIEN_DO_AI.md): trạng thái hiện tại, nhiệm vụ kế tiếp và bằng chứng bàn giao giữa các phiên.
- [Thiết kế lấy tài liệu nguồn bằng API miễn phí](docs/WEB_SOURCE_API.md): OpenAlex/Crossref/Unpaywall, Tavily tùy chọn, lọc Open Access và nhập vào kho `reference`.

Kế hoạch mới đã đối chiếu mã nguồn ngày 19/09/2026. Phần hướng dẫn Module 1 bên dưới là tài liệu cũ; `vector_store.py` đã có trong dự án, còn việc kiểm chứng baseline được lên lịch ở G0.

Đây là module đầu tiên của hệ thống kiểm tra & cảnh báo trùng lặp trong báo cáo đồ án,
tương ứng với mốc **"Xây chức năng tách/trích PDF-DOCX, tiền xử lý/chia đoạn"** trong kế hoạch.

## Cấu trúc

```text
Checking-and-alerting-duplicate-content-in-documents-main/
├── app/                     # Backend FastAPI
│   ├── main.py              # Khởi tạo ứng dụng và khai báo API
│   ├── config.py            # Cấu hình môi trường
│   ├── db.py, models.py      # Kết nối PostgreSQL và mô hình dữ liệu
│   ├── auth.py, security.py, permissions.py
│   ├── services/
│   │   ├── document/        # Trích xuất tài liệu, OCR và xem trước
│   │   ├── matching/        # Đối chiếu nội dung và tạo kết quả
│   │   └── web/             # Tìm kiếm và lưu nguồn Internet
│   └── document_processing/     # Công cụ xử lý độc lập, không cần chạy web
│       ├── extractor.py
│       ├── preprocessor.py
│       ├── pipeline.py           # Xử lý hàng loạt và xuất JSON
│       └── vector_store.py       # Embedding SBERT và tìm kiếm FAISS
├── frontend/
│   ├── index.html            # Trang web do FastAPI phục vụ
│   ├── static/               # JavaScript, CSS và phông chữ tại /static/
│   ├── src/                  # Mã nguồn React
│   └── public/               # Tài nguyên tĩnh của Vite
├── storage/                 # Tệp tải lên và bản xem trước của web
├── evaluation/              # Dữ liệu và chương trình đánh giá
├── tests/                   # Kiểm thử backend
├── scripts/                 # Khởi chạy web và kiểm thử PostgreSQL
├── tessdata/                 # Dữ liệu ngôn ngữ cho Tesseract
└── docs/                    # Hướng dẫn và tài liệu dự án
```

Dữ liệu cục bộ của CLI dùng `Data/`, `request/` và các tệp chỉ mục FAISS ở thư mục gốc. `.env.example` là mẫu cấu hình cho `.env`.

## Cài đặt

```bash
pip install -r requirements.txt
```

## Cách chạy

```bash
python -m app.document_processing.pipeline <thư_mục_chứa_file_pdf_docx> <đường_dẫn_json_đầu_ra>

# Ví dụ:
python -m app.document_processing.pipeline ./Data/file_xu_ly ./output/chunks.json
```

Kết quả: file `chunks.json` chứa danh sách các đoạn văn bản (chunk) đã được:
- Chuẩn hóa Unicode (NFC)
- Làm sạch nhiễu (số trang, dòng phân cách...)
- Tách câu
- Tách từ tiếng Việt (ví dụ: `"học sinh"` → `"học_sinh"`)
- Gắn `chunk_id`, `source_file`, `page` để truy vết nguồn khi phát hiện trùng lặp

Mỗi file cũng chạy độc lập để test/debug nhanh:
```bash
python -m app.document_processing.extractor file.pdf
python -m app.document_processing.preprocessor file.docx
```
