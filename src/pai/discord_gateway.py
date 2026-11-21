"""Discord transport with an explicit opt-in boundary."""

import asyncio
from collections.abc import Awaitable, Callable, Iterable
from datetime import UTC, datetime, timedelta

import discord
from discord.ext import tasks

from pai.commands import controls
from pai.conversation import ConversationContext, direct_mention, prepare_context
from pai.discord_media import discover_media
from pai.policy import PrivacyPolicy
from pai.storage import Archive, MessageRecord


class PaiDiscordClient(discord.Client):
    def __init__(
        self,
        policy: PrivacyPolicy,
        handle_message: Callable[[discord.Message], Awaitable[bool | None]],
        *,
        archive: Archive | None = None,
        respond: Callable[[ConversationContext], Awaitable[str]] | None = None,
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
        self.respond = respond
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
            inserted = await self.handle_message(message)
        if inserted and self.respond is not None:
            await self._respond_if_mentioned(message)

    async def _respond_if_mentioned(self, message: discord.Message) -> None:
        if (
            self.user is None
            or self.archive is None
            or self.respond is None
            or message.guild is None
            or not direct_mention(
                message.content,
                (target.id for target in message.mentions),
                self.user.id,
            )
        ):
            return
        access = await self._current_reply_access(message)
        if access is None:
            return
        _, can_read_history = access
        request = await asyncio.to_thread(self.archive.get, message.id)
        if request is None or request.text != message.content:
            return
        context = ConversationContext(request)
        if can_read_history:
            context = await asyncio.to_thread(
                prepare_context,
                self.archive,
                self.policy,
                request,
                now=datetime.now(UTC),
            )
        response = (await self.respond(context)).strip()
        if not response:
            return

        access = await self._current_reply_access(message)
        if access is None:
            return
        channel, can_read_history = access
        if len(context.sources) > 1 and not can_read_history:
            return
        if not await asyncio.to_thread(self.archive.records_unchanged, context.sources):
            return
        await channel.send(
            response[:2000], allowed_mentions=discord.AllowedMentions.none()
        )

    async def _current_reply_access(
        self, message: discord.Message
    ) -> tuple[discord.TextChannel, bool] | None:
        channel = self.get_channel(message.channel.id)
        if (
            message.guild is None
            or not isinstance(channel, discord.TextChannel)
            or channel.guild.id != message.guild.id
            or not self.policy.permits(channel.guild.id, channel.id, message.author.id)
        ):
            return None
        bot = channel.guild.me
        if bot is None:
            return None
        try:
            requester = await channel.guild.fetch_member(message.author.id)
        except discord.HTTPException:
            return None
        bot_permissions = channel.permissions_for(bot)
        member_permissions = channel.permissions_for(requester)
        if (
            not bot_permissions.view_channel
            or not bot_permissions.send_messages
            or not member_permissions.view_channel
        ):
            return None
        return (
            channel,
            bot_permissions.read_message_history
            and member_permissions.read_message_history,
        )

    async def setup_hook(self) -> None:
        if self.archive is not None:
            await asyncio.to_thread(self.archive.prune, self._retention_cutoff())
            if self.policy.guild_id is not None:
                self.control_tree = controls(self, self.archive, self.policy)
                await self.control_tree.sync(
                    guild=discord.Object(id=self.policy.guild_id)
                )
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


async def archive_message(
    archive: Archive, message: discord.Message, *, include_media: bool = False
) -> bool:
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
    media = (
        tuple(asset.item for asset in discover_media(message)) if include_media else ()
    )
    return await asyncio.to_thread(archive.append, record, media=media)
