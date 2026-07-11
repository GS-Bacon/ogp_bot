"""レスポンスが複数チャンクに分かれて届く状況の再現テスト。

StreamReader.read(n) は n バイト揃うのを待たず到着済みチャンクだけ返すため、
目的のデータが先頭チャンクより後ろにあるとパースに失敗するバグがあった。
サーバ側で小チャンク+sleep で分割送信し、この状況を決定的に再現する。
"""

import asyncio
import json

import aiohttp
from aiohttp import web

from fetchers.aliexpress import AliExpressFetcher
from fetchers.yahoo_auction import YahooAuctionFetcher

_CHUNK = 8 * 1024


def _yahoo_html() -> str:
    item = {
        "title": "テスト商品",
        "auctionItemUrl": "https://auctions.yahoo.co.jp/jp/auction/x1234567890",
        "price": 1500,
        "bidorbuy": 2000,
        "featuredPrice": "24.000000",
        "bids": 3,
        "status": "open",
        "endTime": "2026-07-12T21:00:00+09:00",
        "formattedEndTime": "07/12 21:00",
        "img": [{"image": "https://example.com/img.jpg"}],
        "seller": {"displayName": "tester"},
    }
    next_data = {
        "props": {"pageProps": {"initialState": {"item": {"detail": {"item": item}}}}}
    }
    # 実ページ同様、__NEXT_DATA__ を 100KB 超の位置に置く
    padding = "<!-- pad -->" * 10000
    return (
        "<html><head></head><body>"
        + padding
        + '<script id="__NEXT_DATA__" type="application/json">'
        + json.dumps(next_data, ensure_ascii=False)
        + "</script></body></html>"
    )


def _aliexpress_html() -> str:
    # og タグを先頭チャンク(8KB)より後ろに置く
    padding = "<!-- pad -->" * 3000
    return (
        "<html><head>"
        + padding
        + '<meta property="og:title" content="Test Product"/>'
        + '<meta property="og:image" content="https://example.com/p.jpg"/>'
        + "</head><body></body></html>"
    )


async def _serve_chunked(html: str, request: web.Request) -> web.StreamResponse:
    resp = web.StreamResponse(headers={"Content-Type": "text/html; charset=utf-8"})
    await resp.prepare(request)
    data = html.encode("utf-8")
    for i in range(0, len(data), _CHUNK):
        await resp.write(data[i : i + _CHUNK])
        # クライアント側の read() が先頭チャンクだけで返る状況を作る
        await asyncio.sleep(0.01)
    await resp.write_eof()
    return resp


async def _run_fetch(fetcher, identifier: str, html: str):
    async def handler(request: web.Request) -> web.StreamResponse:
        return await _serve_chunked(html, request)

    app = web.Application()
    app.router.add_get("/", handler)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "127.0.0.1", 0)
    await site.start()
    port = runner.addresses[0][1]
    try:
        async with aiohttp.ClientSession() as session:
            return await fetcher.fetch(identifier, f"http://127.0.0.1:{port}/", session)
    finally:
        await runner.cleanup()


def test_yahoo_url_match():
    f = YahooAuctionFetcher()
    # 英字接頭辞つき ID
    assert f.match("https://auctions.yahoo.co.jp/jp/auction/p1220722681") == "p1220722681"
    # 数字のみの ID も実在する
    assert f.match("https://auctions.yahoo.co.jp/jp/auction/1236316689") == "1236316689"
    assert f.match("https://example.com/foo") is None


def test_yahoo_auction_parses_chunked_response():
    result = asyncio.run(
        _run_fetch(YahooAuctionFetcher(), "x1234567890", _yahoo_html())
    )
    assert result is not None
    assert result.title == "テスト商品"
    assert ("現在価格", "¥1,500", True) in result.fields
    assert ("即決価格", "¥2,000", True) in result.fields
    # featuredPrice(注目のオークション掲載料)を即決価格として出さない
    assert ("即決価格", "¥24", True) not in result.fields
    assert ("入札", "3 件", True) in result.fields
    assert result.image_url == "https://example.com/img.jpg"
    assert result.footer == "出品者: tester"


def test_aliexpress_parses_chunked_response():
    result = asyncio.run(_run_fetch(AliExpressFetcher(), "12345", _aliexpress_html()))
    assert result is not None
    assert result.title == "Test Product"
    assert result.image_url == "https://example.com/p.jpg"
