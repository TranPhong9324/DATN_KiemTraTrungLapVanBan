> ĐÃ HOÀN TÁC theo yêu cầu ngày 08/11/2026. Nội dung dưới đây chỉ lưu lịch sử triển khai; dự án hiện quay về đối chiếu theo đoạn và giao diện STT ở mốc “sửa lại giao diện dự án như này”.

# Đối chiếu từng câu (08/11/2026)

Web kiểm tra mới dùng câu làm đơn vị đối chiếu thay cho chunk khoảng 700 ký tự. CLI pipeline.py/preprocessor.py vẫn giữ chức năng cũ.

## Luồng xử lý

1. Trích xuất và lưu PDF/DOCX như trước; không migration hay sửa tài liệu đã lưu.
2. app/services/sentences.py ghép lại các chunk liên tiếp cùng trang/khối và có offset tiếp giáp. Nhờ vậy câu bị cắt bởi giới hạn chunk cũ được phục hồi trước khi tách.
3. Tách câu theo dấu kết thúc, dấu ngoặc/nháy, dòng trống và danh sách; giữ một số viết tắt phổ biến (TS., ThS., TP., v.v.), số thập phân và dòng xuống hàng của PDF.
4. Tạo ID câu ảo ổn định, ordinal, parent_chunk_ids và location.start/end/sentence/page/block/section. Offset trỏ vào văn bản đã trích xuất, không phải byte hoặc tọa độ trên PDF.
5. Lọc nội dung không thích hợp; kế thừa lý do loại trừ của chunk trước khi tách câu để không làm lọt mục lục.
6. So từng câu với câu trong kho bằng lexical hoặc SBERT/FAISS. Semantic encode các truy vấn theo batch, tái sử dụng index nếu kho không đổi.
7. Cảnh báo câu được giữ riêng, không gộp câu liền nhau. Mỗi câu có điểm và nguồn riêng; giao diện tô đúng câu có cảnh báo.

## Dữ liệu và tương thích

- Kho nguồn hiện có được dựng lại thành câu khi kiểm tra, không cần nhập lại.
- Kết quả mới: schema_version=4, comparison_unit=sentence, segmentation=vi-sentence-rules-v1.
- Để tương thích frontend, document_chunks, total_chunks, eligible_chunks, matched_chunks của báo cáo mới chứa/đếm các câu. original_storage_chunks là số chunk lưu trong CSDL của bản nộp.
- coverage là tỷ lệ ký tự trong câu có cảnh báo trên các câu đủ điều kiện; không đếm khoảng trắng phân cách câu, không cộng lặp khi một câu có nhiều nguồn. Không phải phần trăm đạo văn.
- Báo cáo cũ vẫn là snapshot theo đoạn; phải kiểm tra lại tài liệu để có kết quả theo câu.
- Không áp dụng lại chức năng một nguồn chính đã được người dùng hoàn tác. Một câu có thể có nhiều nguồn, tương ứng các số nguồn bên cạnh.
- Cấu hình mới trong .env.example: MAX_SENTENCES=5000, MAX_REFERENCE_SENTENCES=20000. Chạm giới hạn trả lỗi rõ ràng, không lưu bản nộp lỗi. MAX_CHUNKS/MAX_REFERENCE_CHUNKS vẫn giới hạn kho lưu trữ như trước.

## Giới hạn và đánh giá tiếp

- Đây là tách câu bằng quy tắc, chưa phải bộ phân tích cú pháp. Viết tắt lạ, công thức và OCR sai dấu câu có thể tách sai.
- Không ghép câu xuyên trang PDF hoặc khối DOCX; cần kiểm tra các câu chạy qua ranh giới đó.
- Câu quá dài vẫn có thể bị mô hình cắt theo giới hạn token. Không tự cắt tùy tiện câu thành nhiều mảnh để gọi là nhiều câu.
- Ngưỡng 0.08/0.68 được giữ theo cấu hình nhưng chưa được hiệu chỉnh lại cho câu. API trả threshold_calibrated=false và giao diện có ghi chú. Cần tập câu thật có nhãn để đo precision/recall/F1.
- Internet chỉ so câu với tiêu đề/snippet; số câu được tìm vẫn bị giới hạn bởi SERPER_MAX_QUERIES (mặc định 5). Không khẳng định đã tìm Internet cho toàn bộ câu hoặc đối chiếu toàn văn website.

## Kiểm chứng

- Backend/PostgreSQL tách biệt: 41 passed, gồm vị trí câu, viết tắt/thập phân, xuống dòng, ghép chunk cũ, lọc mục lục, ngân sách câu/rollback, không tô câu độc lập, điểm riêng từng câu và batching.
- React: 10 passed; build thành công.
- Edge headless: 2 passed (luồng cũ và báo cáo câu, desktop/mobile, hộp đối chiếu).
- SBERT/FAISS thật từ model cache đã chạy batch trên văn bản tổng hợp: câu nguyên văn đạt 1.0, câu độc lập có điểm thấp hơn. Đây là smoke test kỹ thuật, không phải báo cáo chất lượng tổng quát.

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
