"""The explicit mention parser and bounded same-channel context."""

import re
from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from pai.policy import PrivacyPolicy
from pai.storage import Archive, MessageRecord

_TOKEN = re.compile(r"\\.|(`+).*?(?<!`)\1(?!`)|<@!?([0-9]+)>", re.DOTALL)
_PARENT_LIMIT = 4
_RECENT_LIMIT = 8
_MEMORY_LIMIT = 4
_QUERY_WORDS = re.compile(r"[^\W_]+")
_DISCORD_TAG = re.compile(r"<[@#][!&]?[0-9]+>")
_STOP_WORDS = frozenset(
    "a an and are as at be by can could did do does for from had has have hey how i in "
    "is it me of on or our pai say tell than that the their them there they this to us "
    "was we were what when where which who why will with would you your".split()
)


_SELF_RECALL = re.compile(
    r"\b(?:(?:what|which|where|when|who)(?:['’]s|\s+(?:is|are|was|were))\s+my|"
    r"(?:what|which|where|when)\s+(?:did|do|was|am|have)\s+i|"
    r"who am i|(?:remember|recall)\s+(?:my|what i|when i))\b"
    r"|(?:شو|ايش|إيش|ما)\s+(?:اسمي|اسمي؟|لعبتي المفضلة)",
    re.IGNORECASE,
)


def direct_mention(text: str, recognized_targets: Iterable[int], bot_id: int) -> bool:
    return bot_id in recognized_targets and any(
        match[2] == str(bot_id) for match in _TOKEN.finditer(text)
    )


@dataclass(frozen=True)
class MediaReading:
    unavailable: bool = False
    description: str = ""
    origin: MessageRecord | None = None
    source: MessageRecord | None = None


@dataclass(frozen=True)
class AssistantTurn:
    text: str
    sources: tuple[MessageRecord, ...]


@dataclass(frozen=True)
class GroupExpression:
    text: str
    sources: tuple[MessageRecord, ...]


@dataclass(frozen=True)
class ConversationContext:
    request: MessageRecord
    parents: tuple[MessageRecord, ...] = ()
    recent: tuple[MessageRecord, ...] = ()
    memory: tuple[MessageRecord, ...] = ()
    style_examples: tuple[MessageRecord, ...] = ()
    media: MediaReading = MediaReading()
    group_style: tuple[GroupExpression, ...] = ()
    self_recall: bool = False
    assistant_turn: AssistantTurn | None = None

    @property
    def sources(self) -> tuple[MessageRecord, ...]:
        included = (
            self.request,
            *self.parents,
            *self.recent,
            *self.memory,
            *self.style_examples,
            *(
                source
                for expression in self.group_style
                for source in expression.sources
            ),
            *(self.assistant_turn.sources if self.assistant_turn is not None else ()),
            *((self.media.origin,) if self.media.origin is not None else ()),
        )
        return tuple(dict.fromkeys(included))


def prepare_context(
    archive: Archive,
    policy: PrivacyPolicy,
    request: MessageRecord,
    *,
    now: datetime | None = None,
) -> ConversationContext:
    if not policy.permits(request.guild_id, request.channel_id, request.author_id):
        raise ValueError("The request is outside authorized scope")
    cutoff = (now or request.created_at) - timedelta(days=policy.retention_days)
    self_recall = bool(_SELF_RECALL.search(request.text))
    authors = (
        frozenset({request.author_id}) if self_recall else policy.consenting_member_ids
    )
    seen = {request.message_id}
    parents = []
    parent_id = request.reply_to_id
    while (
        parent_id is not None and parent_id not in seen and len(parents) < _PARENT_LIMIT
    ):
        parent = archive.get(parent_id, include_style=False)
        if (
            parent is None
            or (parent.guild_id, parent.channel_id)
            != (request.guild_id, request.channel_id)
            or not policy.permits(parent.guild_id, parent.channel_id, parent.author_id)
            or parent.author_id not in authors
            or not cutoff <= parent.created_at <= request.created_at
        ):
            break
        seen.add(parent_id)
        parents.append(parent)
        parent_id = parent.reply_to_id

    recent = archive.recent(request, authors, cutoff, _RECENT_LIMIT + len(parents))
    visible = tuple(row for row in recent if row.message_id not in seen)[:_RECENT_LIMIT]
    seen.update(row.message_id for row in visible)
    terms = _QUERY_WORDS.findall(_DISCORD_TAG.sub("", request.text).lower())
    query = " ".join(
        term
        for term in terms
        if term not in _STOP_WORDS and term != "my" and len(term) > 1
    )
    memory = archive.search(
        query,
        guild_id=request.guild_id,
        channel_id=request.channel_id,
        authors=authors,
        statements_only=self_recall,
        cutoff=cutoff,
        limit=_MEMORY_LIMIT,
        through=request.created_at,
        omit=frozenset(seen),
    )
    style_examples = (
        ()
        if self_recall
        else archive.style_examples(request, policy.consenting_member_ids, cutoff)
    )
    group_style = (
        ()
        if self_recall
        else _shared_expressions(
            archive.style_candidates(request, policy.consenting_member_ids, cutoff),
            frozenset(terms),
        )
    )
    return ConversationContext(
        request,
        tuple(parents),
        tuple(reversed(visible)),
        memory,
        style_examples,
        group_style=group_style,
        self_recall=self_recall,
    )


def _shared_expressions(
    candidates: tuple[MessageRecord, ...], current_terms: frozenset[str]
) -> tuple[GroupExpression, ...]:
    groups = defaultdict(list)
    for row in candidates:
        words = _QUERY_WORDS.findall(row.text.casefold())
        if (
            not 2 <= len(words) <= 7
            or any(
                len(word) > 22 or word.isdigit() or word == "bearer" for word in words
            )
            or any(mark in row.text for mark in ("?", "؟", "<", "@", "_", "/", ":"))
        ):
            continue
        groups[tuple(words)].append(row)
    recurring = [
        (words, rows)
        for words, rows in groups.items()
        if len(rows) >= 3 and len({row.author_id for row in rows}) >= 2
    ]
    recurring.sort(
        key=lambda item: (
            len(current_terms.intersection(item[0])),
            len(item[1]),
            item[1][0].created_at,
        ),
        reverse=True,
    )
    result = []
    for words, rows in recurring[:2]:
        other_author = next(
            row for row in rows[1:] if row.author_id != rows[0].author_id
        )
        third = next(row for row in rows[1:] if row is not other_author)
        result.append(GroupExpression(" ".join(words), (rows[0], other_author, third)))
    return tuple(result)


def share_style_example(
    archive: Archive,
    policy: PrivacyPolicy,
    guild_id: int,
    channel_id: int,
    author_id: int,
    message_id: int,
) -> bool:
    if not policy.permits(guild_id, channel_id, author_id):
        return False
    now = datetime.now(UTC)
    return archive.add_style_example(
        guild_id,
        channel_id,
        author_id,
        message_id,
        now,
        now - timedelta(days=policy.retention_days),
    )
