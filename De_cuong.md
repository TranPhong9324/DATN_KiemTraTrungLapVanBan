	TRƯỜNG ĐẠI HỌC ĐÀ LẠT
		KHOA CÔNG NGHỆ THÔNG TIN

ĐỀ CƯƠNG THỰC HIỆN ĐỒ ÁN 

Tên đề tài: Xây dựng hệ thống tự động kiểm tra và cảnh báo trùng lặp văn bản trong báo cáo đồ án
Sinh viên thực hiện:
STT	Họ và Tên	MSSV	Lớp	Email
1	Trần Văn Ngọc Phong	2212441	CTK46A	2212441@dlu.edu.vn
2	Nguyễn Hoàng Hà	2212362	CTK46A	2212362@dlu.edu.vn
3	Lã Triều Nguyên	2212428	CTK46A	2212428@dlu.edu.vn
Giáo viên hướng dẫn: La Quốc Thắng
1. Mục tiêu đề tài
•	Tự động tiếp nhận, trích xuất và lập chỉ mục nội dung báo cáo PDF/DOCX.
•	Phát hiện các đoạn có mức tương đồng ngữ nghĩa cao với kho đồ án trước, kể cả trường hợp diễn đạt lại.
•	Cung cấp báo cáo cảnh báo có nguồn đối chiếu, mức độ tương đồng và vị trí đoạn văn để hỗ trợ giảng viên thẩm định.
2. Nội dung đề tài
•	Phân tích yêu cầu, quy định bảo mật và phạm vi sử dụng dữ liệu báo cáo đồ án.
•	Xây dựng chức năng tải lên, trích xuất văn bản từ PDF/DOCX; hỗ trợ OCR cơ bản đối với PDF ảnh khi cần.
•	Tiền xử lý văn bản tiếng Việt, loại bỏ phần ít ý nghĩa, chia đoạn/cửa sổ và lưu metadata trang/mục.
•	Sinh text embedding; xây dựng kho vector FAISS/Qdrant cho báo cáo các khóa trước.
•	Thiết kế thuật toán truy vấn, ngưỡng cảnh báo, gom nhóm đoạn trùng và xếp hạng nguồn tương đồng.
•	Xây dựng giao diện hiển thị báo cáo: phần trăm/điểm tương đồng, đoạn nghi vấn, nguồn đối chiếu và liên kết vị trí.
•	Xây dựng tập kiểm thử gồm sao chép trực tiếp, diễn đạt lại và nội dung độc lập; đánh giá Precision/Recall/F1 và thời gian xử lý.
3. Phần mềm và công cụ sử dụng
•	Python; PyMuPDF/pdfplumber, python-docx; Tesseract OCR.
•	Sentence-transformers hoặc mô hình embedding tiếng Việt/đa ngôn ngữ.
•	FAISS hoặc Qdrant; PostgreSQL để quản lý tài liệu và kết quả.
•	FastAPI; React/Streamlit cho giao diện báo cáo.
•	Docker, Git/GitHub; pytest và bộ dữ liệu kiểm thử tự xây dựng.
4. Dự kiến kết quả đạt được
•	Kho báo cáo được trích xuất, chia đoạn, gắn metadata và lập chỉ mục vector.
•	Hệ thống tải PDF/DOCX, tự động so sánh và tạo báo cáo cảnh báo có trích dẫn nguồn/đoạn.
•	Bộ ngưỡng và tiêu chí đánh giá; báo cáo thực nghiệm trên các trường hợp sao chép, paraphrase và không trùng.
•	Cơ chế phân quyền/bảo mật cơ bản; mã nguồn, tài liệu cài đặt, hướng dẫn sử dụng và báo cáo ĐATN.
5. Tài liệu tham khảo
[1] Python Documentation: https://www.python.org/doc/
[2] PyMuPDF Documentation: https://pymupdf.readthedocs.io/
[3] pdfplumber Documentation: https://github.com/jsvine/pdfplumber
[4] python-docx Documentation: https://python-docx.readthedocs.io/
[5] Tesseract OCR Documentation: https://tesseract-ocr.github.io/
[6] Sentence-Transformers Documentation: https://www.sbert.net/
[7] FAISS (Facebook AI Similarity Search) Documentation: https://faiss.ai/
[8] Qdrant Vector Database Documentation: https://qdrant.tech/documentation/
[9] PostgreSQL Documentation: https://www.postgresql.org/docs/
[10] FastAPI Documentation: https://fastapi.tiangolo.com/
[11] React Documentation: https://react.dev/
[12] Streamlit Documentation: https://docs.streamlit.io/
[13] Docker Documentation: https://docs.docker.com/
[14] Git Documentation: https://git-scm.com/doc
[15] pytest Documentation: https://docs.pytest.org/
[16]: Đệ, T. C., Lâm, L. V., Trị, T. C., Bảo, B. V. Q., & Hưng, N. G. (2014). PHÁT TRIỂN HỆ THỐNG PHÁT HIỆN ĐẠO VĂN CHO TRƯỜNG ĐẠI HỌC VIỆT NAM. Tạp chí Khoa học Đại học Cần Thơ, (35), 31-39.
[17]: Nguyễn, N., Nguyễn, X. T., & Đinh, Đ. (2016). Vietnamese plagiarism detection method. Kỷ yếu Hội nghị Quốc tế lần thứ 8 về Khoa học và Kỹ thuật Hệ thống (KSE), 241-246.
[18]: Trần, Q. Đ., Vũ, V. S., & Nguyễn, K. A. (2018). Implementation of the Plagiarism Detection Software used in Universities. Tạp chí Khoa học và Công nghệ Đại học Bách Khoa Hà Nội, 128, 12-18.

Lâm Đồng, ngày 08 tháng 08 năm 2026 
	Giáo viên hướng dẫn	SV Thực hiện 
	(Ký tên)	(Ký tên) 
 


	BCN Khoa
	(Ký tên)

