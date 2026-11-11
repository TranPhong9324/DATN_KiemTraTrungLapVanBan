# Giao diện React

Frontend dùng React + Vite, backend vẫn là FastAPI/PostgreSQL. CSS và bố cục hiện tại được giữ lại. Tham khảo cấu hình Vite: https://vite.dev/guide/.

## Chạy bản build cùng FastAPI

Tại thư mục gốc:

```powershell
cd frontend
npm ci
npm run build
cd ..
.\\.venv\\Scripts\\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Mở http://127.0.0.1:8000. FastAPI phục vụ `frontend/dist/index.html` và `/assets`. Sau mỗi lần sửa React/CSS, build lại để cổng 8000 có thay đổi. Nếu chưa build, trang chủ trả 503 kèm hướng dẫn; API vẫn hoạt động.

Có thể chạy `./scripts/start-web.ps1`: script cài dependency frontend nếu thiếu, build React rồi khởi động backend. Node.js trên máy hiện tại là 24.12.0; dependency được khóa bằng package-lock.json.

## Phát triển với cập nhật giao diện tự động

Cửa sổ 1 tại thư mục gốc:

```powershell
.\\.venv\\Scripts\\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

Cửa sổ 2:

```powershell
cd frontend
npm ci
npm run dev
```

Mở http://127.0.0.1:5173. Vite proxy `/api` và `/static` sang backend 8000, giữ Host/Origin để không bỏ qua kiểm tra cùng nguồn. Không cần bật CORS. Bản xem DOCX dùng CSS tại `frontend/public/doc-preview.css`.

## Cấu trúc

- `src/App.jsx`: trạng thái kết nối, tải tài liệu và mở lịch sử.
- `src/api.js`: fetch, lỗi API và kiểm tra tệp.
- `src/components/UploadPanel.jsx`: chọn/kéo thả tệp, chọn engine.
- `ReferencePanel.jsx`, `HistoryPanel.jsx`: kho nguồn và lịch sử.
- `ReportPanel.jsx`: bản gốc, văn bản đánh dấu, cảnh báo, nguồn Internet và xuất JSON. Hỗ trợ snapshot cũ chưa có document_chunks.
- `styles.css`, `review.css`: bố cục và responsive.

React render dữ liệu dưới dạng text, không dùng innerHTML. Nguồn Internet chỉ mở liên kết HTTP/HTTPS. Điểm Internet đối chiếu title/snippet, chưa phải toàn văn.

## Cấu hình kiểm tra

Giao diện không còn chọn phương pháp, hiển thị ngưỡng hay dòng giải thích ngưỡng trong form. Upload chỉ gửi tệp; API tự chọn engine và ngưỡng từ Settings/.env. Phần tóm tắt kết quả cũng bỏ giá trị ngưỡng. Thông tin kỹ thuật vẫn có trong JSON xuất ra để truy vết.

## Kiểm thử

```powershell
cd frontend
npm test
npm run build
npm run test:e2e
cd ..
.\\.venv\\Scripts\\python.exe scripts/test_postgres.py
```

Test React dùng API giả lập. Test trình duyệt dùng bản production được FastAPI phục vụ trên cổng 8002, dữ liệu API giả lập và Edge headless có sẵn trên Windows; không ghi vào kho thật. Có thể đổi channel trong playwright.config.js nếu dùng trình duyệt khác. Test backend dùng PostgreSQL tách biệt. Build trước khi chạy test backend vì có kiểm tra trang chủ và assets React.

## Giao diện thẩm định theo mẫu (08/11/2026)

- Kết quả mặc định mở Văn bản đánh dấu: chữ serif, tô màu theo mức điểm, số nguồn màu cam bên lề.
- Danh sách gộp nguồn nội bộ và Internet, đánh số ổn định theo vị trí đoạn. Có sắp xếp theo thứ tự xuất hiện hoặc điểm.
- Bấm thẻ nguồn, số bên lề hoặc đoạn tô màu để mở hộp đối chiếu. Hộp hiển thị đoạn báo cáo và đoạn nguồn, làm đậm từ chung; hỗ trợ Đóng/Escape và điều hướng nguồn.
- Loại trừ từng kết quả hoặc chọn nhiều; xem danh sách đã loại trừ và khôi phục.
- Loại trừ lưu localStorage theo ID báo cáo, không thay đổi PostgreSQL hoặc phần trăm gốc. JSON có trường review.excluded_result_ids để giữ thao tác thẩm định. Chưa có lưu thẩm định nhiều người dùng trên server.
- Highlight dựa trên chunk đã trích xuất; Bản gốc vẫn là PDF/DOCX xem riêng. Không khẳng định giữ nguyên bố cục bản gốc trong Văn bản đánh dấu.
- Kiểm chứng: npm test 9 passed, npm run build thành công, npm run test:e2e 1 passed trên Edge headless; kiểm tra dialog, Escape, loại trừ/khôi phục, xuất JSON, desktop/mobile. API trong browser test giả lập.
- Bản FastAPI ở 8000 đã trả HTML tham chiếu assets mới, HTTP 200. Không đổi API/schema/model.



## Khôi phục mốc “sửa lại giao diện dự án như này” (08/11/2026)

- Theo yêu cầu người dùng, quay về giao diện thẩm định ban đầu: STT cạnh đoạn, STT trên thẻ nguồn và trong hộp đối chiếu khớp nhau; giữ loại trừ/khôi phục, sắp xếp và chọn nhiều.
- Hoàn tác các thay đổi sau mốc này: một nguồn chính, tách câu, căn chỉnh cụm từ và tô inline. Backend quay lại đối chiếu theo chunk, schema 3.
- Giữ React/Vite, tích hợp FastAPI, bản xem gốc, kho tài liệu, .env và dữ liệu PostgreSQL.
- Không xóa/sửa kết quả lịch sử schema 4 đã được tạo; cần kiểm tra lại tài liệu để có kết quả theo cách cũ. Chức năng tách câu trong DOI_CHIEU_TUNG_CAU.md hiện là tài liệu lưu trữ, không còn áp dụng.
- Kiểm chứng: 29 test backend, 10 test React (có test STT đồng nhất), 1 test Edge đạt; build thành công và khởi động lại cổng 8000.


[Internet progress and resume](INTERNET_BATCHES.md): automatic search after upload, document-order batches and saved progress.
