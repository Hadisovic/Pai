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


def test_raw_events_apply_edits_and_bulk_deletes_without_message_cache(tmp_path):
    from datetime import UTC, datetime

    from pai.storage import Archive, MessageRecord

    archive = Archive(tmp_path / "pai.sqlite")
    timestamp = datetime(2026, 11, 21, tzinfo=UTC)
    assert archive.append(MessageRecord(5, 1, 2, 3, "Sam", "Old", timestamp))
    client = PaiDiscordClient(policy(), AsyncMock(), archive=archive)
    channel = sample_message().channel
    channel.guild = Mock(id=1, me=Mock())
    client.get_channel = Mock(return_value=channel)
    asyncio.run(
        client.on_raw_message_edit(
            Mock(guild_id=1, channel_id=2, message_id=5, data={"embeds": []})
        )
    )
    assert archive.get(5).text == "Old"
    asyncio.run(
        client.on_raw_message_edit(
            Mock(
                guild_id=1,
                channel_id=2,
                message_id=5,
                data={
                    "content": "New",
                    "edited_timestamp": "2026-11-21T13:00:00+00:00",
                },
            )
        )
    )
    assert archive.get(5).text == "New"
    asyncio.run(
        client.on_raw_bulk_message_delete(
            Mock(guild_id=9, channel_id=2, message_ids={5})
        )
    )
    assert archive.get(5) is not None
    asyncio.run(
        client.on_raw_bulk_message_delete(
            Mock(guild_id=1, channel_id=2, message_ids={5})
        )
    )
    assert archive.get(5) is None


def test_gateway_responds_only_once_to_direct_mentions(tmp_path):
    from datetime import UTC, datetime

    from pai.conversation import MediaReading
    from pai.discord_gateway import archive_message
    from pai.storage import Archive

    archive = Archive(tmp_path / "pai.sqlite")
    respond = AsyncMock(return_value="Synthetic answer")
    event = sample_message()
    event.created_at = datetime.now(UTC)
    event.type = discord.MessageType.default
    event.reference = None
    event.author = Mock(spec=discord.Member, id=3, bot=False, display_name="Sam")
    event.channel.permissions_for.return_value = discord.Permissions(
        view_channel=True, read_message_history=True, send_messages=True
    )
    event.channel.send = AsyncMock()

    async def handle(message):
        return await archive_message(archive, message)

    client = PaiDiscordClient(policy(), handle, archive=archive, respond=respond)
    client._connection.user = Mock(id=42)
    client.read_media = AsyncMock(return_value=MediaReading())
    event.channel.guild = event.guild
    event.guild.fetch_member = AsyncMock(return_value=event.author)
    client.get_channel = Mock(return_value=event.channel)
    event.id = 5
    event.content = "Ordinary message"
    event.mentions = [Mock(id=42)]
    asyncio.run(client.on_message(event))
    respond.assert_not_awaited()
    client.read_media.assert_not_awaited()
    assert archive.get(5).text == "Ordinary message"
    event.id = 6
    event.content = "Hi <@42>"
    asyncio.run(client.on_message(event))
    asyncio.run(client.on_message(event))
    respond.assert_awaited_once()
    client.read_media.assert_awaited_once()
    assert [row.message_id for row in respond.call_args.args[0].recent] == [5]
    event.channel.send.assert_awaited_once()
    assert event.channel.send.call_args.args == ("Synthetic answer",)
    assert event.channel.send.call_args.kwargs["allowed_mentions"].to_dict() == {
        "parse": []
    }


@pytest.mark.parametrize("mutation", ["delete_source", "revoke_history"])
def test_gateway_discards_reply_if_a_source_or_permission_changes(tmp_path, mutation):
    from datetime import UTC, datetime, timedelta

    from pai.discord_gateway import archive_message
    from pai.storage import Archive, MessageRecord

    archive = Archive(tmp_path / "pai.sqlite")
    event = sample_message()
    event.created_at = datetime.now(UTC)
    event.type = discord.MessageType.default
    event.reference = None
    event.author = Mock(spec=discord.Member, id=3, bot=False, display_name="Sam")
    event.id = 6
    event.content = "Hi <@42>"
    event.mentions = [Mock(id=42)]
    event.channel.guild = event.guild
    event.guild.fetch_member = AsyncMock(return_value=event.author)
    event.channel.send = AsyncMock()
    event.channel.permissions_for.return_value = discord.Permissions(
        view_channel=True, read_message_history=True, send_messages=True
    )
    archive.append(
        MessageRecord(
            5,
            1,
            2,
            3,
            "Sam",
            "Old synthetic evidence",
            event.created_at - timedelta(seconds=2),
        )
    )

    async def handle(message):
        return await archive_message(archive, message)

    async def respond(context):
        assert [row.message_id for row in context.recent] == [5]
        if mutation == "delete_source":
            archive.delete(1, 2, [5], datetime.now(UTC))
        else:
            event.channel.permissions_for.return_value = discord.Permissions(
                view_channel=True, send_messages=True
            )
        return "Discard this answer"

    client = PaiDiscordClient(policy(), handle, archive=archive, respond=respond)
    client._connection.user = Mock(id=42)
    client.get_channel = Mock(return_value=event.channel)
    asyncio.run(client.on_message(event))
    event.channel.send.assert_not_awaited()
