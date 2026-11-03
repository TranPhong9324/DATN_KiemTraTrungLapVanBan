# KẾ HOẠCH TRIỂN KHAI CHI TIẾT (v2)
### Hệ thống tự động kiểm tra và cảnh báo trùng lặp trong báo cáo đồ án

> Tài liệu này thay thế `IMPLEMENTATION_PLAN.md` trước đó — bổ sung kiến trúc dự án,
> công nghệ sử dụng, thiết kế CSDL, checklist bảo mật (OWASP), và tái cấu trúc mỗi
> giai đoạn theo khuôn **Đặc tả – Sản phẩm – Test – Tài liệu** theo đúng góp ý của nhóm.
> Số liệu hiện trạng đã được đối chiếu lại với mã nguồn và dữ liệu thật trong repo
> (`vector_store.index` hiện có 17 vector thật, sinh từ 3 tài liệu PDF/DOCX thật).

---

## 0. KIẾN TRÚC, CÔNG NGHỆ VÀ CƠ SỞ DỮ LIỆU

### 0.1. Kiến trúc tổ chức dự án

Áp dụng **kiến trúc phân lớp (Layered Architecture)** — đủ đơn giản cho quy mô đồ án,
nhưng vẫn tách rõ trách nhiệm để test độc lập và dễ thay thế từng phần:

```
┌─────────────────────────────────────────┐
│  Presentation  — Dashboard (React/Vue)   │
├─────────────────────────────────────────┤
│  API layer     — FastAPI routers/schemas │
├─────────────────────────────────────────┤
│  Business logic— extractor, preprocessor,│
│                  vector_store, winnowing,│
│                  threshold engine        │
├─────────────────────────────────────────┤
│  Data layer    — FAISS (vector) +        │
│                  CSDL quan hệ (metadata) │
└─────────────────────────────────────────┘
```

Cấu trúc thư mục đề xuất khi thêm API/CSDL (giai đoạn 6 trở đi):

```
Do_an/
├── app/
│   ├── api/            # FastAPI routers (search.py, documents.py, auth.py)
│   ├── core/           # config, security (JWT, hash mật khẩu)
│   ├── services/        # extractor.py, preprocessor.py, vector_store.py,
│   │                     # winnowing.py, duplication_pipeline.py (giữ nguyên logic đã có)
│   ├── db/              # models.py (SQLAlchemy), migrations/
│   └── main.py
├── frontend/            # Dashboard React/Vue
├── Data/                # file_xu_ly/, file_dxl/ (giữ nguyên cơ chế hiện tại)
├── request/             # JSON tạm — sẽ dần thay bằng bảng `chunks` trong CSDL
├── tests/               # pytest: test_extractor.py, test_preprocessor.py, test_api.py...
├── docs/                # API spec, ERD, báo cáo tiến độ, chương luận văn
└── requirements.txt
```

**Nguyên tắc bắt buộc:** lớp `services/` (business logic) **không được import trực tiếp
FastAPI** — router chỉ gọi hàm service và trả kết quả. Nhờ vậy có thể viết unit test cho
`vector_store.py`/`winnowing.py` mà không cần khởi động server, và có thể đổi framework
API sau này mà không phải viết lại thuật toán.

### 0.2. Công nghệ sử dụng (Technology Stack)

| Lớp | Công nghệ | Vai trò | Trạng thái |
|---|---|---|---|
| Trích xuất | `pdfplumber`, `python-docx` | Đọc PDF/DOCX | ✅ Đã dùng |
| OCR | `Tesseract` hoặc `PaddleOCR` | Đọc PDF scan | ⬜ Chưa tích hợp |
| NLP tiếng Việt | `underthesea` | Tách câu, tách từ | ✅ Đã dùng |
| Embedding | `sentence-transformers` (`keepitreal/vietnamese-sbert`, nền PhoBERT) | Vector hóa ngữ nghĩa | ✅ Đã chạy thật |
| Vector search | `faiss-cpu` (`IndexFlatIP`) | Tìm kiếm tương đồng | ✅ Đã chạy thật |
| Phát hiện sao chép trực tiếp | Winnowing tự cài, `datasketch` (MinHash/LSH) | So khớp lexical | ⬜ Chưa code |
| Backend API | `FastAPI`, `Pydantic`, `Uvicorn` | REST API | ⬜ Đã đặc tả, chưa code |
| Xác thực | `python-jose`/`PyJWT`, `passlib[bcrypt]` | Auth/Authorization | ⬜ Chưa có |
| CSDL | `SQLite` (dev) → `PostgreSQL` (demo/production) qua `SQLAlchemy` | Lưu metadata nghiệp vụ | ⬜ Chưa có |
| Frontend | `React` + `Tailwind CSS` (hoặc `Vue`) | Dashboard | ⬜ Chưa có |
| Kiểm thử | `pytest`, `coverage.py`, `httpx` (TestClient FastAPI) | Unit/integration test | ⬜ Chưa có |
| Đánh giá | `scikit-learn` (ROC, F1, confusion matrix) | Đo chất lượng mô hình | ⬜ Chưa có |
| Bảo mật | `pip-audit`/`safety` | Quét lỗ hổng dependency | ⬜ Chưa có |

### 0.3. Cơ sở dữ liệu (CSDL)

**Hiện trạng:** hệ thống **chưa có CSDL quan hệ**. Dữ liệu đang nằm rời rạc trong file
JSON (`request/pdf`, `request/word`) và file nhị phân (`vector_store.index`,
`vector_store.meta.pkl`). Đây là khoảng trống lớn nhất, cần giải quyết ngay đầu giai
đoạn 6 vì mọi tính năng cảnh báo/phân quyền/lịch sử đều phụ thuộc vào nó.

**Đề xuất schema** (SQLite khi phát triển, có thể migrate PostgreSQL không đổi code
nhờ dùng ORM):

```sql
users (
  id INTEGER PRIMARY KEY,
  username TEXT UNIQUE,
  password_hash TEXT,
  role TEXT CHECK(role IN ('admin','giangvien','sinhvien')),
  created_at DATETIME
)

documents (
  id INTEGER PRIMARY KEY,
  filename TEXT,
  file_type TEXT,               -- 'pdf' | 'docx'
  uploaded_by INTEGER REFERENCES users(id),
  status TEXT,                  -- 'queued' | 'processing' | 'completed' | 'failed'
  uploaded_at DATETIME
)

chunks (
  id INTEGER PRIMARY KEY,
  document_id INTEGER REFERENCES documents(id),
  chunk_index INTEGER,
  page INTEGER,
  raw_text TEXT,
  tokenized_text TEXT,
  vector_id INTEGER             -- vị trí tương ứng trong FAISS index
)

duplicate_reports (
  id INTEGER PRIMARY KEY,
  document_id INTEGER REFERENCES documents(id),
  chunk_id INTEGER REFERENCES chunks(id),
  matched_chunk_id INTEGER REFERENCES chunks(id),
  similarity_score REAL,
  detection_type TEXT,          -- 'direct_copy' | 'paraphrase'
  severity TEXT,                -- 'high' | 'medium' | 'low'
  created_at DATETIME
)

search_logs (
  id INTEGER PRIMARY KEY,
  user_id INTEGER REFERENCES users(id),
  query_text TEXT,
  top_k INTEGER,
  created_at DATETIME
)
```

**Phân chia vai trò rõ ràng:** FAISS tiếp tục lưu **vector** (đúng sở trường — tìm kiếm
nhanh trên không gian nhiều chiều); CSDL quan hệ lưu **metadata nghiệp vụ** (ai upload,
trạng thái xử lý, lịch sử cảnh báo, ai được xem gì). Đây là nguyên tắc "dùng đúng công cụ
cho đúng việc" — FAISS không có transaction, không hỗ trợ JOIN/phân quyền, nên không thể
thay thế CSDL. `chunks.vector_id` là khóa nối sang đúng vị trí vector trong FAISS.

### 0.4. Bảo mật (Security) & Checklist OWASP

Đối chiếu **OWASP Top 10 (2021)** với rủi ro cụ thể của hệ thống upload/xử lý tài liệu:

| OWASP Top 10 | Rủi ro cụ thể trong hệ thống | Biện pháp áp dụng |
|---|---|---|
| A01 – Broken Access Control | Sinh viên xem được báo cáo/cảnh báo của người khác qua đoán ID | Kiểm tra quyền sở hữu ở **mọi** endpoint, không dựa vào việc ẩn ID |
| A02 – Cryptographic Failures | Mật khẩu lưu dạng plaintext, JWT secret yếu | Hash bằng `passlib`/bcrypt; secret key đủ mạnh; bắt buộc HTTPS |
| A03 – Injection | SQL injection khi truy vấn CSDL | Dùng ORM (SQLAlchemy) tham số hóa, tuyệt đối không nối chuỗi SQL thủ công |
| A04 – Insecure Design | Không giới hạn kích thước/loại file upload | Giới hạn dung lượng, whitelist đuôi (`.pdf`/`.docx`), kiểm tra **magic bytes** thay vì chỉ tin đuôi file |
| A05 – Security Misconfiguration | Trả stack trace lỗi trực tiếp cho client | Custom exception handler của FastAPI, ẩn traceback ở môi trường production |
| A06 – Vulnerable Components | Thư viện cũ có lỗ hổng đã biết | `pip-audit` định kỳ, pin version cụ thể trong `requirements.txt` |
| A07 – Auth Failures | Không giới hạn số lần đăng nhập sai | Rate limiting đăng nhập, khóa tài khoản tạm thời sau N lần sai |
| A08 – Data Integrity Failures | Dùng `pickle` cho `vector_store.meta.pkl` — pickle từ nguồn không tin cậy có thể thực thi mã tùy ý | Chỉ load pickle do chính hệ thống sinh ra, **không bao giờ** nhận file pickle từ upload người dùng |
| A09 – Logging Failures | Không có audit log ai upload/xóa gì | Ghi log có timestamp, user_id, hành động; không log nội dung nhạy cảm của tài liệu |
| A10 – SSRF | Chưa áp dụng (hệ thống không tự fetch URL ngoài) | Nếu bổ sung tính năng "kiểm tra từ URL" sau này, phải validate domain đích trước khi fetch |

**Việc riêng cho luồng upload file** (thường bị bỏ sót nhất): kiểm tra magic bytes thay
vì chỉ tin đuôi file người dùng đặt; không dùng trực tiếp tên file gốc để tạo đường dẫn
lưu trên đĩa (tránh path traversal, ví dụ tên file `../../etc/passwd.docx`); giới hạn
dung lượng file tối đa ở tầng reverse proxy lẫn tầng ứng dụng.

---

## 1. ĐỐI CHIẾU HIỆN TRẠNG — MỨC HOÀN THÀNH TỪNG PHẦN

| # | Hạng mục | Hiện trạng (đã kiểm chứng) | % | Còn thiếu gì | Cần làm gì |
|---|---|---|---:|---|---|
| 1 | Trích xuất PDF (có text layer) | Hoạt động đúng, giữ số trang | 100% | Chưa có test tự động | Viết `test_extractor.py` |
| 2 | Trích xuất DOCX | Hoạt động, nhưng **toàn bộ nội dung bị gán `page = 1`** (đã xác nhận trên dữ liệu thật) | 75% | Mất khả năng truy vết đúng vị trí trong file DOCX | Ước lượng "section" theo heading, hoặc đếm theo page-break XML |
| 3 | OCR cho PDF scan | Mới chỉ phát hiện và ghi cảnh báo | 10% | Không trích được nội dung PDF scan | Tích hợp Tesseract/PaddleOCR (giai đoạn 8) |
| 4 | Tiền xử lý (chuẩn hóa, tách câu/từ, chunk) | Chạy ổn định trên dữ liệu thật | 90% | Chưa test edge case (file rỗng, ký tự lạ) | Viết unit test cho từng hàm |
| 5 | Pipeline tự động (`--watch`, move file) | Đúng như thiết kế, đã test thủ công | 90% | Chưa xử lý file đang bị khóa/ghi dở | Thêm retry/lock handling |
| 6 | Vector hóa + FAISS index | **Đã chạy thật** với `vietnamese-sbert`, sinh 17 vector từ 3 tài liệu thật, save/load đúng | 90% | Chưa benchmark tốc độ trên dữ liệu lớn | Đo throughput ở giai đoạn 8 |
| 7 | Tìm kiếm tương đồng (CLI) | Hoạt động qua `build`/`search` | 70% | Chưa có ngưỡng phân loại, chưa có API | Threshold + Search API (giai đoạn 6) |
| 8 | Ngưỡng cảnh báo & phân loại mức độ | Chưa có | 0% | Không có cơ sở định lượng để nói "trùng"/"không trùng" | Gán nhãn tập validation, dùng ROC/F1 chọn ngưỡng (6.1) |
| 9 | Phát hiện sao chép trực tiếp (Winnowing/MinHash) | Chưa code | 0% | Hệ thống mới chỉ có 1 tầng (semantic) | Xây tầng lexical ở giai đoạn 7 |
| 10 | Search API (REST) | Đã đặc tả đầy đủ (endpoint, schema) | 0% (đặc tả 100%, code 0%) | Chưa có backend thật để gọi | Code `api/routers/search.py` theo đặc tả đã có |
| 11 | CSDL | Chưa có, đang dùng JSON + pickle | 0% | Không lưu lịch sử cảnh báo, không phân quyền theo user | Tạo schema SQLite theo mục 0.3 |
| 12 | Authentication/Authorization | Chưa có | 0% | Ai cũng gọi được API nếu có | JWT + role-based access (giai đoạn 8) |
| 13 | Dashboard / Giao diện | Chưa có | 0% | Người dùng buộc phải dùng CLI | React/Vue (giai đoạn 6, tuần 3) |
| 14 | Bảo mật (OWASP) | Chưa áp dụng | 0% | Upload không giới hạn dung lượng/loại; pickle không an toàn nếu nhận từ ngoài | Áp checklist mục 0.4 (giai đoạn 8) |
| 15 | Automated tests | Chưa có test suite | 0% | Không phát hiện được lỗi khi sửa code (regression) | `pytest` cho từng module + `coverage.py` |
| 16 | Đánh giá chất lượng (Precision/Recall/F1) | Chưa có tập nhãn | 0% | Không chứng minh được hệ thống "tốt" bằng số liệu | Gán nhãn, đo metric (giai đoạn 8) |
| 17 | Tài liệu (README, API doc, luận văn) | README mô tả pipeline cơ bản, **chưa cập nhật phần vector store đã xong** | 50% | README vẫn nói vector store là "bước tương lai" dù đã code xong | Cập nhật README, sinh API doc từ FastAPI, viết chương luận văn |

---

## 2. KẾ HOẠCH CHI TIẾT THEO GIAI ĐOẠN
### (mỗi giai đoạn: Đặc tả – Sản phẩm – Test – Tài liệu)

### GIAI ĐOẠN 4 (17/08–13/09) — trạng thái: gần hoàn tất nền tảng
- **Đặc tả:** Trích xuất PDF/DOCX (`pdfplumber`, `python-docx`) → tiền xử lý tiếng Việt
  (`underthesea`, chuẩn hóa NFC, chia chunk) → vector hóa (`vietnamese-sbert`) → FAISS
  `IndexFlatIP` → tìm kiếm k-NN cơ sở.
- **Sản phẩm:** `extractor.py`, `preprocessor.py`, `vector_store.py`, `pipeline.py`
  (chế độ `--watch`), `vector_store.index` + `.meta.pkl` sinh từ dữ liệu thật.
- **Test:**
  - [ ] `test_extractor.py`: PDF có/không text layer, DOCX rỗng, DOCX có heading.
  - [ ] `test_preprocessor.py`: chuẩn hóa Unicode, ranh giới chunk, câu rỗng.
  - [ ] `test_vector_store.py`: add/search/save/load — **đã kiểm bằng vector giả, cần
        bổ sung chạy lại với model thật** để chốt số liệu thời gian encode.
- **Tài liệu:** Cập nhật `README.md` (hiện đang mô tả sai — nói vector store là việc
  "tương lai" dù đã chạy thật), ghi log thời gian trích xuất/encode trên máy thật.

### GIAI ĐOẠN 5 (14/09–20/09) — Báo cáo tiến độ 1
- **Đặc tả:** Chuẩn bị bộ dữ liệu test (10–15 file, có chủ đích tạo cặp trùng/diễn đạt
  lại), đo hiệu năng sơ bộ, demo CLI end-to-end.
- **Sản phẩm:** Bộ dữ liệu test, log đo thời gian (extract/encode/search), báo cáo tiến
  độ 1.
- **Test:** Chạy pipeline trên toàn bộ bộ dữ liệu test, đối chiếu thủ công xem các cặp
  cố tình tạo trùng có được tìm ra top-k hay không (xác nhận bằng mắt, chưa cần ngưỡng
  tự động vì threshold chưa được xây).
- **Tài liệu:** Báo cáo tiến độ 1 (mục tiêu, kiến trúc, kết quả, hạn chế, kế hoạch tiếp
  theo), câu trả lời dự kiến cho câu hỏi GVHD.

### GIAI ĐOẠN 6 (21/09–11/10, 3 tuần) — Threshold, CSDL, API, giao diện
- **Đặc tả:**
  - *Tuần 1:* Tối ưu ngưỡng similarity (ROC curve, F1-score trên tập validation có nhãn).
  - *Tuần 1–2:* Thiết kế và tạo CSDL SQLite theo schema mục 0.3.
  - *Tuần 2:* Document Processing API + **Search API** (đặc tả chi tiết ở phần API spec
    đã có: `POST /api/search`, `POST /api/documents/{id}/check`,
    `GET /api/documents/{id}/report`, `GET /api/health`).
  - *Tuần 3:* Dashboard (React/Vue) — danh sách file, bảng cảnh báo, so sánh nguồn.
- **Sản phẩm:** `threshold_config.json`, `app/db/models.py` + migration script,
  `app/api/` (routers + schemas), `frontend/`.
- **Test:**
  - [ ] Unit test hàm tính threshold (đưa vào tập nhãn giả, kiểm tra chọn đúng ngưỡng).
  - [ ] Test API bằng `pytest` + `httpx.TestClient` (FastAPI) cho từng endpoint.
  - [ ] Test CSDL: tạo/đọc/cập nhật/xóa (CRUD) cho cả 5 bảng.
  - [ ] Test tích hợp: upload → xử lý → search → lưu vào CSDL → đọc lại đúng dữ liệu.
- **Tài liệu:** API spec (OpenAPI/Swagger tự sinh từ FastAPI tại `/docs`), sơ đồ ERD của
  CSDL, hướng dẫn chạy migration.

### GIAI ĐOẠN 7 (12/10–18/10) — Báo cáo tiến độ 2: 2 tầng phát hiện
- **Đặc tả:** Tầng lexical (Shingling, MinHash, LSH, Winnowing — nền tảng MOSS) bắt sao
  chép trực tiếp; kết hợp với tầng semantic (SBERT + cosine, đã có) để phát hiện diễn đạt
  lại; rule-based combination quyết định nhãn cuối.
- **Sản phẩm:** `winnowing.py`, `duplication_pipeline.py` (điều phối 2 tầng), báo cáo
  tiến độ 2.
- **Test:**
  - [ ] Test Winnowing với case biết trước kết quả: đoạn trùng 100%, đoạn khác biệt hoàn
        toàn, đoạn diễn đạt lại (Winnowing phải KHÔNG khớp, tầng semantic phải khớp).
  - [ ] Test tầng kết hợp trả đúng nhãn `direct_copy`/`paraphrase`/`none`.
- **Tài liệu:** Báo cáo tiến độ 2, cập nhật phần lý thuyết thuật toán (mục 4.7 trong
  thuyết minh) với kết quả demo thật.

### GIAI ĐOẠN 8 (19/10–14/11, 4 tuần) — OCR, bảo mật, test, đánh giá
- **Đặc tả:**
  - *Tuần 1:* OCR (Tesseract/PaddleOCR) cho PDF scan; Authentication/Authorization
    (JWT, hash mật khẩu, phân quyền admin/giảng viên/sinh viên).
  - *Tuần 1:* Áp dụng **toàn bộ checklist OWASP** ở mục 0.4.
  - *Tuần 2:* Viết test suite đầy đủ (unit + integration).
  - *Tuần 3:* Đánh giá Precision/Recall/F1, benchmark hiệu năng.
  - *Tuần 4:* Viết bản thảo luận văn.
- **Sản phẩm:** Module OCR, module auth, bộ `tests/` hoàn chỉnh + báo cáo `coverage`,
  báo cáo benchmark, bản thảo chương 1–5.
- **Test:** Đây chính là giai đoạn **về test** — chạy toàn bộ `pytest`, đo coverage;
  test bảo mật thủ công (thử upload file giả mạo đuôi `.pdf`, thử input SQL injection
  cơ bản qua form tìm kiếm để xác nhận ORM chặn được).
- **Tài liệu:** Chương phương pháp/kiến trúc/thực nghiệm của luận văn, checklist OWASP
  đã áp dụng (chuẩn bị sẵn để trả lời câu hỏi phản biện về bảo mật).

### GIAI ĐOẠN 9 (15/11–22/11) — Nộp bản thảo
- **Đặc tả:** Đóng băng phiên bản code + dữ liệu đánh giá, nộp bản thảo, thu thập góp ý.
- **Sản phẩm:** Bản thảo hoàn chỉnh, hướng dẫn cài đặt/demo.
- **Test:** Không phát sinh test mới — đây là giai đoạn review, không sửa code.
- **Tài liệu:** Bảng theo dõi góp ý (vấn đề, mức ưu tiên, người phụ trách, trạng thái).

### GIAI ĐOẠN 10 (23/11–29/11) — Sửa theo góp ý
- **Đặc tả:** Ưu tiên sửa lỗi ảnh hưởng kết quả/bảo mật trước phần giao diện phụ.
- **Sản phẩm:** Bản sửa (release candidate), slide bảo vệ.
- **Test:** **Chạy lại toàn bộ test suite + benchmark** (regression test) sau mỗi thay
  đổi threshold/model — bắt buộc để không phá vỡ những gì đã hoạt động.
- **Tài liệu:** Báo cáo hoàn chỉnh, phụ lục API/schema, slide (bài toán – kiến trúc –
  demo – kết quả – hạn chế – hướng phát triển).

### GIAI ĐOẠN 11 (30/11–06/12) — Nộp ĐATN và bảo vệ
- **Đặc tả:** Khóa phiên bản cuối, chuẩn bị demo, luyện trình bày.
- **Sản phẩm:** ĐATN nộp chính thức, bộ demo ổn định.
- **Test:** Smoke test toàn bộ hệ thống trên máy sạch/môi trường mới trước ngày bảo vệ;
  chuẩn bị kịch bản demo dự phòng khi mất mạng hoặc model chưa cache.
- **Tài liệu:** Hồ sơ nộp cuối cùng (báo cáo, slide, mã nguồn, dữ liệu demo cùng phiên
  bản), câu trả lời chuẩn bị sẵn cho câu hỏi về ngưỡng/metric/OCR/bảo mật.

---

## 3. THỨ TỰ ƯU TIÊN NGAY SAU HIỆN TẠI

1. **P0** — Sửa hạn chế DOCX luôn gán `page = 1` (mục 1, hạng mục #2) trước khi xây API,
   vì lỗi này sẽ lan sang toàn bộ báo cáo cảnh báo sau này nếu không sửa sớm.
2. **P0** — Thiết kế & tạo CSDL (mục 0.3) + threshold (mục "Ngưỡng cảnh báo").
3. **P0** — Viết test suite tối thiểu cho 3 module đã có (`extractor`, `preprocessor`,
   `vector_store`) trước khi thêm tính năng mới, để có lưới an toàn khi refactor.
4. **P1** — Code Search API + Document API theo đặc tả đã có sẵn.
5. **P1** — Xây Dashboard tối thiểu, màn hình so sánh đoạn văn.
6. **P1** — Winnowing/MinHash cho tầng phát hiện sao chép trực tiếp.
7. **P2** — OCR, Authentication/Authorization, áp checklist OWASP đầy đủ.
8. **P2** — Đánh giá metric, benchmark, viết luận văn/slide.

---

## 4. CHECKLIST NGHIỆM THU CUỐI

- [ ] PDF có text layer và PDF scan đều có luồng xử lý rõ ràng (OCR).
- [ ] DOCX được truy vết đúng vị trí (không còn gán cứng `page = 1`).
- [ ] Mỗi chunk có ID ổn định, nguồn, trang, nội dung hiển thị được.
- [ ] Search trả về score, nguồn và đoạn đối chiếu — không chỉ top-k mơ hồ.
- [ ] Threshold được chứng minh bằng tập validation có nhãn (ROC/F1), không phải số đoán.
- [ ] Phát hiện được cả sao chép trực tiếp (Winnowing) lẫn diễn đạt lại (SBERT).
- [ ] Cảnh báo được lưu trong CSDL và xem lại được qua Search API.
- [ ] API có xác thực (JWT), phân quyền theo vai trò, validate upload, giới hạn tài nguyên.
- [ ] Dashboard hoàn thành toàn bộ workflow mà không cần chạy CLI.
- [ ] Checklist OWASP (mục 0.4) đã được rà soát và áp dụng từng mục.
- [ ] Unit/integration test và benchmark chạy lại được (regression-safe).
- [ ] README, API doc, ERD, báo cáo, phụ lục, slide khớp với phiên bản code cuối cùng.
