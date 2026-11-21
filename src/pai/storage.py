"""Versioned SQLite archive for authorized messages."""

import sqlite3
from contextlib import closing
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

_SCHEMA = """
    CREATE TABLE messages (
        message_id TEXT PRIMARY KEY NOT NULL,
        guild_id TEXT NOT NULL,
        channel_id TEXT NOT NULL,
        author_id TEXT NOT NULL,
        author_display TEXT NOT NULL,
        text TEXT NOT NULL,
        created_at TEXT NOT NULL,
        reply_to_id TEXT
    )
"""


@dataclass(frozen=True)
class MessageRecord:
    message_id: int
    guild_id: int
    channel_id: int
    author_id: int
    author_display: str
    text: str
    created_at: datetime
    reply_to_id: int | None = None


class Archive:
    def __init__(self, path: Path) -> None:
        self.path = path.resolve()
        with closing(self.connect()) as connection:
            with connection:
                connection.execute("BEGIN IMMEDIATE")
                version = connection.execute("PRAGMA user_version").fetchone()[0]
                if version == 0:
                    connection.execute(_SCHEMA)
                    connection.execute("PRAGMA user_version = 1")
                elif version != 1:
                    raise ValueError("Unsupported archive version")
            connection.execute("PRAGMA journal_mode = WAL")

    def connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.path)

    def append(self, message: MessageRecord) -> bool:
        if message.created_at.utcoffset() is None:
            raise ValueError("Message timestamps must include a timezone")
        with closing(self.connect()) as connection, connection:
            result = connection.execute(
                """
                INSERT INTO messages (
                    message_id, guild_id, channel_id, author_id,
                    author_display, text, created_at, reply_to_id
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT (message_id) DO NOTHING
                """,
                (
                    str(message.message_id),
                    str(message.guild_id),
                    str(message.channel_id),
                    str(message.author_id),
                    message.author_display,
                    message.text,
                    message.created_at.astimezone(UTC).isoformat(
                        timespec="microseconds"
                    ),
                    str(message.reply_to_id)
                    if message.reply_to_id is not None
                    else None,
                ),
            )
            return result.rowcount == 1

    def get(self, message_id: int) -> MessageRecord | None:
        with closing(self.connect()) as connection:
            row = connection.execute(
                """
                SELECT message_id, guild_id, channel_id, author_id,
                       author_display, text, created_at, reply_to_id
                FROM messages WHERE message_id = ?
                """,
                (str(message_id),),
            ).fetchone()
        if row is None:
            return None
        return MessageRecord(
            message_id=int(row[0]),
            guild_id=int(row[1]),
            channel_id=int(row[2]),
            author_id=int(row[3]),
            author_display=row[4],
            text=row[5],
            created_at=datetime.fromisoformat(row[6]),
            reply_to_id=int(row[7]) if row[7] is not None else None,
        )
