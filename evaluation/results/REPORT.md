# Kết quả hiệu chỉnh ngưỡng ban đầu

> Đây là phép đo trên tập gán nhãn khởi đầu có kiểm soát. Ngưỡng cần được đo lại trên báo cáo thật do giảng viên gán nhãn trước khi nghiệm thu.

- Mô hình semantic: `keepitreal/vietnamese-sbert`
- Số cặp: 32 (validation: 16, test: 16)
- Kho truy xuất: 12 đoạn; 10 truy vấn

## lexical

Ngưỡng được chọn **chỉ bằng validation**: `0.08`.

| Tập | Precision | Recall | F1 | TP | FP | FN | TN |
|---|---:|---:|---:|---:|---:|---:|---:|
| validation | 0.7778 | 0.8750 | 0.8235 | 7 | 2 | 1 | 6 |
| test | 0.8750 | 0.8750 | 0.8750 | 7 | 1 | 1 | 7 |

## semantic

Ngưỡng được chọn **chỉ bằng validation**: `0.68`.

| Tập | Precision | Recall | F1 | TP | FP | FN | TN |
|---|---:|---:|---:|---:|---:|---:|---:|
| validation | 1.0000 | 0.8750 | 0.9333 | 7 | 0 | 1 | 8 |
| test | 1.0000 | 0.6250 | 0.7692 | 5 | 0 | 3 | 8 |

## Recall@k

| Bộ máy | Tập | R@1 | R@3 | R@5 |
|---|---|---:|---:|---:|
| lexical | validation | 1.0000 | 1.0000 | 1.0000 |
| lexical | test | 1.0000 | 1.0000 | 1.0000 |
| lexical | all | 1.0000 | 1.0000 | 1.0000 |
| semantic_faiss | validation | 0.6000 | 1.0000 | 1.0000 |
| semantic_faiss | test | 1.0000 | 1.0000 | 1.0000 |
| semantic_faiss | all | 0.8000 | 1.0000 | 1.0000 |

## Cách đọc ma trận nhầm lẫn

- TP: cảnh báo đúng; FP: cảnh báo nhầm; FN: bỏ sót; TN: không cảnh báo đúng.
- Precision cao giúp giảm cảnh báo nhầm; recall cao giúp giảm bỏ sót; F1 cân bằng hai mục tiêu.
- Recall@k đo tỷ lệ tài liệu liên quan xuất hiện trong k kết quả đầu của bước FAISS; chỉ số này độc lập với ngưỡng cảnh báo.
