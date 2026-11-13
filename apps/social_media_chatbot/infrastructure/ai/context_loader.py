from __future__ import annotations

import ipaddress
import socket
from html.parser import HTMLParser
from urllib.parse import urlparse

import requests


MAX_SITE_BYTES = 512 * 1024
MAX_SITE_CHARS = 12_000


class _TextExtractor(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self._suppressed = 0

    def handle_starttag(self, tag, attrs):
        if tag.lower() in {"script", "style", "noscript", "svg"}:
            self._suppressed += 1
        elif tag.lower() in {"p", "div", "li", "h1", "h2", "h3", "br"}:
            self.parts.append("\n")

    def handle_endtag(self, tag):
        if tag.lower() in {"script", "style", "noscript", "svg"} and self._suppressed:
            self._suppressed -= 1
        elif tag.lower() in {"p", "div", "li", "h1", "h2", "h3"}:
            self.parts.append("\n")

    def handle_data(self, data):
        if not self._suppressed:
            value = " ".join(data.split())
            if value:
                self.parts.append(value)


def fetch_website_context(url: str) -> str:
    """Fetch a bounded public web page and reject local/private destinations."""
    parsed = urlparse(url)
    if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
        return ""
    try:
        addresses = {
            item[4][0]
            for item in socket.getaddrinfo(parsed.hostname, 443, type=socket.SOCK_STREAM)
        }
        if not addresses or any(not ipaddress.ip_address(item).is_global for item in addresses):
            return ""
        with requests.Session() as session:
            session.trust_env = False
            with session.get(
                url,
                headers={"User-Agent": "SocialMediaChatbot/1.0"},
                timeout=(2, 4),
                allow_redirects=False,
                stream=True,
            ) as response:
                if response.status_code != 200 or "text/html" not in response.headers.get(
                    "Content-Type", ""
                ).lower():
                    return ""
                content = bytearray()
                for chunk in response.iter_content(16_384):
                    content.extend(chunk)
                    if len(content) > MAX_SITE_BYTES:
                        break
                parser = _TextExtractor()
                parser.feed(content[:MAX_SITE_BYTES].decode(response.encoding or "utf-8", errors="replace"))
                return " ".join(" ".join(parser.parts).split())[:MAX_SITE_CHARS]
    except (OSError, requests.RequestException, ValueError):
        return ""
