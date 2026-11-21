"""Versioned SQLite archive for authorized messages."""

import json
import re
import sqlite3
from collections.abc import Iterable
from contextlib import closing
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

_MIGRATIONS = (
    (
        """
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
        """,
    ),
    (
        "ALTER TABLE messages ADD COLUMN edited_at TEXT",
        "CREATE INDEX messages_by_age ON messages (created_at)",
        """
        CREATE TABLE deleted_messages (
            message_id TEXT NOT NULL,
            guild_id TEXT NOT NULL,
            channel_id TEXT NOT NULL,
            deleted_at TEXT NOT NULL,
            PRIMARY KEY (message_id, guild_id, channel_id)
        )
        """,
    ),
    (
        "CREATE INDEX messages_by_channel_time ON messages (guild_id, channel_id, created_at)",
        """
        CREATE VIRTUAL TABLE messages_fts USING fts5(
            text, content='messages', content_rowid='rowid'
        )
        """,
        "INSERT INTO messages_fts(messages_fts, rank) VALUES ('secure-delete', 1)",
        "INSERT INTO messages_fts(messages_fts) VALUES ('rebuild')",
        """
        CREATE TRIGGER messages_fts_insert AFTER INSERT ON messages BEGIN
            INSERT INTO messages_fts(rowid, text) VALUES (new.rowid, new.text);
        END
        """,
        """
        CREATE TRIGGER messages_fts_delete AFTER DELETE ON messages BEGIN
            INSERT INTO messages_fts(messages_fts, rowid, text)
            VALUES ('delete', old.rowid, old.text);
        END
        """,
        """
        CREATE TRIGGER messages_fts_update AFTER UPDATE OF text ON messages BEGIN
            INSERT INTO messages_fts(messages_fts, rowid, text)
            VALUES ('delete', old.rowid, old.text);
            INSERT INTO messages_fts(rowid, text) VALUES (new.rowid, new.text);
        END
        """,
    ),
)


_WORDS = re.compile(r"[^\W_]+")


def _utc_text(timestamp: datetime) -> str:
    if timestamp.utcoffset() is None:
        raise ValueError("Message timestamps must include a timezone")
    return timestamp.astimezone(UTC).isoformat(timespec="microseconds")


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
    edited_at: datetime | None = None


class Archive:
    def __init__(self, path: Path, *, max_messages: int = 20_000) -> None:
        if max_messages < 1:
            raise ValueError("The archive budget must be positive")
        self.path = path.resolve()
        self.max_messages = max_messages
        with closing(self.connect()) as connection:
            with connection:
                connection.execute("BEGIN IMMEDIATE")
                version = connection.execute("PRAGMA user_version").fetchone()[0]
                if not 0 <= version <= len(_MIGRATIONS):
                    raise ValueError("Unsupported archive version")
                for index, statements in enumerate(
                    _MIGRATIONS[version:], start=version + 1
                ):
                    for statement in statements:
                        connection.execute(statement)
                    connection.execute(f"PRAGMA user_version = {index}")
            connection.execute("PRAGMA journal_mode = WAL")

    def connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path)
        connection.execute("PRAGMA secure_delete = ON")
        return connection

    def append(self, message: MessageRecord) -> bool:
        scope = (
            str(message.message_id),
            str(message.guild_id),
            str(message.channel_id),
        )
        with closing(self.connect()) as connection, connection:
            result = connection.execute(
                """
                INSERT INTO messages (
                    message_id, guild_id, channel_id, author_id,
                    author_display, text, created_at, reply_to_id
                )
                SELECT ?, ?, ?, ?, ?, ?, ?, ?
                WHERE NOT EXISTS (
                    SELECT 1 FROM deleted_messages
                    WHERE message_id = ? AND guild_id = ? AND channel_id = ?
                )
                ON CONFLICT (message_id) DO NOTHING
                """,
                (
                    *scope,
                    str(message.author_id),
                    message.author_display,
                    message.text,
                    _utc_text(message.created_at),
                    str(message.reply_to_id)
                    if message.reply_to_id is not None
                    else None,
                    *scope,
                ),
            )
            if result.rowcount != 1:
                return False
            count = connection.execute("SELECT count(*) FROM messages").fetchone()[0]
            if count > self.max_messages:
                connection.execute(
                    """
                    DELETE FROM messages
                    WHERE rowid IN (
                        SELECT rowid FROM messages ORDER BY created_at, rowid LIMIT ?
                    )
                    """,
                    (count - self.max_messages,),
                )
                return (
                    connection.execute(
                        "SELECT 1 FROM messages WHERE message_id = ?", (scope[0],)
                    ).fetchone()
                    is not None
                )
            return True

    def edit(
        self,
        message_id: int,
        guild_id: int,
        channel_id: int,
        authors: frozenset[int],
        text: str,
        edited_at: datetime,
    ) -> bool:
        timestamp = _utc_text(edited_at)
        with closing(self.connect()) as connection, connection:
            result = connection.execute(
                """
                UPDATE messages SET text = ?, edited_at = ?
                WHERE message_id = ? AND guild_id = ? AND channel_id = ?
                  AND author_id IN (SELECT value FROM json_each(?))
                  AND created_at <= ? AND (edited_at IS NULL OR edited_at < ?)
                """,
                (
                    text,
                    timestamp,
                    str(message_id),
                    str(guild_id),
                    str(channel_id),
                    json.dumps([str(author) for author in authors]),
                    timestamp,
                    timestamp,
                ),
            )
            return result.rowcount == 1

    def delete(
        self, guild_id: int, channel_id: int, ids: Iterable[int], deleted_at: datetime
    ) -> int:
        timestamp = _utc_text(deleted_at)
        scope = [(str(message), str(guild_id), str(channel_id)) for message in ids]
        with closing(self.connect()) as connection, connection:
            connection.executemany(
                """
                INSERT INTO deleted_messages (message_id, guild_id, channel_id, deleted_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT (message_id, guild_id, channel_id) DO NOTHING
                """,
                ((*message, timestamp) for message in scope),
            )
            return connection.executemany(
                "DELETE FROM messages WHERE message_id = ? AND guild_id = ? AND channel_id = ?",
                scope,
            ).rowcount

    def prune(self, cutoff: datetime) -> None:
        timestamp = _utc_text(cutoff)
        with closing(self.connect()) as connection, connection:
            connection.execute(
                "DELETE FROM messages WHERE created_at < ?", (timestamp,)
            )
            connection.execute(
                "DELETE FROM deleted_messages WHERE deleted_at < ?", (timestamp,)
            )

    def get(self, message_id: int) -> MessageRecord | None:
        with closing(self.connect()) as connection:
            row = connection.execute(
                """
                SELECT message_id, guild_id, channel_id, author_id,
                       author_display, text, created_at, reply_to_id, edited_at
                FROM messages WHERE message_id = ?
                """,
                (str(message_id),),
            ).fetchone()
        if row is None:
            return None
        return _record(row)

    def search(
        self,
        query: str,
        *,
        guild_id: int,
        channel_id: int,
        authors: frozenset[int],
        cutoff: datetime,
        limit: int = 8,
    ) -> tuple[MessageRecord, ...]:
        terms = list(dict.fromkeys(_WORDS.findall(query[:2000].lower())))[:12]
        if not terms or not authors or limit < 1:
            return ()
        expression = " OR ".join(f'"{term}"' for term in terms)
        with closing(self.connect()) as connection:
            rows = connection.execute(
                """
                SELECT messages.message_id, messages.guild_id, messages.channel_id,
                       messages.author_id, messages.author_display, messages.text,
                       messages.created_at, messages.reply_to_id, messages.edited_at
                FROM messages_fts JOIN messages ON messages.rowid = messages_fts.rowid
                WHERE messages_fts MATCH ? AND messages.guild_id = ? AND messages.channel_id = ?
                  AND messages.author_id IN (SELECT value FROM json_each(?))
                  AND messages.created_at >= ?
                ORDER BY bm25(messages_fts), messages.created_at DESC, messages.rowid DESC
                LIMIT ?
                """,
                (
                    expression,
                    str(guild_id),
                    str(channel_id),
                    json.dumps([str(author) for author in authors]),
                    _utc_text(cutoff),
                    min(limit, 32),
                ),
            ).fetchall()
        return tuple(_record(row) for row in rows)

    def recent(
        self,
        request: MessageRecord,
        authors: frozenset[int],
        cutoff: datetime,
        limit: int,
    ) -> tuple[MessageRecord, ...]:
        with closing(self.connect()) as connection:
            rows = connection.execute(
                """
                SELECT message_id, guild_id, channel_id, author_id,
                       author_display, text, created_at, reply_to_id, edited_at
                FROM messages
                WHERE guild_id = ? AND channel_id = ? AND message_id <> ?
                  AND author_id IN (SELECT value FROM json_each(?))
                  AND created_at BETWEEN ? AND ?
                ORDER BY created_at DESC, rowid DESC LIMIT ?
                """,
                (
                    str(request.guild_id),
                    str(request.channel_id),
                    str(request.message_id),
                    json.dumps([str(author) for author in authors]),
                    _utc_text(cutoff),
                    _utc_text(request.created_at),
                    limit,
                ),
            ).fetchall()
        return tuple(_record(row) for row in rows)


def _record(row: tuple) -> MessageRecord:
    return MessageRecord(
        message_id=int(row[0]),
        guild_id=int(row[1]),
        channel_id=int(row[2]),
        author_id=int(row[3]),
        author_display=row[4],
        text=row[5],
        created_at=datetime.fromisoformat(row[6]),
        reply_to_id=int(row[7]) if row[7] is not None else None,
        edited_at=datetime.fromisoformat(row[8]) if row[8] is not None else None,
    )
