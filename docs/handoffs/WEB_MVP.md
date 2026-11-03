# Bàn giao WEB_MVP — Web upload, đối chiếu và PostgreSQL

- Ngày: 19/09/2026.
- Trạng thái: hoàn thành phần mã MVP và kiểm thử PostgreSQL riêng; chưa kết nối database sử dụng thực tế do thiếu cấu hình của người dùng. Không đánh dấu toàn bộ G0–G6 DONE.
- Yêu cầu ưu tiên: bắt đầu xây web tải file, kiểm tra trùng lặp và giải thích cách kết nối PostgreSQL.

## Đã thực hiện

- `app/config.py`, `db.py`, `models.py`: đọc .env, SQLAlchemy/psycopg, khởi tạo ba bảng documents/chunks/checks; không tự fallback SQLite.
- `app/services/documents.py`: validate PDF/DOCX, hạn mức, SHA-256, PDF page và DOCX paragraph/table location, chunk không overlap.
- `app/services/checker.py`: baseline từ vựng và adapter semantic gọi VectorStore hiện có; snapshot kết quả, tỷ lệ đoạn được cảnh báo không đếm hai lần.
- `app/main.py`: API upload nguồn/kiểm tra, lịch sử, tải nguồn, thống kê, trạng thái cấu hình và static frontend.
- `frontend/`: giao diện tiếng Việt, chọn/kéo thả file, ngưỡng, đối chiếu hai cột, lịch sử, xuất JSON và hướng dẫn khi chưa có DB.
- `requirements-web.txt`, `requirements-test.txt`, `.env.example`, `scripts/start-web.ps1`, `scripts/test_postgres.py`, `tests/`.
- `docs/WEB_POSTGRESQL.md`, README và tiến độ được cập nhật.

## Quyết định

- Giữ backend Python và CLI cũ; web dùng service metadata mới để không giả trang DOCX. Chưa refactor CLI.
- Chọn HTML/CSS/JS cùng origin FastAPI cho MVP thay vì thêm build React ở bước đầu.
- Dùng PostgreSQL thật, không tạo dữ liệu demo giả hoặc tự lưu SQLite khi DB lỗi.
- Dùng từ vựng làm chế độ mặc định để chạy được với bộ web nhẹ; ngữ nghĩa là chế độ riêng chưa nghiệm thu model thật.
- Hai vai trò source/submission tách biệt, không tự index submission. Tệp giống source được xem là trường hợp đối chiếu cùng nội dung; source hash chống nhập lặp.
- Bản đầu xử lý request đồng bộ từng tài liệu, chưa có job nền hoặc auth. Chỉ chạy loopback một worker.

## Kiểm chứng

| Lệnh | Kết quả |
|---|---|
| `.venv/Scripts/python.exe scripts/test_postgres.py` | 16 passed trên PostgreSQL 18.3 riêng, bao gồm PDF/DOCX, lưu/đọc lại, rollback, trùng nguồn, kho trống, nhiều nguồn, Unicode và input lỗi |
| `node --check frontend/app.js` | Thành công |
| `.venv/Scripts/python.exe -m compileall -q app` | Thành công |
| `.venv/Scripts/python.exe -m app.db check` | Chưa cấu hình database sử dụng thật; .env chưa có mật khẩu |
| HTTP GET `http://127.0.0.1:8000/` | 200; server web đã khởi động cục bộ |
| HTTP GET `/api/health` | `database=not_configured`, `semantic_enabled=false`, đúng với cấu hình hiện tại |

Có cảnh báo deprecation của Starlette TestClient/httpx và một cảnh báo pytest cache do hai lượt test chồng thời gian khi xử lý vấn đề tiến trình Windows; không phải test chức năng thất bại. Lượt đầu thử khởi động cụm trong sandbox bị chặn; đã chạy lại với quyền phù hợp. Script được sửa dùng file log thay pipe khi chạy pg_ctl để tránh Windows chờ EOF từ tiến trình con.

## Chưa hoàn thành và giới hạn

- Chưa chạy browser QA, semantic model thật, OCR, đánh giá Precision/Recall/F1 hoặc hiệu chỉnh ngưỡng.
- Chưa có auth, quyền nguồn, background job, Alembic, phục hồi sau crash hay dọn tệp mồ côi.
- Index web semantic trong RAM, dựng từ DB; không nạp/ghi index/pickle cũ.
- Không kết nối hoặc sửa tài khoản/dữ liệu PostgreSQL dịch vụ chính.

## Phiên tiếp theo

1. **WEB.1:** đọc hướng dẫn, kiểm tra cấu hình .env đã được người dùng điền (không in secret). Chạy `app.db init`, `app.db check`, mở web và kiểm chứng trên database ứng dụng.
2. **WEB.2:** cài/kiểm tra môi trường ML phù hợp, chạy model thật với nguồn/truy vấn cùng tiền xử lý; xử lý giới hạn tokenizer; ghi kết quả trước khi nhận định paraphrase.
3. **WEB.3:** thêm migration Alembic, xác thực/phân quyền và job nền theo G4/G5 trước khi chia sẻ web ra ngoài máy.
4. Quay lại hoàn thiện các checklist G0–G3, đặc biệt dữ liệu gán nhãn và ngưỡng; không coi MVP là hệ thống đồ án đã nghiệm thu.
