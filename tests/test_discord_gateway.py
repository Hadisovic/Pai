import asyncio
import json
from unittest.mock import AsyncMock, Mock

import discord
import pytest

from pai.discord_gateway import PaiDiscordClient
from pai.policy import PrivacyPolicy, load_policy


def policy():
    return PrivacyPolicy(
        admin_opt_in=True,
        notice_version="notice-1",
        guild_id=1,
        channel_ids=frozenset({2}),
        consenting_member_ids=frozenset({3}),
    )


def sample_message():
    message = Mock(spec=discord.Message)
    message.guild = Mock(id=1, me=Mock())
    message.channel = Mock(spec=discord.TextChannel)
    message.channel.id = 2
    message.channel.permissions_for.return_value = discord.Permissions(
        view_channel=True
    )
    message.author = Mock(id=3, bot=False)
    message.webhook_id = None
    return message


@pytest.mark.parametrize(
    "change",
    [
        "no_admin",
        "no_notice",
        "dm",
        "foreign_guild",
        "foreign_channel",
        "no_consent",
        "bot_author",
        "webhook",
        "no_access",
        "thread",
    ],
)
def test_gateway_rejects_unapproved_messages(change):
    gate = policy()
    message = sample_message()
    if change == "no_admin":
        gate = PrivacyPolicy()
    elif change == "no_notice":
        gate = PrivacyPolicy(True, "", 1, frozenset({2}), frozenset({3}))
    elif change == "dm":
        message.guild = None
    elif change == "foreign_guild":
        message.guild.id = 9
    elif change == "foreign_channel":
        message.channel.id = 9
    elif change == "no_consent":
        message.author.id = 9
    elif change == "bot_author":
        message.author.bot = True
    elif change == "webhook":
        message.webhook_id = 9
    elif change == "no_access":
        message.channel.permissions_for.return_value = discord.Permissions.none()
    else:
        message.channel = Mock(spec=discord.Thread)
    handle = AsyncMock()
    asyncio.run(PaiDiscordClient(gate, handle).on_message(message))
    handle.assert_not_awaited()


def test_gateway_accepts_authorized_message_with_minimal_intents():
    handle = AsyncMock()
    client = PaiDiscordClient(policy(), handle)
    message = sample_message()
    asyncio.run(client.on_message(message))
    handle.assert_awaited_once_with(message)
    assert {name for name, enabled in client.intents if enabled} == {
        "guilds",
        "guild_messages",
        "message_content",
    }
    assert client.allowed_mentions.to_dict() == {"parse": []}
    assert client.allowed_mentions.replied_user is False


def test_policy_loads_private_scope_and_defaults_closed(tmp_path):
    path = tmp_path / "private.json"
    assert load_policy(path) == PrivacyPolicy()
    config = {
        "admin_opt_in": True,
        "notice_version": "notice-1",
        "guild_id": 1,
        "channel_ids": [2],
        "consenting_member_ids": [3],
    }
    path.write_text(json.dumps(config), encoding="utf-8")
    assert load_policy(path) == policy()
    config["guild_id"] = True
    path.write_text(json.dumps(config), encoding="utf-8")
    with pytest.raises(ValueError, match="guild_id"):
        load_policy(path)


def test_authorized_gateway_reaches_persistent_archive(tmp_path):
    from datetime import UTC, datetime

    from pai.discord_gateway import archive_message
    from pai.storage import Archive

    archive = Archive(tmp_path / "pai.sqlite")
    message = sample_message()
    message.id = 5
    message.author.display_name = "Sam"
    message.content = "Synthetic study note"
    message.created_at = datetime(2026, 11, 21, tzinfo=UTC)
    message.reference = None

    async def handle(event):
        return await archive_message(archive, event)

    client = PaiDiscordClient(policy(), handle)
    asyncio.run(client.on_message(message))
    assert archive.get(5).text == "Synthetic study note"
    message.id = 6
    message.author.id = 99
    asyncio.run(client.on_message(message))
    assert archive.get(6) is None
