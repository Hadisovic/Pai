"""Discord transport with an explicit opt-in boundary."""

import asyncio
from collections.abc import Awaitable, Callable, Iterable
from datetime import UTC, datetime, timedelta

import discord
from discord.ext import tasks

from pai.policy import PrivacyPolicy
from pai.storage import Archive, MessageRecord


class PaiDiscordClient(discord.Client):
    def __init__(
        self,
        policy: PrivacyPolicy,
        handle_message: Callable[[discord.Message], Awaitable[None]],
        *,
        archive: Archive | None = None,
    ) -> None:
        super().__init__(
            intents=discord.Intents(
                guilds=True, guild_messages=True, message_content=True
            ),
            member_cache_flags=discord.MemberCacheFlags.none(),
            allowed_mentions=discord.AllowedMentions.none(),
            max_messages=None,
        )
        self.policy = policy
        self.handle_message = handle_message
        self.archive = archive
        self.archive_lock = asyncio.Lock()

    async def on_message(self, message: discord.Message) -> None:
        if (
            message.guild is None
            or not isinstance(message.channel, discord.TextChannel)
            or message.author.bot
            or message.webhook_id is not None
            or not self.policy.permits(
                message.guild.id, message.channel.id, message.author.id
            )
        ):
            return
        bot_member = message.guild.me
        if (
            bot_member is None
            or not message.channel.permissions_for(bot_member).view_channel
        ):
            return
        if self.archive is not None and message.created_at < self._retention_cutoff():
            return
        async with self.archive_lock:
            await self.handle_message(message)

    async def setup_hook(self) -> None:
        if self.archive is not None:
            await asyncio.to_thread(self.archive.prune, self._retention_cutoff())
            self._prune_archive.start()

    async def close(self) -> None:
        self._prune_archive.cancel()
        await super().close()

    def _retention_cutoff(self) -> datetime:
        return datetime.now(UTC) - timedelta(days=self.policy.retention_days)

    @tasks.loop(hours=1)
    async def _prune_archive(self) -> None:
        if self.archive is not None:
            async with self.archive_lock:
                await asyncio.to_thread(self.archive.prune, self._retention_cutoff())

    def _permits_mutation(self, guild_id: int | None, channel_id: int) -> bool:
        if guild_id is None or not self.policy.permits_channel(guild_id, channel_id):
            return False
        channel = self.get_channel(channel_id)
        if not isinstance(channel, discord.TextChannel) or channel.guild.id != guild_id:
            return False
        member = channel.guild.me
        return member is not None and channel.permissions_for(member).view_channel

    async def on_raw_message_edit(self, payload: discord.RawMessageUpdateEvent) -> None:
        archive = self.archive
        guild_id = payload.guild_id
        content = payload.data.get("content")
        timestamp = payload.data.get("edited_timestamp")
        if (
            archive is None
            or guild_id is None
            or not self._permits_mutation(guild_id, payload.channel_id)
            or not isinstance(content, str)
            or not isinstance(timestamp, str)
        ):
            return
        try:
            edited = datetime.fromisoformat(timestamp)
        except ValueError:
            return
        if edited.utcoffset() is None:
            return
        async with self.archive_lock:
            await asyncio.to_thread(
                archive.edit,
                payload.message_id,
                guild_id,
                payload.channel_id,
                self.policy.consenting_member_ids,
                content,
                edited,
            )

    async def on_raw_message_delete(
        self, payload: discord.RawMessageDeleteEvent
    ) -> None:
        await self._apply_deletions(
            payload.guild_id, payload.channel_id, (payload.message_id,)
        )

    async def on_raw_bulk_message_delete(
        self, payload: discord.RawBulkMessageDeleteEvent
    ) -> None:
        await self._apply_deletions(
            payload.guild_id, payload.channel_id, payload.message_ids
        )

    async def _apply_deletions(
        self, guild_id: int | None, channel_id: int, message_ids: Iterable[int]
    ) -> None:
        if (
            self.archive is None
            or guild_id is None
            or not self._permits_mutation(guild_id, channel_id)
        ):
            return
        async with self.archive_lock:
            await asyncio.to_thread(
                self.archive.delete,
                guild_id,
                channel_id,
                message_ids,
                datetime.now(UTC),
            )


async def archive_message(archive: Archive, message: discord.Message) -> bool:
    guild = message.guild
    if guild is None:
        return False
    reference = message.reference
    reply_to_id = None
    if (
        message.type == discord.MessageType.reply
        and reference is not None
        and reference.channel_id == message.channel.id
        and reference.guild_id in (None, guild.id)
    ):
        reply_to_id = reference.message_id
    record = MessageRecord(
        message_id=message.id,
        guild_id=guild.id,
        channel_id=message.channel.id,
        author_id=message.author.id,
        author_display=message.author.display_name,
        text=message.content,
        created_at=message.created_at,
        reply_to_id=reply_to_id,
    )
    return await asyncio.to_thread(archive.append, record)
