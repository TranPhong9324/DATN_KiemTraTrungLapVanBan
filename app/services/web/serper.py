from __future__ import annotations

from dataclasses import dataclass
import re
import requests


class SerperError(RuntimeError):
    pass


@dataclass(frozen=True)
class SerperClient:
    api_key: str
    timeout: int = 20

    def search(self, query: str, *, num: int = 10, country: str = "vn", language: str = "vi") -> dict:
        query = " ".join(query.split()).strip()
        if not query:
            raise SerperError("Truy vấn tìm kiếm đang trống.")
        if len(query) > 400:
            raise SerperError("Truy vấn tìm kiếm quá dài; hãy gửi một cụm từ đặc trưng ngắn hơn.")
        num = max(1, min(int(num), 10))
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
        return {
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


QUERY_WORDS = 12


def web_query_from_text(text: str) -> str | None:
    """Câu truy vấn cụm chính xác từ một đoạn: lấy cửa sổ 12 từ nhiều từ nội dung nhất, không cứ phải là đầu đoạn.

    Đầu đoạn thường là câu dẫn ("Trong chương này, chúng ta sẽ...") nên tìm kiếm trả về trang không liên quan; cửa sổ
    nhiều danh từ/thuật ngữ nhất dễ trùng đúng trang gốc. Cụm đủ ngắn để bản sao hơi khác vẫn tìm được."""
    from app.services.matching.shingles import STOPWORDS

    words = re.findall(r"\w+", text or "", flags=re.UNICODE)
    if len(words) < 10:
        return None
    size = min(QUERY_WORDS, len(words))
    best, best_score = 0, -1
    for start in range(len(words) - size + 1):
        window = words[start:start + size]
        score = sum(w.lower() not in STOPWORDS and not w.isdigit() for w in window)
        if score > best_score:  # hòa thì lấy cửa sổ đầu tiên
            best, best_score = start, score
    return '"' + " ".join(words[best:best + size]) + '"'
