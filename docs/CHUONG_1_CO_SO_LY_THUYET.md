# CHƯƠNG 1. CƠ SỞ LÝ THUYẾT

Chương này trình bày các khái niệm, công nghệ và kỹ thuật làm cơ sở khoa học cho việc xây dựng hệ thống kiểm tra và cảnh báo trùng lặp nội dung trong báo cáo đồ án. Nội dung tập trung vào xử lý tài liệu PDF/DOCX, tiền xử lý tiếng Việt, các phương pháp phát hiện trùng lặp từ vựng và ngữ nghĩa, tìm kiếm vector, công nghệ ứng dụng web và cơ sở đánh giá hiệu năng của hệ thống.

## 1.1. Trùng lặp và đạo văn trong tài liệu khoa học

### 1.1.1. Khái niệm trùng lặp và đạo văn

Trùng lặp văn bản là tình trạng hai hoặc nhiều đoạn văn có nội dung giống nhau hoặc tương đồng với mức độ nhất định. Trong lĩnh vực kiểm tra tài liệu học thuật, trùng lặp có thể xuất hiện do sao chép trực tiếp, sao chép có thay đổi một phần, diễn đạt lại ý của nguồn hoặc viết theo cấu trúc, nội dung nền của nhiều tài liệu cùng chủ đề.

Đạo văn là hành vi sử dụng ý tưởng, lập luận, câu chữ hoặc dữ liệu của người khác mà không ghi rõ nguồn hoặc không có sự cho phép phù hợp. Đạo văn có thể xảy ra chủ ý hoặc vô ý, tuy nhiên cả hai trường hợp đều có thể vi phạm quy tắc học thuật. Không phải mọi trường hợp trùng lặp đều được kết luận là đạo văn. Ví dụ, một số câu khái niệm, tên thuật ngữ, công thức, ghi chú pháp lý hoặc những câu mẫu bắt buộc có thể xuất hiện giống nhau trong nhiều tài liệu nhưng không nhất thiết phản ánh hành vi sao chép. Do đó, kết quả của hệ thống chỉ mang tính chất “cảnh báo tương đồng” và cần người dùng đối chiếu nội dung, bối cảnh và nguồn trích dẫn để đưa ra kết luận cuối cùng.

Trong đề tài này, nội dung trùng lặp được coi là một cấp độ tương đồng giữa hai đoạn văn. Hệ thống thực hiện ba nhiệm vụ chính:

- Xác định các đoạn văn trong báo cáo được kiểm tra có nội dung tương đồng với tài liệu trong kho tham chiếu;
- Phân biệt mức tương đồng từ vựng và tương đồng ngữ nghĩa;
- Trích xuất, hiển thị đoạn trích và vị trí đối chiếu để hỗ trợ người kiểm định xem xét.

### 1.1.2. Các hình thức trùng lặp văn bản

Các hình thức trùng lặp thường gặp có thể được phân loại như sau:

- **Sao chép nguyên văn:** Người viết sử dụng gần như toàn bộ hoặc một phần lớn câu chữ của tài liệu gốc mà không thay đổi.
- **Sao chép có chỉnh sửa:** Nội dung gốc được thay đổi một số từ, bổ sung từ đồng nghĩa, thêm câu, xóa bớt hoặc đảo thứ tự một vài cụm từ.
- **Diễn đạt lại:** Ý nghĩa được giữ lại nhưng câu chữ, trật tự từ hoặc cấu trúc câu được thay đổi.
- **Trùng lặp ý tưởng:** Hai bài văn diễn đạt một nội dung hoặc lập luận tương tự, mặc dù không có nhiều cụm từ giống nhau.
- **Trùng lặp lặp lại trong chính tài liệu:** Một thuật ngữ, câu khai báo, công thức, tiêu đề hoặc đoạn văn được lặp lại nhiều lần do định dạng hoặc cấu trúc tài liệu.

Ba hình thức đầu có thể được phát hiện hiệu quả bằng so khớp chuỗi hoặc n-gram. Hình thức diễn đạt lại đòi hỏi phương pháp embedding ngữ nghĩa. Trùng lặp ý tưởng là trường hợp khó nhất vì ngữ nghĩa tương đồng có thể không đi kèm các từ hay cụm từ chung.

### 1.1.3. Quy trình phát hiện trùng lặp

Quy trình phát hiện trùng lặp trong hệ thống gồm các bước sau:

1. Tiếp nhận và kiểm tra tệp PDF/DOCX;
2. Trích xuất văn bản thô cùng các thông tin vị trí;
3. Chuẩn hóa Unicode, làm sạch văn bản và tách câu;
4. Chia tài liệu thành các đoạn nhỏ gọi là chunk;
5. Loại bỏ các phần ít giá trị đối chiếu như mục lục, danh mục và tài liệu tham khảo;
6. Thực hiện truy vấn theo chế độ từ vựng hoặc ngữ nghĩa;
7. Gom các đoạn liền nhau thành cảnh báo;
8. Xếp hạng tài liệu nguồn và trình bày báo cáo đối chiếu.

Mỗi đoạn được gắn thông tin ordinal, trang, khối nội dung hoặc section tương ứng. Đây là cơ sở để hệ thống không chỉ trả về điểm tương đồng mà còn hiển thị vị trí của đoạn nghi vấn trong bài nộp và đoạn nguồn trong kho.

## 1.2. Đặc điểm của văn bản tiếng Việt

Tiếng Việt là ngôn ngữ đơn lập và có dấu thanh. Một đơn vị ngữ nghĩa có thể gồm một từ đơn hoặc nhiều từ ghép. Ví dụ, cụm “hệ thống thông tin” được tạo bởi ba từ đơn nhưng mang một nghĩa kết hợp. Vì vậy, việc tách từ tiếng Việt cần được xử lý riêng thay vì chỉ dựa vào khoảng trắng như các ngôn ngữ chữ tách rời.

Ngoài ra, văn bản tiếng Việt còn có các đặc điểm sau:

- Dùng nhiều ký tự dấu câu và ký tự Unicode;
- Có thể sử dụng nhiều dạng Unicode nếu tài liệu được tạo bởi phần mềm khác nhau;
- Từ viết hoa, viết thường có thể thay đổi tùy ngữ cảnh;
- Một ý có thể được diễn đạt bằng nhiều từ đồng nghĩa;
- Các từ phổ biến như “và”, “của”, “trong”, “là” xuất hiện với tần suất cao nhưng ít mang nghĩa phân biệt.

Hệ thống sử dụng chuẩn Unicode NFC để thống nhất cách biểu diễn ký tự, chuyển văn bản về chữ thường trong các bước so khớp từ vựng và loại bỏ dấu câu trước khi sinh cụm từ. Trong chế độ ngữ nghĩa, văn bản được tiền xử lý và tách từ bằng các module riêng, sau đó mã hóa thành embedding bằng mô hình tiếng Việt.

## 1.3. Trích xuất và tiền xử lý tài liệu

### 1.3.1. Trích xuất nội dung PDF

PDF là định dạng mô tả cách bố trí trang thay vì định dạng văn bản có cấu trúc. Một trang PDF có thể lưu chữ như text layer, hoặc chỉ lưu hình ảnh quét. Do đó, trích xuất PDF được chia thành hai trường hợp:

- PDF có text layer: phần mềm đọc trực tiếp chuỗi ký tự và vị trí trên trang;
- PDF scan hoặc hỗn hợp: trang không đủ text cần được OCR để nhận dạng chữ.

Hệ thống sử dụng `pdfplumber` để trích xuất PDF có text layer. Kết quả được lưu kèm số trang, khối, cột và vị trí tương ứng để hỗ trợ truy vết. Đối với PDF scan, hệ thống sử dụng Tesseract OCR với ngôn ngữ tiếng Việt và tiếng Anh. Tesseract cần các tệp traineddata tương ứng và có thể được cấu hình thông qua `TESSERACT_CMD`, `OCR_LANGUAGE`, `OCR_DPI` và các giới hạn trang trong file môi trường.

Kết quả OCR có thể chứa sai ký tự do chất lượng ảnh, độ phân giải hoặc bố cục nhiều cột. Vì vậy, hệ thống ghi nhận cảnh báo trích xuất để người dùng biết trang nào có khả năng chưa được đọc chính xác. OCR không thay thế hoàn toàn việc kiểm tra thủ công đối với tài liệu scan chất lượng thấp.

### 1.3.2. Trích xuất nội dung DOCX

DOCX là định dạng XML nén, lưu nội dung theo các phần, đoạn văn, bảng, tiêu đề và thuộc tính định dạng. So với PDF, DOCX có nhiều thông tin cấu trúc hơn. Hệ thống sử dụng `python-docx` để lấy nội dung đoạn văn, bảng và thông tin section hoặc heading.

Việc duy trì heading là thuận lợi trong quá trình đối chiếu vì heading cho phép xác định vị trí logic của nội dung, ví dụ “Chương 1”, “Giải pháp”, “Kết luận” hoặc “Tài liệu tham khảo”. Tuy nhiên, DOCX không cung cấp số trang chính xác theo cách PDF thể hiện. Do đó, hệ thống lưu các thông tin như section, paragraph hoặc vị trí logic thay cho số trang khi thông tin này không tồn tại.

### 1.3.3. Chuẩn hóa và làm sạch văn bản

Tiền xử lý văn bản là bước chuẩn bị dữ liệu trước khi lập chỉ mục hoặc đối chiếu. Các bước chính gồm:

- Chuẩn hóa Unicode về dạng NFC;
- Loại bỏ ký tự điều khiển;
- Chuẩn hóa dấu cách, dòng xuống dòng và khoảng cách trước dấu câu;
- Loại bỏ số trang, dòng phân cách, ký hiệu nhiễu;
- Chuyển chữ hoa thành chữ thường khi cần;
- Tách câu theo dấu câu và cấu trúc đoạn văn;
- Tách từ tiếng Việt bằng thư viện phù hợp;
- Loại bỏ chunk quá ngắn hoặc không mang nghĩa đối chiếu.

Chuẩn hóa giúp tránh sai khác không mang ý nghĩa, chẳng hạn hai văn bản có cùng nội dung nhưng một văn bản sử dụng ký tự tổ hợp khác hoặc khoảng trống không nhất quán. Đồng thời, hệ thống phải giữ một bản văn bản thô để hiển thị lại cho người dùng.

### 1.3.4. Chia tài liệu thành chunk

Chunk là đoạn văn ngắn được trích từ tài liệu để đưa vào quá trình đối chiếu. Việc chia tài liệu thành chunk giúp:

- Giảm độ dài văn bản cần mã hóa trong mỗi truy vấn;
- Xác định vị trí tương đồng chính xác hơn;
- Tăng hiệu năng truy xuất;
- Gom các đoạn ngắn liên tiếp thành cảnh báo có ngữ cảnh.

Hệ thống có thể điều chỉnh kích thước chunk thông qua cấu hình `CHUNK_CHARS`. Trong implementation hiện tại, kích thước chunk mặc định là 700 ký tự. Mỗi chunk được gắn số thứ tự trong tài liệu. Thông tin này được lưu kèm khi nội dung được lưu vào PostgreSQL hoặc mã hóa thành vector.

## 1.4. Phương pháp phát hiện trùng lặp từ vựng

### 1.4.1. N-gram

N-gram là chuỗi liên tiếp gồm *n* đơn vị, có thể là ký tự hoặc từ. Với hệ thống phát hiện trùng lặp văn bản, word n-gram thường được sử dụng để đo phần cụm từ giống nhau giữa hai đoạn.

Giả sử đoạn văn sau khi tách từ được biểu diễn thành:

```text
[hệ, thống, kiểm, tra, báo, cáo]
```

Các cụm 4 từ liên tiếp có thể là:

```text
(hệ, thống, kiểm, tra)
(thống, kiểm, tra, báo)
(kiểm, tra, báo, cáo)
```

Hai đoạn có chung một cụm 4 từ được xem là có bằng chứng trùng khớp theo kiểu nguyên văn. Một n-gram quá ngắn có thể xuất hiện ngẫu nhiên do các từ phổ biến. Ngược lại, n-gram quá dài có thể bỏ lỡ trường hợp người viết sửa nhẹ một vài từ.

Trong implementation của đề tài, chế độ từ vựng sử dụng cụm 4 từ liên tiếp. Cụm không được tính nếu số từ nội dung trong cụm dưới mức quy định. Hệ thống cũng loại các cụm chủ yếu gồm từ chức năng như “và”, “của”, “trong”, “là”. Cách làm này giúp giảm cảnh báo sai do hai văn bản chỉ dùng chung nhiều cấu trúc ngữ pháp.

### 1.4.2. Chỉ mục ngược

Chỉ mục ngược là cấu trúc ánh xạ một cụm từ đến các chunk chứa cụm đó. Khi truy vấn một chunk mới, hệ thống lấy các cụm trong chunk truy vấn, tìm trong chỉ mục những chunk nguồn có ít nhất một cụm trùng và xếp hạng theo mức độ phủ.

Nếu các cụm 4 từ được biểu diễn bởi \(g_1, g_2, ..., g_n\), mỗi cụm liên kết đến danh sách chunk nguồn chứa cụm đó:

\[
g_i \rightarrow [chunk_{i1}, chunk_{i2}, ..., chunk_{ik}]
\]

Phương pháp này không cần so cặp từng chunk truy vấn với toàn bộ chunk trong kho. Nhờ đó, thời gian truy vấn chỉ phụ thuộc vào số ứng viên được chỉ mục ngược tìm thấy.

### 1.4.3. Điểm trùng khớp từ vựng

Điểm trùng khớp của một chunk được tính theo tỷ lệ số từ nằm trong cụm trùng:

\[
S_{lexical} = \frac{W_{matched}}{W_{total}}
\]

Trong đó:

- \(W_{matched}\) là số từ của chunk truy vấn thuộc một cụm trùng với nguồn;
- \(W_{total}\) là tổng số từ của chunk truy vấn.

Giá trị \(S_{lexical}\) nằm trong khoảng từ 0 đến 1. Khi các cụm trùng lặp giao nhau hoặc một cụm bao phủ nhiều từ, hệ thống chỉ đếm mỗi từ một lần trong phạm vi chunk. Điểm này được dùng đồng thời để hiển thị số từ trùng, phần tô đậm trong giao diện và mức độ cảnh báo.

Chế độ từ vựng phù hợp để phát hiện sao chép nguyên văn hoặc chỉnh sửa ít. Chế độ này không phát hiện được phần lớn trường hợp diễn đạt lại, khi câu chữ đã thay đổi nhưng ý nghĩa được giữ nguyên.

## 1.5. Phương pháp phát hiện trùng lặp ngữ nghĩa

### 1.5.1. Mô hình nhúng văn bản

Embedding là một vector số biểu diễn nội dung ngữ nghĩa của văn bản trong không gian nhiều chiều. Hai câu có ý nghĩa gần nhau thường có embedding gần nhau, ngay cả khi chúng không dùng chung nhiều từ.

Hệ thống sử dụng mô hình Sentence-BERT tiếng Việt `keepitreal/vietnamese-sbert`, được huấn luyện trên nền PhoBERT. Mô hình nhận chuỗi từ đã tách từ, trong đó các từ ghép được nối bằng dấu gạch dưới. Output của mô hình là vector cố định, hiện được lưu và truy vấn thông qua FAISS.

Ưu điểm của embedding ngữ nghĩa là:

- Nhận diện các câu sử dụng từ đồng nghĩa;
- Bắt chước ý nghĩa tương tự dù trật tự hoặc cấu trúc câu thay đổi;
- Giảm ảnh hưởng của ký tự hoặc sai chính tả cục bộ;
- Có thể tìm kiếm trên một kho tài liệu lớn bằng cơ chế nearest neighbor.

Nhược điểm của embedding là:

- Không cho biết chính xác cụm từ nào được sao chép;
- Có thể tạo điểm tương đồng cao cho hai đoạn cùng chủ đề nhưng không sao chép;
- Cần tài nguyên bộ nhớ và thời gian tính toán lớn hơn;
- Cần mô hình và môi trường phụ thuộc phù hợp.

Chính vì vậy, hệ thống trình bày đồng thời số liệu theo hai chế độ: chế độ từ vựng cung cấp bằng chứng cụm từ cụ thể, chế độ ngữ nghĩa cung cấp mức tương đồng tổng quát của nội dung.

### 1.5.2. Cosine similarity

Cosine similarity đo góc giữa hai embedding:

\[
cos(a,b)=\frac{a\cdot b}{\|a\|\|b\|}
\]

Trong đó:

- \(a\) là vector embedding của chunk truy vấn;
- \(b\) là vector embedding của chunk nguồn;
- \(a\cdot b\) là tích vô hướng;
- \(\|a\|\) và \(\|b\|\) là chuẩn Euclidean của hai vector.

Cosine similarity nhận giá trị trong khoảng [-1, 1]. Trong hệ thống vector đã chuẩn hóa độ dài, tích vô hướng có thể được sử dụng trực tiếp để mô phỏng cosine similarity. Một giá trị càng gần 1 cho thấy hai chunk càng gần nhau trong không gian ngữ nghĩa.

Hệ thống thiết lập ngưỡng semantic mặc định là 0,68. Tuy nhiên, ngưỡng này phải được đánh giá lại trên tập dữ liệu báo cáo thật. Ngưỡng thấp có thể làm tăng Recall nhưng đồng thời làm tăng số cảnh báo sai. Ngưỡng cao có thể giảm cảnh báo sai nhưng bỏ sót các đoạn diễn đạt lại.

## 1.6. FAISS và tìm kiếm vector

FAISS (Facebook AI Similarity Search) là thư viện hỗ trợ tìm kiếm vector hiệu quả. Trong đề tài, FAISS được sử dụng để lưu embedding của các chunk tham chiếu và tìm các chunk gần nhất với chunk truy vấn.

Hệ thống sử dụng `IndexFlatIP`, tức index lưu vector và thực hiện tìm kiếm bằng tích vô hướng. Trước khi thêm vector vào index, hệ thống chuẩn hóa từng vector bằng chuẩn L2. Khi vector truy vấn và vector kho đều được chuẩn hóa, tích vô hướng tương đương cosine similarity.

Quy trình tìm kiếm gồm:

1. Tiền xử lý và tách từ chunk truy vấn;
2. Mã hóa chunk truy vấn thành embedding;
3. Chuẩn hóa embedding;
4. Truy vấn top-k vector gần nhất trong FAISS;
5. Ánh xạ kết quả vector về metadata của chunk nguồn;
6. Lọc và gộp kết quả theo tài liệu, vị trí và ngưỡng.

Lợi ích của FAISS là hỗ trợ truy vấn nhanh trên kho vector lớn. Tuy nhiên, FAISS chủ yếu lưu vector và dữ liệu phục vụ tìm kiếm; các thông tin quản lý tài liệu, người dùng, quyền truy cập và lịch sử kiểm tra vẫn được lưu trong CSDL quan hệ.

## 1.7. Kiến trúc hệ thống web

### 1.7.1. Kiến trúc phân lớp

Hệ thống được xây dựng theo kiến trúc phân lớp để tách giao diện, API, nghiệp vụ và dữ liệu:

- **Lớp trình bày:** hiển thị trang chủ, đăng nhập, tải tài liệu, kết quả và báo cáo;
- **Lớp API:** cung cấp REST endpoint bằng FastAPI;
- **Lớp xử lý nghiệp vụ:** trích xuất tài liệu, tiền xử lý, tìm kiếm và gom cảnh báo;
- **Lớp dữ liệu:** PostgreSQL lưu tài liệu, chunk, lịch sử kiểm tra và tài khoản;
- **Lớp tìm kiếm vector:** FAISS lưu embedding cho chế độ ngữ nghĩa.

Kiến trúc phân lớp giúp thay thế hoặc nâng cấp từng thành phần mà không ảnh hưởng trực tiếp toàn bộ hệ thống. Ví dụ, giao diện có thể thay đổi mà không làm thay đổi thuật toán đối chiếu; mô hình embedding có thể được thay bằng mô hình khác nếu lớp truy vấn giữ nguyên giao diện đầu ra.

### 1.7.2. FastAPI

FastAPI là framework Python dùng để xây dựng API hiệu năng cao dựa trên kiểu dữ liệu và Pydantic. FastAPI hỗ trợ khai báo tham số, validation dữ liệu, dependency injection và sinh tài liệu OpenAPI.

Trong đề tài, FastAPI thực hiện các nhiệm vụ:

- Nhận tệp PDF/DOCX qua HTTP;
- Xác thực người dùng;
- Kiểm tra quyền truy cập tài liệu;
- Gọi các service trích xuất, tiền xử lý và đối chiếu;
- Trả kết quả JSON gồm báo cáo, source, chunk và cảnh báo;
- Cung cấp endpoint xem trước tài liệu và tải báo cáo.

Uvicorn là máy chủ ASGI dùng để chạy FastAPI.

### 1.7.3. Giao diện React

Giao diện của hệ thống sử dụng React để xây dựng ứng dụng đơn trang. React chia giao diện thành các component có thể tái sử dụng, ví dụ form đăng nhập, danh sách tài liệu, khu vực tải tệp, bảng kết quả và hộp xem đoạn đối chiếu.

Giao diện giao tiếp với backend thông qua API và chỉ hiển thị dữ liệu mà người dùng có quyền truy cập. Trong implementation của dự án, frontend có thể hiển thị hai vai trò:

- **Người dùng (`user`):** nộp tài liệu, xem bài nộp của mình và chạy kiểm tra;
- **Quản trị (`admin`):** quản lý tài khoản, kho tham chiếu, trang Internet đã lưu và xem báo cáo của tất cả người dùng.

## 1.8. PostgreSQL và mô hình dữ liệu

PostgreSQL là hệ quản trị CSDL quan hệ mã nguồn mở. Hệ thống sử dụng PostgreSQL để lưu thông tin nghiệp vụ thay vì lưu mọi dữ liệu trong JSON hoặc pickle.

Các thực thể chính gồm:

| Thực thể | Vai trò |
|---|---|
| `users` | Lưu tài khoản, mật khẩu đã băm, vai trò và trạng thái hoạt động |
| `documents` | Lưu metadata tài liệu, loại vai trò, hash, chủ sở hữu và đường dẫn lưu |
| `chunks` | Lưu nội dung từng chunk và vị trí trong tài liệu |
| `checks` | Lưu kết quả kiểm tra, chế độ, ngưỡng và snapshot báo cáo |

Document có ba vai trò:

- `submission`: bài báo cáo do người dùng nộp để kiểm tra;
- `reference`: tài liệu nguồn trong kho tham chiếu;
- `web`: trang Internet đã được tải và lưu để đối chiếu.

Lưu trữ snapshot trong bảng `checks` giúp kết quả kiểm tra không bị thay đổi nếu tài liệu hoặc kho tham chiếu được cập nhật sau đó. Đồng thời, sử dụng khóa ngoại và quan hệ ORM giúp CSDL đảm bảo tính nhất quán dữ liệu.

## 1.9. Xác thực, phân quyền và bảo mật

### 1.9.1. Xác thực bằng JWT

Hệ thống sử dụng JSON Web Token (JWT) để xác thực người dùng. Khi đăng nhập thành công, backend cấp token đã ký bằng khóa bí mật. Token được gửi trong cookie `HttpOnly` hoặc header `Authorization: Bearer`.

Trong implementation của đề tài:

- JWT sử dụng thuật toán ký `HS256`;
- Token chứa email, vai trò phiên bản và thời điểm hết hạn;
- Cookie được đặt `HttpOnly` và `SameSite=Strict`;
- Trạng thái người dùng không được tin cậy hoàn toàn từ token mà được nạp lại từ CSDL;
- Khi đổi mật khẩu, vai trò hoặc trạng thái khóa tài khoản, `token_version` tăng để vô hiệu hóa token cũ.

Việc nạp lại người dùng từ CSDL giúp hệ thống phản ứng ngay khi tài khoản bị khóa hoặc bị thay đổi quyền.

### 1.9.2. Kiểm soát truy cập theo vai trò

Hệ thống phân quyền theo hai vai trò:

- **User:** nộp bài, chạy kiểm tra và xem tài liệu do mình tải lên;
- **Admin:** quản lý tài khoản, kho tham chiếu, nguồn Internet và xem báo cáo của mọi người.

Quyền không chỉ được kiểm tra ở giao diện mà còn được kiểm tra ở backend. Nếu người dùng truy cập tài liệu không thuộc quyền của mình, hệ thống trả kết quả 404 thay vì tiết lộ rằng tài liệu tồn tại. Nguyên tắc này giúp hạn chế dò ID tài liệu.

### 1.9.3. Bảo mật dữ liệu tải lên

Tài liệu tải lên có thể chứa dữ liệu nhạy cảm hoặc mã độc. Hệ thống áp dụng các biện pháp:

- Kiểm tra đuôi tệp và loại PDF/DOCX;
- Kiểm tra dung lượng tối đa;
- Tạo tên tệp ngẫu nhiên thay vì dùng tên gốc;
- Lưu tệp trong thư mục upload riêng;
- Giới hạn số trang, số chunk và kích thước xử lý;
- Sử dụng truy vấn tham số hóa của SQLAlchemy;
- Không trả traceback nội bộ cho người dùng;
- Không lưu mật khẩu dưới dạng plaintext, chỉ lưu hash bcrypt.

Ngoài ra, đăng nhập sai nhiều lần được giới hạn theo tổ hợp email và địa chỉ IP. Thông báo cho email tồn tại và email không tồn tại được chuẩn hóa tương đương để giảm rủi ro lộ tài khoản.

## 1.10. Tìm kiếm nguồn Internet

Hệ thống có thể tích hợp tìm kiếm nguồn Internet thông qua Serper API. Khi phát hiện các đoạn nghi vấn trong báo cáo nộp, backend có thể tạo truy vấn tìm kiếm từ đoạn văn, gọi Serper, lấy kết quả và tải toàn văn các trang phù hợp.

Dữ liệu Internet được lưu dưới role `web` trong PostgreSQL để tái sử dụng ở các lần kiểm tra sau. Hệ thống giới hạn số trang mới trong mỗi lần kiểm tra, dung lượng tối đa của từng trang và tổng số chunk nguồn Internet.

Quá trình tìm kiếm Internet không làm hỏng kết quả đối chiếu nội bộ. Nếu dịch vụ Internet thất bại, hệ thống vẫn trả báo cáo dựa trên kho tham chiếu và ghi cảnh báo vào kết quả.

Tính năng này cần được giám sát về bản quyền, quyền truy cập trang web và giới hạn API. Kết quả tìm kiếm không đồng nghĩa với tài liệu là nguồn đạo văn; người kiểm định vẫn phải xem bối cảnh, nội dung trích dẫn và khả năng trùng lập ý.

## 1.11. Đánh giá hiệu năng hệ thống phát hiện trùng lặp

### 1.11.1. Tập dữ liệu đánh giá

Để đánh giá hệ thống, cần xây dựng tập cặp văn bản có nhãn:

- Nhãn 1: hai đoạn có nội dung trùng hoặc tương đương;
- Nhãn 0: hai đoạn không trùng hoặc không tương đương.

Trong dự án, tập dữ liệu được chia thành tập validation và tập test. Ngưỡng được chọn chỉ trên tập validation, sau đó giữ nguyên để đo kết quả trên tập test. Việc này tránh sử dụng tập test để điều chỉnh ngưỡng theo kết quả mong muốn.

Bên cạnh kiểm thử theo cặp đoạn, hệ thống còn đo truy xuất tài liệu bằng các chỉ số Recall@1, Recall@3 và Recall@5. Chỉ số này trả lời câu hỏi: trong top-k tài liệu nguồn được truy xuất, tài liệu thực sự tương ứng có xuất hiện hay không.

### 1.11.2. Confusion matrix

Đối với bài toán phân loại hai lớp trùng hoặc không trùng, kết quả được biểu diễn bằng ma trận nhầm lẫn:

| | Dự đoán trùng | Dự đoán không trùng |
|---|---:|---:|
| Thực tế trùng | True Positive (TP) | False Negative (FN) |
| Thực tế không trùng | False Positive (FP) | True Negative (TN) |

- **False Positive:** Báo trùng một cặp thực tế không trùng;
- **False Negative:** Không báo trùng một cặp thực tế trùng.

Trong bối cảnh phát hiện trùng lặp học thuật, False Positive có thể gây khó chịu, yêu cầu kiểm tra thêm hoặc tác động sai đến người viết. False Negative có thể bỏ sót trường hợp sao chép và làm giảm độ tin cậy của hệ thống. Vì vậy, hệ thống cần cân bằng giữa Precision và Recall thay vì chỉ theo dõi một chỉ số duy nhất.

### 1.11.3. Precision, Recall và F1-score

Precision đo tỷ lệ cặp được dự đoán trùng thực sự trùng:

\[
Precision=\frac{TP}{TP+FP}
\]

Recall đo tỷ lệ cặp trùng thực tế được hệ thống phát hiện:

\[
Recall=\frac{TP}{TP+FN}
\]

F1-score là trung bình điều hòa giữa Precision và Recall:

\[
F1=2\times\frac{Precision\times Recall}{Precision+Recall}
\]

F1 phù hợp khi cần cân bằng hai loại sai. Khi chọn ngưỡng, hệ thống có thể ưu tiên F1 cao nhất; trong trường hợp hòa, ưu tiên Precision trước rồi chọn ngưỡng cao hơn để hạn chế cảnh báo sai.

### 1.11.4. Recall@k

Trong bài toán truy xuất nguồn, Recall@k được tính theo:

\[
Recall@k=\frac{\text{số truy vấn tìm thấy nguồn đúng trong top-k}}{\text{tổng số truy vấn}}
\]

Recall@k cho biết khả năng mô hình đưa tài liệu nguồn đúng vào danh sách ứng viên. Chỉ số này đặc biệt quan trọng trong khi hệ thống semantic sử dụng top-k sau đó mới gom và xếp hạng cảnh báo.

### 1.11.5. Giới hạn của các chỉ số

Điểm tương đồng, độ phủ hoặc phần trăm ký tự không phải là xác nhận đạo văn. Một đoạn có điểm trùng cao vẫn có thể là câu định nghĩa, công thức hoặc tài liệu tham khảo được trích dẫn hợp lệ. Ngược lại, một đoạn có điểm thấp vẫn có thể là nội dung diễn đạt lại ý của nguồn.

Do đó, kết quả đánh giá cần được trình bày cùng bối cảnh:

- Tập dữ liệu có bao gồm báo cáo thật hay không;
- Các nhãn được ai gán và có quy tắc thống nhất không;
- Tài liệu có thuộc cùng chủ đề hay nội dung độc lập;
- Kết quả có áp dụng cho PDF scan, DOCX hay cả hai không;
- Ngưỡng được chọn trên tập nào.

Đối với đồ án tốt nghiệp, tập dữ liệu nhỏ hoặc tạo tự động chỉ có ý nghĩa kiểm chứng quy trình. Chất lượng cuối cùng nên được đánh giá bằng báo cáo thật, có ít nhất hai người gán nhãn và thống nhất các trường hợp bất đồng.

## 1.12. Phân biệt so khớp từ vựng và tương đồng ngữ nghĩa

Hai tầng phát hiện của hệ thống có vai trò khác nhau.

| Tiêu chí | Từ vựng | Ngữ nghĩa |
|---|---|---|
| Cơ sở so sánh | Cụm từ liên tiếp và từ chung | Vector embedding |
| Phát hiện sao chép trực tiếp | Tốt | Có thể phát hiện |
| Phát hiện diễn đạt lại | Hạn chế | Ưu thế |
| Giải thích kết quả | Rõ ràng bằng cụm từ trùng | Mức tương đồng tổng quát |
| Mô hình học máy | Không bắt buộc | Cần Sentence-BERT |
| Phụ thuộc tài nguyên | Thấp | Cao hơn |
| Nhược điểm | Có thể bỏ sót từ đồng nghĩa | Có thể cảnh báo sai do cùng chủ đề |

Hệ thống kết hợp hai phương pháp thay vì chỉ sử dụng một phương pháp duy nhất. Chế độ từ vựng cung cấp bằng chứng cụ thể cho việc sao chép nguyên văn hoặc chỉnh sửa nhẹ. Chế độ ngữ nghĩa giúp phát hiện các đoạn diễn đạt lại ở mức độ cao hơn.

Kết quả cuối cùng không dựa trên điểm số đơn thuần. Hệ thống lọc chunk, gom các đoạn liền nhau, xếp hạng nguồn, tính độ phủ và hiển thị nội dung nguồn, vị trí và cảnh báo để người thẩm định đưa ra quyết định.

## 1.13. Tổng kết chương

Chương này đã trình bày cơ sở lý thuyết của hệ thống kiểm tra trùng lặp trong báo cáo đồ án, bao gồm khái niệm trùng lặp, đặc điểm văn bản tiếng Việt, trích xuất PDF/DOCX, OCR, tiền xử lý và chia chunk. Hệ thống sử dụng đồng thời n-gram từ vựng, embedding SBERT, cosine similarity và FAISS để phát hiện các mức tương đồng khác nhau.

Bên cạnh thuật toán đối chiếu, hệ thống còn sử dụng FastAPI, React và PostgreSQL để xây dựng ứng dụng web, đồng thời áp dụng xác thực JWT, phân quyền người dùng/quản trị và các biện pháp bảo vệ dữ liệu tải lên. Hiệu quả của mô hình được đánh giá thông qua Precision, Recall, F1-score và Recall@k, với ngưỡng cần được kiểm chứng trên dữ liệu báo cáo thật.

Cơ sở lý thuyết trên là nền tảng cho việc phân tích yêu cầu, thiết kế kiến trúc, thiết kế CSDL, triển khai thuật toán và đánh giá hệ thống ở các chương tiếp theo.

## 1.14. Các công nghệ sử dụng trong đề tài

### 1.14.1. Ngôn ngữ lập trình

**Python** được sử dụng để xây dựng chương trình trích xuất tài liệu, tiền xử lý, đối chiếu trùng lặp, API và xử lý CSDL. Python có nhiều thư viện mã nguồn mở hỗ trợ xử lý văn bản, tài liệu, học máy và phát triển web, nên phù hợp với quy mô và mục tiêu của đề tài.

**JavaScript** được sử dụng để xây dựng giao diện người dùng trong môi trường trình duyệt. JavaScript giao tiếp với backend thông qua các yêu cầu HTTP và cập nhật trạng thái, danh sách tài liệu và báo cáo mà không cần tải lại toàn bộ trang.

### 1.14.2. Công nghệ backend

**FastAPI** là framework Python dùng để xây dựng REST API. FastAPI hỗ trợ khai báo endpoint, kiểm tra dữ liệu đầu vào, xử lý tệp tải lên, authentication, authorization và sinh tài liệu API. Hệ thống sử dụng FastAPI để cung cấp các chức năng đăng ký, đăng nhập, quản lý tài liệu, chạy kiểm tra, xem trước và tải kết quả.

**Uvicorn** là máy chủ ASGI dùng để chạy ứng dụng FastAPI trên môi trường phát triển hoặc triển khai cục bộ.

Các thư viện Python backend chính gồm:

| Thư viện | Vai trò trong đề tài |
|---|---|
| `SQLAlchemy` | ORM ánh xạ các thực thể User, Document, Chunk và Check sang PostgreSQL |
| `psycopg` | Trình điều khiển kết nối Python với PostgreSQL |
| `python-multipart` | Nhận tệp tải lên qua HTTP |
| `python-dotenv` | Đọc cấu hình và thông tin bí mật từ file `.env` |
| `bcrypt` | Băm mật khẩu người dùng |
| `PyJWT` | Tạo và kiểm tra JSON Web Token |
| `requests` | Gọi HTTP, tải nội dung trang web và API tìm kiếm |

### 1.14.3. Công nghệ giao diện

**React** là thư viện JavaScript xây dựng giao diện người dùng theo component. React được sử dụng để chia giao diện thành các thành phần đăng nhập, đăng ký, tải tài liệu, danh sách kho tham chiếu, báo cáo kết quả và hộp đối chiếu đoạn văn.

**React DOM** kết nối các component React với DOM của trình duyệt.

**Vite** là công cụ phát triển và đóng gói frontend. Vite hỗ trợ khởi động nhanh môi trường phát triển, hot reload và build sản phẩm tĩnh cho ứng dụng React.

Phiên bản frontend được khai báo trong dự án gồm React 19.3.1 và React DOM 19.3.1, với Vite 8.3.6. Giao diện được phục vụ cùng backend FastAPI sau khi build.

**Vitest** và **React Testing Library** được sử dụng để kiểm thử component, tương tác người dùng và các luồng frontend. **Playwright** được dùng cho kiểm thử end-to-end trên trình duyệt.

### 1.14.4. Hệ quản trị CSDL

**PostgreSQL** là CSDL quan hệ được sử dụng để lưu tài khoản, tài liệu, chunk, kết quả kiểm tra và nguồn Internet. PostgreSQL hỗ trợ khóa chính, khóa ngoại, chỉ mục, ràng buộc duy nhất, JSON và các truy vấn giao dịch phù hợp với dữ liệu nghiệp vụ.

Trong hệ thống:

- Tài liệu được lưu trong bảng `documents`;
- Nội dung từng đoạn được lưu trong bảng `chunks`;
- Kết quả kiểm tra và snapshot báo cáo được lưu trong bảng `checks`;
- Tài khoản, vai trò và phiên bản token được lưu trong bảng `users`.

Cấu trúc này giúp lưu lịch sử, phân quyền truy cập và truy xuất metadata của tài liệu. FAISS không thay thế PostgreSQL mà chỉ dùng cho vector nhúng; PostgreSQL lưu dữ liệu quan hệ còn FAISS lưu dữ liệu tìm kiếm ngữ nghĩa.

### 1.14.5. Công nghệ xử lý tài liệu

**pdfplumber** được sử dụng để trích xuất văn bản và thông tin vị trí từ các trang PDF có text layer. `pypdfium2` hỗ trợ xử lý PDF ở các thành phần rendering và đọc tài liệu.

**python-docx** được sử dụng để đọc nội dung DOCX, bao gồm đoạn văn, bảng, heading và các section.

**Tesseract OCR** được sử dụng để nhận dạng văn bản trong PDF scan hoặc PDF hỗn hợp. Hệ thống hỗ trợ cấu hình ngôn ngữ OCR, độ phân giải DPI, số trang tối đa và đường dẫn executable Tesseract.

Việc trích xuất DOCX/PDF không chỉ giữ chuỗi văn bản mà còn lưu vị trí, section, trang, khối hoặc số thứ tự để truy vết kết quả.

### 1.14.6. Công nghệ tiền xử lý và xử lý ngôn ngữ tự nhiên

**underthesea** là thư viện xử lý ngôn ngữ tự nhiên tiếng Việt hỗ trợ tách câu và tách từ trong pipeline tiền xử lý.

Hệ thống sử dụng các thuật toán tự triển khai cho chuẩn hóa Unicode, tách từ, word n-gram, loại chunk ít ý nghĩa và tính điểm phủ của cụm trùng. Cách này không phụ thuộc nhiều vào mô hình học máy trong chế độ so khớp trực tiếp.

### 1.14.7. Công nghệ embedding và tìm kiếm ngữ nghĩa

**Sentence-Transformers** cung cấp cơ chế mã hóa văn bản thành embedding ngữ nghĩa. Đề tài sử dụng mô hình `keepitreal/vietnamese-sbert`, nền PhoBERT.

**FAISS** là thư viện tìm kiếm vector tương tự của Facebook AI Research. Hệ thống sử dụng `IndexFlatIP` cùng vector đã chuẩn hóa L2 để thực hiện cosine similarity. FAISS hỗ trợ tìm kiếm top-k nhanh hơn so với duyệt từng cặp chunk bằng phép tính cosine thông thường.

Embeddings được sinh từ văn bản tiếng Việt đã được tiền xử lý. Chế độ từ vựng dùng n-gram tự triển khai; chế độ ngữ nghĩa dùng SBERT kết hợp FAISS.

### 1.14.8. Công nghệ xác thực và bảo mật

**JSON Web Token (JWT)** được sử dụng để xác thực phiên đăng nhập. **bcrypt** được sử dụng để băm mật khẩu, thay vì lưu mật khẩu dưới dạng plaintext.

Hệ thống sử dụng hai vai trò `user` và `admin`. Middleware kiểm tra Origin đối với yêu cầu thay đổi dữ liệu, cookie đặt `HttpOnly` và `SameSite=Strict`, kiểm tra quyền ở backend và giới hạn số lần đăng nhập sai.

Các biện pháp khác gồm giới hạn kích thước tệp, giới hạn số trang/chunk, tạo tên tệp lưu trữ ngẫu nhiên, truy vấn SQL tham số hóa và ẩn traceback khỏi người dùng.

### 1.14.9. Công nghệ tìm kiếm nguồn Internet

**Serper API** được sử dụng để tìm các trang Internet có khả năng liên quan đến đoạn văn nghi vấn. Hệ thống tạo truy vấn từ các chunk, lấy kết quả tìm kiếm, tải toàn văn trang phù hợp và lưu vào CSDL để tái sử dụng.

Dữ liệu từ Internet được lưu dưới vai trò `web`, có giới hạn số trang, dung lượng trang, thời gian fetch và tổng số chunk nguồn.

### 1.14.10. Công nghệ kiểm thử và đánh giá

**pytest** được sử dụng để kiểm thử backend, API, tiền xử lý, OCR, cache tìm kiếm Internet và báo cáo.

**HTTPX** được sử dụng để mô phỏng yêu cầu HTTP trong kiểm thử ứng dụng FastAPI.

**Vitest**, **React Testing Library** và **Playwright** được sử dụng để kiểm thử giao diện, tương tác React và luồng truy cập end-to-end trên trình duyệt.

Kết quả thuật toán được đánh giá bằng:

- Confusion matrix;
- Precision;
- Recall;
- F1-score;
- Recall@k;
- Độ phủ chunk và số từ trùng nguyên văn.
