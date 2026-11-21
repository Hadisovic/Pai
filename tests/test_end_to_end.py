import asyncio
import json
from datetime import UTC, datetime, timedelta
from io import BytesIO
from unittest.mock import AsyncMock, Mock

import discord
from PIL import Image

from pai.discord_gateway import PaiDiscordClient, archive_message
from pai.model_router import ProviderRoute, Quota, Router
from pai.policy import PrivacyPolicy
from pai.reply_engine import ReplyEngine
from pai.storage import Archive
from pai.vision import MentionVision


def test_offline_discord_archive_recall_gif_and_deletion_flow(tmp_path, monkeypatch):
    archive = Archive(tmp_path / "pai.sqlite")
    policy = PrivacyPolicy(
        True,
        "synthetic-v1",
        1,
        frozenset({2}),
        frozenset({3, 4}),
        external_ai_opt_in=True,
        media_opt_in=True,
    )
    guild = Mock(id=1, me=Mock())
    channel = Mock(spec=discord.TextChannel, id=2, guild=guild)
    channel.permissions_for.return_value = discord.Permissions(
        view_channel=True, read_message_history=True, send_messages=True
    )
    channel.send = AsyncMock()
    author = Mock(spec=discord.Member, id=3, bot=False, display_name="Sam")
    guild.fetch_member = AsyncMock(return_value=author)
    now = datetime.now(UTC)

    def message(identifier, text, *, date=now, target_channel=channel, parent=None):
        event = Mock(spec=discord.Message)
        event.id, event.guild, event.channel, event.author = (
            identifier,
            guild,
            target_channel,
            author,
        )
        event.content, event.created_at, event.edited_at = text, date, None
        event.webhook_id = None
        event.mentions = [Mock(id=42)] if "<@42>" in text else []
        event.attachments, event.embeds, event.stickers = [], [], []
        event.reference = None
        event.type = discord.MessageType.default
        if parent is not None:
            event.reference = Mock(
                channel_id=2,
                guild_id=1,
                message_id=parent.id,
                resolved=parent,
            )
            event.type = discord.MessageType.reply
        return event

    current_router_quota = Quota(20, 100, 40_000, 100_000)
    seen_requests = []

    async def completion(request):
        seen_requests.append(request)
        if request.frames:
            assert len(request.frames) == 3
            return "A yellow marker moves from left to right."
        payload = json.loads(request.payload)
        if "media_description" in payload:
            return "The marker moves from left to right. [s1]"
        source = next(row for row in payload["history"] if "Waffle" in row["text"])
        return f"Sam named the router Waffle. [{source['source']}]"

    router = Router(
        archive,
        (ProviderRoute("synthetic", 3, True, current_router_quota, completion),),
    )
    vision = MentionVision(archive, Mock(), router, policy)
    output = BytesIO()
    frames = [Image.new("RGB", (24, 24), color) for color in ("red", "green", "blue")]
    frames[0].save(
        output, format="GIF", save_all=True, append_images=frames[1:], duration=100
    )
    download = AsyncMock(return_value=output.getvalue())
    monkeypatch.setattr("pai.vision.fetch_image", download)

    async def handle(event):
        return await archive_message(archive, event, include_media=True)

    client = PaiDiscordClient(
        policy, handle, archive=archive, respond=ReplyEngine(router), read_media=vision
    )
    client._connection.user = Mock(id=42)
    client.get_channel = Mock(return_value=channel)
    clock = [0]
    client.reply_limits.clock = lambda: clock[0]

    async def replay():
        await client.on_message(
            message(1, "We named the router Waffle.", date=now - timedelta(days=6))
        )
        for index in range(2, 11):
            await client.on_message(
                message(
                    index, "Good morning.", date=now - timedelta(minutes=30 - index)
                )
            )
        foreign = Mock(spec=discord.TextChannel, id=99)
        await client.on_message(
            message(20, "<@42> Restricted conversation", target_channel=foreign)
        )
        assert archive.get(20) is None
        assert (
            not seen_requests
            and not download.await_count
            and not channel.send.await_count
        )
        await client.on_message(message(30, "<@42> What did Sam call the router?"))
        assert channel.send.call_args.args[0] == (
            "Sam named the router Waffle. [source](<https://discord.com/channels/1/2/1>)"
        )
        clock[0] += 15
        gif = message(31, "Watch this.", date=now + timedelta(seconds=1))
        gif.attachments = [
            Mock(
                id=77,
                size=100,
                filename="example.gif",
                content_type="image/gif",
                url="https://cdn.discordapp.com/attachments/2/77/example.gif",
            )
        ]
        await client.on_message(gif)
        assert len(seen_requests) == 1
        await client.on_message(
            message(
                32,
                "<@42> What is the GIF doing?",
                date=now + timedelta(seconds=2),
                parent=gif,
            )
        )
        assert len(seen_requests) == 3
        assert "moves from left to right" in channel.send.call_args.args[0]
        assert "<https://discord.com/channels/1/2/31>" in channel.send.call_args.args[0]
        download.assert_awaited_once()
        await client.on_raw_message_delete(Mock(guild_id=1, channel_id=2, message_id=1))
        assert not archive.search(
            "Waffle",
            guild_id=1,
            channel_id=2,
            authors=frozenset({3}),
            cutoff=now - timedelta(days=8),
        )

    asyncio.run(replay())
