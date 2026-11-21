from datetime import UTC, datetime, timedelta

import pytest

from pai.conversation import direct_mention, prepare_context
from pai.policy import PrivacyPolicy
from pai.storage import Archive, MessageRecord


@pytest.mark.parametrize(
    ("text", "mentions", "expected"),
    [
        ("Hey <@42>", [42], True),
        ("Hey <@!42>", [42], True),
        ("Just a reply ping", [42], False),
        ("Hey <@42>", [], False),
        ("Hey <@420>", [420], False),
        (r"Hey \<@42>", [42], False),
        ("Look at `<@42>`", [42], False),
        ("Example:```\n<@42>\n```", [42], False),
    ],
)
def test_direct_mention_requires_literal_and_discord_target(text, mentions, expected):
    assert direct_mention(text, mentions, 42) is expected


def test_context_keeps_authorized_chain_and_recent_messages_only(tmp_path):
    archive = Archive(tmp_path / "pai.sqlite")
    time = datetime(2026, 11, 21, tzinfo=UTC)
    policy = PrivacyPolicy(True, "v1", 10, frozenset({20, 21}), frozenset({30}))
    records = [
        MessageRecord(1, 10, 20, 30, "Sam", "Old parent", time, reply_to_id=4),
        MessageRecord(
            2, 10, 20, 30, "Sam", "Parent", time + timedelta(seconds=1), reply_to_id=1
        ),
        MessageRecord(3, 10, 20, 30, "Sam", "Recent", time + timedelta(seconds=2)),
        MessageRecord(
            4, 10, 21, 30, "Sam", "Different channel", time + timedelta(seconds=3)
        ),
        MessageRecord(
            5, 10, 20, 31, "Jo", "Consent withdrawn", time + timedelta(seconds=4)
        ),
        MessageRecord(
            6, 10, 20, 30, "Sam", "Request", time + timedelta(seconds=5), reply_to_id=2
        ),
        MessageRecord(7, 10, 20, 30, "Sam", "Future", time + timedelta(seconds=6)),
    ]
    for record in records:
        assert archive.append(record)
    context = prepare_context(archive, policy, records[5])
    assert [record.message_id for record in context.parents] == [2, 1]
    assert [record.message_id for record in context.recent] == [3]
    assert context.request == records[5]
