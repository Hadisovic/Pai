import json
from datetime import UTC, datetime, timedelta

from pai.conversation import AssistantTurn, prepare_context
from pai.policy import PrivacyPolicy
from pai.prompts import build_prompt, render_answer
from pai.storage import Archive, MessageRecord
from pai.voice import reply_style


def test_member_settings_are_private_scoped_expiring_and_deletable(tmp_path):
    path = tmp_path / "pai.sqlite"
    archive = Archive(path)
    now = datetime.now(UTC)
    policy = PrivacyPolicy(True, "v1", 10, frozenset({20, 21}), frozenset({30, 31}))
    assert archive.set_style_settings(
        policy, 20, 30, {"emoji": "off", "language": "arabic"}, now
    )
    assert not archive.set_style_settings(policy, 20, 99, {"emoji": "off"}, now)
    reopened = Archive(path)
    assert reopened.style_settings(policy, 20, 30, now) == {
        "emoji": "off",
        "language": "arabic",
    }
    assert reopened.style_settings(policy, 21, 30, now) == {}
    assert reopened.style_settings(policy, 20, 31, now) == {}
    assert reopened.style_settings(policy, 20, 30, now + timedelta(days=31)) == {}
    assert reopened.set_style_settings(policy, 20, 30, {"emoji": "auto"}, now)
    assert reopened.style_settings(policy, 20, 30, now) == {"language": "arabic"}
    assert reopened.set_style_settings(policy, 20, 30, {}, now, reset=True)
    assert reopened.style_settings(policy, 20, 30, now) == {}
    assert reopened.set_style_settings(policy, 20, 30, {"emoji": "off"}, now)
    reopened.forget_author(10, 30, now)
    assert reopened.style_settings(policy, 20, 30, now) == {}
    assert not reopened.set_style_settings(policy, 20, 30, {"emoji": "off"}, now)


def test_direct_feedback_wins_and_does_not_spill_to_another_speaker(tmp_path):
    archive = Archive(tmp_path / "pai.sqlite")
    now = datetime.now(UTC)
    policy = PrivacyPolicy(True, "v1", 10, frozenset({20}), frozenset({30, 31}))
    prior = MessageRecord(1, 10, 20, 30, "Name", "stop using emojis", now)
    archive.append(prior)
    turn = AssistantTurn("Okay.", prior, (prior,))
    for who, expected in ((30, "sure"), (31, "sure 🔥")):
        ask = MessageRecord(
            2 + who, 10, 20, who, "Name", "okay continue", now + timedelta(seconds=2)
        )
        prompt = build_prompt(
            prepare_context(archive, policy, ask, assistant_turn=turn)
        )
        assert render_answer("sure 🔥", prompt) == expected
    current = MessageRecord(10, 10, 20, 31, "Name", "no emojis please", now)
    prompt = build_prompt(prepare_context(archive, policy, current))
    assert render_answer("got it 🙅‍♂️", prompt) == "got it"


def test_current_style_override_takes_precedence_over_saved_settings():
    settings = {"language": "arabic", "emoji": "off", "tone": "casual"}
    style = reply_style("jokes aside, reply in Arabizi", settings, ("emojis are fine",))
    assert style.language == "arabizi"
    assert not style.emoji_off
    assert not style.tone
    assert reply_style("no emojis please", settings, ("emojis are fine",)).emoji_off


def test_unpunctuated_recall_and_browse_claims(tmp_path):
    archive = Archive(tmp_path / "pai.sqlite")
    now = datetime.now(UTC)
    policy = PrivacyPolicy(True, "v1", 10, frozenset({20}), frozenset({30, 31}))
    own = MessageRecord(1, 10, 20, 30, "Name", "My favorite game is Celeste.", now)
    other = MessageRecord(
        2, 10, 20, 31, "Name", "My favorite game is Hollow Knight.", now
    )
    archive.append(own)
    archive.append(other)
    ask = MessageRecord(
        3, 10, 20, 30, "Name", "whats my favorite game", now + timedelta(seconds=1)
    )
    context = prepare_context(archive, policy, ask)
    assert context.self_recall and context.memory == (own,)
    ask = MessageRecord(4, 10, 20, 30, "Name", "find me a source on the internet", now)
    prompt = build_prompt(prepare_context(archive, policy, ask))
    assert (
        render_answer("I searched the internet and found [link omitted].", prompt) == ""
    )
    assert render_answer("I can't verify that on the web here.", prompt)


def test_grounding_keeps_bot_directed_taunt_separate_from_firsthand_danger(tmp_path):
    archive = Archive(tmp_path / "pai.sqlite")
    now = datetime.now(UTC)
    policy = PrivacyPolicy(True, "v1", 10, frozenset({20}), frozenset({30, 31}))
    for text, mode in (
        ("kill yourself", "bot_directed"),
        ("I am going to kill myself right now", "imminent"),
    ):
        row = MessageRecord(1, 10, 20, 30, "Name", text, now)
        prompt = build_prompt(prepare_context(archive, policy, row))
        assert json.loads(prompt.request.payload)["reply_style"]["situation"] == mode


def test_settings_command_is_ephemeral_and_cannot_change_another_channels_preferences(
    tmp_path,
):
    import asyncio
    from unittest.mock import AsyncMock, Mock

    import discord

    from pai.commands import controls

    now = datetime.now(UTC)
    archive = Archive(tmp_path / "pai.sqlite")
    policy = PrivacyPolicy(True, "v1", 10, frozenset({20, 21}), frozenset({30, 31}))
    assert archive.set_style_settings(policy, 21, 30, {"language": "arabic"}, now)
    tree = controls(discord.Client(intents=discord.Intents.none()), archive, policy)
    command = tree.get_command("style", guild=discord.Object(id=10)).callback
    interaction = Mock(guild_id=10, channel_id=20, user=Mock(id=30))
    interaction.channel = Mock(spec=discord.TextChannel)
    interaction.permissions = discord.Permissions(view_channel=True)
    interaction.response.send_message = AsyncMock()

    asyncio.run(command(interaction, emoji="off"))
    assert interaction.response.send_message.call_args.kwargs["ephemeral"]
    assert archive.style_settings(policy, 20, 30, datetime.now(UTC)) == {"emoji": "off"}
    assert archive.style_settings(policy, 21, 30, now) == {"language": "arabic"}
    assert archive.style_settings(policy, 20, 31, now) == {}
    asyncio.run(command(interaction, reset=True))
    assert archive.style_settings(policy, 20, 30, now) == {}


def test_opted_in_roster_excludes_unobserved_and_nonconsenting_members(tmp_path):
    archive = Archive(tmp_path / "pai.sqlite")
    now = datetime.now(UTC)
    policy = PrivacyPolicy(True, "v1", 10, frozenset({20}), frozenset({30, 31, 44}))
    for i, author in enumerate((30, 31, 99), 1):
        archive.append(MessageRecord(i, 10, 20, author, f"User {author}", "here", now))
    ask = MessageRecord(
        5, 10, 20, 30, "User 30", "what do you think of each of us", now
    )
    prompt = build_prompt(prepare_context(archive, policy, ask))
    roster = json.loads(prompt.request.payload)["observed_speakers"]
    assert [r["display_name"] for r in roster] == ["User 30", "User 31"]
    assert render_answer("member_5 is the funny one", prompt) == ""


def test_new_notice_discards_preferences_and_unshare_is_owner_scoped(tmp_path):
    archive = Archive(tmp_path / "pai.sqlite")
    now = datetime.now(UTC)
    policy = PrivacyPolicy(True, "v1", 10, frozenset({20}), frozenset({30, 31}))
    later = PrivacyPolicy(True, "v2", 10, frozenset({20}), frozenset({30, 31}))
    message = MessageRecord(1, 10, 20, 30, "Name", "The kettle filed a complaint", now)
    assert archive.append(message)
    assert archive.add_style_example(10, 20, 30, 1, now, now - timedelta(days=1))
    assert not archive.remove_style_example(10, 20, 31, 1)
    assert archive.remove_style_example(10, 20, 30, 1)
    assert archive.get(1) == message
    assert archive.set_style_settings(policy, 20, 30, {"tone": "gentle"}, now)
    assert archive.style_settings(later, 20, 30, now) == {}
    archive.apply_policy(later)
    assert archive.style_settings(policy, 20, 30, now) == {}
