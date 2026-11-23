from datetime import UTC, datetime, timedelta

import pytest

from pai.conversation import AssistantTurn, direct_mention, prepare_context
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


def test_old_recall_preserves_source_and_excludes_future_content(tmp_path):
    archive = Archive(tmp_path / "pai.sqlite")
    time = datetime(2026, 11, 21, tzinfo=UTC)
    policy = PrivacyPolicy(True, "v1", 10, frozenset({20}), frozenset({30}))
    old = MessageRecord(1, 10, 20, 30, "Sam", "We named the lab router Waffle.", time)
    archive.append(old)
    for index in range(2, 14):
        archive.append(
            MessageRecord(
                index, 10, 20, 30, "Jo", "Daily greeting", time + timedelta(hours=index)
            )
        )
    archive.append(
        MessageRecord(
            14,
            10,
            20,
            30,
            "Jo",
            "We renamed the router",
            time + timedelta(days=3),
        )
    )
    request = MessageRecord(
        15,
        10,
        20,
        30,
        "Jo",
        "Hey <@42> what did we name the router?",
        time + timedelta(days=2),
    )
    archive.append(request)
    context = prepare_context(archive, policy, request)
    assert context.memory == (old,)
    assert context.memory[0].jump_url == "https://discord.com/channels/10/20/1"


def test_first_person_recall_uses_immutable_author_across_shared_names_and_renames(
    tmp_path,
):
    archive = Archive(tmp_path / "pai.sqlite")
    now = datetime.now(UTC)
    policy = PrivacyPolicy(True, "v1", 10, frozenset({20}), frozenset({30, 31}))
    own = MessageRecord(1, 10, 20, 31, "Old Jo", "My favorite game is Cyberpunk.", now)
    other = MessageRecord(2, 10, 20, 30, "Sam", "My favorite game is Minecraft.", now)
    ask = MessageRecord(
        3,
        10,
        20,
        31,
        "Sam",
        "Pai, what's my favorite game?",
        now + timedelta(seconds=1),
    )
    for record in (own, other, ask):
        archive.append(record)
    context = prepare_context(archive, policy, ask)
    assert own in (*context.memory, *context.recent)
    assert other not in (*context.memory, *context.recent)

    earlier_question = ask
    ask = MessageRecord(
        4,
        10,
        20,
        30,
        "Old Jo",
        "what did I say my favorite game was?",
        now + timedelta(seconds=2),
    )
    archive.append(ask)
    context = prepare_context(archive, policy, ask)
    assert other in (*context.memory, *context.recent)
    assert own not in (*context.memory, *context.recent)
    assert earlier_question not in (*context.memory, *context.recent)


def test_follow_up_keeps_the_recall_topic_and_switches_to_current_speaker(tmp_path):
    archive = Archive(tmp_path / "pai.sqlite")
    now = datetime.now(UTC)
    policy = PrivacyPolicy(True, "v1", 10, frozenset({20}), frozenset({30, 31}))

    def row(index, author, text):
        return MessageRecord(
            index, 10, 20, author, "Same name", text, now + timedelta(seconds=index)
        )

    favorite = row(1, 30, "My favorite test game is Stardew Valley.")
    other_favorite = row(2, 31, "My favorite test game is Portal.")
    question = row(3, 31, "What's my fav game?")
    unrelated = row(4, 30, "One word, what color is a ripe banana?")
    follow_up = row(5, 30, "what is mine tho?")
    repeat = row(6, 30, "uhm say it")
    for record in (favorite, other_favorite, question, unrelated, follow_up, repeat):
        archive.append(record)

    turn = AssistantTurn(
        "Portal.",
        request=question,
        sources=(question, other_favorite),
        recall_question=question,
    )
    context = prepare_context(archive, policy, follow_up, assistant_turn=turn)
    assert context.self_recall
    assert context.recall_question == question
    assert context.memory == (favorite,)
    assert context.assistant_turn is None
    assert unrelated not in context.sources

    turn = AssistantTurn(
        "Stardew Valley.",
        request=follow_up,
        sources=context.sources,
        recall_question=context.recall_question,
    )
    context = prepare_context(archive, policy, repeat, assistant_turn=turn)
    assert context.recall_question == question
    assert context.memory == (favorite,)

    new_topic = row(7, 30, "What's my favorite color?")
    changed = prepare_context(archive, policy, new_topic, assistant_turn=turn)
    assert changed.recall_question == new_topic


def test_standalone_message_does_not_receive_an_unrelated_recent_recall(tmp_path):
    archive = Archive(tmp_path / "pai.sqlite")
    now = datetime.now(UTC)
    policy = PrivacyPolicy(True, "v1", 10, frozenset({20}), frozenset({30, 31}))
    favorite = MessageRecord(1, 10, 20, 30, "Sam", "My favorite game is Portal.", now)
    relevant = MessageRecord(2, 10, 20, 31, "Jo", "I opened five recipe tabs.", now)
    request = MessageRecord(
        3,
        10,
        20,
        30,
        "Sam",
        "I opened six tabs to find one recipe and forgot the dish.",
        now + timedelta(seconds=1),
    )
    for record in (favorite, relevant, request):
        archive.append(record)

    context = prepare_context(archive, policy, request)
    assert context.recent == (relevant,)


@pytest.mark.parametrize(
    "question",
    [
        "shoo kan el favorite co-op game taba3i? Answer in Arabic.",
        "شو كانت لعبتي المفضلة؟ جاوبني بالإنجليزي",
    ],
)
def test_multilingual_personal_recall_keeps_other_members_and_format_out(
    tmp_path, question
):
    import json

    from pai.prompts import build_prompt

    archive = Archive(tmp_path / "pai.sqlite")
    now = datetime.now(UTC)
    policy = PrivacyPolicy(True, "v1", 10, frozenset({20}), frozenset({30, 31}))

    def row(index, author, text):
        return MessageRecord(
            index, 10, 20, author, "Same name", text, now + timedelta(seconds=index)
        )

    first = row(1, 30, "My favourite game is Tetris.")
    second = row(2, 31, "لعبتي المفضلة هي Celeste.")
    distractor = row(3, 31, "My favorite color is violet.")
    ask = row(4, 31, question)
    follow = row(5, 30, "طيب وأنا؟")
    for record in (first, second, distractor, ask, follow):
        archive.append(record)

    context = prepare_context(archive, policy, ask)
    assert context.self_recall and context.memory == (second,)
    turn = AssistantTurn("Celeste.", ask, context.sources, context.recall_question)
    context = prepare_context(archive, policy, follow, assistant_turn=turn)
    assert context.self_recall and context.memory == (first,)
    prompt = build_prompt(context)
    data = json.loads(prompt.request.payload)
    assert data["recall_topic"] == ["favorite", "game"]
    assert "Celeste" not in prompt.request.payload
    assert question not in prompt.request.payload
    assert prompt.sources == (("s1", first.jump_url),)
