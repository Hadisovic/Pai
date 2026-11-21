"""The explicit mention trigger and bounded same-channel context."""

import re
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime, timedelta

from pai.policy import PrivacyPolicy
from pai.storage import Archive, MessageRecord

_TOKEN = re.compile(r"\\.|(`+).*?(?<!`)\1(?!`)|<@!?([0-9]+)>", re.DOTALL)
_PARENT_LIMIT = 4
_RECENT_LIMIT = 8


def direct_mention(text: str, recognized_targets: Iterable[int], bot_id: int) -> bool:
    return bot_id in recognized_targets and any(
        match[2] == str(bot_id) for match in _TOKEN.finditer(text)
    )


@dataclass(frozen=True)
class ConversationContext:
    request: MessageRecord
    parents: tuple[MessageRecord, ...] = ()
    recent: tuple[MessageRecord, ...] = ()


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
        parent = archive.get(parent_id)
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
    return ConversationContext(request, tuple(parents), tuple(reversed(visible)))
