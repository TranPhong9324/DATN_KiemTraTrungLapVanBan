from io import BytesIO
import os
from uuid import uuid4

import docx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

from app.config import Settings
from app.db import Database
from app.main import create_app


def make_docx(*paragraphs, table=False):
    document = docx.Document()
    for paragraph in paragraphs:
        document.add_paragraph(paragraph)
    if table:
        row = document.add_table(rows=1, cols=2).rows[0]
        row.cells[0].text, row.cells[1].text = "Tên phương pháp", "Đối chiếu ngữ nghĩa"
    stream = BytesIO()
    document.save(stream)
    return stream.getvalue()


def make_pdf(pages):
    objects = [b"<< /Type /Catalog /Pages 2 0 R >>", b""]
    kids = []
    for value in pages:
        page_id = len(objects) + 1
        kids.append(f"{page_id} 0 R")
        objects.append(f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 << /Type /Font /Subtype /Type1 /BaseFont /Helvetica >> >> >> /Contents {page_id + 1} 0 R >>".encode())
        content = f"BT /F1 12 Tf 72 700 Td ({value}) Tj ET".encode("ascii") if value else b""
        objects.append(f"<< /Length {len(content)} >>\nstream\n".encode() + content + b"\nendstream")
    objects[1] = f"<< /Type /Pages /Kids [{' '.join(kids)}] /Count {len(pages)} >>".encode()
    result = b"%PDF-1.4\n"
    positions = [0]
    for index, obj in enumerate(objects, 1):
        positions.append(len(result))
        result += f"{index} 0 obj\n".encode() + obj + b"\nendobj\n"
    offset = len(result)
    result += f"xref\n0 {len(positions)}\n0000000000 65535 f \n".encode()
    result += b"".join(f"{position:010} 00000 n \n".encode() for position in positions[1:])
    result += f"trailer\n<< /Size {len(positions)} /Root 1 0 R >>\nstartxref\n{offset}\n%%EOF".encode()
    return result


@pytest.fixture
def postgres_db():
    url = os.getenv("TEST_DATABASE_URL")
    if not url:
        pytest.skip("Set TEST_DATABASE_URL or run scripts/test_postgres.py for real PostgreSQL tests.")
    schema = "checker_test_" + uuid4().hex
    admin = create_engine(url, hide_parameters=True)
    with admin.begin() as connection:
        connection.execute(text(f'CREATE SCHEMA "{schema}"'))
    test_url = make_url(url).update_query_dict({"options": f"-csearch_path={schema}"})
    database = Database(test_url)
    database.initialize()
    try:
        yield database
    finally:
        database.engine.dispose()
        # Only the unique schema created by this fixture is removed.
        with admin.begin() as connection:
            connection.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
        admin.dispose()


@pytest.fixture
def web(tmp_path, postgres_db):
    settings = Settings(upload_dir=tmp_path / "uploads", max_upload_mb=1)
    app = create_app(settings, postgres_db)
    with TestClient(app) as client:
        yield client, app, settings
