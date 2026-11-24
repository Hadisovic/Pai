"""Source-linked metadata for previously shared animations."""

from __future__ import annotations

import json
import re
import sqlite3
from contextlib import closing
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pai.policy import PrivacyPolicy
    from pai.storage import Archive, MessageRecord

_MAX_SOURCES = 256
_TERMS = re.compile(r"[^\W_]{3,}", re.UNICODE)
_STOP = frozenset(
    "the and for this that was are with you your have from about would could gif reply says what why when where who how now".split()
)


def _words(text: str) -> set[str]:
    return set(_TERMS.findall(text.casefold())) - _STOP


def _time(value: datetime) -> str:
    return value.astimezone(UTC).isoformat(timespec="microseconds")


def purge_gifs(db: sqlite3.Connection, policy: PrivacyPolicy) -> None:
    # An optional, separately versioned extension keeps the golden archive
    # schema version readable on a code rollback.
    if not db.execute(
        "SELECT 1 FROM sqlite_master WHERE name='gif_sources_v1'"
    ).fetchone():
        return
    db.execute(
        """DELETE FROM gif_sources_v1
           WHERE notice_version<>? OR message_id IN (
             SELECT message_id FROM messages
             WHERE NOT ? OR guild_id<>? OR channel_id NOT IN (SELECT value FROM json_each(?))
               OR author_id NOT IN (SELECT value FROM json_each(?))
           )""",
        (
            policy.notice_version,
            policy.is_enabled and policy.gif_reuse_opt_in and policy.external_ai_opt_in,
            str(policy.guild_id),
            json.dumps([str(x) for x in policy.channel_ids]),
            json.dumps(
                [
                    str(x)
                    for x in policy.gif_consenting_member_ids
                    & policy.consenting_member_ids
                ]
            ),
        ),
    )


@dataclass(frozen=True)
class GifEntry:
    source: MessageRecord
    asset_id: str
    fingerprint: str
    description: str


class GifStore:
    def __init__(self, archive: Archive, policy: PrivacyPolicy) -> None:
        self.archive = archive
        self.policy = policy
        with closing(archive.connect()) as db, db:
            db.execute("""CREATE TABLE IF NOT EXISTS gif_sources_v1 (
                message_id TEXT NOT NULL REFERENCES messages(message_id) ON DELETE CASCADE,
                asset_id TEXT NOT NULL,
                fingerprint TEXT NOT NULL,
                description TEXT NOT NULL,
                notice_version TEXT NOT NULL,
                last_used TEXT,
                PRIMARY KEY (message_id, asset_id)
            )""")
            db.execute(
                "CREATE INDEX IF NOT EXISTS gif_sources_fingerprint ON gif_sources_v1(fingerprint)"
            )
            db.execute("""CREATE TRIGGER IF NOT EXISTS gif_sources_edited AFTER UPDATE OF edited_at, media_revision
                ON messages WHEN NEW.edited_at IS NOT OLD.edited_at OR NEW.media_revision <> OLD.media_revision
                BEGIN DELETE FROM gif_sources_v1 WHERE message_id=NEW.message_id; END""")
            db.execute(
                "CREATE TABLE IF NOT EXISTS gif_analysis_v1 (started_at TEXT PRIMARY KEY)"
            )
            purge_gifs(db, policy)

    def reserve_analysis(self) -> bool:
        now = datetime.now(UTC)
        with closing(self.archive.connect()) as db, db:
            db.execute("BEGIN IMMEDIATE")
            db.execute(
                "DELETE FROM gif_analysis_v1 WHERE started_at<?",
                (_time(now - timedelta(days=1)),),
            )
            count, last = db.execute(
                "SELECT count(*), max(started_at) FROM gif_analysis_v1"
            ).fetchone()
            if count >= 12 or (last and last > _time(now - timedelta(seconds=30))):
                return False
            db.execute("INSERT INTO gif_analysis_v1 VALUES (?)", (_time(now),))
            return True

    def permits(self, record: MessageRecord) -> bool:
        return self.policy.permits_gif(
            record.guild_id, record.channel_id, record.author_id
        ) and (
            record.created_at
            >= datetime.now(UTC) - timedelta(days=self.policy.retention_days)
        )

    def _scope(self, record: MessageRecord):
        return (
            str(record.guild_id),
            str(record.channel_id),
            self.policy.notice_version,
            json.dumps(
                [
                    str(a)
                    for a in self.policy.gif_consenting_member_ids
                    & self.policy.consenting_member_ids
                ]
            ),
            _time(datetime.now(UTC) - timedelta(days=self.policy.retention_days)),
        )

    def _rows(self, scope: MessageRecord, extra: str = "", args: tuple = ()):
        if not self.permits(scope):
            return ()
        with closing(self.archive.connect()) as db:
            return db.execute(
                """SELECT g.message_id,g.asset_id,g.fingerprint,g.description,g.last_used,m.text,
                          EXISTS(SELECT 1 FROM style_examples WHERE message_id=g.message_id)
                   FROM gif_sources_v1 g JOIN messages m ON m.message_id=g.message_id
                   WHERE m.guild_id=? AND m.channel_id=? AND g.notice_version=?
                     AND m.author_id IN (SELECT value FROM json_each(?)) AND m.created_at>=?
                   """
                + extra
                + " ORDER BY m.created_at DESC, m.rowid DESC LIMIT ?",
                (*self._scope(scope), *args, _MAX_SOURCES),
            ).fetchall()

    def description(self, scope: MessageRecord, fingerprint: str) -> str:
        rows = self._rows(scope, "AND g.fingerprint=?", (fingerprint,))
        return rows[0][3] if rows else ""

    def entry(
        self, record: MessageRecord, asset_id: str | None = None
    ) -> GifEntry | None:
        extra = "AND g.message_id=?"
        args = (str(record.message_id),)
        if asset_id is not None:
            extra += " AND g.asset_id=?"
            args += (asset_id,)
        rows = self._rows(record, extra, args)
        if not rows or not self.archive.records_unchanged((record,)):
            return None
        _, asset, fingerprint, description, *_ = rows[0]
        return GifEntry(record, asset, fingerprint, description)

    def retain_assets(self, source: MessageRecord, assets: tuple[str, ...]) -> None:
        if not self.permits(source):
            return
        with closing(self.archive.connect()) as db, db:
            db.execute(
                """DELETE FROM gif_sources_v1 WHERE message_id=?
                   AND asset_id NOT IN (SELECT value FROM json_each(?))
                   AND EXISTS(SELECT 1 FROM messages WHERE message_id=?
                       AND edited_at IS ? AND media_revision=?)""",
                (
                    str(source.message_id),
                    json.dumps(assets),
                    str(source.message_id),
                    _time(source.edited_at) if source.edited_at else None,
                    source.media_revision,
                ),
            )

    def remember(
        self, source: MessageRecord, asset_id: str, fingerprint: str, description: str
    ) -> bool:
        if not self.permits(source) or not description or len(description) > 600:
            return False
        with closing(self.archive.connect()) as db, db:
            row = db.execute(
                """INSERT INTO gif_sources_v1(message_id,asset_id,fingerprint,description,notice_version,last_used)
                   SELECT message_id,?,?,?,?,
                     (SELECT max(g.last_used) FROM gif_sources_v1 g JOIN messages other USING(message_id)
                      WHERE g.fingerprint=? AND other.guild_id=? AND other.channel_id=?)
                   FROM messages WHERE message_id=? AND guild_id=? AND channel_id=? AND author_id=?
                     AND text=? AND edited_at IS ? AND media_revision=?
                   ON CONFLICT(message_id,asset_id) DO NOTHING""",
                (
                    asset_id,
                    fingerprint,
                    description,
                    self.policy.notice_version,
                    fingerprint,
                    str(source.guild_id),
                    str(source.channel_id),
                    str(source.message_id),
                    str(source.guild_id),
                    str(source.channel_id),
                    str(source.author_id),
                    source.text,
                    _time(source.edited_at) if source.edited_at else None,
                    source.media_revision,
                ),
            )
            if not row.rowcount:
                return False
            db.execute(
                """DELETE FROM gif_sources_v1 WHERE (message_id,asset_id) IN (
                   SELECT g.message_id,g.asset_id FROM gif_sources_v1 g JOIN messages m USING(message_id)
                   WHERE m.guild_id=? AND m.channel_id=?
                   ORDER BY m.created_at DESC,m.rowid DESC,g.asset_id LIMIT -1 OFFSET ?
                )""",
                (str(source.guild_id), str(source.channel_id), _MAX_SOURCES),
            )
            return True

    def candidates(self, request: MessageRecord, query: str) -> tuple[GifEntry, ...]:
        terms = _words(query)
        if not terms:
            return ()
        cooldown = _time(datetime.now(UTC) - timedelta(minutes=12))
        ranked = []
        for row in self._rows(
            request, "AND (g.last_used IS NULL OR g.last_used<?)", (cooldown,)
        ):
            mid, asset, fingerprint, description, _, caption, approved = row
            score = len(terms & _words(description)) * 2 + len(terms & _words(caption))
            if score and int(mid) != request.message_id:
                ranked.append(
                    (score + int(approved), mid, asset, fingerprint, description)
                )
        entries = []
        seen = set()
        for _, mid, asset, fingerprint, description in sorted(
            ranked, key=lambda r: r[0], reverse=True
        ):
            if fingerprint in seen:
                continue
            source = self.archive.get(int(mid))
            if source is not None and self.permits(source):
                entries.append(GifEntry(source, asset, fingerprint, description))
                seen.add(fingerprint)
            if len(entries) == 3:
                break
        return tuple(entries)

    def mark_used(self, entry: GifEntry) -> None:
        with closing(self.archive.connect()) as db, db:
            db.execute(
                """UPDATE gif_sources_v1 SET last_used=? WHERE fingerprint=? AND message_id IN (
                    SELECT message_id FROM messages WHERE guild_id=? AND channel_id=?
                )""",
                (
                    _time(datetime.now(UTC)),
                    entry.fingerprint,
                    str(entry.source.guild_id),
                    str(entry.source.channel_id),
                ),
            )
