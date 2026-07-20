from __future__ import annotations

import logging
import logging.handlers
import re
from pathlib import Path

import aiohttp
import discord
from discord import app_commands

import config
from blocklist import Blocklist
from fetchers import find_fetcher
from fetchers.base import REGISTRY
from ui import BlocklistView, build_embed

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

_DEFAULT_COLOR = discord.Color.from_str("#00ae86")
_BLOCKLIST_PATH = Path("data/blocklist.json")


class OGPBot(discord.Client):
    def __init__(self) -> None:
        intents = discord.Intents.default()
        intents.message_content = True
        super().__init__(intents=intents)
        self._session: aiohttp.ClientSession | None = None
        self.blocklist = Blocklist(_BLOCKLIST_PATH)
        self.tree = app_commands.CommandTree(self)
        _register_commands(self.tree, self.blocklist)

    async def setup_hook(self) -> None:
        self._session = aiohttp.ClientSession()
        self.blocklist.load()
        await self.tree.sync()

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

            if message.guild and self.blocklist.is_blocked(message.guild.id, fetcher.KEY):
                continue

            data = await fetcher.fetch(identifier, url, self._session)
            if data is None:
                continue

            color = discord.Color(data.color) if data.color is not None else _DEFAULT_COLOR
            embed = discord.Embed(
                title=data.title,
                url=data.source_url,
                color=color,
            )
            if data.description:
                embed.description = data.description
            if data.image_url:
                embed.set_image(url=data.image_url)
            for name, value, inline in data.fields:
                embed.add_field(name=name, value=value, inline=inline)
            if data.footer:
                embed.set_footer(text=data.footer)

            await message.channel.send(embed=embed)
            logger.info(
                "Sent embed for %s in channel=%s guild=%s",
                url,
                message.channel.id,
                getattr(message.guild, "id", None),
            )


def _register_commands(tree: app_commands.CommandTree, blocklist: Blocklist) -> None:
    @tree.command(
        name="ogp-block",
        description="このサーバーで OGP を表示しないサイトを設定します",
    )
    @app_commands.default_permissions(manage_guild=True)
    @app_commands.guild_only()
    async def ogp_block(interaction: discord.Interaction) -> None:
        if interaction.guild is None:
            await interaction.response.send_message(
                "このコマンドはサーバー内でのみ使用できます。", ephemeral=True
            )
            return
        embed = build_embed(interaction.guild.name, blocklist, interaction.guild.id, REGISTRY)
        view = BlocklistView(blocklist, interaction.guild.id, REGISTRY)
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)


def main() -> None:
    bot = OGPBot()
    bot.run(config.DISCORD_TOKEN, log_handler=None)


if __name__ == "__main__":
    main()
