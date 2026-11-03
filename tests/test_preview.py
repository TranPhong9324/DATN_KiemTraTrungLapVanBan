from pathlib import Path

from app.services.preview import render_docx_html
from conftest import make_docx


def test_docx_preview_preserves_text_table_and_escapes_html(tmp_path):
    upload_dir = tmp_path / "uploads"
    upload_dir.mkdir()
    source = upload_dir / "sample.docx"
    source.write_bytes(make_docx("Tiêu đề <không phải HTML>", table=True))
    html = render_docx_html(source, upload_dir, "sample.docx")
    assert "Tiêu đề &lt;không phải HTML&gt;" in html
    assert "<table" in html
    assert "Đối chiếu ngữ nghĩa" in html
    assert '<script' not in html
