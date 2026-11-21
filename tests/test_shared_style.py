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
