from datetime import UTC, datetime, timedelta

from pai.conversation import prepare_context, share_style_example
from pai.policy import PrivacyPolicy
from pai.storage import Archive, MessageRecord


def test_deliberate_style_examples_remain_source_linked_and_separate_from_facts(
    tmp_path,
):
    path = tmp_path / "pai.sqlite"
    archive = Archive(path)
    time = datetime.now(UTC) - timedelta(minutes=4)
    policy = PrivacyPolicy(True, "v1", 10, frozenset({20, 21}), frozenset({30, 31}))
    example = MessageRecord(
        1, 10, 20, 30, "Sam", "The router is obviously haunted.", time
    )
    outsider = MessageRecord(2, 10, 21, 30, "Sam", "Other channel style", time)
    request = MessageRecord(
        3, 10, 20, 31, "Jo", "Router question", time + timedelta(seconds=3)
    )
    for record in (example, outsider, request):
        assert archive.append(record)
    assert not share_style_example(archive, policy, 10, 20, 31, 1)
    assert not share_style_example(archive, policy, 10, 20, 30, 2)
    assert share_style_example(archive, policy, 10, 20, 30, 1)
    assert not share_style_example(archive, policy, 10, 20, 30, 1)

    reopened = Archive(path)
    context = prepare_context(reopened, policy, request)
    assert context.style_examples == (example,)
    assert example not in (*context.parents, *context.recent, *context.memory)
    assert example in context.sources

    assert reopened.edit(1, 10, 20, frozenset({30}), "Corrected", request.created_at)
    assert prepare_context(reopened, policy, request).style_examples == ()
    assert share_style_example(reopened, policy, 10, 20, 30, 1)
    assert reopened.delete(10, 20, [1], request.created_at) == 1
    assert prepare_context(reopened, policy, request).style_examples == ()


def test_automatic_group_style_learns_expressions_with_author_diversity(tmp_path):
    path = tmp_path / "pai.sqlite"
    archive = Archive(path)
    base_time = datetime(2026, 11, 21, 12, 0, tzinfo=UTC)
    policy = PrivacyPolicy(True, "v1", 10, frozenset({20}), frozenset({30, 31}))

    # Sam (30) posts multiple messages
    sam_msgs = [
        MessageRecord(1, 10, 20, 30, "Sam", "oldest banter", base_time),
        MessageRecord(
            2,
            10,
            20,
            30,
            "Sam",
            "https://example.com/link",
            base_time + timedelta(seconds=1),
        ),
        MessageRecord(
            3, 10, 20, 30, "Sam", "!command bot", base_time + timedelta(seconds=2)
        ),
        MessageRecord(
            4,
            10,
            20,
            30,
            "Sam",
            "that demo was an absolute disaster lol",
            base_time + timedelta(seconds=3),
        ),
    ]
    # Jo (31) posts banter
    jo_msgs = [
        MessageRecord(
            5,
            10,
            20,
            31,
            "Jo",
            "weather event incoming for real",
            base_time + timedelta(seconds=4),
        ),
    ]
    # Bob (32) is non-consenting
    bob_msg = MessageRecord(
        6, 10, 20, 32, "Bob", "unconsented banter", base_time + timedelta(seconds=5)
    )
    # Outsider channel message
    other_ch_msg = MessageRecord(
        7, 10, 21, 30, "Sam", "other channel banter", base_time + timedelta(seconds=6)
    )

    for m in (*sam_msgs, *jo_msgs, bob_msg, other_ch_msg):
        archive.append(m)

    cutoff = base_time - timedelta(days=1)
    req = MessageRecord(
        8,
        10,
        20,
        31,
        "Jo",
        "what did we call the demo?",
        base_time + timedelta(seconds=10),
    )
    archive.append(req)

    # Test group_style directly
    expressions = archive.group_style(
        req, policy.consenting_member_ids, cutoff, limit=2
    )
    assert len(expressions) == 2
    authors = {e.author_id for e in expressions}
    assert authors == {30, 31}  # Diversity: 1 from Sam, 1 from Jo
    texts = {e.text for e in expressions}
    assert "that demo was an absolute disaster lol" in texts
    assert "weather event incoming for real" in texts
    assert "unconsented banter" not in texts

    # Verify build_prompt incorporates group_expressions without citation tags
    import json

    from pai.conversation import ConversationContext
    from pai.prompts import build_prompt

    ctx = ConversationContext(request=req, group_style=expressions)
    prompt = build_prompt(ctx)
    payload = json.loads(prompt.request.payload)
    assert "group_expressions" in payload
    assert len(payload["group_expressions"]) == 2
    # Ensure no citations were created for group expressions
    for item in payload["group_expressions"]:
        assert "source" not in item
