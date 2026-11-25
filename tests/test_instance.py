import asyncio
from datetime import UTC, datetime
from unittest.mock import AsyncMock, Mock

import discord
import pytest

from pai.conversation import ConversationContext
from pai.discord_gateway import PaiDiscordClient
from pai.identity import Identity
from pai.instance import (
    Instance,
    current_name,
    distress_reply,
    run_until_stopped,
    runtime_lock,
    verify_discord,
)
from pai.model_router import ModelRequest
from pai.policy import PrivacyPolicy
from pai.runtime_info import BuildInfo, runtime_reply
from pai.storage import MessageRecord
from pai.voice import ReplyStyle


def test_named_instance_changes_only_application_labels():
    instance = Instance("Kirky", 100, 101, 102, 103)
    before = ModelRequest(
        "You're Pai. Usually chill and dry.\nPai: ok",
        'T3 is Pai\'s preceding reply.\nAddressee: Pai (native reply)\nCurrent speaker member_1: "tell Pai hi"',
        prior_messages=(("assistant", "hey Pai"),),
    )
    actual = instance.brand(before)
    assert actual.instructions == "You're Kirky. Usually chill and dry.\nKirky: ok"
    assert "Addressee: Kirky" in actual.payload
    assert 'member_1: "tell Pai hi"' in actual.payload
    assert actual.prior_messages == before.prior_messages
    assert actual.max_output_tokens == before.max_output_tokens


def test_trusted_identity_and_version_have_isolated_names():
    policy = PrivacyPolicy(True, "test", 1, frozenset({2}), frozenset({3}))
    request = MessageRecord(4, 1, 2, 3, "Synthetic", "who is Kirky", datetime.now(UTC))
    context = ConversationContext(request)
    identity = Identity(policy, ("qwen", "fallback"))
    token = current_name.set("Kirky")
    try:
        assert identity.reply(context) == "i'm Kirky, your Discord companion."
        ver = MessageRecord(
            5, 1, 2, 3, "Synthetic", "which commit is Kirky running", request.created_at
        )
        assert "Kirky's" in runtime_reply(
            ConversationContext(ver),
            BuildInfo("a" * 40),
            vision=False,
            primary_model=None,
        )
    finally:
        current_name.reset(token)
    assert current_name.get() == "Pai"


def test_private_launch_gate_disallows_shared_quota_and_wrong_scope():
    inst = Instance("Kirky", 100, 101, 102, 103)
    policy = PrivacyPolicy(
        True, "test", 100, frozenset({101}), frozenset({4}), external_ai_opt_in=True
    )
    with pytest.raises(ValueError, match="distress"):
        inst.validate_start(policy, hosted=False)
    ready = Instance("Kirky", 100, 101, 102, 103, distress_reviewed=True)
    ready.validate_start(policy, hosted=False)
    with pytest.raises(ValueError, match="quota"):
        ready.validate_start(policy, hosted=True)
    with pytest.raises(ValueError, match="channel"):
        ready.validate_start(
            PrivacyPolicy(True, "test", 100, frozenset({101, 104}), frozenset({4})),
            hosted=False,
        )


def test_preflight_rejects_extra_channel_and_original_bot():
    instance = Instance("Kirky", 100, 101, 102, 103)
    user = Mock(id=102, avatar=object(), bot=True)
    user.name = "Kirky"
    approved = Mock(spec=discord.TextChannel, id=101)
    approved.permissions_for.return_value = discord.Permissions(
        view_channel=True, send_messages=True, read_message_history=True
    )
    denied = Mock(spec=discord.TextChannel, id=104)
    denied.permissions_for.return_value = discord.Permissions.none()
    guild = Mock(
        fetch_member=AsyncMock(
            return_value=Mock(guild_permissions=discord.Permissions.none())
        ),
        fetch_channels=AsyncMock(return_value=[approved, denied]),
    )

    async def listed(**kwargs):
        yield Mock(id=100)

    client = Mock(
        user=user, fetch_guilds=listed, fetch_guild=AsyncMock(return_value=guild)
    )
    asyncio.run(verify_discord(client, instance))
    denied.permissions_for.return_value = discord.Permissions(view_channel=True)
    with pytest.raises(discord.ClientException, match="another channel"):
        asyncio.run(verify_discord(client, instance))
    user.id = 103
    with pytest.raises(discord.ClientException, match="identity"):
        asyncio.run(verify_discord(client, instance))


def test_experimental_distress_response_directs_real_help_without_promising_availability():
    row = MessageRecord(4, 1, 2, 3, "Synthetic", "test", datetime.now(UTC))
    assert distress_reply(ConversationContext(row)) is None
    answer = distress_reply(
        ConversationContext(row, style=ReplyStyle(situation="imminent"))
    )
    assert "emergency services" in answer and "someone nearby" in answer
    assert "not going anywhere" not in answer


def test_experimental_ingest_ignores_bots_and_other_channels():
    policy = PrivacyPolicy(True, "test", 1, frozenset({2}), frozenset({3}))
    handle = AsyncMock()
    client = PaiDiscordClient(policy, handle)
    guild = Mock(id=1)
    for bot, channel in ((True, 2), (False, 9)):
        event = Mock(
            guild=guild,
            channel=Mock(spec=discord.TextChannel, id=channel),
            author=Mock(id=3, bot=bot),
            webhook_id=None,
        )
        asyncio.run(client.on_message(event))
    handle.assert_not_awaited()


def test_single_instance_lock_is_separate_per_private_root(tmp_path):
    other = tmp_path / "other"
    other.mkdir()
    with runtime_lock(tmp_path):
        with pytest.raises(ValueError, match="already running"), runtime_lock(tmp_path):
            pass
        with runtime_lock(other):
            pass
    with runtime_lock(tmp_path):
        pass


def test_stop_request_closes_only_its_experimental_client(tmp_path):
    signal = tmp_path / "stop.request"

    async def start(token):
        assert token == "fixture"
        signal.touch()
        await asyncio.Future()

    client = Mock(start=start, close=AsyncMock())
    asyncio.run(run_until_stopped(client, "fixture", signal))
    client.close.assert_awaited_once()
