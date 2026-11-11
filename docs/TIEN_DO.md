# Tiến độ và điểm tiếp tục cho AI

> Đọc cùng [KE_HOACH_TRIEN_KHAI.md](KE_HOACH_TRIEN_KHAI.md). Cập nhật tệp này trước khi kết thúc mỗi phiên triển khai; không ghi kết quả dự kiến thành kết quả đã đạt.

## Trạng thái hiện tại

- `updated_at`: 2026-11-08
- `project_status`: IN_PROGRESS
- `current_stage`: WEB_MVP (ưu tiên xây web theo yêu cầu mới; triển khai một phần G1/G3/G4/G5/G6, chưa nghiệm thu toàn bộ các giai đoạn)
- `next_task`: G2.2
- `next_action`: Thu thập chunk từ báo cáo thật, gán nhãn độc lập, rà soát các chunk bị bộ lọc loại nhầm và chạy lại `python -m evaluation.evaluate`; chỉ chốt ngưỡng cuối sau khi tập thật đủ đại diện.
- `last_completed_stage`: Chưa có giai đoạn triển khai nào được nghiệm thu theo kế hoạch mới.
- `latest_handoff`: docs/handoffs/REACT_MIGRATION.md
- `blockers`: Không còn chặn kết nối PostgreSQL, model hoặc quy trình đo. Tập hiện tại chỉ có 32 cặp kiểm soát và 10 truy vấn; chưa đủ để công bố chất lượng cuối.

## Bảng giai đoạn

| Mã | Nội dung | Trạng thái | Bằng chứng nghiệm thu |
|---|---|---|---|
| G0 | Đặc tả và baseline | IN_PROGRESS | Kiểm kê Python/PostgreSQL và bộ web; chưa hoàn tất baseline ML |
| G1 | Lõi xử lý và truy vết | IN_PROGRESS | Service web giữ vị trí PDF/DOCX, test đạt; CLI cũ chưa sửa |
| G2 | Dữ liệu và đánh giá | IN_PROGRESS | Có pipeline đánh giá, tập khởi đầu, Precision/Recall/F1, confusion matrix và Recall@k; còn thiếu tập báo cáo thật được gán nhãn |
| G3 | Kiểm tra toàn bộ báo cáo | IN_PROGRESS | Web từ vựng + snapshot kết quả; chưa hiệu chỉnh ngưỡng |
| G4 | CSDL, kho và job | IN_PROGRESS | Ba bảng PostgreSQL, kiểm thử lưu/đọc thật; chưa migration/job |
| G5 | API và phân quyền | IN_PROGRESS | API cục bộ có upload validation; chưa xác thực/phân quyền |
| G6 | Giao diện | IN_PROGRESS | Giao diện HTML/CSS/JS có luồng upload/đối chiếu/lịch sử; chưa QA trình duyệt |
| G7 | OCR và so khớp từ vựng | IN_PROGRESS | Đã tích hợp luồng Tesseract theo trang, PDF hỗn hợp và giới hạn tài nguyên; máy hiện thiếu Tesseract/vie để nghiệm thu engine thật |
| G8 | Đánh giá cuối | TODO | Chưa có |
| G9 | Đóng gói và bảo vệ | TODO | Chưa có |

## Những gì đã xác minh trong phiên lập kế hoạch

- Đã đọc đề cương, kế hoạch v2, slide đợt 1, README, requirements và bốn module Python.
- Có lõi trích xuất, tiền xử lý, batch và FAISS search trong mã nguồn; chưa chạy model hoặc kiểm thử chức năng trong phiên này.
- Dữ liệu JSON có 13 chunk PDF và 4 chunk DOCX. Chưa xác nhận lại số vector trong index nhị phân.
- DOCX gán `page = 1`; `--watch` quét một lần; tìm kiếm chuỗi chưa thống nhất tiền xử lý và self-match hiện dựa vào tên tệp.
- `git status` báo thư mục chưa phải Git repository; không dùng commit hash làm bằng chứng cho đến khi xác minh/quản lý phiên bản được thiết lập.
- Chỉ tạo tài liệu kế hoạch và tiến độ, thêm liên kết README; chưa sửa mã xử lý hoặc dữ liệu.

## Cập nhật sau khi triển khai web lần đầu

- Người dùng yêu cầu bắt đầu xây web upload/kiểm tra và hướng dẫn PostgreSQL; ưu tiên một luồng MVP xuyên suốt, không tự đánh dấu DONE các giai đoạn kế hoạch chưa đủ nghiệm thu.
- Tạo `app/`, `frontend/`, `.env.example`, `requirements-web.txt`, `requirements-test.txt`, `tests/` và script chạy/test.
- Dùng giao diện HTML/CSS/JavaScript phục vụ từ FastAPI cho bản đầu, chưa dùng React như kiến trúc đích. Không triển khai Sites vì backend Python/FAISS/PostgreSQL cần runtime riêng.
- Cài bộ web vào `.venv` với Python 3.14.2. PostgreSQL binary 18.3 có trên máy.
- Kiểm thử PostgreSQL thật bằng cụm tách biệt `127.0.0.1:55439`: **16 passed**. Cụm đã tự dừng sau test; không dùng tài khoản/dữ liệu dịch vụ PostgreSQL chính.
- `node --check frontend/app.js` và biên dịch Python thành công. Chưa kiểm thử giao diện bằng trình duyệt, chưa chạy model thật.
- `.env` đã tạo từ mẫu, chưa có mật khẩu. `python -m app.db check` báo chưa cấu hình; không tuyên bố database sử dụng thật đã kết nối.
- Server đã khởi động ở `http://127.0.0.1:8000`; kiểm tra HTTP trang chủ trả 200, health báo `not_configured` đúng thực tế. Nếu server đã dừng khi sang phiên khác, chạy lại lệnh uvicorn trong hướng dẫn.
- Chế độ mặc định từ vựng; ngữ nghĩa có adapter SBERT/FAISS, cần cài requirements.txt và bật ENABLE_SEMANTIC. Không tự fallback khi model lỗi.
- Hướng dẫn sử dụng/kết nối: `docs/WEB_POSTGRESQL.md`. Các module CLI, tài liệu gốc và index cũ không bị ghi đè.

## Cập nhật sửa chế độ semantic (21/09/2026)

- Xác định lỗi `WinError 10013`: model `keepitreal/vietnamese-sbert` chưa có trong cache, web cố truy cập Hugging Face nhưng kết nối bị Windows chặn.
- Đã tải model vào cache và kiểm chứng tạo embedding 768 chiều thành công.
- Sửa `VectorStore` nhận `local_files_only`; adapter web dùng `local_files_only=True` để không chờ retry mạng trong lúc xử lý.
- Kiểm chứng semantic core trên 43 chunk tham chiếu trong PostgreSQL: trả top-3, đoạn tự đối chiếu có cosine `1.0`.
- PostgreSQL `ready`, `ENABLE_SEMANTIC=true`; web đã khởi động lại tại `127.0.0.1:8000`.
- Kiểm thử nhanh sau sửa: `5 passed`, `11 skipped` (các test tích hợp cần `TEST_DATABASE_URL`); biên dịch Python và kiểm tra JavaScript thành công.

## Tệp AI cần đọc khi tiếp tục

1. `KE_HOACH_TRIEN_KHAI.md`: mục G0, nguyên tắc và quy trình bàn giao.
2. `De_cuong.md`: yêu cầu chính thức của đồ án.
3. `requirements.txt`, `extractor.py`, `preprocessor.py`, `pipeline.py`, `vector_store.py`: kiểm kê môi trường và baseline.
4. `README.md`: đối chiếu hướng dẫn chạy, chỉnh phần đã lỗi thời trong G0.

## Nhật ký kiểm tra

| Ngày | Kiểm tra | Kết quả | Giới hạn |
|---|---|---|---|
| 2026-09-19 | Đọc mã và đếm JSON bằng PowerShell | Hai JSON, tổng 17 chunk | Không chứng minh index đồng bộ hoặc model hoạt động |
| 2026-09-19 | `git status --short` | Không nhận diện Git repository | Chưa có trạng thái Git để đối chiếu |
| 2026-09-21 | Tải và encode Vietnamese SBERT | `MODEL_OK 768 (1, 768)` | Chưa phải đánh giá chất lượng paraphrase |
| 2026-09-21 | Semantic core với dữ liệu PostgreSQL | 43 nguồn chunk, top-3 trả đúng, self-query cosine 1.0 | Chưa chạy upload semantic đầu cuối và chưa hiệu chỉnh ngưỡng |

## Cập nhật hiệu chỉnh ngưỡng ban đầu (21/09/2026)

- Thêm `evaluation/` với 32 cặp gán nhãn, tách 16 validation và 16 test theo nhóm nội dung; thêm kho 12 đoạn và 10 truy vấn để đo Recall@k.
- Script `python -m evaluation.evaluate` dùng đúng đặc trưng lexical của web và đúng SBERT/FAISS của dự án. Ngưỡng chỉ được chọn trên validation theo F1, sau đó giữ nguyên khi đo test.
- Ngưỡng khởi đầu: lexical `0.08`; semantic `0.68`. Lexical test: Precision/Recall/F1 = `0.8750/0.8750/0.8750`. Semantic test: `1.0000/0.6250/0.7692`.
- FAISS semantic trên toàn bộ tập truy vấn: Recall@1 = `0.8000`, Recall@3 = `1.0000`, Recall@5 = `1.0000`.
- Web đọc hai ngưỡng khởi đầu từ cấu hình và trả cờ `threshold_calibrated`; đây chưa phải kết quả cuối vì tập hiện tại nhỏ và do nhóm tự xây dựng.
- Kết quả chi tiết: `evaluation/results/REPORT.md`, `metrics.json`, `pair_predictions.json`.

## Cập nhật hoàn thiện kết quả (21/09/2026)

- Lọc mục lục, danh mục, phần tài liệu tham khảo và câu mẫu trước khi lexical/FAISS tìm kiếm.
- Mỗi chunk truy vấn chỉ giữ ứng viên tốt nhất trên từng tài liệu; các cặp chunk liền nhau được gộp thành một cảnh báo.
- Giới hạn 5 cảnh báo mỗi nguồn và 50 cảnh báo toàn báo cáo, đồng thời lưu số cảnh báo đã ẩn.
- Xếp hạng nguồn theo số ký tự được đối chiếu, số chunk và điểm tốt nhất; giao diện hiển thị hạng và coverage của từng nguồn.
- Phân biệt `lexical_overlap`/“Trùng khớp từ vựng” và `semantic_similarity`/“Tương đồng ngữ nghĩa”.
- Kiểm thử toàn bộ trên PostgreSQL tách biệt: **22 passed**. Kiểm tra JavaScript và biên dịch Python thành công.
- Tài liệu thiết kế: `docs/XU_LY_KET_QUA.md`.

## Cập nhật OCR PDF scan (21/09/2026)

- PDF có text layer giữ nguyên văn bản; chỉ trang không có chữ mới được dựng ảnh và gửi sang Tesseract.
- Chunk lưu `extraction_method=text_layer|ocr`, số trang và cảnh báo/lỗi OCR theo từng trang.
- Thêm giới hạn DPI 100–300, số trang OCR, timeout mỗi trang, tổng trang và tổng chunk.
- `/api/health` trả trạng thái Tesseract và danh sách ngôn ngữ; thiếu `vie.traineddata` được báo riêng.
- Đã kiểm thử bằng OCR giả lập trên ảnh trang PDF: scan thuần, PDF hỗn hợp, trang lỗi, trang trắng và giới hạn số trang đều đạt.
- Máy hiện có bộ dựng ảnh `pypdfium2` nhưng chưa có `tesseract.exe`. Chocolatey cần PowerShell Administrator; cài theo `docs/OCR_PDF.md` rồi chạy nghiệm thu engine thật.

## Cập nhật giao diện đọc kết quả hai cột (21/09/2026)

- Báo cáo schema 3 lưu `document_chunks`, số cảnh báo trên từng chunk và điểm cao nhất để tái dựng toàn bộ văn bản.
- Cột trái hiển thị văn bản theo thứ tự, tô màu mức cảnh báo và gắn số trực tiếp vào đoạn trùng.
- Cột phải liệt kê cảnh báo theo thứ tự xuất hiện, nguồn, vị trí, loại lexical/semantic và điểm phần trăm.
- Bấm thẻ cảnh báo sẽ cuộn tới đoạn tương ứng; bấm số trên văn bản sẽ cuộn về thẻ nguồn.
- Kết quả lịch sử schema cũ có chế độ hiển thị tương thích từ các đoạn match đã lưu.
- Giao diện responsive chuyển thành hai vùng xếp dọc trên màn hình nhỏ. Kiểm thử tích hợp PostgreSQL: **26 passed**.

## Cập nhật bản xem gốc và cuộn độc lập (21/09/2026)

- Sửa `min-height/overflow` để vùng văn bản và danh sách cảnh báo nhận con lăn chuột độc lập.
- Thêm hai chế độ cột trái: `Bản gốc` và `Văn bản đánh dấu`; bấm cảnh báo tự chuyển sang bản đánh dấu và cuộn đúng đoạn.
- PDF dùng trình xem PDF gốc của Chrome. DOCX được dựng an toàn từ tệp gốc, giữ thứ tự đoạn, tiêu đề, căn lề, định dạng run, bảng và ảnh.
- Endpoint `/api/documents/{id}/preview` đã kiểm chứng trên DOCX đang lưu; kiểm thử tích hợp PostgreSQL: **27 passed**.

## Cập nhật giới hạn cảnh báo (21/09/2026)

- Tăng giới hạn trình bày lên tối đa `1000` cảnh báo mỗi nguồn và `1000` cảnh báo toàn báo cáo.
- Giữ bước chọn ứng viên tốt nhất, gộp chunk liền nhau và khử cảnh báo lặp trước khi áp giới hạn.
- Hai giá trị cấu hình bằng `MAX_ALERTS_PER_SOURCE` và `MAX_ALERTS_PER_REPORT`; hệ thống chặn cấu hình vượt quá 1000.

## Quy tắc cập nhật

- Đánh dấu nhiệm vụ ở kế hoạch sau khi có đầu ra và bằng chứng; sửa dòng trạng thái tương ứng tại đây.
- Giai đoạn hoàn tất: tạo `docs/handoffs/Gx.md`, điền `latest_handoff`, đổi `last_completed_stage`, đặt giai đoạn kế tiếp và mã nhiệm vụ đầu tiên chưa xong.
- Đang làm dở: ghi tệp đã sửa, test đã chạy, lỗi còn lại và lệnh/hành động kế tiếp vào đây.
- Bị chặn: ghi nguyên nhân cụ thể và điều kiện để tiếp tục; không tự bỏ qua tiêu chí nghiệm thu.
- Người dùng có thể giao tiếp: “Đọc kế hoạch và tiến độ, tiếp tục nhiệm vụ tiếp theo.” AI vẫn phải được gọi trong một phiên làm việc; tệp này không tự chạy công việc.

## Cập nhật chuyển React và sửa engine mặc định (08/11/2026)

- Giao diện hiện dùng React + Vite; cấu trúc component và hướng dẫn dev/build/test: [REACT_FRONTEND.md](REACT_FRONTEND.md).
- Backend phục vụ frontend/dist. Script start-web.ps1 build React trước khi khởi động.
- Thêm chọn lexical/semantic theo trạng thái backend, lấy ngưỡng từ Settings; sửa lỗi API mặc định semantic trong khi cấu hình tắt gây 6 test lỗi.
- Kiểm chứng: 29 test backend/PostgreSQL tách biệt đạt, 6 test React đạt, 1 test Edge headless đạt; build thành công.
- Test browser dùng API giả lập và kiểm tra desktop/mobile, không ghi dữ liệu người dùng. Chưa nghiệm thu model/OCR thật trong phiên này.
- Bàn giao: [REACT_MIGRATION.md](handoffs/REACT_MIGRATION.md).
- Bước kế tiếp vẫn là G2.2: dữ liệu báo cáo thật và đánh giá; không coi chuyển framework là hoàn tất độ chính xác thuật toán.

## Giao diện thẩm định theo mẫu (08/11/2026)

- Kết quả mặc định mở Văn bản đánh dấu: chữ serif, tô màu theo mức điểm, số nguồn màu cam bên lề.
- Danh sách gộp nguồn nội bộ và Internet, đánh số ổn định theo vị trí đoạn. Có sắp xếp theo thứ tự xuất hiện hoặc điểm.
- Bấm thẻ nguồn, số bên lề hoặc đoạn tô màu để mở hộp đối chiếu. Hộp hiển thị đoạn báo cáo và đoạn nguồn, làm đậm từ chung; hỗ trợ Đóng/Escape và điều hướng nguồn.
- Loại trừ từng kết quả hoặc chọn nhiều; xem danh sách đã loại trừ và khôi phục.
- Loại trừ lưu localStorage theo ID báo cáo, không thay đổi PostgreSQL hoặc phần trăm gốc. JSON có trường review.excluded_result_ids để giữ thao tác thẩm định. Chưa có lưu thẩm định nhiều người dùng trên server.
- Highlight dựa trên chunk đã trích xuất; Bản gốc vẫn là PDF/DOCX xem riêng. Không khẳng định giữ nguyên bố cục bản gốc trong Văn bản đánh dấu.
- Kiểm chứng: npm test 9 passed, npm run build thành công, npm run test:e2e 1 passed trên Edge headless; kiểm tra dialog, Escape, loại trừ/khôi phục, xuất JSON, desktop/mobile. API trong browser test giả lập.
- Bản FastAPI ở 8000 đã trả HTML tham chiếu assets mới, HTTP 200. Không đổi API/schema/model.

## Cập nhật đối chiếu từng câu (08/11/2026)

- Web chuyển đơn vị truy vấn/kho nguồn sang câu, giữ offset trang/khối và cảnh báo riêng từng câu; semantic encode theo batch.
- Kho cũ dùng được qua dựng câu lúc kiểm tra; schema mới 4, báo cáo cũ giữ nguyên và cần kiểm tra lại để có kết quả câu.
- Không khôi phục chức năng một nguồn chính đã hoàn tác. Nhiều nguồn của một câu vẫn hiện các số nguồn.
- Ngưỡng hiện chưa được hiệu chỉnh cho câu; threshold_calibrated=false. Internet vẫn giới hạn số câu tìm và chỉ đối chiếu snippet.
- Kiểm chứng: 41 test backend, 10 test React, 2 test Edge đạt; build thành công và smoke test SBERT/FAISS thật đạt.
- Chi tiết: [DOI_CHIEU_TUNG_CAU.md](DOI_CHIEU_TUNG_CAU.md).
- Bước tiếp: dữ liệu câu thật, gán nhãn và hiệu chỉnh ngưỡng/đánh giá trước khi kết luận chất lượng phát hiện.

## Sửa tô đúng vùng trùng theo mẫu 1 (08/11/2026)

- Bổ sung app/services/alignment.py: căn chỉnh chuỗi từ với nguồn bằng SequenceMatcher, giữ offset gốc. Cụm thông thường cần ít nhất 3 từ và 12 ký tự; hai văn bản giống toàn bộ có thể dùng cụm ngắn từ 2 từ.
- API trả highlight_spans theo query_chunk_id, start/end và kind. Offset là code point Python; frontend chuyển sang UTF-16 khi cắt chuỗi.
- Cảnh báo lexical không có cụm đủ bằng chứng không được tô cả câu. Semantic không có cụm nguyên văn dùng loại semantic_sentence riêng, hiển thị xanh nhạt/gạch chấm và giải thích rõ.
- Frontend dùng mark inline, màu bám theo chữ và tự xuống dòng. Không dùng nút nhiều dòng có nền chữ nhật để tô toàn bộ câu. Ghép câu về cùng đoạn, giữ separator_before/after cho kết quả mới, bỏ nhãn Đoạn/khối/Câu khỏi phần nội dung đọc.
- Các phạm vi trùng chồng nhau thành một vùng có một nhãn đại diện; vẫn giữ các nguồn trong hộp đối chiếu và sidebar. Không áp dụng một nguồn chính cho toàn bộ câu/đoạn.
- Mở kết quả lịch sử được bổ sung alignment khi đọc dựa trên văn bản/nguồn đã lưu, không ghi đè snapshot hoặc tính lại điểm. Phải tải lại trang và mở lại kết quả để nhận dữ liệu mới.
- Điểm/cảnh báo và coverage gốc không bị đổi bởi việc căn chỉnh màu. Đây là vùng bằng chứng từ/cụm từ, không phải phép đo chất lượng phát hiện mới.
- Văn bản đánh dấu được dựng từ nội dung trích xuất, chưa overlay trực tiếp lên bố cục PDF/DOCX. Bản gốc vẫn xem riêng. Chất lượng trích xuất/OCR và dấu câu ảnh hưởng kết quả; Internet vẫn chỉ đối chiếu title/snippet.
- Kiểm chứng: 50 test backend/PostgreSQL tách biệt, 16 test frontend, 3 test Edge đều đạt; build thành công. Có kiểm tra đoạn dài chỉ tô hai cụm, phần còn lại để trắng, nguồn chồng nhau, mobile, emoji/NFD và đọc lịch sử không sửa dữ liệu.

## Khôi phục mốc “sửa lại giao diện dự án như này” (08/11/2026)

- Theo yêu cầu người dùng, quay về giao diện thẩm định ban đầu: STT cạnh đoạn, STT trên thẻ nguồn và trong hộp đối chiếu khớp nhau; giữ loại trừ/khôi phục, sắp xếp và chọn nhiều.
- Hoàn tác các thay đổi sau mốc này: một nguồn chính, tách câu, căn chỉnh cụm từ và tô inline. Backend quay lại đối chiếu theo chunk, schema 3.
- Giữ React/Vite, tích hợp FastAPI, bản xem gốc, kho tài liệu, .env và dữ liệu PostgreSQL.
- Không xóa/sửa kết quả lịch sử schema 4 đã được tạo; cần kiểm tra lại tài liệu để có kết quả theo cách cũ. Chức năng tách câu trong DOI_CHIEU_TUNG_CAU.md hiện là tài liệu lưu trữ, không còn áp dụng.
- Kiểm chứng: 29 test backend, 10 test React (có test STT đồng nhất), 1 test Edge đạt; build thành công và khởi động lại cổng 8000.

## Tìm Internet đầy đủ theo từng đợt (08/11/2026)

- Sửa giới hạn 5 đoạn/cả báo cáo thành tối đa 5 đoạn/đợt (SERPER_MAX_QUERIES), duyệt theo thứ tự văn bản và tiếp tục qua mọi đoạn đủ điều kiện.
- Upload không tự gửi nội dung ra ngoài. Người dùng xác nhận gửi truy vấn tới Serper/Google trước khi bắt đầu tìm Internet; đây là phương án an toàn sau khi kiểm duyệt tự động từ chối gửi toàn báo cáo không có đồng ý rõ ràng.
- Có tiến độ đã tìm/bỏ qua/còn lại, trạng thái từng đoạn và tạm dừng sau đợt hiện tại. Mở lịch sử để tiếp tục từ tiến độ đã lưu, kể cả báo cáo cũ đã tìm 5 đoạn rời rạc.
- Không đổi UI STT/đơn vị chunk hoặc điểm nội bộ. Internet vẫn so title/snippet; đoạn ngắn được ghi bỏ qua, không tính là đã kiểm tra.
- Kiểm chứng: 36 test backend, 14 test React, 2 test Edge đạt; provider/API giả lập, không gửi nội dung người dùng ra ngoài.
- Hướng dẫn: [INTERNET_BATCHES.md](INTERNET_BATCHES.md).

## Bỏ xác nhận, tự động tìm Internet sau kiểm tra (08/11/2026)

- Người dùng yêu cầu rõ xóa bước xác nhận và cho tự động gửi truy vấn báo cáo để tìm toàn bộ. Đây là ủy quyền mới thay cho cơ chế opt-in trước đó.
- Bỏ checkbox và allow_external_search ở API. Sau upload/đối chiếu nội bộ, frontend tự chạy các đợt Internet đến hết đoạn đủ điều kiện.
- Giữ tiến độ, giới hạn từng đợt, tạm dừng/tiếp tục và dừng khi lỗi API; lịch sử chưa hoàn tất tiếp tục bằng nút hiện có, không phải xác nhận.
- 36 test backend, 14 test React, 2 test Edge đạt; build thành công. Chỉ dùng Serper/API giả lập trong kiểm thử.
- Hướng dẫn hiện hành: [INTERNET_BATCHES.md](INTERNET_BATCHES.md).

## Bỏ phương pháp và ngưỡng khỏi form web (08/11/2026)

- Bỏ dropdown phương pháp, số ngưỡng và ghi chú validation trong form tải báo cáo; bỏ giá trị ngưỡng ở tóm tắt kết quả.
- Upload không gửi engine/threshold, backend tự dùng cấu hình .env hiện tại. Không sửa .env hoặc thuật toán.
- Kiểm chứng: 14 test React đạt, build thành công; kiểm tra Edge luồng upload và tìm Internet tự động.
