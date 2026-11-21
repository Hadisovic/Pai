"""The explicit mention trigger and bounded same-channel context."""

import re
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


def direct_mention(text: str, recognized_targets: Iterable[int], bot_id: int) -> bool:
    return bot_id in recognized_targets and any(
        match[2] == str(bot_id) for match in _TOKEN.finditer(text)
    )


@dataclass(frozen=True)
class ConversationContext:
    request: MessageRecord
    parents: tuple[MessageRecord, ...] = ()
    recent: tuple[MessageRecord, ...] = ()
    memory: tuple[MessageRecord, ...] = ()
    style_examples: tuple[MessageRecord, ...] = ()

    @property
    def sources(self) -> tuple[MessageRecord, ...]:
        return (
            self.request,
            *self.parents,
            *self.recent,
            *self.memory,
            *self.style_examples,
        )


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
            or not cutoff <= parent.created_at <= request.created_at
        ):
            break
        seen.add(parent_id)
        parents.append(parent)
        parent_id = parent.reply_to_id

    recent = archive.recent(
        request, policy.consenting_member_ids, cutoff, _RECENT_LIMIT + len(parents)
    )
    visible = tuple(row for row in recent if row.message_id not in seen)[:_RECENT_LIMIT]
    seen.update(row.message_id for row in visible)
    terms = _QUERY_WORDS.findall(_DISCORD_TAG.sub("", request.text).lower())
    query = " ".join(
        term for term in terms if term not in _STOP_WORDS and len(term) > 1
    )
    memory = archive.search(
        query,
        guild_id=request.guild_id,
        channel_id=request.channel_id,
        authors=policy.consenting_member_ids,
        cutoff=cutoff,
        limit=_MEMORY_LIMIT,
        through=request.created_at,
        omit=frozenset(seen),
    )
    style_examples = archive.style_examples(
        request, policy.consenting_member_ids, cutoff
    )
    return ConversationContext(
        request, tuple(parents), tuple(reversed(visible)), memory, style_examples
    )


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
