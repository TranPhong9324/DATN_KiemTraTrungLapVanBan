# Hiệu chỉnh ngưỡng lexical và semantic

Tập này tạo một quy trình đo lặp lại được thay vì chọn ngưỡng `0.65` hoặc `0.80` theo cảm tính.

```powershell
.\.venv\Scripts\python.exe -m evaluation.evaluate
```

Quy trình thực hiện:

1. `pairs.jsonl` chứa cặp đoạn văn có nhãn `1` (trùng/tương đương) hoặc `0` (không trùng). Các nhóm nội dung của validation và test không giao nhau.
2. Với lexical, script dùng đúng unigram + bigram + cosine của web. Với semantic, script dùng đúng tiền xử lý tiếng Việt, model SBERT và cosine trên embedding chuẩn hóa.
3. Script thử các ngưỡng từ `0.00` đến `1.00`, bước `0.01`, **chỉ trên validation**. Tiêu chí là F1 cao nhất; nếu hòa thì ưu tiên precision rồi ngưỡng cao hơn.
4. Ngưỡng đã chọn được giữ nguyên khi đo test. Test không được dùng để sửa ngưỡng.
5. `retrieval_corpus.jsonl` và `retrieval_queries.jsonl` đo Recall@1, Recall@3, Recall@5. Semantic truy xuất qua đúng `VectorStore`/FAISS của dự án.

Đầu ra nằm trong `evaluation/results/`:

- `REPORT.md`: bảng kết quả dễ đưa vào báo cáo.
- `metrics.json`: số liệu có cấu trúc.
- `pair_predictions.json`: điểm và dự đoán của từng mẫu để xem FP/FN.

Tập hiện tại là **tập khởi đầu có kiểm soát**, dùng để chứng minh quy trình và phát hiện lỗi. Trước khi chốt ngưỡng cho đồ án, cần thay hoặc bổ sung bằng các cặp chunk từ báo cáo thật, do ít nhất hai người gán nhãn và thống nhất các trường hợp bất đồng. Không được báo cáo số liệu của tập nhỏ này như chất lượng cuối cùng của hệ thống.
