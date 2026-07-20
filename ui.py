from __future__ import annotations

import logging
from typing import Sequence

import discord

from blocklist import Blocklist
from fetchers.base import Fetcher

logger = logging.getLogger(__name__)

_EMBED_COLOR = discord.Color.from_str("#00ae86")


def build_embed(
    guild_name: str, blocklist: Blocklist, guild_id: int, fetchers: Sequence[Fetcher]
) -> discord.Embed:
    blocked = blocklist.get(guild_id)
    lines = []
    for f in fetchers:
        mark = "🚫" if f.KEY in blocked else "✅"
        state = "非表示" if f.KEY in blocked else "表示"
        lines.append(f"{mark} **{f.DISPLAY_NAME}** — {state}")
    description = "\n".join(lines) if lines else "(対応サイトがありません)"

    embed = discord.Embed(
        title="OGP 表示設定",
        description=description,
        color=_EMBED_COLOR,
    )
    embed.set_footer(text=f"サーバー: {guild_name} / 下の選択肢でチェックしたサイトを非表示にします")
    return embed


class BlocklistSelect(discord.ui.Select):
    def __init__(
        self, blocklist: Blocklist, guild_id: int, fetchers: Sequence[Fetcher]
    ) -> None:
        self._blocklist = blocklist
        self._guild_id = guild_id
        self._fetchers = list(fetchers)

        blocked = blocklist.get(guild_id)
        options = [
            discord.SelectOption(
                label=f.DISPLAY_NAME,
                value=f.KEY,
                default=(f.KEY in blocked),
            )
            for f in self._fetchers
        ]
        super().__init__(
            placeholder="OGP を非表示にするサイトを選択",
            min_values=0,
            max_values=max(1, len(options)),
            options=options,
        )

    async def callback(self, interaction: discord.Interaction) -> None:
        selected = set(self.values)
        self._blocklist.set(self._guild_id, selected)
        try:
            self._blocklist.save()
        except Exception:
            logger.exception("Failed to save blocklist for guild=%s", self._guild_id)
            await interaction.response.send_message(
                "設定の保存に失敗しました。ログを確認してください。", ephemeral=True
            )
            return

        embed = build_embed(
            interaction.guild.name if interaction.guild else "-",
            self._blocklist,
            self._guild_id,
            self._fetchers,
        )
        view = BlocklistView(self._blocklist, self._guild_id, self._fetchers)
        await interaction.response.edit_message(embed=embed, view=view)


class BlocklistView(discord.ui.View):
    def __init__(
        self, blocklist: Blocklist, guild_id: int, fetchers: Sequence[Fetcher]
    ) -> None:
        super().__init__(timeout=180)
        self.add_item(BlocklistSelect(blocklist, guild_id, fetchers))
