from __future__ import annotations

import html
import logging
import re
import time
from html.parser import HTMLParser

import aiohttp

from .base import Fetcher, OGPData, REGISTRY

logger = logging.getLogger(__name__)

_API_URL = "https://makerworld.com/api/v1/design-service/design/{id}"
_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120.0.0.0 Safari/537.36"
)
_TIMEOUT = aiohttp.ClientTimeout(total=10)
_URL_RE = re.compile(r"makerworld\.com/(?:[a-z]{2}/)?models/(\d+)")

_DESC_MAX_CHARS = 50
_CACHE_TTL = 60  # seconds


class _HTMLStripper(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self._parts: list[str] = []

    def handle_data(self, data: str) -> None:
        self._parts.append(data)

    def get_text(self) -> str:
        return "".join(self._parts)


def _strip_html(raw: str) -> str:
    s = _HTMLStripper()
    s.feed(raw)
    return html.unescape(s.get_text()).strip()


def _short_desc(raw: str | None) -> str | None:
    if not raw:
        return None
    text = _strip_html(raw)
    if not text:
        return None
    if len(text) <= _DESC_MAX_CHARS:
        return text
    return text[:_DESC_MAX_CHARS] + "…"


class MakerWorldFetcher(Fetcher):
    def __init__(self) -> None:
        # {id: (OGPData, expires_at)}
        self._cache: dict[str, tuple[OGPData, float]] = {}

    def match(self, url: str) -> str | None:
        m = _URL_RE.search(url)
        return m.group(1) if m else None

    async def fetch(
        self, identifier: str, url: str, session: aiohttp.ClientSession
    ) -> OGPData | None:
        now = time.monotonic()
        cached = self._cache.get(identifier)
        if cached and cached[1] > now:
            return cached[0]

        api_url = _API_URL.format(id=identifier)
        try:
            async with session.get(
                api_url,
                headers={"User-Agent": _UA, "Accept": "application/json"},
                timeout=_TIMEOUT,
            ) as resp:
                if resp.status != 200:
                    logger.warning("MakerWorld API returned %s for id=%s", resp.status, identifier)
                    return None
                data = await resp.json(content_type=None)
        except Exception:
            logger.exception("Failed to fetch MakerWorld data for id=%s", identifier)
            return None

        if not isinstance(data, dict):
            logger.warning("Unexpected MakerWorld API response type for id=%s", identifier)
            return None

        title = data.get("title") or f"MakerWorld model {identifier}"
        image_url = data.get("coverUrl") or None
        description = _short_desc(data.get("summary"))

        footer_parts: list[str] = []
        if (likes := data.get("likeCount")) is not None:
            footer_parts.append(f"❤️ {likes:,}")
        if (downloads := data.get("downloadCount")) is not None:
            footer_parts.append(f"⬇️ {downloads:,}")
        footer = "  ".join(footer_parts) if footer_parts else None

        result = OGPData(
            title=title,
            source_url=url,
            image_url=image_url,
            description=description,
            footer=footer,
        )
        self._cache[identifier] = (result, now + _CACHE_TTL)
        return result


REGISTRY.append(MakerWorldFetcher())
