"""Replay held-out synthetic Discord dialogues; review actual replies by hand."""

import argparse
import asyncio
import json
import os
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import AsyncMock, Mock

import aiohttp
import discord

from pai.conversation import ConversationContext
from pai.discord_gateway import PaiDiscordClient, archive_message
from pai.model_router import Router
from pai.policy import PrivacyPolicy
from pai.providers import Groq
from pai.reply_engine import ReplyEngine
from pai.storage import Archive


@dataclass(frozen=True)
class Event:
    label: str
    speaker: int
    text: str
    reply_to: str | None = None


DIALOGUE = (
    Event("ordinary", 3, "the label maker printed an entire blank roll again"),
    Event("interjection", 4, "does anyone have a spare charging cable"),
    Event("banter", 3, "<@42> it's charging us for invisible ink now"),
    Event(
        "literal-pause",
        4,
        "<@42> pause the stream while I reconnect. Which control do I use?",
    ),
    Event(
        "repair",
        3,
        "i meant the label maker, we don't even have an ink cartridge",
        "banter",
    ),
    Event(
        "tone-shift",
        3,
        "jokes aside, my cat's at the vet and i'm worried. no advice please",
        "repair",
    ),
    Event("first-fact", 3, "My favourite game is Slay the Spire."),
    Event("second-fact", 4, "لعبتي المفضلة هي Hades."),
    Event("distractor", 4, "My favorite food is tacos."),
    Event("unconsented", 5, "<@42> My favorite game is checkers."),
    Event("arabizi-recall", 4, "<@42> shou kanet le3beti taba3i? Answer in English."),
    Event("switch-speaker", 3, "طيب وأنا؟", "arabizi-recall"),
    Event("repeat", 3, "just say it", "switch-speaker"),
    Event("one-word", 4, "<@42> one word, what color is snow?"),
)


async def replay(
    dialogue: tuple[Event, ...],
    archive: Archive,
    respond: Callable[[ConversationContext], Awaitable[str]],
    *,
    conversation_engine: str = "legacy",
    assistant_continuity: bool = False,
    restart_before: str | None = None,
) -> list[dict]:
    policy = PrivacyPolicy(
        True,
        "synthetic",
        1,
        frozenset({2}),
        frozenset({3, 4}),
        assistant_continuity_opt_in=assistant_continuity,
    )
    guild = Mock(id=1, me=Mock(), owner_id=3)
    channel = Mock(spec=discord.TextChannel, id=2, guild=guild)
    channel.permissions_for.return_value = discord.Permissions.all()
    members = {
        key: Mock(spec=discord.Member, id=key, display_name="Fictional Sam", bot=False)
        for key in (3, 4, 5)
    }
    guild.fetch_member = AsyncMock(side_effect=members.__getitem__)
    replies = {}
    transcript = []
    now = datetime.now(UTC) - timedelta(seconds=len(dialogue))

    async def send(content, *, reference, allowed_mentions):
        assert reference is not None and reference.message_id == identifier
        assert allowed_mentions.to_dict() == {"parse": []}
        reply = Mock(
            spec=discord.Message,
            id=identifier + 1000,
            author=Mock(id=42),
            guild=guild,
            channel=channel,
            content=content,
            webhook_id=None,
            reference=reference,
            created_at=now + timedelta(seconds=identifier - 100, microseconds=1),
        )
        replies[event.label] = reply
        return reply

    async def ingest(message):
        return await archive_message(archive, message)

    channel.send = AsyncMock(side_effect=send)

    def make_client():
        client = PaiDiscordClient(
            policy,
            ingest,
            archive=archive,
            respond=respond,
            conversation_engine=conversation_engine,
        )
        client._connection.user = Mock(id=42)
        client.get_channel = Mock(return_value=channel)
        return client

    client = make_client()
    for identifier, event in enumerate(dialogue, 100):
        if event.label == restart_before:
            archive = Archive(archive.path)
            client = make_client()
        parent = replies.get(event.reply_to)
        reference = (
            Mock(message_id=parent.id, guild_id=1, channel_id=2, resolved=parent)
            if parent is not None
            else None
        )
        msg = Mock(
            spec=discord.Message,
            id=identifier,
            author=members[event.speaker],
            guild=guild,
            channel=channel,
            content=event.text,
            mentions=[Mock(id=42)] if "<@42>" in event.text else [],
            webhook_id=None,
            created_at=now + timedelta(seconds=identifier - 100),
            edited_at=None,
            reference=reference,
            type=discord.MessageType.reply
            if reference
            else discord.MessageType.default,
        )
        await client.on_message(msg)
        answer = replies.get(event.label)
        transcript.append(
            {
                "event": event.label,
                "speaker": event.speaker,
                "text": event.text,
                "reply_to": event.reply_to,
                "archived": archive.get(identifier) is not None,
                "pai": answer.content if answer is not None else None,
            }
        )
    return transcript


async def run_free(key: str, quota_path: Path) -> dict:
    usage = []
    async with aiohttp.ClientSession() as session:
        route = Groq(
            session, key, free_plan_confirmed=True, observe_usage=usage.append
        ).routes()[0]
        engine = ReplyEngine(Router(Archive(quota_path), (route,)))
        with TemporaryDirectory(prefix="pai-held-out-") as tmp:
            turns = await replay(
                DIALOGUE, Archive(Path(tmp) / "archive.sqlite"), engine
            )
    return {"model": route.name, "reported_tokens": usage, "turns": turns}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--groq-free", action="store_true", required=True)
    parser.add_argument(
        "--quota-db", type=Path, required=True, help="Separate private quota ledger"
    )
    args = parser.parse_args()
    key = os.environ.get("PAI_GROQ_KEY", "").strip()
    if not key:
        parser.error("Set the verified Free Groq key in PAI_GROQ_KEY")
    print(
        json.dumps(
            asyncio.run(run_free(key, args.quota_db)), ensure_ascii=True, indent=2
        )
    )


if __name__ == "__main__":
    main()
