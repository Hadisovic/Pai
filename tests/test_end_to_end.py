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


def test_interleaved_multi_user_conversations_preserve_topics_and_references(tmp_path):
    archive = Archive(tmp_path / "pai.sqlite")
    policy = PrivacyPolicy(
        admin_opt_in=True,
        notice_version="v1",
        guild_id=1,
        channel_ids=frozenset({2}),
        consenting_member_ids=frozenset({101, 102}),
        external_ai_opt_in=True,
    )
    guild = Mock(id=1, me=Mock())
    channel = Mock(spec=discord.TextChannel, id=2, guild=guild)
    channel.permissions_for.return_value = discord.Permissions(
        view_channel=True, read_message_history=True, send_messages=True
    )

    sent_messages = []

    async def mock_send(content, **kwargs):
        msg_id = 500 + len(sent_messages)
        m = Mock(
            spec=discord.Message,
            id=msg_id,
            content=content,
            channel=channel,
            guild=guild,
            author=Mock(id=42),
            webhook_id=None,
        )
        sent_messages.append((content, kwargs, m))
        return m

    channel.send = AsyncMock(side_effect=mock_send)

    user_a = Mock(spec=discord.Member, id=101, bot=False, display_name="Alice")
    user_b = Mock(spec=discord.Member, id=102, bot=False, display_name="Bob")

    def fetch_member(user_id):
        return user_a if user_id == 101 else user_b

    guild.fetch_member = AsyncMock(side_effect=fetch_member)

    seen_payloads = []

    async def completion(request):
        payload = json.loads(request.payload)
        seen_payloads.append(payload)
        text = payload["request"]["text"]
        if "calculator" in text:
            return "been there. staring at 0 like it holds the secrets of the universe"
        if "banana" in text:
            return "yellow"
        if "still blank" in text:
            return "check the receipt or your browser tabs"
        if "fav game" in text:
            history = payload.get("history", [])
            for row in history:
                if "Minecraft" in row.get("text", ""):
                    return f"Minecraft [{row['source']}]"
            return "You didn't tell me."
        if "mine" in text:
            history = payload.get("history", [])
            for row in history:
                if "Portal" in row.get("text", ""):
                    return f"Portal [{row['source']}]"
            return "You haven't told me yours either."
        return "yeah"

    router = Router(
        archive,
        (
            ProviderRoute(
                "synthetic", 3, True, Quota(100, 100, 100_000, 100_000), completion
            ),
        ),
    )

    async def handle(event):
        return await archive_message(archive, event)

    client = PaiDiscordClient(
        policy, handle, archive=archive, respond=ReplyEngine(router)
    )
    client._connection.user = Mock(id=42)
    client.get_channel = Mock(return_value=channel)

    now = datetime.now(UTC)

    def make_msg(msg_id, author, content, parent=None, is_reply=False, mentions=()):
        m = Mock(spec=discord.Message)
        m.id = msg_id
        m.guild = guild
        m.channel = channel
        m.author = author
        m.content = content
        m.created_at = now + timedelta(seconds=msg_id)
        m.edited_at = None
        m.webhook_id = None
        m.mentions = list(mentions)
        m.attachments, m.embeds, m.stickers = [], [], []
        if is_reply and parent:
            m.type = discord.MessageType.reply
            m.reference = Mock(
                channel_id=channel.id,
                guild_id=guild.id,
                message_id=parent.id,
                resolved=parent,
            )
        else:
            m.type = discord.MessageType.default
            m.reference = None
        return m

    async def run_chained_dialogue():
        # 1. User A mentions Pai about forgetting what they were calculating
        m1 = make_msg(
            1,
            user_a,
            "<@42> bro I opened the calculator and forgot what I was calculating 💀",
            mentions=[Mock(id=42)],
        )
        await client.on_message(m1)

        # 2. User B interrupts with an unrelated banana question
        m2 = make_msg(
            2,
            user_b,
            "<@42> one word, what color is a ripe banana?",
            mentions=[Mock(id=42)],
        )
        await client.on_message(m2)

        # 3. User A replies directly to Pai's first answer without mentioning Pai
        ans1_msg = sent_messages[0][2]
        m3 = make_msg(
            3,
            user_a,
            "it was literally right there and now it's still blank",
            parent=ans1_msg,
            is_reply=True,
        )
        await client.on_message(m3)

        # 4. User B asks about their favorite game (has never stated it)
        m4 = make_msg(4, user_b, "What's my fav game <@42>", mentions=[Mock(id=42)])
        await client.on_message(m4)

        # 5. User A asks "what is mine tho?" replying to Pai's answer to User B
        ans4_msg = sent_messages[3][2]
        m5 = make_msg(5, user_a, "what is mine tho?", parent=ans4_msg, is_reply=True)
        await client.on_message(m5)

        assert len(sent_messages) == 5
        # Verify message references (case 9)
        assert sent_messages[0][1]["reference"].message_id == 1
        assert sent_messages[1][1]["reference"].message_id == 2
        assert sent_messages[2][1]["reference"].message_id == 3
        assert sent_messages[3][1]["reference"].message_id == 4
        assert sent_messages[4][1]["reference"].message_id == 5

        # Verify allowed_mentions has parse: [] (no ping)
        for _, kwargs, _ in sent_messages:
            assert kwargs["allowed_mentions"].to_dict() == {"parse": []}

        # Verify responses
        assert "staring at 0" in sent_messages[0][0]
        assert sent_messages[1][0] == "yellow"
        assert "receipt" in sent_messages[2][0]
        assert sent_messages[3][0] == "You didn't tell me."
        assert sent_messages[4][0] == "You haven't told me yours either."

    asyncio.run(run_chained_dialogue())
