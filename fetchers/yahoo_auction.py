from __future__ import annotations

import json
import logging
import re
import time
from datetime import datetime

import aiohttp

from .base import Fetcher, OGPData, REGISTRY, read_capped

logger = logging.getLogger(__name__)

_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120.0.0.0 Safari/537.36"
)
_TIMEOUT = aiohttp.ClientTimeout(total=10)
_URL_RE = re.compile(r"auctions\.yahoo\.co\.jp/jp/auction/([a-zA-Z]\d+)")
_NEXT_DATA_RE = re.compile(
    r'<script id="__NEXT_DATA__" type="application/json">(.+?)</script>', re.S
)

_CACHE_TTL = 60
# __NEXT_DATA__ の終端が実測 176KB 付近まで来るページがあるため余裕を持たせる
_MAX_READ_BYTES = 1024 * 1024
_YAHOO_COLOR = 0xFF0033


class YahooAuctionFetcher(Fetcher):
    def __init__(self) -> None:
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
                        "Yahoo Auction returned %s for id=%s", resp.status, identifier
                    )
                    return None
                raw = await read_capped(resp, _MAX_READ_BYTES)
        except Exception:
            logger.exception("Failed to fetch Yahoo Auction page for id=%s", identifier)
            return None

        html_text = raw.decode("utf-8", errors="replace")
        m = _NEXT_DATA_RE.search(html_text)
        if not m:
            logger.warning("Yahoo Auction __NEXT_DATA__ not found for id=%s", identifier)
            return None

        try:
            data = json.loads(m.group(1))
            item = data["props"]["pageProps"]["initialState"]["item"]["detail"]["item"]
        except Exception:
            logger.exception("Failed to parse Yahoo Auction JSON for id=%s", identifier)
            return None

        try:
            result = _build_ogp(item, url)
        except Exception:
            logger.exception("Failed to build Yahoo Auction OGP for id=%s", identifier)
            return None

        self._cache[identifier] = (result, now + _CACHE_TTL)
        return result


def _build_ogp(item: dict, fallback_url: str) -> OGPData:
    title = item["title"]
    source_url = item.get("auctionItemUrl") or fallback_url

    image_url: str | None = None
    imgs = item.get("img")
    if isinstance(imgs, list) and imgs:
        first = imgs[0]
        if isinstance(first, dict):
            image_url = first.get("image") or first.get("thumbnail")

    fields: list[tuple[str, str, bool]] = []

    price = item.get("price")
    if price is not None:
        fields.append(("現在価格", f"¥{int(price):,}", True))

    # featuredPrice は「注目のオークション」掲載料なので使わない。即決価格は bidorbuy
    bidorbuy = item.get("bidorbuy")
    if bidorbuy:
        fields.append(("即決価格", f"¥{int(bidorbuy):,}", True))

    bids = item.get("bids")
    if bids is not None:
        fields.append(("入札", f"{bids} 件", True))

    end_value = _format_end(item)
    if end_value:
        fields.append(("終了", end_value, True))

    seller_name = None
    seller = item.get("seller")
    if isinstance(seller, dict):
        seller_name = seller.get("displayName")
    footer = f"出品者: {seller_name}" if seller_name else None

    return OGPData(
        title=title,
        source_url=source_url,
        image_url=image_url,
        fields=fields,
        footer=footer,
        color=_YAHOO_COLOR,
    )


def _format_end(item: dict) -> str | None:
    if item.get("status") != "open":
        return "終了しました"
    end_iso = item.get("endTime")
    formatted = item.get("formattedEndTime")
    if not end_iso:
        return formatted or None
    try:
        dt = datetime.fromisoformat(end_iso)
        unix = int(dt.timestamp())
    except Exception:
        return formatted or None
    if formatted:
        return f"<t:{unix}:R> ({formatted})"
    return f"<t:{unix}:R>"


REGISTRY.append(YahooAuctionFetcher())
