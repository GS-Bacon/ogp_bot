from __future__ import annotations

import logging
import re
import time
from html.parser import HTMLParser

import aiohttp

from .base import Fetcher, OGPData, REGISTRY, read_capped

logger = logging.getLogger(__name__)

_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120.0.0.0 Safari/537.36"
)
_TIMEOUT = aiohttp.ClientTimeout(total=10)
_URL_RE = re.compile(
    r"(?:[a-z0-9-]+\.)?aliexpress\.(?:com|us)/(?:item/(\d+)\.html|_([A-Za-z0-9]+))"
)

_CACHE_TTL = 60  # seconds
# 商品 1 ページが ~75KB 程度。og タグは <head> 内にあるので 256KB あれば十分手前で見つかる
_MAX_READ_BYTES = 256 * 1024


class _OGTagExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.title: str | None = None
        self.image: str | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag != "meta":
            return
        attr = dict(attrs)
        prop = attr.get("property")
        content = attr.get("content")
        if not prop or not content:
            return
        if prop == "og:title" and self.title is None:
            self.title = content
        elif prop == "og:image" and self.image is None:
            self.image = content


class AliExpressFetcher(Fetcher):
    KEY = "aliexpress"
    DISPLAY_NAME = "AliExpress"

    def __init__(self) -> None:
        # {id: (OGPData, expires_at)}
        self._cache: dict[str, tuple[OGPData, float]] = {}

    def match(self, url: str) -> str | None:
        m = _URL_RE.search(url)
        if not m:
            return None
        return m.group(1) or m.group(2)

    async def fetch(
        self, identifier: str, url: str, session: aiohttp.ClientSession
    ) -> OGPData | None:
        now = time.monotonic()
        cached = self._cache.get(identifier)
        if cached and cached[1] > now:
            return cached[0]

        try:
            async with session.get(
                url,
                headers={
                    "User-Agent": _UA,
                    "Accept": "text/html,application/xhtml+xml",
                    "Accept-Language": "ja,en;q=0.8",
                },
                timeout=_TIMEOUT,
            ) as resp:
                if resp.status != 200:
                    logger.warning(
                        "AliExpress returned %s for id=%s", resp.status, identifier
                    )
                    return None
                raw = await read_capped(resp, _MAX_READ_BYTES)
        except Exception:
            logger.exception("Failed to fetch AliExpress page for id=%s", identifier)
            return None

        try:
            html_text = raw.decode("utf-8", errors="replace")
        except Exception:
            logger.exception("Failed to decode AliExpress HTML for id=%s", identifier)
            return None

        extractor = _OGTagExtractor()
        try:
            extractor.feed(html_text)
        except Exception:
            logger.exception("Failed to parse AliExpress HTML for id=%s", identifier)

        if not extractor.title:
            logger.warning("AliExpress og:title not found for id=%s", identifier)
            return None

        result = OGPData(
            title=extractor.title,
            source_url=url,
            image_url=extractor.image,
            description=None,
        )
        self._cache[identifier] = (result, now + _CACHE_TTL)
        return result


REGISTRY.append(AliExpressFetcher())
