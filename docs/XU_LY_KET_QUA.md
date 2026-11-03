# Hoàn thiện cách tính và trình bày kết quả

## Luồng xử lý mới

1. Trích xuất tài liệu thành các chunk có `ordinal` và vị trí.
2. Loại trước khi tìm kiếm các chunk thuộc mục lục, danh mục bảng/hình, tài liệu tham khảo và một số câu mẫu ngắn. Việc lọc trước giúp chúng không chiếm vị trí top-k của FAISS.
3. Tìm top-k bằng lexical hoặc SBERT/FAISS và áp dụng ngưỡng tương ứng.
4. Với mỗi chunk truy vấn và mỗi tài liệu nguồn, chỉ giữ ứng viên có điểm cao nhất.
5. Gộp các kết quả khi chunk truy vấn liền nhau và chunk nguồn trùng hoặc liền nhau.
6. Giới hạn tối đa 5 cảnh báo trên một nguồn và 50 cảnh báo trong một báo cáo; trường `suppressed_alerts` cho biết số cảnh báo đã ẩn.
7. Xếp hạng tài liệu nguồn theo số ký tự được đối chiếu, số chunk và điểm cao nhất.

## Các trường kết quả chính

- `alert_type`: `lexical_overlap` hoặc `semantic_similarity`.
- `alert_label`: nhãn tiếng Việt hiển thị trên giao diện.
- `eligible_chunks`: số chunk còn lại sau bộ lọc.
- `ignored_chunks`: số chunk bỏ qua theo từng lý do.
- `matched_chunks`: số chunk đủ điều kiện có ít nhất một cảnh báo.
- `coverage`: tỷ lệ ký tự của chunk được cảnh báo trên tổng ký tự đủ điều kiện.
- `matches[].chunk_count`: số chunk liền nhau đã được gộp.
- `matches[].score`: điểm cao nhất trong nhóm.
- `matches[].average_score`: điểm trung bình trong nhóm.
- `sources[].rank`: thứ hạng nguồn.
- `sources[].coverage`: tỷ lệ ký tự của báo cáo có cảnh báo với nguồn đó.

`coverage` là tỷ lệ nội dung bị cảnh báo, không phải kết luận phần trăm đạo văn. Người đọc vẫn phải xem hai đoạn văn và nguồn trước khi kết luận.

## Giới hạn bộ lọc

Bộ lọc hoạt động tốt nhất với DOCX có Heading vì tên mục được giữ trong `location.section`. Với PDF không có cấu trúc, hệ thống nhận diện mục lục qua dấu chấm dẫn trang và nhận diện một số tiêu đề/câu mẫu. Tập quy tắc cần được bổ sung từ lỗi thực tế; không nên dùng bộ lọc quá rộng vì có thể loại nhầm nội dung nghiên cứu hợp lệ.
