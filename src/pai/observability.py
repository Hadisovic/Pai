"""Local health checks, payload-free logging and a bounded reply limiter."""

import logging
import platform
import sqlite3
from collections import deque
from collections.abc import Callable, Iterator
from contextlib import closing, contextmanager
from pathlib import Path
from tempfile import TemporaryDirectory
from time import monotonic

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
    def __init__(self, *, clock: Callable[[], float] = monotonic) -> None:
        self.clock = clock
        self.active = 0
        self.guild_attempts: deque[float] = deque()
        self.member_attempts: dict[int, float] = {}

    @contextmanager
    def slot(self, author_id: int) -> Iterator[bool]:
        now = self.clock()
        while self.guild_attempts and self.guild_attempts[0] <= now - 60:
            self.guild_attempts.popleft()
        self.member_attempts = {
            member: last
            for member, last in self.member_attempts.items()
            if last > now - 12
        }
        if (
            self.active >= 2
            or len(self.guild_attempts) >= 8
            or author_id in self.member_attempts
        ):
            yield False
            return
        self.active += 1
        self.guild_attempts.append(now)
        self.member_attempts[author_id] = now
        try:
            yield True
        finally:
            self.active -= 1
