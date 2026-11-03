# OCR cho PDF scan

## Luồng xử lý

```text
PDF
  ├─ Trang có text layer → giữ văn bản gốc
  └─ Trang không có text → dựng ảnh ở OCR_DPI
                           → Tesseract vie+eng
                           → chuẩn hóa/chia chunk
                           → lexical hoặc SBERT/FAISS
```

Mỗi chunk PDF lưu `location.extraction_method` là `text_layer` hoặc `ocr`. PDF hỗn hợp chỉ OCR trang không có chữ. Cảnh báo của tài liệu ghi rõ trang đã OCR, trang trắng, lỗi OCR và trang vượt giới hạn.

## Cài Tesseract trên Windows

Mở PowerShell **Run as Administrator**:

```powershell
choco install tesseract -y
tesseract --list-langs
```

Danh sách phải có `vie` và `eng`. Nếu `vie` chưa có, cài `vie.traineddata` từ kho chính thức `tesseract-ocr/tessdata` vào thư mục `tessdata` của Tesseract. Sau đó cấu hình đường dẫn tuyệt đối nếu Tesseract chưa nằm trong PATH:

```dotenv
ENABLE_OCR=true
TESSERACT_CMD=C:\Program Files\Tesseract-OCR\tesseract.exe
OCR_LANGUAGE=vie+eng
```

Khởi động lại web rồi xem `/api/health`. Trường `ocr.available` phải là `true`.

## Giới hạn an toàn

- `OCR_DPI=200`: đủ cho thử nghiệm, bị chặn trong khoảng 100–300 DPI.
- `MAX_OCR_PAGES=30`: giới hạn số trang OCR mỗi tệp.
- `OCR_PAGE_TIMEOUT=30`: giới hạn thời gian Tesseract trên mỗi trang.
- `OCR_MIN_TEXT_CHARS=1`: mặc định chỉ OCR trang hoàn toàn không có text layer. Có thể tăng nếu tài liệu có lớp chữ hỏng.
- `MAX_PAGES` và `MAX_CHUNKS` vẫn áp dụng sau OCR.

Nếu Tesseract hoặc `vie.traineddata` chưa sẵn sàng, trang scan không bị coi là 0% trùng lặp. Hệ thống trả lỗi có nguyên nhân; PDF hỗn hợp vẫn xử lý các trang có text và ghi lỗi cho trang OCR thất bại.
