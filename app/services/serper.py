from __future__ import annotations

from dataclasses import dataclass
import re
import json
import logging
import sqlite3
import unicodedata
from pathlib import Path
import requests


class SerperError(RuntimeError):
    pass


@dataclass(frozen=True)
class SerperClient:
    api_key: str
    timeout: int = 20
    cache_path: Path | None = None

    def _cache(self, key: str, payload: dict | None = None) -> dict | None:
        if self.cache_path is None:
            return None
        try:
            self.cache_path.parent.mkdir(parents=True, exist_ok=True)
            with sqlite3.connect(self.cache_path, timeout=10) as connection:
                connection.execute("CREATE TABLE IF NOT EXISTS searches (key TEXT PRIMARY KEY, payload TEXT NOT NULL, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)")
                if payload is not None:
                    connection.execute("INSERT OR REPLACE INTO searches (key, payload) VALUES (?, ?)", (key, json.dumps(payload, ensure_ascii=False)))
                    return None
                row = connection.execute("SELECT payload FROM searches WHERE key = ?", (key,)).fetchone()
                if row:
                    cached = json.loads(row[0])
                    if isinstance(cached, dict) and isinstance(cached.get("organic"), list):
                        return cached
        except (OSError, sqlite3.Error, ValueError):
            logging.getLogger(__name__).warning("Internet search cache unavailable; continuing without cache")
        return None

    def search(self, query: str, *, num: int = 10, country: str = "vn", language: str = "vi") -> dict:
        query = " ".join(query.split()).strip()
        if not query:
            raise SerperError("Truy vấn tìm kiếm đang trống.")
        if len(query) > 400:
            raise SerperError("Truy vấn tìm kiếm quá dài; hãy gửi một cụm từ đặc trưng ngắn hơn.")
        num = max(1, min(int(num), 10))
        cache_key = json.dumps(["serper-v1", unicodedata.normalize("NFC", query).casefold(), num, country, language], ensure_ascii=False)
        cached = self._cache(cache_key)
        if cached is not None:
            return {**cached, "cache_hit": True}
        def request(search_query: str) -> dict:
            try:
                response = requests.post(
                    "https://google.serper.dev/search",
                    headers={"X-API-KEY": self.api_key, "Content-Type": "application/json"},
                    json={"q": search_query, "gl": country, "hl": language, "num": num},
                    timeout=self.timeout,
                )
            except requests.RequestException as error:
                raise SerperError("Không kết nối được Serper. Kiểm tra mạng và thử lại.") from error
            if response.status_code in {401, 403}:
                raise SerperError("Serper API key không hợp lệ hoặc chưa được cấp quyền.")
            if response.status_code == 429:
                raise SerperError("Serper đã giới hạn tốc độ hoặc hết credits. Hãy kiểm tra tài khoản.")
            if response.status_code >= 400:
                raise SerperError(f"Serper trả về lỗi HTTP {response.status_code}.")
            try:
                return response.json()
            except ValueError as error:
                raise SerperError("Serper trả về dữ liệu không hợp lệ.") from error

        payload = request(query)
        # Exact phrases are precise but often return zero results after OCR or
        # translation changes a single word. Retry once without quotes so the
        # automatic Internet stage still produces candidate sources.
        if not payload.get("organic") and query.startswith('"') and query.endswith('"'):
            payload = request(query[1:-1])
            query = query[1:-1]
        result = {
            "query": query,
            "provider": "serper",
            "organic": [
                {
                    "position": item.get("position"),
                    "title": item.get("title", ""),
                    "link": item.get("link", ""),
                    "snippet": item.get("snippet", ""),
                    "date": item.get("date"),
                    "source": item.get("source"),
                }
                for item in payload.get("organic", [])
                if item.get("link")
            ],
        }
        self._cache(cache_key, result)
        return {**result, "cache_hit": False}


def web_query_from_text(text: str) -> str | None:
    """Build a bounded exact-phrase query from one extracted chunk."""
    words = re.findall(r"\w+", text or "", flags=re.UNICODE)
    if len(words) < 10:
        return None
    # Keep the exact phrase distinctive without making it so long that a
    # slightly different web copy cannot be found.
    phrase = " ".join(words[:16])
    return f'"{phrase}"'
