"""Bounded, reversible social evidence sourced from authorized human messages."""

from __future__ import annotations

import json
import re
import sqlite3
import unicodedata
from collections import defaultdict
from contextlib import closing
from dataclasses import dataclass, replace
from datetime import UTC, datetime, timedelta
from hashlib import sha256
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pai.policy import PrivacyPolicy
    from pai.storage import Archive, MessageRecord

_MAX_ROWS = 192
_GAP = timedelta(minutes=20)
_ARABIC_MARKS = re.compile(r"[\u064b-\u065f\u0670\u0640]")
# Prefer clear group explanations over guessing from ordinary chatter.
_EXPLANATION = re.compile(
    r"^(?P<correction>actually[,: ]+|correction[,: ]+|لا[،, ]+|قصدي[،, ]+)?"
    r"(?:(?:for us|in (?:this|our) chat|عنا|عندنا|bil group|bel group)[,:، ]+)?"
    r'["“«\x60](?P<term>[^"”»\x60\n]+)["”»\x60]\s+'
    r"(?:means|is short for|يعني|معناها|ya3ni|yaani)\s+(?P<meaning>[^?\n]+)$",
    re.IGNORECASE,
)
_EXPLICIT_SUPPORT = re.compile(
    r"^(?:exactly[,. ]+)?(?:that['’]s what we mean|yeah[,]? that['’]s what we mean"
    r"|هذا قصدنا|بالضبط هيك قصدنا|ah hek asdna)[.!، ]*$",
    re.IGNORECASE,
)
_NEGATIVE = re.compile(
    r"^(?:(?:please )?(?:no more|stop (?:using|saying)|don['’]?t (?:use|say))\s+"
    r'["“«\x60](?P<term>[^"”»\x60\n]+)["”»\x60]|that joke is (?:annoying|not funny)'
    r"|please (?:stop using|don['’]t use) that (?:joke|expression)"
    r"|خلص بلاش هالمزحة)[.!، ]*$",
    re.IGNORECASE,
)
_UNSAFE = re.compile(
    r"https?://|[@<>]|[\r\n]|[\u202a-\u202e\u2066-\u2069]"
    r"|\b(?:ignore|instructions?|prompt|system message|password|token|credential|dox"
    r"|send me|reveal|address|phone number|full name|email|medical diagnosis)\b"
    r"|\d{7,}|(?:تجاهل|تعليمات|كلمة السر|رقم الهاتف|عنوان البيت|ابعثلي)"
    r"|\b(?:he|she|his|her|they|my|their|our friend)\s+(?:is|are|always|never|address|phone)\b",
    re.IGNORECASE,
)


def _key(text: str) -> str:
    text = unicodedata.normalize("NFKC", text).replace("\ufe0f", "")
    return " ".join(_ARABIC_MARKS.sub("", text).casefold().split())


def mentions_term(text: str, term: str) -> bool:
    return bool(re.search(rf"(?<!\w){re.escape(term)}(?!\w)", _key(text)))


def _term(text: str) -> str:
    key = _key(text)
    if not 1 <= len(key) <= 56 or len(key.split()) > 6 or _UNSAFE.search(text):
        return ""
    return key


def _time(value: datetime) -> str:
    return value.astimezone(UTC).isoformat(timespec="microseconds")


def _members(policy: PrivacyPolicy) -> str:
    return json.dumps(
        sorted(
            str(x)
            for x in policy.social_consenting_member_ids & policy.consenting_member_ids
        )
    )


def purge_social(db: sqlite3.Connection, policy: PrivacyPolicy) -> None:
    if not db.execute(
        "SELECT 1 FROM sqlite_master WHERE name='social_evidence_v1'"
    ).fetchone():
        return
    db.execute(
        """DELETE FROM social_evidence_v1
           WHERE notice_version<>? OR message_id IN (
             SELECT message_id FROM messages WHERE
               NOT ? OR guild_id<>? OR channel_id NOT IN (SELECT value FROM json_each(?))
               OR author_id NOT IN (SELECT value FROM json_each(?))
           )""",
        (
            policy.notice_version,
            policy.is_enabled
            and policy.social_learning_opt_in
            and policy.external_ai_opt_in,
            str(policy.guild_id),
            json.dumps(sorted(str(ch) for ch in policy.channel_ids)),
            _members(policy),
        ),
    )


@dataclass(frozen=True)
class SocialNote:
    term: str
    meaning: str
    confidence: str
    sources: tuple[MessageRecord, ...]

    @property
    def fingerprint(self) -> str:
        value = (
            self.term,
            self.meaning,
            self.confidence,
            sorted(row.message_id for row in self.sources),
        )
        return sha256(json.dumps(value, ensure_ascii=False).encode()).hexdigest()


@dataclass(frozen=True)
class _Evidence:
    term: str
    meaning: str
    kind: str
    source: MessageRecord
    parent: MessageRecord | None


class SocialStore:
    def __init__(self, archive: Archive, policy: PrivacyPolicy) -> None:
        self.archive = archive
        self.policy = policy
        with closing(archive.connect()) as db, db:
            db.execute("""CREATE TABLE IF NOT EXISTS social_evidence_v1 (
                message_id TEXT NOT NULL REFERENCES messages(message_id) ON DELETE CASCADE,
                term TEXT NOT NULL,
                meaning TEXT NOT NULL,
                kind TEXT NOT NULL CHECK(kind IN ('candidate','confirm','support','suppress')),
                notice_version TEXT NOT NULL,
                parent_id TEXT REFERENCES messages(message_id) ON DELETE CASCADE,
                PRIMARY KEY (message_id,term)
            )""")
            db.execute("""CREATE TRIGGER IF NOT EXISTS social_evidence_edited
                AFTER UPDATE OF edited_at ON messages WHEN NEW.edited_at IS NOT OLD.edited_at
                BEGIN DELETE FROM social_evidence_v1 WHERE message_id=NEW.message_id; END""")
            db.execute("""CREATE TRIGGER IF NOT EXISTS social_evidence_unsupported
                AFTER DELETE ON social_evidence_v1 WHEN OLD.parent_id IS NULL
                BEGIN DELETE FROM social_evidence_v1 WHERE parent_id=OLD.message_id AND term=OLD.term; END""")
            purge_social(db, policy)

    def permits(self, source: MessageRecord) -> bool:
        return self.policy.permits_social(
            source.guild_id, source.channel_id, source.author_id
        ) and source.created_at >= datetime.now(UTC) - timedelta(
            days=self.policy.retention_days
        )

    def _write(
        self,
        source: MessageRecord,
        term: str,
        meaning: str,
        kind: str,
        *,
        parent: MessageRecord | None = None,
        correction: bool = False,
    ) -> bool:
        if not self.permits(source) or not term:
            return False
        with closing(self.archive.connect()) as db, db:
            db.execute("BEGIN IMMEDIATE")
            if not self.archive.records_unchanged(
                (source,) + ((parent,) if parent else ())
            ):
                return False
            if correction:
                db.execute(
                    """DELETE FROM social_evidence_v1 WHERE term=? AND kind!='suppress'
                       AND message_id IN (SELECT message_id FROM messages
                         WHERE guild_id=? AND channel_id=? AND author_id=? AND created_at<=?)""",
                    (
                        term,
                        str(source.guild_id),
                        str(source.channel_id),
                        str(source.author_id),
                        _time(source.created_at),
                    ),
                )
            inserted = db.execute(
                """INSERT INTO social_evidence_v1 VALUES (?,?,?,?,?,?)
                   ON CONFLICT(message_id,term) DO NOTHING""",
                (
                    str(source.message_id),
                    term,
                    meaning,
                    kind,
                    self.policy.notice_version,
                    str(parent.message_id) if parent else None,
                ),
            ).rowcount
            db.execute(
                """DELETE FROM social_evidence_v1 WHERE (message_id,term) IN (
                   SELECT e.message_id,e.term FROM social_evidence_v1 e JOIN messages m USING(message_id)
                   WHERE m.guild_id=? AND m.channel_id=? ORDER BY m.created_at DESC,m.rowid DESC
                   LIMIT -1 OFFSET ?
               )""",
                (str(source.guild_id), str(source.channel_id), _MAX_ROWS),
            )
            return bool(inserted)

    def observe(
        self, source: MessageRecord, feedback_terms: tuple[str, ...] = ()
    ) -> bool:
        if not self.permits(source):
            return False
        text = source.text.strip()
        if len(text) > 360:
            return False
        if negative := _NEGATIVE.fullmatch(text):
            term = negative["term"]
            words = (_term(term),) if term else feedback_terms[:2]
            return bool(
                sum(self._write(source, word, "", "suppress") for word in words)
            )
        if match := _EXPLANATION.fullmatch(text):
            term = _term(match["term"])
            meaning = match["meaning"].strip().rstrip(".!،")
            if 4 <= len(meaning) <= 160 and not _UNSAFE.search(meaning):
                return self._write(
                    source,
                    term,
                    meaning,
                    "candidate",
                    correction=bool(match["correction"]),
                )
            return False
        if not source.reply_to_id or not _EXPLICIT_SUPPORT.fullmatch(text):
            return False
        parent = self.archive.get(source.reply_to_id)
        if (
            parent is None
            or parent.author_id == source.author_id
            or not self.permits(parent)
            or (parent.guild_id, parent.channel_id)
            != (source.guild_id, source.channel_id)
            or parent.created_at >= source.created_at
        ):
            return False
        with closing(self.archive.connect()) as db:
            row = db.execute(
                """SELECT term FROM social_evidence_v1
                   WHERE message_id=? AND notice_version=? AND kind IN ('candidate','confirm')
                   LIMIT 1""",
                (str(parent.message_id), self.policy.notice_version),
            ).fetchone()
        return bool(row and self._write(source, row[0], "", "support", parent=parent))

    def _evidence(self, scope: MessageRecord) -> tuple[_Evidence, ...]:
        if not self.permits(scope):
            return ()
        from pai.storage import _record

        columns = (
            "message_id",
            "guild_id",
            "channel_id",
            "author_id",
            "author_display",
            "text",
            "created_at",
            "reply_to_id",
            "edited_at",
            "media_revision",
        )
        source_columns = ",".join(f"m.{column}" for column in columns)
        parent_columns = ",".join(f"root.{column}" for column in columns)
        with closing(self.archive.connect()) as db:
            rows = db.execute(
                f"""SELECT e.term,coalesce(p.meaning,e.meaning),e.kind,
                           {source_columns},{parent_columns}
                    FROM social_evidence_v1 e JOIN messages m ON e.message_id=m.message_id
                    LEFT JOIN social_evidence_v1 p ON e.parent_id=p.message_id AND e.term=p.term
                    LEFT JOIN messages root ON root.message_id=e.parent_id
                    WHERE m.guild_id=? AND m.channel_id=? AND e.notice_version=?
                      AND m.author_id IN (SELECT value FROM json_each(?))
                      AND m.created_at BETWEEN ? AND ? AND m.message_id<>?
                      AND (e.parent_id IS NULL OR p.notice_version=e.notice_version)
                    ORDER BY m.created_at DESC,m.rowid DESC LIMIT ?""",
                (
                    str(scope.guild_id),
                    str(scope.channel_id),
                    self.policy.notice_version,
                    _members(self.policy),
                    _time(
                        datetime.now(UTC) - timedelta(days=self.policy.retention_days)
                    ),
                    _time(scope.created_at),
                    str(scope.message_id),
                    _MAX_ROWS,
                ),
            ).fetchall()
        result = []
        for term, meaning, kind, *references in rows:
            source = _record(references[:10])
            parent = _record(references[10:]) if references[10] is not None else None
            if parent is not None and (
                not self.permits(parent)
                or (parent.guild_id, parent.channel_id)
                != (scope.guild_id, scope.channel_id)
            ):
                continue
            result.append(_Evidence(term, meaning, kind, source, parent))
        return tuple(result)

    def retrieve(
        self,
        request: MessageRecord,
        query: str | None = None,
        *,
        terms: frozenset[str] | None = None,
    ) -> tuple[SocialNote, ...]:
        if _NEGATIVE.fullmatch(request.text.strip()) or _EXPLANATION.fullmatch(
            request.text.strip()
        ):
            return ()
        text = request.text if query is None else query
        groups: dict[str, list[_Evidence]] = defaultdict(list)
        suppressed = set()
        for row in self._evidence(request):
            if not (
                row.term in terms
                if terms is not None
                else mentions_term(text, row.term)
            ):
                continue
            if row.kind == "suppress":
                if row.source.author_id == request.author_id:
                    suppressed.add(row.term)
            else:
                groups[row.term].append(row)
        notes = []
        for term, rows in sorted(
            groups.items(), key=lambda item: len(item[0]), reverse=True
        ):
            if term in suppressed or len({_key(row.meaning) for row in rows}) != 1:
                continue
            chosen = next((row for row in rows if row.kind == "confirm"), None)
            if chosen:
                witnesses = (chosen,)
                confidence = "confirmed"
            else:
                witnesses = next(
                    (
                        (a, b)
                        for a in rows
                        for b in reversed(rows)
                        if a.source.author_id != b.source.author_id
                        and a.source.created_at - b.source.created_at >= _GAP
                    ),
                    (),
                )
                confidence = "corroborated"
            if witnesses:
                provenance = tuple(
                    dict.fromkeys(
                        x
                        for w in witnesses
                        for x in (w.source, w.parent)
                        if x is not None
                    )
                )
                notes.append(
                    SocialNote(term, witnesses[0].meaning, confidence, provenance)
                )
            if len(notes) == 2:
                break
        return tuple(notes)

    def revalidate(
        self,
        origin: MessageRecord,
        recipient: MessageRecord,
        fingerprints: dict[str, str],
    ) -> tuple[SocialNote, ...] | None:
        if (
            (origin.guild_id, origin.channel_id)
            != (recipient.guild_id, recipient.channel_id)
            or not self.permits(origin)
            or not self.permits(recipient)
        ):
            return None
        through = max(datetime.now(UTC), recipient.created_at)
        terms = frozenset(fingerprints)
        notes = self.retrieve(replace(origin, created_at=through), terms=terms)
        if {note.term: note.fingerprint for note in notes} != fingerprints:
            return None
        if origin.author_id != recipient.author_id:
            current = self.retrieve(
                replace(origin, author_id=recipient.author_id, created_at=through),
                terms=terms,
            )
            if {note.term: note.fingerprint for note in current} != fingerprints:
                return None
        return notes

    def confirm(self, scope: MessageRecord, message_id: int) -> bool:
        if not self.permits(scope):
            return False
        with closing(self.archive.connect()) as db, db:
            return bool(
                db.execute(
                    """UPDATE social_evidence_v1 SET kind='confirm' WHERE message_id=?
                   AND notice_version=? AND kind='candidate' AND message_id IN (
                     SELECT message_id FROM messages WHERE guild_id=? AND channel_id=? AND author_id=?
                     AND created_at>=?
                   )""",
                    (
                        str(message_id),
                        self.policy.notice_version,
                        str(scope.guild_id),
                        str(scope.channel_id),
                        str(scope.author_id),
                        _time(
                            datetime.now(UTC)
                            - timedelta(days=self.policy.retention_days)
                        ),
                    ),
                ).rowcount
            )

    def withdraw(self, scope: MessageRecord, expression: str) -> int:
        if not self.permits(scope) or not (term := _term(expression)):
            return 0
        with closing(self.archive.connect()) as db, db:
            return db.execute(
                """DELETE FROM social_evidence_v1 WHERE term=? AND notice_version=?
                   AND message_id IN (SELECT message_id FROM messages
                     WHERE guild_id=? AND channel_id=? AND author_id=?)""",
                (
                    term,
                    self.policy.notice_version,
                    str(scope.guild_id),
                    str(scope.channel_id),
                    str(scope.author_id),
                ),
            ).rowcount

    def inspect(self, scope: MessageRecord) -> tuple[tuple[str, str, str], ...]:
        return tuple(
            (row.term, row.kind, row.source.jump_url)
            for row in self._evidence(scope)
            if row.source.author_id == scope.author_id
        )[:8]
