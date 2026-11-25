"""Verified native branch continuity without a second transcript."""

from contextlib import closing
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from hashlib import sha256
from sqlite3 import Connection

from pai.conversation import AssistantTurn, ConversationContext, _normalized_request
from pai.policy import PrivacyPolicy
from pai.storage import Archive, MessageRecord, _record, _utc_text
from pai.voice import _BOT_TAUNT

_SCHEMA = """
CREATE TABLE IF NOT EXISTS assistant_receipts_v1 (
    reply_id TEXT PRIMARY KEY,
    request_id TEXT NOT NULL REFERENCES messages(message_id) ON DELETE CASCADE,
    guild_id TEXT NOT NULL,
    channel_id TEXT NOT NULL,
    notice_version TEXT NOT NULL,
    delivered_at TEXT NOT NULL,
    digest TEXT NOT NULL,
    recall_id TEXT
);
CREATE INDEX IF NOT EXISTS assistant_receipts_scope
    ON assistant_receipts_v1(guild_id,channel_id,delivered_at);
CREATE TABLE IF NOT EXISTS assistant_receipt_sources_v1 (
    reply_id TEXT NOT NULL REFERENCES assistant_receipts_v1(reply_id) ON DELETE CASCADE,
    source_id TEXT NOT NULL REFERENCES messages(message_id) ON DELETE CASCADE,
    ordinal INTEGER NOT NULL,
    PRIMARY KEY (reply_id, source_id)
);
CREATE INDEX IF NOT EXISTS assistant_receipt_sources_message
    ON assistant_receipt_sources_v1(source_id);
CREATE TRIGGER IF NOT EXISTS assistant_receipt_source_delete BEFORE DELETE ON messages
BEGIN
  DELETE FROM assistant_receipts_v1 WHERE reply_id IN (
      SELECT reply_id FROM assistant_receipt_sources_v1 WHERE source_id=OLD.message_id);
END;
CREATE TRIGGER IF NOT EXISTS assistant_receipt_source_change
AFTER UPDATE OF text, edited_at, media_revision ON messages
WHEN NEW.text IS NOT OLD.text OR NEW.edited_at IS NOT OLD.edited_at
    OR NEW.media_revision IS NOT OLD.media_revision
BEGIN
  DELETE FROM assistant_receipts_v1 WHERE reply_id IN (
      SELECT reply_id FROM assistant_receipt_sources_v1 WHERE source_id=OLD.message_id);
END;
CREATE TRIGGER IF NOT EXISTS assistant_receipt_target_delete
AFTER INSERT ON deleted_messages
BEGIN
  DELETE FROM assistant_receipts_v1 WHERE reply_id=NEW.message_id
    AND guild_id=NEW.guild_id AND channel_id=NEW.channel_id;
END;
"""


def purge_receipts(connection: Connection, policy: PrivacyPolicy) -> None:
    if connection.execute(
        "SELECT 1 FROM sqlite_master WHERE name='assistant_receipts_v1'"
    ).fetchone():
        connection.execute(
            "DELETE FROM assistant_receipts_v1 WHERE NOT ? OR notice_version<>?",
            (
                policy.assistant_continuity_opt_in and policy.is_enabled,
                policy.notice_version,
            ),
        )


class AssistantReceipts:
    def __init__(self, archive: Archive, policy: PrivacyPolicy) -> None:
        self.archive = archive
        self.policy = policy
        if policy.assistant_continuity_opt_in and policy.is_enabled:
            with closing(archive.connect()) as connection:
                connection.executescript(_SCHEMA)

    def _eligible(self, row: MessageRecord, guild: int, channel: int) -> bool:
        return (
            self.policy.assistant_continuity_opt_in
            and (row.guild_id, row.channel_id) == (guild, channel)
            and self.policy.permits(guild, channel, row.author_id)
        )

    def remember(self, turn: AssistantTurn) -> bool:
        request = turn.request
        sources = tuple(dict.fromkeys(turn.sources))
        guild, channel = request.guild_id, request.channel_id
        if (
            not turn.text
            or turn.message_id is None
            or turn.created_at is None
            or not 1 <= len(sources) <= 32
            or request not in sources
            or not all(self._eligible(row, guild, channel) for row in sources)
        ):
            return False
        reply_id = str(turn.message_id)
        recall_id = (
            str(turn.recall_question.message_id)
            if turn.recall_question is not None and turn.recall_question in sources
            else None
        )
        with closing(self.archive.connect()) as db, db:
            db.execute("BEGIN IMMEDIATE")
            if (
                not self.archive.records_unchanged(sources)
                or db.execute(
                    """SELECT 1 FROM deleted_messages
                   WHERE message_id=? AND guild_id=? AND channel_id=?""",
                    (reply_id, str(guild), str(channel)),
                ).fetchone()
            ):
                return False
            cursor = db.execute(
                """INSERT INTO assistant_receipts_v1
                   (reply_id,request_id,guild_id,channel_id,notice_version,
                    delivered_at,digest,recall_id) VALUES (?,?,?,?,?,?,?,?)
                   ON CONFLICT(reply_id) DO NOTHING""",
                (
                    reply_id,
                    str(request.message_id),
                    str(guild),
                    str(channel),
                    self.policy.notice_version,
                    _utc_text(turn.created_at),
                    sha256(turn.text.encode()).hexdigest(),
                    recall_id,
                ),
            )
            if not cursor.rowcount:
                return False
            db.executemany(
                "INSERT INTO assistant_receipt_sources_v1 VALUES (?,?,?)",
                ((reply_id, str(row.message_id), i) for i, row in enumerate(sources)),
            )
            db.execute(
                """DELETE FROM assistant_receipts_v1 WHERE reply_id IN (
                       SELECT reply_id FROM assistant_receipts_v1
                       WHERE guild_id=? AND channel_id=?
                       ORDER BY delivered_at DESC, rowid DESC LIMIT -1 OFFSET 192
                   )""",
                (str(guild), str(channel)),
            )
        return True

    def recover(
        self, request: MessageRecord, reply_id: int, original_id: int, text: str
    ) -> AssistantTurn | None:
        guild, channel = request.guild_id, request.channel_id
        if request.reply_to_id != reply_id or not self._eligible(
            request, guild, channel
        ):
            return None
        cutoff = max(request.created_at, datetime.now(UTC)) - timedelta(
            days=self.policy.retention_days
        )
        with closing(self.archive.connect()) as db:
            db.execute("BEGIN")
            receipt = db.execute(
                """SELECT delivered_at, recall_id FROM assistant_receipts_v1
                   WHERE reply_id=? AND request_id=? AND guild_id=? AND channel_id=?
                     AND notice_version=? AND delivered_at BETWEEN ? AND ? AND digest=?""",
                (
                    str(reply_id),
                    str(original_id),
                    str(guild),
                    str(channel),
                    self.policy.notice_version,
                    _utc_text(cutoff),
                    _utc_text(request.created_at),
                    sha256(text.encode()).hexdigest(),
                ),
            ).fetchone()
            if receipt is None:
                return None
            rows = db.execute(
                """SELECT m.message_id,m.guild_id,m.channel_id,m.author_id,
                          m.author_display,m.text,m.created_at,m.reply_to_id,
                          m.edited_at,m.media_revision
                   FROM assistant_receipt_sources_v1 s JOIN messages m
                     ON s.source_id=m.message_id WHERE s.reply_id=? ORDER BY s.ordinal""",
                (str(reply_id),),
            ).fetchall()
        sources = tuple(_record(row) for row in rows)
        if not sources or not all(
            self._eligible(row, guild, channel)
            and cutoff <= row.created_at <= request.created_at
            for row in sources
        ):
            return None
        by_id = {str(row.message_id): row for row in sources}
        original = by_id.get(str(original_id))
        if not original:
            return None
        return AssistantTurn(
            text,
            original,
            sources,
            by_id.get(receipt[1]),
            message_id=reply_id,
            created_at=datetime.fromisoformat(receipt[0]),
        )


def focus_native_branch(context: ConversationContext) -> ConversationContext:
    if not context.native_reply or context.assistant_turn is None:
        return context
    anchors = {
        context.request.reply_to_id,
        *(row.message_id for row in context.parents),
    }
    turn = context.assistant_turn
    while turn is not None:
        anchors.update(
            (turn.message_id, turn.request.message_id, turn.request.reply_to_id)
        )
        turn = turn.prior_turn
    excluded = set()
    for row in context.recent:
        if row.reply_to_id in anchors and row.reply_to_id is not None:
            anchors.add(row.message_id)
        elif row.reply_to_id is not None:
            excluded.add(row.message_id)
    if not excluded:
        return context
    return replace(
        context,
        recent=tuple(row for row in context.recent if row.message_id not in excluded),
        observed_speakers=tuple(
            row for row in context.observed_speakers if row.message_id not in excluded
        ),
    )


def clarify_harmful_parent(context: ConversationContext) -> bool:
    return bool(
        not _normalized_request(context.request.text).strip()
        and context.parents
        and context.parents[0].message_id == context.request.reply_to_id
        and _BOT_TAUNT.fullmatch(_normalized_request(context.parents[0].text))
    )
