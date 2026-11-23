# Chạy web kiểm tra trùng lặp và kết nối PostgreSQL

Phiên bản web đầu tiên: FastAPI phục vụ cả API và giao diện HTML/CSS/JavaScript. PostgreSQL lưu metadata, đoạn văn và kết quả; tệp gốc nằm trong `storage/uploads`. Giao diện này chưa dùng React, để chạy ngay cùng Python mà không cần một máy chủ frontend riêng. Các module CLI cũ vẫn giữ nguyên.

## 1. Cài thư viện web

Mở PowerShell tại thư mục gốc dự án:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-web.txt
```

Nếu đã có `.venv`, dùng lại và chỉ chạy lệnh cài thư viện. Bản web từ vựng đã được chuẩn bị để không cần tải SBERT/PyTorch. Không bắt buộc kích hoạt venv; dùng trực tiếp đường dẫn Python như các lệnh dưới.

## 2. Tạo database và tài khoản PostgreSQL

Máy hiện có dịch vụ `postgresql-x64-18`. Không thay mật khẩu quản trị hoặc sửa database hiện có. Tạo database riêng cho ứng dụng.

### Cách A — SQL Shell / psql

Khởi động SQL Shell (psql) từ Start, hoặc chạy:

```powershell
& 'C:\Program Files\PostgreSQL\18\bin\psql.exe' -h 127.0.0.1 -p 5432 -U postgres -d postgres
```

Nhập mật khẩu tài khoản `postgres` trên máy. Trong psql, chạy lần lượt:

```sql
CREATE ROLE document_checker LOGIN;
```

```text
\password document_checker
```

Nhập mật khẩu riêng cho ứng dụng tại lời nhắc. Sau đó:

```sql
CREATE DATABASE document_checker OWNER document_checker ENCODING 'UTF8';
```

```text
\q
```

Nếu role hoặc database đã tồn tại, dùng thông tin hiện có; không chạy xóa rồi tạo lại. `CREATE DATABASE` cần chạy ngoài transaction.

### Cách B — pgAdmin

1. Kết nối server PostgreSQL đang chạy bằng tài khoản quản trị.
2. Trong **Login/Group Roles → Create**, tạo `document_checker`, đặt mật khẩu tại **Definition**, bật **Can login** tại **Privileges**. Không cần quyền Superuser.
3. Trong **Databases → Create**, tạo database `document_checker`, đặt Owner là `document_checker`.

## 3. Điền thông tin kết nối

Chỉ sao chép nếu chưa có `.env`:

```powershell
if (-not (Test-Path .env)) { Copy-Item .env.example .env }
```

Mở `.env` trong IDE và điền:

```dotenv
PGHOST=127.0.0.1
PGPORT=5432
PGDATABASE=document_checker
PGUSER=document_checker
PGPASSWORD="mat_khau_ban_vua_dat"
```

Thay giá trị mẫu bằng mật khẩu thật tại máy. Dấu nháy giúp giữ khoảng trắng hoặc dấu `#`. Không gửi mật khẩu vào chat, không commit `.env`. Nếu sử dụng các trường `PG*`, mật khẩu có `@`, `:` hoặc `/` không cần URL-encode: `app/config.py` xây URL bằng SQLAlchemy `URL.create`.

Cũng hỗ trợ `DATABASE_URL=postgresql+psycopg://...`; khi khai báo, giá trị này ưu tiên hơn `PG*`. Mật khẩu trong URL phải URL-encode ký tự đặc biệt. Chỉ dùng một cách để tránh nhầm cấu hình.

Luồng kết nối thực tế:

```text
.env → Settings.load() → SQLAlchemy Engine → psycopg → PostgreSQL
```

Tài liệu driver chính thức: [SQLAlchemy PostgreSQL / psycopg](https://docs.sqlalchemy.org/en/20/dialects/postgresql.html#module-sqlalchemy.dialects.postgresql.psycopg).

## 4. Tạo bảng và kiểm tra kết nối

```powershell
$env:PYTHONUTF8 = '1'
.\.venv\Scripts\python.exe -m app.db init
.\.venv\Scripts\python.exe -m app.db check
```

Kết quả thành công: `PostgreSQL: kết nối thành công; các bảng documents, chunks, checks đã sẵn sàng.`

`init` tạo các bảng chưa có, không xóa bảng hoặc dữ liệu. Đây là cơ chế khởi tạo schema phiên bản đầu bằng SQLAlchemy, **chưa phải migration nâng cấp schema**. Khi thay đổi model ở phiên tiếp theo, cần bổ sung Alembic trước khi nâng cấp database có dữ liệu.

| Bảng | Dữ liệu lưu |
|---|---|
| `documents` | UUID, tên tệp hiển thị, loại tệp, vai trò (`submission` / `reference` / `web`), SHA-256, tên tệp lưu nội bộ, kích thước, cảnh báo, thời gian; `owner_id` (người nộp); `source_url` (chỉ `web`, duy nhất) |
| `chunks` | UUID, khóa ngoại tài liệu, thứ tự đoạn, nội dung gốc đã trích xuất, vị trí trang hoặc khối DOCX và khoảng ký tự |
| `checks` | UUID lần kiểm tra, báo cáo truy vấn, engine, ngưỡng, tỷ lệ cảnh báo, snapshot JSON của kết quả và cấu hình |

Snapshot JSON chứa đoạn truy vấn, đoạn nguồn, vị trí hai phía và danh sách ID các đoạn trong kho dùng cho lần kiểm tra. Chưa có bảng người dùng, bảng job hoặc phân quyền.

## 5. Khởi động web

```powershell
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Hoặc chạy `scripts/start-web.ps1` nếu chính sách PowerShell trên máy cho phép.

- Giao diện: http://127.0.0.1:8000
- API docs: http://127.0.0.1:8000/docs
- Trạng thái database: http://127.0.0.1:8000/api/health

Ứng dụng vẫn mở được giao diện hướng dẫn khi chưa cấu hình PostgreSQL. Các nút upload chỉ bật khi database và bảng sẵn sàng. Sau khi đổi `.env`, dừng bằng Ctrl+C và chạy lại server. Chạy **một worker** trong bản hiện tại; không bật nhiều worker vì khóa xử lý và cache model đang nằm trong bộ nhớ một tiến trình.

## 6. Cách sử dụng

1. Trong **Kho tham chiếu**, thêm một PDF có chữ hoặc DOCX được phép sử dụng, chẳng hạn một bản sao tài liệu trong `Data/file_dxl`.
2. Chọn báo cáo cần kiểm tra ở khung bên trái. Có thể dùng lại nội dung của nguồn để thử trường hợp sao chép hoàn toàn.
3. Chọn **So khớp từ vựng**, giữ ngưỡng thử nghiệm 0.65 hoặc điều chỉnh rồi bấm **Kiểm tra báo cáo**.
4. Xem đoạn truy vấn cạnh đoạn nguồn, điểm và vị trí; tải tệp nguồn để đối chiếu.
5. Mở lại kết quả ở **Lịch sử kiểm tra**, hoặc tải JSON.

Nguồn được nhập trước khi kiểm tra. Báo cáo vừa tải không tự thêm vào nguồn. Vì hai vai trò khác nhau, kiểm tra một tệp có nội dung giống nguồn là tình huống sao chép hợp lệ và có thể cho tỷ lệ 100%; đây không phải tự khớp do hệ thống thêm chính truy vấn vào index. Nguồn trùng SHA-256 bị từ chối ngay cả khi đổi tên. Hai tài liệu khác nội dung nhưng cùng tên vẫn có ID riêng.

Kho từ các tệp `request/*.json` và `vector_store.index` cũ **chưa tự nhập vào database**. Hãy thêm tài liệu gốc qua web; web không ghi đè index/pickle cũ.

## 7. Hai phương pháp kiểm tra

### Từ vựng — mặc định

So khớp **cụm 4 từ liên tiếp** (`app/services/shingles.py`, mô hình báo cáo `word-4gram-verbatim-v2`). Kho được lập chỉ mục ngược từ mỗi cụm 4 từ tới các đoạn chứa nó (dựng một lần, dùng lại cho các lần kiểm tra cùng kho); mỗi đoạn truy vấn lấy tối đa 3 nguồn trùng nhiều nhất. **Điểm của một đoạn = tỷ lệ số từ của đoạn nằm trong cụm trùng nguyên văn với nguồn** (0..1), nên điểm, mức Cao/Trung bình/Thấp và phần tô đậm trên giao diện luôn khớp nhau. Cụm chỉ gồm từ chức năng ("của các và những…") không được tính. Ngưỡng mặc định `VERBATIM_THRESHOLD=0.30` (chọn trên validation của `evaluation/benchmark_docs.py`).

Hệ quả: hai văn bản chỉ cùng chủ đề không tạo cảnh báo; đoạn chép một phần vẫn bị phát hiện (không bị pha loãng như cosine); **diễn đạt lại không được phát hiện** ở chế độ này (việc của chế độ ngữ nghĩa).

Hai con số trong báo cáo:

- `similarity_index` (**chỉ số trùng nguyên văn**, hiển thị chính): số từ của bài nằm trong cụm trùng ≥ 4 từ / tổng số từ đủ điều kiện đối chiếu × 100. Hợp các từ trùng trên mọi nguồn nên một từ chỉ tính một lần. Mỗi nguồn có `matched_words` và `word_coverage`.
- `coverage` (giữ để tương thích): tỷ lệ ký tự của các **đoạn** có cảnh báo; thường cao hơn nhiều vì cả đoạn được tính khi chỉ một phần trùng.

Cả hai đều không phải phần trăm đạo văn. Báo cáo cũ giữ nguyên số liệu tại thời điểm tạo.

### Ngữ nghĩa SBERT + FAISS — tùy chọn

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

Đổi `.env`:

```dotenv
ENABLE_SEMANTIC=true
SEMANTIC_MODEL=keepitreal/vietnamese-sbert
```

Khởi động lại web. Luồng gọi `VectorStore` hiện có; cả nguồn và truy vấn đi qua cùng các hàm chuẩn hóa/tách từ trong `preprocessor.py`. Cache FAISS trong RAM được xây lại khi danh sách chunk nguồn thay đổi. Lần đầu có thể tải model qua mạng. Chế độ này chưa được chạy model thật trong lần triển khai web đầu tiên; cài đặt SBERT/PyTorch trên Python 3.14 cần được kiểm chứng riêng. Nếu không chạy được, dùng môi trường Python phù hợp với các thư viện ML rồi kiểm tra lại.

Web không âm thầm thay SBERT bằng từ vựng khi lỗi. Ngưỡng 0.80 của chế độ ngữ nghĩa và 0.65 của chế độ từ vựng đều chưa hiệu chỉnh. Chunking hiện theo ký tự; cần kiểm tra và xử lý giới hạn tokenizer trước khi nghiệm thu chất lượng semantic.

## 8. API chính

| Endpoint | Chức năng |
|---|---|
| `GET /api/health` | Trạng thái kết nối, hạn mức và chế độ model |
| `GET /api/stats` | Số nguồn, số chunk nguồn, số lần kiểm tra |
| `GET /api/documents?role=reference` | 100 tài liệu nguồn mới nhất (chỉ quản trị) |
| `GET /api/documents?role=web` | 100 trang Internet đã lưu mới nhất (chỉ quản trị) |
| `DELETE /api/documents/{id}` | Xóa một trang Internet đã lưu (chỉ quản trị; không xóa được tài liệu kho hay bài nộp) |
| `POST /api/references` | Upload multipart trường `file` vào kho |
| `POST /api/checks` | Upload multipart `file`, `engine`, `threshold`; trả báo cáo khi xử lý xong |
| `GET /api/checks` | 100 lần kiểm tra gần nhất |
| `GET /api/checks/{id}` | Snapshot báo cáo đã lưu |
| `GET /api/documents/{id}/file` | Tải tệp gốc |

Trích xuất và kiểm tra chạy đồng bộ trong thread xử lý request; giao diện hiển thị đang xử lý cho đến khi API trả kết quả. Chưa có hàng đợi, phần trăm tiến độ thật hoặc job tiếp tục sau restart. Lần kiểm tra thất bại được rollback, tệp mới bị xóa; lần thành công chỉ thông báo sau khi commit DB. Nếu tiến trình bị tắt đột ngột, có thể còn tệp mồ côi; chưa có tác vụ dọn tự động.

FastAPI nhận upload bằng `UploadFile` và multipart theo [tài liệu chính thức](https://fastapi.tiangolo.com/tutorial/request-files/).

## 9. Kiểm thử

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-test.txt
.\.venv\Scripts\python.exe -m pytest tests -q
```

Lệnh trên bỏ qua test tích hợp nếu chưa có `TEST_DATABASE_URL`. Để chạy toàn bộ trên PostgreSQL thật mà không cần mật khẩu dịch vụ đang có:

```powershell
.\.venv\Scripts\python.exe scripts/test_postgres.py
```

Script dùng binary PostgreSQL 18 đã cài, tạo cụm riêng trong `storage/pg-tests/<uuid>`, mật khẩu ngẫu nhiên, listen `127.0.0.1:55439` và tự dừng sau kiểm thử. Nó không thay đổi PostgreSQL dịch vụ tại cổng 5432. Nếu cổng kiểm thử bận, script dừng lỗi; không dừng tiến trình khác. Có thể đặt `PG_BIN` nếu binary ở đường dẫn khác. Dữ liệu kiểm thử được giữ trong thư mục ignored, không commit.

Trên máy khác có PostgreSQL kiểm thử riêng, đặt `TEST_DATABASE_URL` rồi chạy pytest. Fixture tạo và dọn một schema UUID dành riêng cho từng test; tài khoản cần quyền tạo schema. Không trỏ vào database sản xuất.

## 10. Giới hạn và việc tiếp theo

- Chỉ dùng tại máy cá nhân trên `127.0.0.1`; chưa có đăng nhập/phân quyền. Không mở ra Internet hoặc chia sẻ LAN trước khi bổ sung G5.
- PDF scan chưa OCR: file hoàn toàn không đọc được chữ trả lỗi; file đọc một phần hiển thị cảnh báo trang và tỷ lệ chỉ tính trên phần đã đọc.
- DOCX định vị theo mục/đoạn/bảng, không giả số trang. Header/footer, textbox và một số cấu trúc DOCX phức tạp chưa hỗ trợ.
- Chưa loại riêng mục lục, tài liệu tham khảo, câu mẫu, trích dẫn hợp lệ; cần giảng viên xem xét.
- Có hạn mức tệp/trang/chunk và xử lý từng tài liệu, chưa có timeout cưỡng chế parser hoặc xử lý nền bền vững.
- Chưa có đánh giá Precision/Recall/F1, chưa nghiệm thu semantic, OCR, migration hoặc bảo mật đa người dùng.
- Sao lưu phải gồm **cả PostgreSQL và `storage/uploads`**, không chỉ một phía.

Ưu tiên tiếp theo: kết nối database sử dụng thực tế → chạy bộ demo của nhóm → kiểm chứng SBERT → bổ sung migration, xác thực, job nền → gán nhãn/hiệu chỉnh ngưỡng theo kế hoạch.

## 11. Lỗi thường gặp

| Biểu hiện | Cách xử lý |
|---|---|
| Chưa cấu hình PostgreSQL | Điền `.env`, nhất là `PGPASSWORD`, khởi động lại web |
| Không kết nối được | Kiểm tra service, host/port, tên database, username/password bằng psql; không gửi secret vào log |
| Kết nối đúng nhưng chưa sẵn sàng | Chạy `python -m app.db init` bằng Python trong `.venv` |
| `permission denied for schema public` | Dùng database riêng có Owner là tài khoản ứng dụng; nhờ quản trị cấp quyền schema nếu dùng DB có sẵn |
| Kho tham chiếu trống | Thêm ít nhất một tài liệu nguồn qua web trước |
| Chế độ ngữ nghĩa chưa bật/lỗi | Cài bộ ML, bật cấu hình và kiểm tra model cache; từ vựng vẫn là chế độ riêng |
| Không có chữ / cần OCR | Dùng PDF có text layer hoặc chuyển OCR trước; không coi đó là 0% trùng |
| Cổng 8000 đang dùng | Chọn cổng khác ở lệnh uvicorn, ví dụ `--port 8001` |

## Khi nào một trang Internet được lưu, và cách tự chẩn đoán

Trang chỉ được tải và lưu khi kết quả tìm kiếm **có vẻ là bản gốc của một đoạn trong bài**: đoạn trích của kết quả trùng nguyên văn từ `SERPER_MIN_WORDS` (mặc định 8) từ trở lên với đoạn của bài. Bài tự viết, hoặc chỉ cùng chủ đề, thì không trang nào được lưu — đó là hành vi đúng, không phải lỗi. Lần kiểm tra sau, các trang đã lưu được đối chiếu toàn văn mà không tốn thêm lượt tìm kiếm.

Nếu bài chắc chắn có đoạn chép từ web mà vẫn không có trang nào được lưu, phần tóm tắt kết quả sẽ ghi lý do (không tải được / kho đầy / không có trang nào trùng đủ dài). Với lỗi tải, thử trực tiếp trên máy chủ:

```powershell
.\.venv\Scripts\python.exe -m app.services.web.webpages "https://trang-can-thu/"
```

Lệnh in nội dung tải được hoặc lỗi đầy đủ; lỗi bất ngờ cũng được ghi vào log của máy chủ kèm tên loại lỗi trong thông báo.
