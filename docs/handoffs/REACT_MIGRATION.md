# Bàn giao chuyển giao diện sang React — 08/11/2026

- Đã chuyển frontend sang React + Vite; bỏ app.js dùng innerHTML và sự kiện DOM thủ công.
- Tách App, API/format và các component UploadPanel, ReferencePanel, ReportPanel, HistoryPanel.
- Giữ upload/kéo thả, kho nguồn, báo cáo hai cột, bản gốc/văn bản đánh dấu, điều hướng cảnh báo hai chiều, nguồn Internet, lịch sử và xuất JSON.
- Hỗ trợ snapshot cũ chưa có document_chunks. React render text và chặn URL web ngoài HTTP/HTTPS.
- FastAPI phục vụ dist tại / và /assets; /static chỉ phục vụ frontend/public (CSS bản xem DOCX).
- Vite dev cổng 5173 proxy API/static sang FastAPI 8000, giữ Host/Origin.
- API chọn engine theo ENABLE_SEMANTIC nếu bỏ trống; ngưỡng theo engine trong Settings. Giao diện chọn phương pháp rõ ràng, không cố định semantic/0.68. Yêu cầu semantic khi chưa bật vẫn báo 503.
- Script start-web.ps1 cài frontend nếu thiếu node_modules và build trước khi chạy backend.
- Đã sửa tràn ngang mobile do vị trí phần tử hỗ trợ đọc màn hình ở bảng lịch sử.

## Kiểm chứng

- npm test: 6 passed, API giả lập; kiểm tra upload/engine, mở lịch sử, lỗi mạng, chuyển chế độ, cảnh báo và tương thích báo cáo cũ.
- npm run build: thành công.
- npm run test:e2e: 1 passed trên Microsoft Edge headless, bản build do FastAPI phục vụ ở 8002. API giả lập; kiểm tra upload, cảnh báo, xuất JSON, lịch sử, màn hình 390px, không lỗi JavaScript.
- Ảnh desktop/mobile trong frontend/test-results/ (không commit).
- .venv/Scripts/python.exe scripts/test_postgres.py: 29 passed trên PostgreSQL tách biệt. Có cảnh báo deprecation thư viện và pytest cache; không có test lỗi.
- Test semantic mới kiểm tra routing/default ngưỡng bằng bộ so khớp giả lập; chưa phải nghiệm thu mô hình thật.
- Không đổi schema, dữ liệu hoặc cấu hình .env. Không tải lại mô hình hay chạy đánh giá ML.
- CUA lỗi khởi tạo sandbox; kiểm tra trình duyệt thay bằng Playwright/Edge headless.

## Tiếp tục

Ưu tiên G2.2: thu thập và gán nhãn độc lập đoạn báo cáo thật; chia validation/test theo nguồn hoặc nhóm nội dung; phân tích false negative semantic và chạy lại evaluation. Chưa đánh dấu toàn bộ G1–G6/G8 hoàn tất.

Hướng dẫn chạy: docs/REACT_FRONTEND.md. Khi sửa React/CSS, dùng npm run dev hoặc build lại trước khi xem cổng 8000.

## Giao diện thẩm định theo mẫu (08/11/2026)

- Kết quả mặc định mở Văn bản đánh dấu: chữ serif, tô màu theo mức điểm, số nguồn màu cam bên lề.
- Danh sách gộp nguồn nội bộ và Internet, đánh số ổn định theo vị trí đoạn. Có sắp xếp theo thứ tự xuất hiện hoặc điểm.
- Bấm thẻ nguồn, số bên lề hoặc đoạn tô màu để mở hộp đối chiếu. Hộp hiển thị đoạn báo cáo và đoạn nguồn, làm đậm từ chung; hỗ trợ Đóng/Escape và điều hướng nguồn.
- Loại trừ từng kết quả hoặc chọn nhiều; xem danh sách đã loại trừ và khôi phục.
- Loại trừ lưu localStorage theo ID báo cáo, không thay đổi PostgreSQL hoặc phần trăm gốc. JSON có trường review.excluded_result_ids để giữ thao tác thẩm định. Chưa có lưu thẩm định nhiều người dùng trên server.
- Highlight dựa trên chunk đã trích xuất; Bản gốc vẫn là PDF/DOCX xem riêng. Không khẳng định giữ nguyên bố cục bản gốc trong Văn bản đánh dấu.
- Kiểm chứng: npm test 9 passed, npm run build thành công, npm run test:e2e 1 passed trên Edge headless; kiểm tra dialog, Escape, loại trừ/khôi phục, xuất JSON, desktop/mobile. API trong browser test giả lập.
- Bản FastAPI ở 8000 đã trả HTML tham chiếu assets mới, HTTP 200. Không đổi API/schema/model.
