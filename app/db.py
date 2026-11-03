"""PostgreSQL connection and explicit first-time schema initialization."""
import sys
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.engine import make_url

from app.config import Settings
from app.models import Base


class Database:
    def __init__(self, url):
        if make_url(url).get_backend_name() != "postgresql":
            raise ValueError("Ứng dụng yêu cầu PostgreSQL; không tự chuyển sang SQLite.")
        self.engine = create_engine(
            url, pool_pre_ping=True, pool_size=5, max_overflow=5,
            hide_parameters=True, connect_args={"connect_timeout": 5},
        )
        self.session = sessionmaker(self.engine, expire_on_commit=False)

    def verify(self):
        with self.engine.connect() as connection:
            connection.execute(text("SELECT 1"))
            # Check that schema initialization has actually been performed.
            for table in ("documents", "chunks", "checks"):
                if connection.scalar(text("SELECT to_regclass(:name)"), {"name": table}) is None:
                    raise RuntimeError("Chưa có bảng dữ liệu. Chạy python -m app.db init.")

    def initialize(self):
        Base.metadata.create_all(self.engine)


def main():
    if len(sys.argv) != 2 or sys.argv[1] not in {"init", "check"}:
        print("Cách dùng: python -m app.db init | check")
        return 2
    settings = Settings.load()
    if not settings.database_url:
        print("Chưa cấu hình PostgreSQL. Sao chép .env.example thành .env và nhập thông tin kết nối.")
        return 1
    db = Database(settings.database_url)
    try:
        if sys.argv[1] == "init":
            db.initialize()
        db.verify()
        print("PostgreSQL: kết nối thành công; các bảng documents, chunks, checks đã sẵn sàng.")
        return 0
    except Exception:
        print("Không kết nối được hoặc chưa có schema. Kiểm tra dịch vụ PostgreSQL, database, tài khoản và mật khẩu trong .env. Sau đó chạy python -m app.db init.")
        return 1
    finally:
        db.engine.dispose()


if __name__ == "__main__":
    raise SystemExit(main())
