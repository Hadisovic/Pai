"""Discord transport with an explicit opt-in boundary."""

import asyncio
from collections.abc import Awaitable, Callable, Iterable
from dataclasses import replace
from datetime import UTC, datetime, timedelta

import discord
from discord.ext import tasks

from pai.commands import controls
from pai.conversation import (
    AssistantTurn,
    ConversationContext,
    MediaReading,
    direct_mention,
    prepare_context,
)
from pai.discord_media import discover_media
from pai.observability import LOG, ReplyLimits
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
        read_media: Callable[
            [discord.Message, ConversationContext], Awaitable[MediaReading]
        ]
        | None = None,
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
        self.read_media = read_media
        self.reply_limits = ReplyLimits()
        self.assistant_turns: dict[int, AssistantTurn] = {}
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
            await self._respond_if_addressed(message)

    async def _respond_if_addressed(self, message: discord.Message) -> None:
        if self.user is None or self.archive is None or message.guild is None:
            return
        mentioned = direct_mention(
            message.content, (target.id for target in message.mentions), self.user.id
        )
        reference = message.reference
        is_reply = (
            message.type == discord.MessageType.reply
            and reference is not None
            and reference.message_id is not None
            and reference.channel_id == message.channel.id
            and reference.guild_id in (None, message.guild.id)
        )
        known_parent = (
            self._is_pai_message(reference.resolved, message) if is_reply else False
        )
        if not mentioned and not (
            is_reply and (known_parent or reference.resolved is None)
        ):
            return

        async with self.reply_limits.slot(
            message.channel.id, message.author.id
        ) as admitted:
            if admitted:
                await self._deliver_reply(
                    message, mentioned, reference if is_reply else None
                )
            elif (mentioned or known_parent) and self.reply_limits.announce_busy(
                message.channel.id
            ):
                access = await self._current_reply_access(message)
                if access is not None:
                    await access[0].send(
                        "too many pings at once. try me again in a sec",
                        allowed_mentions=discord.AllowedMentions.none(),
                    )

    def _is_pai_message(self, parent: object, message: discord.Message) -> bool:
        return (
            self.user is not None
            and isinstance(parent, discord.Message)
            and parent.id == message.reference.message_id
            and parent.channel.id == message.channel.id
            and parent.guild is not None
            and parent.guild.id == message.guild.id
            and parent.author.id == self.user.id
            and parent.webhook_id is None
        )

    async def _deliver_reply(
        self,
        message: discord.Message,
        mentioned: bool,
        reference: discord.MessageReference | None,
    ) -> None:
        if self.archive is None or self.respond is None:
            return
        access = await self._current_reply_access(message)
        if access is None:
            return
        channel, can_read_history = access
        parent = (
            reference.resolved if reference is not None and can_read_history else None
        )
        if reference is not None and can_read_history and parent is None:
            try:
                parent = await channel.fetch_message(reference.message_id)
            except discord.HTTPException:
                pass
        bot_reply = (
            reference is not None
            and can_read_history
            and self._is_pai_message(parent, message)
        )
        if not mentioned and not bot_reply:
            return
        request = await asyncio.to_thread(self.archive.get, message.id)
        if request is None or request.text != message.content:
            return
        assistant_turn = None
        if bot_reply and (turn := self.assistant_turns.get(parent.id)) is not None:
            cutoff = self._retention_cutoff()
            if (
                parent.content == turn.text
                and all(
                    source.channel_id == request.channel_id
                    and self.policy.permits(
                        source.guild_id, source.channel_id, source.author_id
                    )
                    and cutoff <= source.created_at <= request.created_at
                    for source in turn.sources
                )
                and await asyncio.to_thread(
                    self.archive.records_unchanged, turn.sources
                )
            ):
                assistant_turn = turn
        context = ConversationContext(request)
        if can_read_history:
            context = await asyncio.to_thread(
                prepare_context,
                self.archive,
                self.policy,
                request,
                now=datetime.now(UTC),
                assistant_turn=assistant_turn,
            )
        if self.read_media is not None:
            media = await self.read_media(message, context)
            if (
                not can_read_history
                and media.origin
                and media.origin.message_id != request.message_id
            ):
                media = MediaReading(unavailable=True)
            context = replace(context, media=media)
        if not await asyncio.to_thread(self.archive.records_unchanged, context.sources):
            return
        response = (await self.respond(context)).strip()
        if not response:
            return

        access = await self._current_reply_access(message)
        if access is None:
            return
        channel, can_read_history = access
        if not can_read_history and any(
            source.message_id != request.message_id for source in context.sources
        ):
            return
        if not await asyncio.to_thread(self.archive.records_unchanged, context.sources):
            return
        outgoing_reference = (
            discord.MessageReference(
                message_id=message.id, channel_id=channel.id, guild_id=channel.guild.id
            )
            if can_read_history
            else None
        )
        sent = await channel.send(
            response[:2000],
            reference=outgoing_reference,
            allowed_mentions=discord.AllowedMentions.none(),
        )
        if type(sent.id) is int and len(context.sources) <= 32:
            if len(self.assistant_turns) >= 64:
                self.assistant_turns.pop(next(iter(self.assistant_turns)))
            self.assistant_turns[sent.id] = AssistantTurn(
                response[:2000],
                request,
                context.sources,
                context.recall_question,
                prior_turn=context.assistant_turn,
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

    async def on_ready(self) -> None:
        LOG.info("Discord gateway is ready")

    async def on_resumed(self) -> None:
        LOG.info("Discord gateway resumed")

    async def on_disconnect(self) -> None:
        LOG.info("Discord gateway disconnected")

    async def on_error(
        self, event_method: str, *args: object, **kwargs: object
    ) -> None:
        LOG.warning("Discord event handling failed")

    def _retention_cutoff(self) -> datetime:
        return datetime.now(UTC) - timedelta(days=self.policy.retention_days)

    @tasks.loop(hours=1)
    async def _prune_archive(self) -> None:
        if self.archive is not None:
            async with self.archive_lock:
                await asyncio.to_thread(self.archive.prune, self._retention_cutoff())

    @_prune_archive.error
    async def _prune_failed(self, error: BaseException) -> None:
        LOG.error("Archive maintenance stopped. Restart and check the local archive")

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
        if (
            archive is None
            or guild_id is None
            or not self._permits_mutation(guild_id, payload.channel_id)
        ):
            return
        content = payload.data.get("content")
        timestamp = payload.data.get("edited_timestamp")
        try:
            edited = (
                datetime.fromisoformat(timestamp)
                if isinstance(timestamp, str)
                else None
            )
        except ValueError:
            edited = None
        kinds = frozenset(
            kind
            for field, kind in (
                ("attachments", "attachment"),
                ("sticker_items", "sticker"),
                ("embeds", "embed"),
            )
            if field in payload.data
        )
        async with self.archive_lock:
            if (
                isinstance(content, str)
                and edited is not None
                and edited.utcoffset() is not None
            ):
                await asyncio.to_thread(
                    archive.edit,
                    payload.message_id,
                    guild_id,
                    payload.channel_id,
                    self.policy.consenting_member_ids,
                    content,
                    edited,
                )
            if self.policy.media_opt_in and kinds:
                items = tuple(asset.item for asset in discover_media(payload.message))
                await asyncio.to_thread(
                    archive.update_media,
                    payload.message_id,
                    guild_id,
                    payload.channel_id,
                    self.policy.consenting_member_ids,
                    kinds,
                    items,
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
