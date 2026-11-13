# Tìm Internet tự động theo từng đợt

## Cách dùng

- Bấm kiểm tra báo cáo như trước. Khi đối chiếu nội bộ xong và Serper đã được cấu hình, web tự tìm Internet qua tất cả các đoạn đủ điều kiện. Không có checkbox hay bước xác nhận.
- SERPER_MAX_QUERIES=5 là tối đa 5 đoạn mỗi đợt; các đợt chạy lần lượt theo thứ tự văn bản đến khi hoàn tất.
- Có tiến độ đã tìm/bỏ qua/còn lại và trạng thái từng đoạn.
- “Tạm dừng sau đợt này” dừng sau khi đợt đang chạy trả về. Có thể bấm tiếp tục mà không cần xác nhận.
- Mở một kết quả lịch sử chưa hoàn tất rồi bấm “Tiếp tục kiểm tra Internet” để bổ sung phần còn lại; các truy vấn đã lưu thành công không bị tìm lại.
- Nếu API lỗi hoặc hết quota, hệ thống giữ tiến độ và dừng, không thử vô hạn. Sau khi xử lý nguyên nhân, bấm tiếp tục.
- Khi đóng trang, server có thể xử lý xong đợt đang nhận; không có worker tự chạy các đợt còn lại. Mở lại báo cáo để tiếp tục.

## Phạm vi và dữ liệu

- Người dùng đã yêu cầu rõ ngày 08/11/2026 bỏ xác nhận và tự động tìm toàn báo cáo. Cơ chế xác nhận từng báo cáo trước đó đã được gỡ theo ủy quyền mới này.
- Truy vấn lấy nội dung báo cáo và gửi tới Serper/Google khi tự động tìm sau upload.
- Đoạn dưới 10 từ được ghi “Bỏ qua — đoạn quá ngắn”; mục lục/tài liệu tham khảo/nội dung mẫu bị bộ lọc loại không thuộc phạm vi tìm.
- Mỗi đoạn dùng cụm tối đa 16 từ đầu để tìm. Provider có thể thử lại không có dấu nháy, nên số lượt API có thể lớn hơn số đoạn đã tìm.
- Internet vẫn đối chiếu title/snippet, chưa so khớp toàn văn website. Không tô màu chưa chứng minh không trùng.
- Không đổi điểm/coverage nội bộ. Chỉ bổ sung kết quả Internet và tiến độ sau mỗi đợt.
- Không đổi schema PostgreSQL hay .env hiện có. Kết quả cũ tìm vài đoạn rời rạc vẫn được tiếp tục để điền phần chưa tìm.
- POST /api/checks/{id}/internet/continue không cần body xác nhận.

## Kiểm chứng

36 test backend/PostgreSQL, 14 test React và 2 test Edge đạt; build thành công. Test tự động tìm sau upload, tạm dừng/tiếp tục, lưu tiến độ, lỗi API và tìm đến đoạn cuối dùng provider/API giả lập.


## Local Internet search cache

Successful Serper results (including empty results) are stored in `storage/internet_cache.sqlite3`. Repeated queries reuse this cache across reports and server restarts, without another API call. Keys normalize whitespace, Unicode and case, and include result count, country and language. Similarity is recalculated for each document chunk; only its highest-scoring web source is kept. Errors are not cached. Cached results have no automatic expiry; delete this file while the server is stopped to refresh all searches. Existing report history is unchanged, and reports saved before this feature do not automatically populate the cache.
