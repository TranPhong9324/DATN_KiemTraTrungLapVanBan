"""Safe, read-only browser previews for uploaded DOCX documents."""
from base64 import b64encode
from html import escape
from pathlib import Path

import docx
from docx.table import Table
from docx.text.paragraph import Paragraph
from docx.oxml.ns import qn


class PreviewError(RuntimeError):
    pass


def _run_html(run, paragraph) -> str:
    parts = []
    text = escape(run.text).replace("\n", "<br>")
    if text:
        if run.underline:
            text = f"<u>{text}</u>"
        if run.italic:
            text = f"<em>{text}</em>"
        if run.bold:
            text = f"<strong>{text}</strong>"
        parts.append(text)
    for blip in run._element.xpath(".//*[local-name()='blip']"):
        relation_id = blip.get(qn("r:embed"))
        image_part = paragraph.part.related_parts.get(relation_id)
        if image_part is not None:
            mime = getattr(image_part, "content_type", "image/png")
            encoded = b64encode(image_part.blob).decode("ascii")
            parts.append(f'<img src="data:{escape(mime)};base64,{encoded}" alt="Hình trong tài liệu">')
    return "".join(parts)


def _paragraph_html(paragraph: Paragraph) -> str:
    alignment = {1: "center", 2: "right", 3: "justify"}.get(paragraph.alignment, "left")
    style = (paragraph.style.name if paragraph.style else "Normal").lower()
    tag = "p"
    if style.startswith("heading"):
        try:
            level = min(6, max(1, int(style.split()[-1])))
        except ValueError:
            level = 2
        tag = f"h{level}"
    body = "".join(_run_html(run, paragraph) for run in paragraph.runs) or "&nbsp;"
    classes = f"align-{alignment}" + (" list-item" if "list" in style else "")
    return f'<{tag} class="{classes}">{body}</{tag}>'


def _table_html(table: Table) -> str:
    rows = []
    for row in table.rows:
        cells = []
        for cell in row.cells:
            content = "".join(_paragraph_html(paragraph) for paragraph in cell.paragraphs)
            cells.append(f"<td>{content}</td>")
        rows.append("<tr>" + "".join(cells) + "</tr>")
    return '<table class="docx-table">' + "".join(rows) + "</table>"


def render_docx_html(source: Path, upload_dir: Path, title: str) -> str:
    source = source.resolve()
    if source.parent != upload_dir.resolve() or not source.is_file() or source.suffix.lower() != ".docx":
        raise PreviewError("Tệp DOCX gốc không còn trong kho lưu trữ.")
    try:
        document = docx.Document(source)
        body = [_table_html(block) if isinstance(block, Table) else _paragraph_html(block) for block in document.iter_inner_content()]
    except Exception as error:
        raise PreviewError("Không thể tạo bản xem trước từ DOCX.") from error
    return ('<!doctype html><html lang="vi"><head><meta charset="utf-8">'
            f'<title>{escape(title)}</title><link rel="stylesheet" href="/static/doc-preview.css"></head>'
            f'<body><main class="docx-page">{"".join(body)}</main></body></html>')
