"""Offline exercise for synthetic messages. No Discord or AI connections."""

import sqlite3
from dataclasses import dataclass, field


@dataclass(frozen=True)
class Message:
    message_id: str
    guild_id: str | None
    channel_id: str
    author: str
    text: str
    mentions: tuple[str, ...] = ()
    reply_to_id: str | None = None
    bot: bool = False


@dataclass
class FakeDiscordGateway:
    events: tuple[Message, ...]
    replies: list[tuple[str, str]] = field(default_factory=list, init=False)


@dataclass
class FakeAIProvider:
    response: str
    requests: list[tuple[Message, str | None]] = field(default_factory=list, init=False)

    def generate(self, message: Message, reply_context: str | None) -> str:
        self.requests.append((message, reply_context))
        return self.response


def run_smoke(
    gateway: FakeDiscordGateway,
    provider: FakeAIProvider,
    archive: sqlite3.Connection,
    *,
    authorized_channel: tuple[str, str] | None = None,
    bot_id: str = "pai",
) -> None:
    """Replay synthetic events against a disposable archive supplied by the caller."""
    with archive:
        archive.execute(
            "CREATE TABLE IF NOT EXISTS messages ("
            "message_id TEXT PRIMARY KEY, guild_id TEXT NOT NULL, "
            "channel_id TEXT NOT NULL, text TEXT NOT NULL)"
        )
        for event in gateway.events:
            if (
                event.guild_id is None
                or event.bot
                or (event.guild_id, event.channel_id) != authorized_channel
            ):
                continue
            inserted = archive.execute(
                "INSERT INTO messages (message_id, guild_id, channel_id, text) VALUES (?, ?, ?, ?) "
                "ON CONFLICT (message_id) DO NOTHING",
                (event.message_id, event.guild_id, event.channel_id, event.text),
            )
            if inserted.rowcount == 0 or bot_id not in event.mentions:
                continue
            parent = archive.execute(
                "SELECT text FROM messages WHERE message_id = ? AND guild_id = ? AND channel_id = ?",
                (event.reply_to_id, event.guild_id, event.channel_id),
            ).fetchone()
            reply = provider.generate(event, parent[0] if parent else None)
            gateway.replies.append((event.message_id, reply))
