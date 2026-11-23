"""Tải trang web công khai và trích văn bản để lưu vào CSDL làm nguồn đối chiếu.

Máy chủ tự gọi địa chỉ lấy từ kết quả tìm kiếm (hoặc do quản trị nhập) nên phải chống SSRF:
  - chỉ http/https, cổng 80/443, không có user:pass trong URL;
  - mọi địa chỉ IP phân giải được phải là địa chỉ công khai (không loopback, mạng nội bộ, link-local, metadata cloud);
  - kiểm tra lại ở từng lần chuyển hướng (tối đa 4) và kiểm tra địa chỉ máy chủ thực sự đã kết nối;
  - giới hạn dung lượng, thời gian, kiểu nội dung; không gửi cookie/thông tin đăng nhập.
Giới hạn còn lại: giữa lúc kiểm tra DNS và lúc kết nối có một khoảng hở rất nhỏ (DNS rebinding); bước kiểm tra
địa chỉ thật sau kết nối chặn việc đọc dữ liệu từ máy nội bộ nhưng yêu cầu GET đã được gửi đi.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, replace
from hashlib import sha256
from html.parser import HTMLParser
from pathlib import Path
from tempfile import TemporaryDirectory
from urllib.parse import parse_qsl, unquote, urlencode, urljoin, urlsplit, urlunsplit
import ipaddress
import re
import logging
import socket
import unicodedata

import requests

from app.services.document.documents import DocumentError, extract_chunks, normalize, split_block, validate_file

logger = logging.getLogger(__name__)
MAX_REDIRECTS = 4
MAX_TEXT_CHARS = 400_000
MIN_LINE_WORDS = 6  # bỏ các dòng ngắn: menu, nút bấm, đường dẫn điều hướng
USER_AGENT = "DocumentChecker/1.0 (kiểm tra trùng lặp báo cáo đồ án; truy cập tự động)"
TRACKING_PARAMS = {"fbclid", "gclid", "msclkid", "mc_cid", "mc_eid", "igshid", "yclid", "_ga", "ref", "ref_src"}


class WebFetchError(RuntimeError):
    """Lỗi tải trang. `status` là mã HTTP nên trả cho người gọi API: 422 (địa chỉ/nội dung không dùng được), 502 (mạng)."""

    def __init__(self, message: str, status: int = 422):
        super().__init__(message)
        self.status = status


@dataclass
class WebPage:
    url: str
    title: str
    chunks: list[dict]
    size_bytes: int
    content_hash: str
    warnings: list[str]


def canonical_url(url: str) -> str:
    """Dạng chuẩn để so trùng: bỏ #fragment, tham số theo dõi (utm_*, fbclid...), cổng mặc định; chữ thường cho scheme/host."""
    raw = (url or "").strip()
    if not raw or len(raw) > 2048 or any(ord(c) < 33 for c in raw):
        raise WebFetchError("Địa chỉ web không hợp lệ.")
    try:
        parts = urlsplit(raw)  # ném ValueError với địa chỉ dị dạng như "http://[abc"
        raw.encode("utf-8")    # ký tự đại diện lẻ không mã hóa được
    except (ValueError, UnicodeError) as error:
        raise WebFetchError("Địa chỉ web không hợp lệ.") from error
    if parts.scheme.lower() not in {"http", "https"}:
        raise WebFetchError("Chỉ hỗ trợ địa chỉ http:// hoặc https://.")
    if not parts.hostname:
        raise WebFetchError("Địa chỉ web thiếu tên miền.")
    if parts.username or parts.password:
        raise WebFetchError("Địa chỉ web không được chứa tên đăng nhập/mật khẩu.")
    try:
        port = parts.port
        host = parts.hostname.encode("idna").decode("ascii").lower()
    except (ValueError, UnicodeError) as error:
        raise WebFetchError("Địa chỉ web không hợp lệ.") from error
    scheme = parts.scheme.lower()
    if port is not None and port not in {80, 443}:
        raise WebFetchError("Chỉ hỗ trợ cổng 80 và 443.")
    if port and ((scheme == "http" and port == 80) or (scheme == "https" and port == 443)):
        port = None
    netloc = f"[{host}]" if ":" in host else host
    if port:
        netloc += f":{port}"
    query = urlencode([(k, v) for k, v in parse_qsl(parts.query, keep_blank_values=True)
                       if not k.lower().startswith("utm_") and k.lower() not in TRACKING_PARAMS])
    result = urlunsplit((scheme, netloc, parts.path or "/", query, ""))
    try:
        result.encode("utf-8")
    except UnicodeError as error:
        raise WebFetchError("Địa chỉ web không hợp lệ.") from error
    return result


def _resolve(host: str, port: int) -> list[str]:
    try:
        return sorted({info[4][0] for info in socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)})
    except socket.gaierror as error:
        raise WebFetchError("Không phân giải được tên miền của trang web.", 502) from error


def _is_public(address: str) -> bool:
    try:
        ip = ipaddress.ip_address(address.split("%")[0])
    except ValueError:
        return False
    ip = getattr(ip, "ipv4_mapped", None) or ip
    return ip.is_global and not ip.is_multicast


def assert_public_host(url: str, resolver=_resolve):
    parts = urlsplit(url)
    host = parts.hostname
    port = parts.port or (443 if parts.scheme == "https" else 80)
    try:  # địa chỉ IP viết thẳng trong URL
        literal = [str(ipaddress.ip_address(host))]
    except ValueError:
        literal = None
    addresses = literal or resolver(host, port)
    if not addresses or not all(_is_public(address) for address in addresses):
        raise WebFetchError("Địa chỉ này trỏ tới mạng nội bộ hoặc địa chỉ không công khai nên không được tải.")


def _peer_address(response) -> str | None:
    try:
        return response.raw._connection.sock.getpeername()[0]
    except Exception:  # noqa: BLE001 - không đọc được thì dựa vào kết quả kiểm tra DNS trước đó
        try:
            return response.raw.connection.sock.getpeername()[0]
        except Exception:  # noqa: BLE001
            return None


# ---- HTML -> văn bản -------------------------------------------------------------------------------------------------

SKIP_TAGS = {"script", "style", "noscript", "svg", "template", "iframe", "canvas", "nav", "footer", "aside",
             "button", "select", "dialog", "video", "audio", "object", "embed", "map"}
BLOCK_TAGS = {"p", "div", "br", "li", "ul", "ol", "tr", "table", "section", "article", "main", "blockquote", "pre",
              "h1", "h2", "h3", "h4", "h5", "h6", "dd", "dt", "dl", "hr", "figcaption", "caption", "header", "td", "th"}
VOID_TAGS = {"br", "hr", "img", "input", "meta", "link", "area", "base", "col", "source", "track", "wbr", "embed"}


class _TextExtractor(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.lines: list[str] = []
        self._current: list[str] = []
        self._skip: list[str] = []
        self._in_title = False
        self.title_parts: list[str] = []
        self.first_h1: list[str] = []
        self._in_h1 = False
        self.charset: str | None = None

    def _flush(self):
        line = " ".join("".join(self._current).split())
        self._current = []
        if line:
            self.lines.append(line)

    def handle_starttag(self, tag, attrs):
        if tag == "meta":
            values = {key.lower(): (value or "") for key, value in attrs}
            if "charset" in values:
                self.charset = values["charset"]
            elif values.get("http-equiv", "").lower() == "content-type":
                match = re.search(r"charset=([\w-]+)", values.get("content", ""), re.I)
                if match:
                    self.charset = match.group(1)
            return
        if tag == "title":
            self._in_title = True
        if self._skip:
            if tag in SKIP_TAGS and tag not in VOID_TAGS:
                self._skip.append(tag)
            return
        if tag in SKIP_TAGS and tag not in VOID_TAGS:
            self._skip.append(tag)
            return
        if tag == "h1":
            self._in_h1 = True
        if tag in BLOCK_TAGS:
            self._flush()

    def handle_endtag(self, tag):
        if tag == "title":
            self._in_title = False
        if self._skip:
            if tag in self._skip:  # đóng cả các thẻ con chưa đóng bên trong, để không bị kẹt ở chế độ bỏ qua đến hết trang
                while self._skip.pop() != tag:
                    pass
            return
        if tag == "h1":
            self._in_h1 = False
        if tag in BLOCK_TAGS:
            self._flush()

    def handle_data(self, data):
        if self._in_title:
            self.title_parts.append(data)
            return
        if self._skip:
            return
        if self._in_h1 and sum(len(part) for part in self.first_h1) < 300:
            self.first_h1.append(data)
        self._current.append(data)

    def close(self):
        super().close()
        self._flush()


def html_to_text(html: str) -> tuple[str, str, str | None]:
    """Trả (tiêu đề, văn bản, charset khai báo trong thẻ meta). Văn bản: mỗi dòng một khối, đã bỏ menu/script/chân trang."""
    parser = _TextExtractor()
    parser.feed(html)
    parser.close()
    title = " ".join("".join(parser.title_parts).split()) or " ".join("".join(parser.first_h1).split())
    seen, lines = set(), []
    for line in parser.lines:
        line = unicodedata.normalize("NFC", line)
        if len(line.split()) < MIN_LINE_WORDS or line in seen:
            continue
        seen.add(line)
        lines.append(line)
    return title, "\n".join(lines)[:MAX_TEXT_CHARS], parser.charset


def text_to_chunks(text: str, chunk_chars: int) -> list[dict]:
    """Gộp các dòng liền nhau thành đoạn cỡ chunk_chars (giống độ chi tiết của đoạn trong tài liệu tải lên)."""
    chunks, buffer, block = [], "", 0

    def emit(value):
        nonlocal block
        block += 1
        chunks.extend(split_block(value, {"page": None, "block": block, "label": f"Đoạn {block} của trang web"}, chunk_chars))

    for line in text.splitlines():
        if buffer and len(buffer) + 1 + len(line) > chunk_chars:
            emit(buffer)
            buffer = ""
        buffer = f"{buffer} {line}".strip() if buffer else line
    if buffer:
        emit(buffer)
    return chunks


def _decode(body: bytes, header_charset: str | None) -> tuple[str, str | None]:
    sniff = body[:4096].decode("ascii", errors="ignore")
    match = re.search(r"charset=[\"']?([\w-]+)", sniff, re.I)
    for charset in (header_charset, match.group(1) if match else None, "utf-8"):
        if not charset:
            continue
        try:
            return body.decode(charset), charset
        except (LookupError, UnicodeDecodeError):
            continue
    return body.decode("utf-8", errors="replace"), None


# ---- Tải trang -------------------------------------------------------------------------------------------------------

def _download(url: str, timeout: int, max_bytes: int, session=None, resolver=_resolve):
    own = session is None
    session = session or requests.Session()
    session.max_redirects = MAX_REDIRECTS
    headers = {"User-Agent": USER_AGENT, "Accept": "text/html,application/xhtml+xml,text/plain;q=0.8,application/pdf;q=0.6,*/*;q=0.1",
               "Accept-Language": "vi,en;q=0.7"}
    try:
        current = canonical_url(url)
        for _ in range(MAX_REDIRECTS + 1):
            assert_public_host(current, resolver)
            try:
                response = session.get(current, headers=headers, timeout=timeout, stream=True, allow_redirects=False)
            except requests.RequestException as error:
                raise WebFetchError("Không tải được trang web (lỗi kết nối hoặc quá thời gian).", 502) from error
            with response:
                if response.is_redirect or response.status_code in {301, 302, 303, 307, 308}:
                    location = response.headers.get("Location")
                    if not location:
                        raise WebFetchError("Trang web chuyển hướng không hợp lệ.", 502)
                    current = canonical_url(urljoin(current, location))
                    continue
                if not requests.utils.select_proxy(current, requests.utils.getproxies()):
                    peer = _peer_address(response)
                    if peer is not None and not _is_public(peer):
                        raise WebFetchError("Máy chủ đích nằm trong mạng nội bộ nên không được tải.")
                if response.status_code != 200:
                    raise WebFetchError(f"Trang web trả về mã lỗi HTTP {response.status_code}.", 502)
                kind = response.headers.get("Content-Type", "").split(";")[0].strip().lower()
                if kind not in {"text/html", "application/xhtml+xml", "text/plain", "application/pdf"}:
                    raise WebFetchError("Chỉ lưu trang HTML, văn bản thuần hoặc PDF.")
                declared = response.headers.get("Content-Length", "")
                if declared.isdigit() and int(declared) > max_bytes:
                    raise WebFetchError("Trang web vượt giới hạn dung lượng cho phép.")
                body = bytearray()
                try:
                    for block in response.iter_content(65536):
                        body.extend(block)
                        if len(body) > max_bytes:
                            raise WebFetchError("Trang web vượt giới hạn dung lượng cho phép.")
                except requests.RequestException as error:
                    raise WebFetchError("Quá trình tải trang web bị gián đoạn.", 502) from error
                charset = re.search(r"charset=([\w-]+)", response.headers.get("Content-Type", ""), re.I)
                return current, kind, bytes(body), charset.group(1) if charset else None
        raise WebFetchError("Trang web chuyển hướng quá nhiều lần.", 502)
    finally:
        if own:
            session.close()


def fetch_page(url: str, settings, *, session=None, resolver=_resolve) -> WebPage:
    """Tải một trang rồi tách thành các đoạn. Ném WebFetchError nếu không dùng được."""
    max_bytes = settings.web_max_page_mb * 1024 * 1024
    final, kind, body, header_charset = _download(url, settings.web_fetch_timeout, max_bytes, session, resolver)
    warnings: list[str] = []
    if kind == "application/pdf":
        with TemporaryDirectory() as directory:
            path = Path(directory) / "page.pdf"
            path.write_bytes(body)
            try:
                validate_file(path, ".pdf", max_bytes)
                # Không chạy OCR cho PDF tải từ web: chậm và dễ vượt thời gian chờ.
                extracted = extract_chunks(path, replace(settings, enable_ocr=False))
            except DocumentError as error:
                raise WebFetchError(f"Không đọc được PDF từ trang web: {error}") from error
        chunks, warnings = extracted.chunks, extracted.warnings
        name = unquote(Path(urlsplit(final).path).name) or urlsplit(final).hostname
        title = name
    else:
        if kind == "text/plain":
            text, _ = _decode(body, header_charset)
            title, text = "", "\n".join(" ".join(line.split()) for line in text.splitlines() if len(line.split()) >= MIN_LINE_WORDS)[:MAX_TEXT_CHARS]
        else:
            text, _ = _decode(body, header_charset)
            title, text, _charset = html_to_text(text)
        chunks = text_to_chunks(text, settings.chunk_chars)
        title = title or urlsplit(final).hostname or final
    if not chunks:
        raise WebFetchError("Trang web không có đủ văn bản để lưu (có thể nội dung được tải bằng JavaScript hoặc cần đăng nhập).")
    digest = sha256("\n".join(normalize(chunk["text"]) for chunk in chunks).encode("utf-8")).hexdigest()
    return WebPage(url=final, title=title[:240], chunks=chunks, size_bytes=len(body), content_hash=digest, warnings=warnings)


def fetch_pages(urls: list[str], settings, workers: int = 4, **kwargs) -> dict[str, WebPage | WebFetchError]:
    """Tải song song nhiều trang. Kết quả theo URL yêu cầu; lỗi từng trang không làm hỏng các trang khác."""
    def one(url):
        try:
            return fetch_page(url, settings, **kwargs)
        except WebFetchError as error:
            return error
        except Exception as error:  # noqa: BLE001 - không để một trang lạ làm hỏng cả lần kiểm tra
            logger.exception("Không xử lý được trang web %s", url)
            return WebFetchError(f"Không xử lý được trang web này ({type(error).__name__}).", 502)

    if not urls:
        return {}
    with ThreadPoolExecutor(max_workers=max(1, min(workers, len(urls)))) as pool:
        return dict(zip(urls, pool.map(one, urls)))


if __name__ == "__main__":  # chẩn đoán: python -m app.services.web.webpages <địa chỉ>  -> in lỗi đầy đủ hoặc tóm tắt nội dung tải được
    import sys
    import traceback

    from app.config import Settings

    if len(sys.argv) != 2:
        raise SystemExit("Cách dùng: python -m app.services.web.webpages https://trang-can-thu/")
    try:
        page = fetch_page(sys.argv[1], Settings.load())
    except WebFetchError as error:
        raise SystemExit(f"Không tải được (lỗi đã biết, mã {error.status}): {error}")
    except Exception:  # noqa: BLE001
        traceback.print_exc()
        raise SystemExit("Lỗi bất ngờ ở trên: hãy gửi nguyên đoạn này.")
    print(f"Tải được: {page.title!r}\n  địa chỉ cuối: {page.url}\n  {len(page.chunks)} đoạn, {page.size_bytes} byte")
    print("  đoạn đầu:", page.chunks[0]["text"][:200].replace("\n", " "))
