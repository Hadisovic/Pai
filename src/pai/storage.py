"""Versioned SQLite archive for authorized messages."""

import json
import re
import sqlite3
from collections.abc import Iterable
from contextlib import closing
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path

from pai.media import MAX_MEDIA_ITEMS, MediaItem
from pai.policy import PrivacyPolicy

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
    (
        """
        CREATE TABLE style_examples (
            message_id TEXT PRIMARY KEY NOT NULL REFERENCES messages(message_id) ON DELETE CASCADE,
            chosen_at TEXT NOT NULL
        )
        """,
        """
        CREATE TRIGGER style_example_update AFTER UPDATE OF text ON messages
        WHEN old.text <> new.text BEGIN
            DELETE FROM style_examples WHERE message_id = old.message_id;
        END
        """,
    ),
    (
        """
        CREATE TABLE member_opt_outs (
            guild_id TEXT NOT NULL,
            author_id TEXT NOT NULL,
            recorded_at TEXT NOT NULL,
            PRIMARY KEY (guild_id, author_id)
        )
        """,
        "CREATE INDEX messages_by_author ON messages (guild_id, author_id, channel_id, created_at)",
    ),
    (
        """
        CREATE TABLE model_attempts (
            route TEXT NOT NULL, occurred_at TEXT NOT NULL, tokens INTEGER NOT NULL
        )
        """,
        "CREATE INDEX model_attempts_by_route ON model_attempts (route, occurred_at)",
        """
        CREATE TABLE model_backoff (
            route TEXT PRIMARY KEY NOT NULL, until_at TEXT NOT NULL
        )
        """,
    ),
    (
        """
        CREATE TABLE message_media (
            message_id TEXT NOT NULL REFERENCES messages(message_id) ON DELETE CASCADE,
            position INTEGER NOT NULL,
            kind TEXT NOT NULL,
            external_id TEXT NOT NULL,
            mime TEXT,
            size INTEGER,
            PRIMARY KEY (message_id, position)
        )
        """,
    ),
    (
        """
        CREATE TABLE media_descriptions (
            guild_id TEXT NOT NULL,
            channel_id TEXT NOT NULL,
            fingerprint TEXT NOT NULL,
            message_id TEXT NOT NULL REFERENCES messages(message_id) ON DELETE CASCADE,
            description TEXT NOT NULL,
            described_at TEXT NOT NULL,
            PRIMARY KEY (guild_id, channel_id, fingerprint)
        )
        """,
        "CREATE INDEX media_descriptions_by_source ON media_descriptions(message_id)",
        """
        CREATE TRIGGER media_description_update AFTER UPDATE OF edited_at ON messages
        BEGIN
            DELETE FROM media_descriptions WHERE message_id = old.message_id;
        END
        """,
    ),
    (
        "ALTER TABLE messages ADD COLUMN media_revision INTEGER NOT NULL DEFAULT 0",
        """
        CREATE TRIGGER media_metadata_update AFTER UPDATE OF media_revision ON messages
        BEGIN
            DELETE FROM media_descriptions WHERE message_id = old.message_id;
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
    media_revision: int = 0

    @property
    def jump_url(self) -> str:
        return f"https://discord.com/channels/{self.guild_id}/{self.channel_id}/{self.message_id}"


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
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    def append(
        self, message: MessageRecord, *, media: tuple[MediaItem, ...] = ()
    ) -> bool:
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
                AND NOT EXISTS (
                    SELECT 1 FROM member_opt_outs WHERE guild_id = ? AND author_id = ?
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
                    scope[1],
                    str(message.author_id),
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
                if (
                    connection.execute(
                        "SELECT 1 FROM messages WHERE message_id = ?", (scope[0],)
                    ).fetchone()
                    is None
                ):
                    return False
            if media:
                _write_media(connection, scope[0], media)
            return True

    def media_for(self, message_id: int) -> tuple[MediaItem, ...]:
        with closing(self.connect()) as connection:
            rows = connection.execute(
                """
                SELECT kind, external_id, mime, size
                FROM message_media WHERE message_id = ? ORDER BY position
                """,
                (str(message_id),),
            ).fetchall()
        return tuple(MediaItem(*row) for row in rows)

    def update_media(
        self,
        message_id: int,
        guild_id: int,
        channel_id: int,
        authors: frozenset[int],
        changed_kinds: frozenset[str],
        media: tuple[MediaItem, ...],
    ) -> bool:
        identifier = str(message_id)
        with closing(self.connect()) as connection, connection:
            connection.execute("BEGIN IMMEDIATE")
            authorized = connection.execute(
                """
                SELECT 1 FROM messages WHERE message_id = ? AND guild_id = ? AND channel_id = ?
                  AND author_id IN (SELECT value FROM json_each(?))
                """,
                (
                    identifier,
                    str(guild_id),
                    str(channel_id),
                    json.dumps([str(author) for author in authors]),
                ),
            ).fetchone()
            if authorized is None:
                return False
            current = tuple(
                MediaItem(*row)
                for row in connection.execute(
                    """
                    SELECT kind, external_id, mime, size FROM message_media
                    WHERE message_id = ? ORDER BY position
                    """,
                    (identifier,),
                )
            )
            updated = (
                tuple(item for item in current if item.kind not in changed_kinds)
                + tuple(item for item in media if item.kind in changed_kinds)
            )[:MAX_MEDIA_ITEMS]
            if set(current) == set(updated):
                return False
            connection.execute(
                "DELETE FROM message_media WHERE message_id = ?", (identifier,)
            )
            _write_media(connection, identifier, updated)
            connection.execute(
                "UPDATE messages SET media_revision = media_revision + 1 WHERE message_id = ?",
                (identifier,),
            )
            return True

    def find_description(
        self,
        fingerprint: str,
        guild_id: int,
        channel_id: int,
        authors: frozenset[int],
        cutoff: datetime,
    ) -> tuple[MessageRecord, str] | None:
        with closing(self.connect()) as connection:
            row = connection.execute(
                """
                SELECT messages.message_id, messages.guild_id, messages.channel_id,
                       messages.author_id, messages.author_display, messages.text,
                       messages.created_at, messages.reply_to_id, messages.edited_at, messages.media_revision, description
                FROM media_descriptions JOIN messages USING (message_id)
                WHERE media_descriptions.guild_id = ? AND media_descriptions.channel_id = ?
                  AND fingerprint = ? AND messages.created_at >= ?
                  AND messages.author_id IN (SELECT value FROM json_each(?))
                """,
                (
                    str(guild_id),
                    str(channel_id),
                    fingerprint,
                    _utc_text(cutoff),
                    json.dumps([str(author) for author in authors]),
                ),
            ).fetchone()
        return (_record(row[:-1]), row[-1]) if row is not None else None

    def save_description(
        self, source: MessageRecord, fingerprint: str, description: str, now: datetime
    ) -> bool:
        with closing(self.connect()) as connection, connection:
            row = connection.execute(
                """
                INSERT INTO media_descriptions
                    (guild_id, channel_id, fingerprint, message_id, description, described_at)
                SELECT guild_id, channel_id, ?, message_id, ?, ? FROM messages
                WHERE message_id = ? AND guild_id = ? AND channel_id = ? AND text = ?
                  AND edited_at IS ? AND media_revision = ?
                ON CONFLICT (guild_id, channel_id, fingerprint) DO UPDATE SET
                    message_id = excluded.message_id, description = excluded.description,
                    described_at = excluded.described_at
                """,
                (
                    fingerprint,
                    description,
                    _utc_text(now),
                    str(source.message_id),
                    str(source.guild_id),
                    str(source.channel_id),
                    source.text,
                    _utc_text(source.edited_at)
                    if source.edited_at is not None
                    else None,
                    source.media_revision,
                ),
            )
            return row.rowcount == 1

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

    def forget_author(self, guild_id: int, author_id: int, now: datetime) -> int:
        scope = (str(guild_id), str(author_id))
        with closing(self.connect()) as connection, connection:
            connection.execute(
                """
                INSERT INTO member_opt_outs (guild_id, author_id, recorded_at)
                VALUES (?, ?, ?) ON CONFLICT (guild_id, author_id) DO NOTHING
                """,
                (*scope, _utc_text(now)),
            )
            return connection.execute(
                "DELETE FROM messages WHERE guild_id = ? AND author_id = ?", scope
            ).rowcount

    def is_opted_out(self, guild_id: int, author_id: int) -> bool:
        with closing(self.connect()) as connection:
            return (
                connection.execute(
                    "SELECT 1 FROM member_opt_outs WHERE guild_id = ? AND author_id = ?",
                    (str(guild_id), str(author_id)),
                ).fetchone()
                is not None
            )

    def apply_policy(self, policy: PrivacyPolicy) -> int:
        with closing(self.connect()) as connection, connection:
            if not policy.media_opt_in:
                connection.execute("DELETE FROM media_descriptions")
                connection.execute("DELETE FROM message_media")
            return connection.execute(
                """
                DELETE FROM messages
                WHERE NOT ? OR guild_id <> ?
                   OR channel_id NOT IN (SELECT value FROM json_each(?))
                   OR author_id NOT IN (SELECT value FROM json_each(?))
                """,
                (
                    policy.is_enabled,
                    str(policy.guild_id),
                    json.dumps([str(channel) for channel in policy.channel_ids]),
                    json.dumps(
                        [str(author) for author in policy.consenting_member_ids]
                    ),
                ),
            ).rowcount

    def export_author(
        self, guild_id: int, channel_id: int, author_id: int, cutoff: datetime
    ) -> tuple[MessageRecord, ...]:
        with closing(self.connect()) as connection:
            rows = connection.execute(
                """
                SELECT message_id, guild_id, channel_id, author_id,
                       author_display, text, created_at, reply_to_id, edited_at, media_revision
                FROM messages WHERE guild_id = ? AND channel_id = ? AND author_id = ?
                  AND created_at >= ?
                ORDER BY created_at DESC, rowid DESC LIMIT 100
                """,
                (str(guild_id), str(channel_id), str(author_id), _utc_text(cutoff)),
            ).fetchall()
        return tuple(_record(row) for row in rows)

    def reserve_model_attempt(
        self,
        route: str,
        now: datetime,
        tokens: int,
        request_limits: tuple[int, int],
        token_limits: tuple[int, int],
    ) -> bool:
        current = _utc_text(now)
        minute = _utc_text(now - timedelta(minutes=1))
        day = _utc_text(now - timedelta(days=1))
        with closing(self.connect()) as connection, connection:
            connection.execute("BEGIN IMMEDIATE")
            blocked = connection.execute(
                "SELECT 1 FROM model_backoff WHERE route = ? AND until_at > ?",
                (route, current),
            ).fetchone()
            if blocked:
                return False
            connection.execute(
                "DELETE FROM model_attempts WHERE route = ? AND occurred_at < ?",
                (route, day),
            )
            minute_calls, day_calls, minute_tokens, day_tokens = connection.execute(
                """
                SELECT coalesce(sum(occurred_at >= ?), 0), count(*),
                       coalesce(sum(CASE WHEN occurred_at >= ? THEN tokens ELSE 0 END), 0),
                       coalesce(sum(tokens), 0)
                FROM model_attempts WHERE route = ?
                """,
                (minute, minute, route),
            ).fetchone()
            if (
                minute_calls >= request_limits[0]
                or day_calls >= request_limits[1]
                or minute_tokens + tokens > token_limits[0]
                or day_tokens + tokens > token_limits[1]
            ):
                return False
            connection.execute(
                "INSERT INTO model_attempts (route, occurred_at, tokens) VALUES (?, ?, ?)",
                (route, current, tokens),
            )
            return True

    def block_model_route(self, route: str, until: datetime) -> None:
        with closing(self.connect()) as connection, connection:
            connection.execute(
                """
                INSERT INTO model_backoff (route, until_at) VALUES (?, ?)
                ON CONFLICT (route) DO UPDATE SET until_at = max(until_at, excluded.until_at)
                """,
                (route, _utc_text(until)),
            )

    def prune(self, cutoff: datetime) -> None:
        timestamp = _utc_text(cutoff)
        with closing(self.connect()) as connection, connection:
            connection.execute(
                "DELETE FROM messages WHERE created_at < ?", (timestamp,)
            )
            connection.execute(
                "DELETE FROM deleted_messages WHERE deleted_at < ?", (timestamp,)
            )

    def get(
        self, message_id: int, *, include_style: bool = True
    ) -> MessageRecord | None:
        with closing(self.connect()) as connection:
            row = connection.execute(
                """
                SELECT message_id, guild_id, channel_id, author_id,
                       author_display, text, created_at, reply_to_id, edited_at, media_revision
                FROM messages WHERE message_id = ?
                  AND (? OR message_id NOT IN (SELECT message_id FROM style_examples))
                """,
                (str(message_id), include_style),
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
        through: datetime | None = None,
        omit: frozenset[int] = frozenset(),
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
                       messages.created_at, messages.reply_to_id, messages.edited_at, messages.media_revision
                FROM messages_fts JOIN messages ON messages.rowid = messages_fts.rowid
                WHERE messages_fts MATCH ? AND messages.guild_id = ? AND messages.channel_id = ?
                  AND messages.author_id IN (SELECT value FROM json_each(?))
                  AND messages.created_at BETWEEN ? AND ?
                  AND messages.message_id NOT IN (SELECT value FROM json_each(?))
                  AND messages.message_id NOT IN (SELECT message_id FROM style_examples)
                ORDER BY bm25(messages_fts), messages.created_at DESC, messages.rowid DESC
                LIMIT ?
                """,
                (
                    expression,
                    str(guild_id),
                    str(channel_id),
                    json.dumps([str(author) for author in authors]),
                    _utc_text(cutoff),
                    _utc_text(through) if through is not None else "9999",
                    json.dumps([str(message_id) for message_id in omit]),
                    min(limit, 32),
                ),
            ).fetchall()
        return tuple(_record(row) for row in rows)

    def add_style_example(
        self,
        guild_id: int,
        channel_id: int,
        author_id: int,
        message_id: int,
        chosen_at: datetime,
        cutoff: datetime,
    ) -> bool:
        with closing(self.connect()) as connection, connection:
            row = connection.execute(
                """
                INSERT INTO style_examples (message_id, chosen_at)
                SELECT message_id, ? FROM messages
                WHERE message_id = ? AND guild_id = ? AND channel_id = ? AND author_id = ?
                  AND created_at BETWEEN ? AND ?
                ON CONFLICT (message_id) DO NOTHING
                """,
                (
                    _utc_text(chosen_at),
                    str(message_id),
                    str(guild_id),
                    str(channel_id),
                    str(author_id),
                    _utc_text(cutoff),
                    _utc_text(chosen_at),
                ),
            )
            return row.rowcount == 1

    def style_examples(
        self, request: MessageRecord, authors: frozenset[int], cutoff: datetime
    ) -> tuple[MessageRecord, ...]:
        with closing(self.connect()) as connection:
            rows = connection.execute(
                """
                SELECT messages.message_id, messages.guild_id, messages.channel_id,
                       messages.author_id, messages.author_display, messages.text,
                       messages.created_at, messages.reply_to_id, messages.edited_at, messages.media_revision
                FROM style_examples JOIN messages USING (message_id)
                WHERE guild_id = ? AND channel_id = ? AND message_id <> ?
                  AND author_id IN (SELECT value FROM json_each(?))
                  AND created_at BETWEEN ? AND ?
                ORDER BY chosen_at DESC, messages.rowid DESC LIMIT 2
                """,
                (
                    str(request.guild_id),
                    str(request.channel_id),
                    str(request.message_id),
                    json.dumps([str(author) for author in authors]),
                    _utc_text(cutoff),
                    _utc_text(request.created_at),
                ),
            ).fetchall()
        return tuple(_record(row) for row in rows)

    def group_style(
        self,
        request: MessageRecord,
        authors: frozenset[int],
        cutoff: datetime,
        omit: frozenset[int] = frozenset(),
        limit: int = 2,
    ) -> tuple[MessageRecord, ...]:
        if limit <= 0 or not authors:
            return ()
        omitted = [str(item) for item in (omit | {request.message_id})]
        with closing(self.connect()) as connection:
            rows = connection.execute(
                """
                WITH candidates AS (
                    SELECT messages.message_id, messages.guild_id, messages.channel_id,
                           messages.author_id, messages.author_display, messages.text,
                           messages.created_at, messages.reply_to_id, messages.edited_at, messages.media_revision,
                           ROW_NUMBER() OVER (PARTITION BY messages.author_id ORDER BY messages.created_at DESC) as author_rank
                    FROM messages
                    WHERE guild_id = ? AND channel_id = ?
                      AND author_id IN (SELECT value FROM json_each(?))
                      AND message_id NOT IN (SELECT value FROM json_each(?))
                      AND created_at BETWEEN ? AND ?
                      AND length(text) >= 8 AND length(text) <= 160
                      AND text NOT GLOB '[/!.]*'
                      AND text NOT LIKE '%http://%' AND text NOT LIKE '%https://%'
                )
                SELECT message_id, guild_id, channel_id, author_id,
                       author_display, text, created_at, reply_to_id, edited_at, media_revision
                FROM candidates
                WHERE author_rank = 1
                ORDER BY created_at DESC LIMIT ?
                """,
                (
                    str(request.guild_id),
                    str(request.channel_id),
                    json.dumps([str(author) for author in authors]),
                    json.dumps(omitted),
                    _utc_text(cutoff),
                    _utc_text(request.created_at),
                    limit,
                ),
            ).fetchall()
        return tuple(_record(row) for row in rows)

    def records_unchanged(self, sources: tuple[MessageRecord, ...]) -> bool:
        with closing(self.connect()) as connection:
            rows = connection.execute(
                """
                SELECT message_id, guild_id, channel_id, author_id,
                       author_display, text, created_at, reply_to_id, edited_at, media_revision
                FROM messages WHERE message_id IN (SELECT value FROM json_each(?))
                """,
                (json.dumps([str(source.message_id) for source in sources]),),
            ).fetchall()
        return {_record(row) for row in rows} == set(sources)

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
                       author_display, text, created_at, reply_to_id, edited_at, media_revision
                FROM messages
                WHERE guild_id = ? AND channel_id = ? AND message_id <> ?
                  AND message_id NOT IN (SELECT message_id FROM style_examples)
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


def _write_media(
    connection: sqlite3.Connection, message_id: str, items: tuple[MediaItem, ...]
) -> None:
    connection.executemany(
        """
        INSERT INTO message_media (message_id, position, kind, external_id, mime, size)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            (message_id, index, item.kind, item.external_id, item.mime, item.size)
            for index, item in enumerate(items[:MAX_MEDIA_ITEMS])
        ),
    )


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
        media_revision=row[9],
    )
