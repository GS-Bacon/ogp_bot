from __future__ import annotations

import json
import logging
import os
from pathlib import Path

logger = logging.getLogger(__name__)


class Blocklist:
    """guild ごとに「OGP を出さない fetcher の KEY 集合」を保持し JSON に永続化する。"""

    def __init__(self, path: Path) -> None:
        self._path = path
        self._data: dict[int, set[str]] = {}

    def load(self) -> None:
        if not self._path.exists():
            self._data = {}
            return
        try:
            raw = json.loads(self._path.read_text(encoding="utf-8"))
        except Exception:
            logger.exception("Failed to load blocklist from %s; starting empty", self._path)
            self._data = {}
            return

        if not isinstance(raw, dict):
            logger.warning("Blocklist at %s is not a JSON object; ignoring", self._path)
            self._data = {}
            return

        parsed: dict[int, set[str]] = {}
        for gid_str, keys in raw.items():
            try:
                gid = int(gid_str)
            except (TypeError, ValueError):
                logger.warning("Skipping non-integer guild id in blocklist: %r", gid_str)
                continue
            if not isinstance(keys, list):
                logger.warning("Skipping non-list value for guild %s in blocklist", gid)
                continue
            parsed[gid] = {str(k) for k in keys}
        self._data = parsed

    def save(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        serializable = {str(gid): sorted(keys) for gid, keys in self._data.items() if keys}
        tmp = self._path.with_suffix(self._path.suffix + ".tmp")
        tmp.write_text(
            json.dumps(serializable, ensure_ascii=False, indent=2, sort_keys=True),
            encoding="utf-8",
        )
        os.replace(tmp, self._path)

    def get(self, guild_id: int) -> set[str]:
        return set(self._data.get(guild_id, set()))

    def set(self, guild_id: int, keys: set[str]) -> None:
        if keys:
            self._data[guild_id] = set(keys)
        else:
            self._data.pop(guild_id, None)

    def is_blocked(self, guild_id: int, key: str) -> bool:
        return key in self._data.get(guild_id, set())
