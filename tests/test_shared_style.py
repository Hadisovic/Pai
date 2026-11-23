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


def test_group_style_uses_shared_repetition_with_scope_and_deletion(tmp_path):
    import json

    from pai.prompts import build_prompt

    archive = Archive(tmp_path / "pai.sqlite")
    now = datetime.now(UTC)
    policy = PrivacyPolicy(True, "v1", 10, frozenset({20}), frozenset({30, 31}))
    evidence = [
        (1, 20, 30, "Weather event incoming!"),
        (2, 20, 31, "weather event incoming"),
        (3, 20, 30, "WEATHER EVENT INCOMING"),
        (4, 20, 30, "secret side quest"),
        (5, 20, 31, "secret side quest"),
        (6, 20, 32, "secret side quest"),
        (7, 21, 31, "secret side quest"),
        (8, 20, 30, "random one-off chat"),
    ]
    for identifier, channel, author, text in evidence:
        archive.append(
            MessageRecord(identifier, 10, channel, author, "Synthetic", text, now)
        )
    request = MessageRecord(
        9, 10, 20, 31, "Synthetic", "weather event for the demo", now
    )
    context = prepare_context(archive, policy, request)
    assert [expression.text.casefold() for expression in context.group_style] == [
        "weather event incoming"
    ]
    assert {row.message_id for row in context.group_style[0].sources} == {1, 2, 3}
    payload = json.loads(build_prompt(context).request.payload)
    assert (
        payload["group_expressions"][0]["text"].casefold() == "weather event incoming"
    )
    assert payload["group_expressions"][0]["usage"] == "shared expression"
    archive.delete(10, 20, [2], now)
    assert not archive.records_unchanged(context.sources)
    assert not prepare_context(archive, policy, request).group_style
