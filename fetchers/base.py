from __future__ import annotations

import abc
from dataclasses import dataclass, field

import aiohttp


@dataclass
class OGPData:
    title: str
    source_url: str
    image_url: str | None = None
    description: str | None = None
    fields: list[tuple[str, str, bool]] = field(default_factory=list)
    footer: str | None = None
    color: int | None = None


class Fetcher(abc.ABC):
    @abc.abstractmethod
    def match(self, url: str) -> str | None:
        """Return an identifier string if this fetcher handles the URL, else None."""

    @abc.abstractmethod
    async def fetch(
        self, identifier: str, url: str, session: aiohttp.ClientSession
    ) -> OGPData | None:
        """Fetch metadata and return OGPData, or None on failure."""


REGISTRY: list[Fetcher] = []


def find_fetcher(url: str) -> tuple[Fetcher, str] | None:
    """Return (fetcher, identifier) for the first registered fetcher that matches url."""
    for fetcher in REGISTRY:
        identifier = fetcher.match(url)
        if identifier is not None:
            return fetcher, identifier
    return None
