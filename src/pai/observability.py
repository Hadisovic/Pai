"""Local health checks, payload-free logging and a bounded reply limiter."""

import asyncio
import logging
import platform
import sqlite3
from collections import Counter
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager, closing
from pathlib import Path
from tempfile import TemporaryDirectory

from pai.storage import Archive

LOG = logging.getLogger("pai")


def initialize_logs() -> None:
    if not LOG.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
        LOG.addHandler(handler)
    LOG.setLevel(logging.INFO)
    LOG.propagate = False
    discord = logging.getLogger("discord")
    discord.addHandler(logging.NullHandler())
    discord.propagate = False


def diagnose() -> dict[str, str | bool]:
    with TemporaryDirectory(prefix="pai-doctor-") as directory:
        archive = Archive(Path(directory) / "health.sqlite")
        with closing(archive.connect()) as connection:
            integrity = connection.execute("PRAGMA quick_check").fetchone()[0]
            connection.execute(
                "SELECT rowid FROM messages_fts WHERE messages_fts MATCH 'probe'"
            )
    return {
        "python": platform.python_version(),
        "sqlite": sqlite3.sqlite_version,
        "sqlite_check": integrity,
        "fts5": True,
    }


class ReplyLimits:
    """Bound live work without imposing a timer between conversations."""

    def __init__(self) -> None:
        self.pending = 0
        self.by_author: Counter[int] = Counter()
        self.channels: dict[int, asyncio.Lock] = {}
        self.active = asyncio.Semaphore(2)
        self.busy_channels: set[int] = set()

    @asynccontextmanager
    async def slot(self, channel_id: int, author_id: int) -> AsyncIterator[bool]:
        if self.pending >= 32 or self.by_author[author_id] >= 8:
            yield False
            return
        self.pending += 1
        self.by_author[author_id] += 1
        channel = self.channels.setdefault(channel_id, asyncio.Lock())
        try:
            async with channel, self.active:
                yield True
        finally:
            self.pending -= 1
            self.by_author[author_id] -= 1
            if not self.by_author[author_id]:
                del self.by_author[author_id]
            self.busy_channels.discard(channel_id)

    def announce_busy(self, channel_id: int) -> bool:
        if channel_id in self.busy_channels:
            return False
        self.busy_channels.add(channel_id)
        return True
