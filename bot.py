from __future__ import annotations

import logging
import logging.handlers
import re

import aiohttp
import discord

import config
from fetchers import find_fetcher

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.handlers.RotatingFileHandler(
            "bot.log", maxBytes=1_000_000, backupCount=3, encoding="utf-8"
        ),
    ],
)
logger = logging.getLogger(__name__)

_URL_RE = re.compile(r"https?://\S+")

_MAKERWORLD_COLOR = discord.Color.from_str("#00ae86")


class OGPBot(discord.Client):
    def __init__(self) -> None:
        intents = discord.Intents.default()
        intents.message_content = True
        super().__init__(intents=intents)
        self._session: aiohttp.ClientSession | None = None

    async def setup_hook(self) -> None:
        self._session = aiohttp.ClientSession()

    async def close(self) -> None:
        if self._session:
            await self._session.close()
        await super().close()

    async def on_ready(self) -> None:
        logger.info("Logged in as %s (id=%s)", self.user, self.user.id if self.user else "?")

    async def on_message(self, message: discord.Message) -> None:
        if message.author.bot:
            return

        urls = _URL_RE.findall(message.content)
        if not urls:
            return

        assert self._session is not None

        for url in urls:
            hit = find_fetcher(url)
            if hit is None:
                continue
            fetcher, identifier = hit
            data = await fetcher.fetch(identifier, url, self._session)
            if data is None:
                continue

            embed = discord.Embed(
                title=data.title,
                url=data.source_url,
                color=_MAKERWORLD_COLOR,
            )
            if data.description:
                embed.description = data.description
            if data.image_url:
                embed.set_thumbnail(url=data.image_url)

            footer_parts: list[str] = []
            if "likes" in data.extra:
                footer_parts.append(f"❤️ {data.extra['likes']:,}")
            if "downloads" in data.extra:
                footer_parts.append(f"⬇️ {data.extra['downloads']:,}")
            if footer_parts:
                embed.set_footer(text="  ".join(footer_parts))

            await message.channel.send(embed=embed)
            logger.info(
                "Sent embed for %s in channel=%s guild=%s",
                url,
                message.channel.id,
                getattr(message.guild, "id", None),
            )


def main() -> None:
    bot = OGPBot()
    bot.run(config.DISCORD_TOKEN, log_handler=None)


if __name__ == "__main__":
    main()
