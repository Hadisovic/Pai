from datetime import UTC, datetime

from pai.policy import PrivacyPolicy
from pai.storage import Archive, MessageRecord


def test_forget_removes_archive_index_and_style_and_blocks_future_collection(tmp_path):
    path = tmp_path / "pai.sqlite"
    archive = Archive(path)
    now = datetime.now(UTC)
    target = MessageRecord(1, 10, 20, 30, "Sam", "Synthetic waffle", now)
    other = MessageRecord(2, 10, 20, 31, "Jo", "Other message", now)
    assert archive.append(target)
    assert archive.append(other)
    assert archive.forget_author(10, 30, now) == 1
    reopened = Archive(path)
    assert reopened.is_opted_out(10, 30)
    assert not reopened.append(MessageRecord(3, 10, 21, 30, "Sam", "New", now))
    assert reopened.get(1) is None
    assert reopened.get(2) == other
    assert not reopened.search(
        "waffle", guild_id=10, channel_id=20, authors=frozenset({30}), cutoff=now
    )
    assert reopened.export_author(10, 20, 31, now) == (other,)


def test_reconciling_policy_purges_revoked_members_and_channels(tmp_path):
    archive = Archive(tmp_path / "pai.sqlite")
    now = datetime.now(UTC)
    for index, guild, channel, author in [
        (1, 10, 20, 30),
        (2, 10, 20, 31),
        (3, 10, 21, 30),
        (4, 11, 20, 30),
    ]:
        archive.append(
            MessageRecord(index, guild, channel, author, "Sam", "Synthetic", now)
        )
    policy = PrivacyPolicy(True, "v1", 10, frozenset({20}), frozenset({30}))
    assert archive.apply_policy(policy) == 3
    assert archive.get(1) is not None
    assert archive.get(2) is None
    assert archive.get(3) is None
    assert archive.get(4) is None


def test_discord_privacy_controls_return_data_only_to_the_requesting_member(tmp_path):
    import asyncio
    import json
    from unittest.mock import AsyncMock, Mock

    import discord

    from pai.commands import controls

    archive = Archive(tmp_path / "pai.sqlite")
    now = datetime.now(UTC)
    for index, channel, author in [(1, 20, 30), (2, 20, 31), (3, 21, 30)]:
        archive.append(
            MessageRecord(
                index, 10, channel, author, "Synthetic", f"Message {index}", now
            )
        )
    policy = PrivacyPolicy(True, "v1", 10, frozenset({20, 21}), frozenset({30, 31}))
    guild = discord.Object(id=10)
    tree = controls(discord.Client(intents=discord.Intents.none()), archive, policy)
    interaction = Mock(guild_id=10, channel_id=20, user=Mock(id=30))
    interaction.channel = Mock(spec=discord.TextChannel)
    interaction.permissions = discord.Permissions(
        view_channel=True, read_message_history=True
    )
    interaction.response.send_message = AsyncMock()
    interaction.response.defer = AsyncMock()
    interaction.followup.send = AsyncMock()

    asyncio.run(tree.get_command("memory", guild=guild).callback(interaction))
    response = interaction.response.send_message.call_args.kwargs
    assert response["ephemeral"] is True
    file = response["file"]
    try:
        assert [record["text"] for record in json.load(file.fp)] == ["Message 1"]
    finally:
        file.close()
    asyncio.run(tree.get_command("forgetme", guild=guild).callback(interaction))
    interaction.response.defer.assert_awaited_once_with(ephemeral=True, thinking=True)
    assert interaction.followup.send.call_args.kwargs["ephemeral"] is True
    assert archive.get(1) is None and archive.get(3) is None
    assert archive.get(2) is not None
