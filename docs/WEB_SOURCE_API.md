# Thiết kế lấy tài liệu nguồn từ Internet bằng API miễn phí

Tài liệu này bổ sung cho `De_cuong.md`, `TIEN_DO.md` và `KE_HOACH_TRIEN_KHAI.md`.
Mục tiêu là tìm các tài liệu công khai có khả năng chứa nội dung trùng, tải đúng bản
được phép sử dụng, đưa về pipeline PDF/DOCX hiện có, rồi lưu như `reference`.

## 1. Quyết định kiến trúc

Không dùng một Search API để tải bừa toàn bộ Internet. Chia thành hai lớp:

1. **Discovery/metadata**: tìm bài viết, DOI, tác giả, năm, URL và trạng thái Open Access.
2. **Full-text ingestion**: chỉ tải URL PDF/HTML công khai, kiểm tra kích thước/loại file,
   lưu license và URL gốc, sau đó gọi lại `extract_chunks()` và luồng thêm reference.

Luồng đề xuất:

```text
đoạn cần kiểm tra
   -> tạo query (exact phrase + từ khóa)
   -> OpenAlex search (chính) / Tavily search (tùy chọn)
   -> chuẩn hóa DOI, URL, tiêu đề
   -> OpenAlex best_oa_location hoặc Unpaywall theo DOI
   -> kiểm tra robots/content-type/license/hash
   -> tải vào storage/uploads
   -> extract_chunks -> Document(role=reference) -> checker hiện có
```

### API nên dùng

| API | Vai trò | Miễn phí | Ghi chú |
|---|---|---|---|
| OpenAlex | Tìm tài liệu học thuật, lọc `is_oa:true`, lấy `best_oa_location` | Có, không bắt buộc key; key miễn phí tăng hạn mức | Lựa chọn mặc định cho đề tài |
| Crossref | Bổ sung DOI/metadata và xác định bản ghi học thuật | Có, không cần đăng ký | Gửi `mailto` để vào polite pool |
| Unpaywall | Từ DOI tìm bản toàn văn OA | Có, cần email trong query | Chỉ dùng fallback theo DOI; endpoint search đã bị ngừng từ 18/09/2026 |
| Tavily | Tìm web rộng, báo cáo/kho luận văn/trang trường | 1.000 credits/tháng, không cần thẻ | Tùy chọn; không coi snippet là toàn văn |
| Google Custom Search JSON API | Tìm exact phrase trên web | 100 query/ngày miễn phí cho khách hàng hiện hữu | Không nhận khách hàng mới; dự kiến ngừng 01/01/2027 |

OpenAlex phù hợp nhất với phạm vi đồ án vì API cho phép truy vấn `/works` miễn phí,
không cần key ở mức cơ bản, và mỗi kết quả có `open_access` cùng
`best_oa_location`. Crossref công khai REST API, còn Unpaywall trả về URL bản OA theo DOI.
Tavily dành cho các nguồn ngoài chỉ mục học thuật; gói miễn phí hiện có 1.000 credits/tháng.

Google Custom Search vẫn có thể dùng cho prototype nếu nhóm đã có quyền truy cập hiện tại.
Tài liệu Google hiện ghi rõ API đã đóng với khách hàng mới và sẽ ngừng vào 01/01/2027;
do đó không nên xây toàn bộ hệ thống phụ thuộc vào Google. Với search engine mới, Google
chuyển sang cấu hình các domain được chọn, tối đa 50 domain; tùy chọn `Search the entire web`
chỉ còn duy trì cho engine cũ.

## 2. Đăng ký và cấu hình

### Phương án mặc định: OpenAlex + Crossref + Unpaywall

Không bắt buộc API key. Chỉ cần dùng email thật của nhóm trong `mailto`/`email` để
nhà cung cấp nhận diện client và tránh bị giới hạn vì request ẩn danh.

Thêm vào `.env` (không commit file này):

```dotenv
WEB_SOURCE_ENABLED=true
WEB_SOURCE_CONTACT_EMAIL=2212441@dlu.edu.vn
WEB_SOURCE_MAX_RESULTS=20
WEB_SOURCE_MAX_DOWNLOAD_MB=20
WEB_SOURCE_TIMEOUT_SECONDS=20
WEB_SOURCE_USER_AGENT=DLU-DuplicateChecker/0.1 (mailto:2212441@dlu.edu.vn)
OPENALEX_API_KEY=
TAVILY_API_KEY=
GOOGLE_CSE_API_KEY=
GOOGLE_CSE_ID=
```

Nếu đăng ký key OpenAlex miễn phí thì điền `OPENALEX_API_KEY`; nếu không, để trống.
Tavily để trống khi chỉ dùng kho học thuật.

## 3. API request mẫu

### 3.1 Tìm bài OA bằng OpenAlex

```bash
curl "https://api.openalex.org/works?search=vietnamese%20plagiarism%20detection&filter=open_access.is_oa:true&per-page=10&select=id,doi,title,publication_year,open_access,best_oa_location,primary_location,authorships&mailto=2212441%40dlu.edu.vn"
```

Trong code, dùng `params` thay vì tự nối chuỗi URL:

```python
import os
import requests

def search_openalex(query: str, per_page: int = 10) -> list[dict]:
    params = {
        "search": query,
        "filter": "open_access.is_oa:true",
        "per-page": min(per_page, 100),
        "select": "id,doi,title,publication_year,open_access,best_oa_location,authorships",
        "mailto": os.environ["WEB_SOURCE_CONTACT_EMAIL"],
    }
    key = os.getenv("OPENALEX_API_KEY")
    if key:
        params["api_key"] = key
    response = requests.get(
        "https://api.openalex.org/works", params=params,
        headers={"User-Agent": os.getenv("WEB_SOURCE_USER_AGENT", "DLU-DuplicateChecker")},
        timeout=20,
    )
    response.raise_for_status()
    return response.json().get("results", [])
```

URL ưu tiên lấy theo thứ tự:

```python
def oa_url(work: dict) -> str | None:
    location = work.get("best_oa_location") or {}
    return location.get("pdf_url") or location.get("landing_page_url")
```

### 3.2 Bổ sung metadata bằng Crossref

```bash
curl "https://api.crossref.org/works?query.bibliographic=Vietnamese%20plagiarism%20detection&filter=has-full-text:true&rows=10&mailto=2212441%40dlu.edu.vn"
```

Chỉ dùng Crossref để lấy metadata/DOI và link được công bố trong metadata. Không tự
vượt paywall của nhà xuất bản.

### 3.3 Tìm bản OA theo DOI bằng Unpaywall

```bash
curl "https://api.unpaywall.org/v2/10.xxxx%2Fyyyy?email=2212441%40dlu.edu.vn"
```

Lấy `best_oa_location.url_for_pdf` hoặc `url`. Nếu không có `is_oa=true`/location hợp lệ
thì bỏ qua tài liệu. Không dùng endpoint `/v2/search` vì endpoint search đã bị retired;
hãy tìm DOI bằng OpenAlex rồi gọi Unpaywall theo DOI.

### 3.4 Tavily (tùy chọn)

```python
import os
from tavily import TavilyClient

client = TavilyClient(api_key=os.environ["TAVILY_API_KEY"])
results = client.search(
    query='"kiểm tra trùng lặp văn bản" filetype:pdf site:edu.vn',
    search_depth="basic", max_results=5,
)
```

Tavily chỉ trả về kết quả discovery. Với mỗi `url`, vẫn phải tải và kiểm tra file,
license, robots, hash và giới hạn tài nguyên trước khi đưa vào kho.

### 3.5 Google Custom Search JSON API (chỉ khi đã có quyền truy cập)

Google dùng hai giá trị: API key (`key`) và Programmable Search Engine ID (`cx`).
Không gửi key xuống frontend.

```python
import os
import requests

def search_google_exact(phrase: str, start: int = 1) -> list[dict]:
    params = {
        "key": os.environ["GOOGLE_CSE_API_KEY"],
        "cx": os.environ["GOOGLE_CSE_ID"],
        "q": f'"{phrase}"',
        "num": 10,
        "start": start,
        "safe": "active",
    }
    response = requests.get(
        "https://www.googleapis.com/customsearch/v1",
        params=params, timeout=20,
    )
    if response.status_code == 429:
        raise RuntimeError("Google quota exceeded; stop retrying until quota reset")
    response.raise_for_status()
    return response.json().get("items", [])
```

Query nên lấy từ 8–20 từ đặc trưng, không gửi toàn bộ tài liệu. Có thể thêm bộ lọc:

```text
"chuỗi từ hiếm trong đoạn văn" filetype:pdf
"chuỗi từ hiếm trong đoạn văn" site:edu.vn
```

Chỉ coi kết quả Google là candidate. `items[].snippet` không phải bằng chứng toàn văn;
cần mở `items[].link`, kiểm tra quyền truy cập rồi mới tải PDF/DOCX và chạy pipeline hiện có.
Nên cache theo `sha256(query)` và đặt ngân sách, ví dụ tối đa 5 query cho mỗi tài liệu,
để mức miễn phí 100 query/ngày không bị tiêu hết bởi một báo cáo dài.

## 4. Bộ lọc an toàn trước khi nhập kho

Không đưa trực tiếp kết quả search vào FAISS/PostgreSQL. Mỗi candidate phải qua các bước:

1. Chuẩn hóa URL HTTPS; từ chối `localhost`, IP nội bộ, `file://`, redirect quá 3 lần.
2. HEAD/GET với timeout; chấp nhận `application/pdf`, DOCX hoặc HTML có thể trích xuất.
3. Giới hạn 20 MB, 200 trang, 2.000 chunk theo đúng cấu hình hiện tại.
4. Kiểm tra `robots.txt` và điều khoản nguồn; ưu tiên `is_oa=true`, DOI repository,
   institutional repository, arXiv/Zenodo/PMC.
5. Tính SHA-256 trước khi lưu; nếu đã có `reference_hash` thì bỏ qua.
6. Lưu provenance: `provider`, `query`, `retrieved_at`, `source_url`, `landing_url`,
   `doi`, `license`, `oa_status`, `content_sha256`, `download_status`.
7. Chỉ sau khi tải thành công mới gọi logic nhập reference hiện có. Với HTML, cần thêm
   bộ trích xuất HTML; MVP nên chỉ nhận PDF/DOCX để không làm thay đổi kết quả baseline.

Không tải tài liệu trả phí, không bỏ qua robots/điều khoản, không dùng snippet để kết luận
trùng lặp, và không lưu lại nội dung có bản quyền nếu license không cho phép. Hệ thống dùng
nguồn web để cảnh báo/cung cấp liên kết đối chiếu, không tuyên bố kết luận đạo văn tự động.

## 5. Thay đổi tối thiểu trong codebase

Đề xuất triển khai theo G2.2 -> G3 -> G4:

```text
app/services/web_sources.py       # clients + rate limit + normalize candidate
app/services/downloader.py        # robots, SSRF, size/type/hash, temp file
app/models.py                     # WebSource/SourceFetch hoặc cột provenance JSONB
app/main.py                       # POST /api/source-search, POST /api/source-import
frontend/                         # danh sách candidate, nút “Nhập vào kho”
tests/test_web_sources.py         # mock response, 429, redirect, duplicate, OA filter
```

API MVP nên là:

```text
POST /api/source-search
  body: {"query": "...", "provider": "openalex", "limit": 10}

POST /api/source-import
  body: {"candidate_id": "..."}
  -> tải file -> extract_chunks -> tạo Document(role="reference")
```

Không chạy đồng bộ trong request web lâu dài. Ở MVP có thể giới hạn 1 job như hiện tại;
sau đó chuyển sang job nền cho G4. Không gửi API key ra frontend; mọi request đi qua backend.

## 6. Tạo query từ đoạn văn cần kiểm tra

Với mỗi chunk hiện có (`CHUNK_CHARS=700`), tạo tối đa 3 query:

```text
Q1 exact: 20–30 từ liên tiếp, bỏ số trang và khoảng trắng thừa
Q2 key:   6–10 cụm từ hiếm + chủ đề
Q3 doi:   DOI/tên tài liệu nếu chunk chứa trích dẫn
```

URL source chỉ là ứng viên. Sau khi nhập vào kho, dùng checker hiện có để xác nhận bằng
lexical/semantic similarity. Không dùng điểm của Search API làm điểm trùng lặp.

## 7. Kế hoạch kiểm thử và đánh giá

Tạo ba nhóm dữ liệu, mỗi nhóm ít nhất 20 chunk:

- exact copy từ PDF OA;
- paraphrase tiếng Việt/Anh;
- nội dung độc lập nhưng cùng chủ đề.

Đo riêng:

- `Search recall@10`: nguồn đúng có xuất hiện trong 10 candidate không;
- `Import success rate`: candidate OA tải và trích xuất thành công;
- Precision/Recall/F1 của checker sau khi nhập nguồn;
- thời gian, số request, tỉ lệ 429/403/timeout;
- số nguồn bị loại vì paywall, license không rõ, file lỗi hoặc trùng hash.

Không chốt lại `LEXICAL_THRESHOLD=0.08` hoặc `SEMANTIC_THRESHOLD=0.68` chỉ từ dữ liệu web
mới. Cần gán nhãn và chạy lại `python -m evaluation.evaluate`, đúng với trạng thái G2 hiện tại.

## 8. Cách chạy thử bằng tay

```powershell
$env:WEB_SOURCE_CONTACT_EMAIL = "2212441@dlu.edu.vn"
.\.venv\Scripts\python.exe -m pip install requests
curl.exe "https://api.openalex.org/works?search=vietnamese%20plagiarism%20detection&filter=open_access.is_oa:true&per-page=5&mailto=2212441%40dlu.edu.vn"
```

Sau khi có `pdf_url` hợp lệ, có thể tải thủ công rồi nhập qua giao diện “Thêm tài liệu
nguồn”. Đây là cách kiểm thử an toàn trước khi mở endpoint tự động.

## 9. Nguồn tham khảo chính thức

- OpenAlex API: https://help.openalex.org/api/
- OpenAlex authentication/rate limits: https://help.openalex.org/api/authentication/
- OpenAlex locations/Open Access: https://help.openalex.org/data/locations/
- Crossref REST API: https://www.crossref.org/documentation/retrieve-metadata/rest-api/access-and-authentication/
- Unpaywall API: https://data.unpaywall.org/products/api
- Tavily pricing/API: https://www.tavily.com/pricing
