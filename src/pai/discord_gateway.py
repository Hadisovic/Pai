"""Discord transport with an explicit opt-in boundary."""

import asyncio
from collections.abc import Awaitable, Callable, Iterable
from dataclasses import replace
from datetime import UTC, datetime, timedelta

import discord
from discord.ext import tasks

from pai.commands import controls
from pai.continuity import (
    AssistantReceipts,
    RecoveredReply,
    clarify_harmful_parent,
    focus_native_branch,
)
from pai.conversation import (
    AssistantTurn,
    ConversationContext,
    MediaReading,
    direct_mention,
    prepare_context,
)
from pai.discord_media import discover_media
from pai.identity import Identity
from pai.members import (
    Member,
    MemberDirectory,
    MemberPlan,
    label,
    member_intent,
    render_member_reply,
)
from pai.observability import LOG, ReplyLimits
from pai.policy import PrivacyPolicy
from pai.reply_engine import ReplyEngine
from pai.social import SocialLearning, SocialReply, respond_with_context
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
        conversation_engine: str = "legacy",
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
        self.timeline = conversation_engine != "legacy"
        self.social: SocialLearning | None = None
        self.identity: Identity | None = None
        self.members = (
            MemberDirectory(archive, policy)
            if archive is not None and policy.member_awareness_opt_in
            else None
        )
        self.receipts = (
            AssistantReceipts(archive, policy)
            if archive is not None
            and self.timeline
            and policy.assistant_continuity_opt_in
            else None
        )
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
        if (
            inserted
            and self.members is not None
            and self.policy.permits_member_awareness(
                message.guild.id, message.channel.id, message.author.id
            )
        ):
            await asyncio.to_thread(self._observe_member, message)
        if (
            inserted
            and self.social is not None
            and self.policy.permits_social(
                message.guild.id, message.channel.id, message.author.id
            )
        ):
            await self.social.observe(
                message.id, self.receipts.feedback_terms if self.receipts else None
            )
        if inserted and self.respond is not None:
            await self._respond_if_addressed(message)

    def _observe_member(self, message: discord.Message) -> None:
        row = self.archive.get(message.id)
        if row is not None:
            self.members.observe(row, message.author.name, message.author.display_name)

    async def _visible_member_labels(
        self,
        channel: discord.TextChannel,
        candidates: tuple[Member, ...],
    ) -> dict[int, str]:
        async def resolve(candidate: Member) -> tuple[int, str] | None:
            try:
                member = await channel.guild.fetch_member(candidate.id)
            except discord.HTTPException:
                return None
            if (
                member.id != candidate.id
                or member.guild.id != channel.guild.id
                or member.bot
            ):
                return None
            permissions = channel.permissions_for(member)
            if not (permissions.view_channel and permissions.read_message_history):
                return None
            return candidate.id, label(member.display_name)

        return dict(
            item
            for item in await asyncio.gather(*(resolve(row) for row in candidates))
            if item is not None
        )

    async def _member_plan(
        self,
        message: discord.Message,
        channel: discord.TextChannel,
        context: ConversationContext,
    ) -> MemberPlan | None:
        request = context.request
        if (
            self.members is None
            or not self.members.permits(request)
            or (context.style and context.style.situation)
        ):
            return None
        intent = member_intent(
            request.text, self.user.id, {target.id for target in message.mentions}
        )
        if intent is None:
            return None
        present = {
            row.author_id for row in (request, *context.parents, *context.recent)
        }
        if intent.appearance or intent.sensitive:
            return self.members.plan(request, intent, (), present)
        candidates = await asyncio.to_thread(
            self.members.lookup,
            request,
            ids=intent.ids if intent.ids or intent.unavailable else None,
            alias=intent.alias,
        )
        if (
            intent.group
            and not intent.ids
            and not intent.alias
            and not intent.unavailable
        ):
            candidates = tuple(
                sorted(candidates, key=lambda member: member.id not in present)
            )
        candidates = candidates[:4]
        labels = await self._visible_member_labels(channel, candidates)
        return await asyncio.to_thread(
            self.members.plan,
            request,
            intent,
            tuple(member for member in candidates if member.id in labels),
            present,
            live_labels=labels,
        )

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
        return self._is_own_reply(
            parent, message.reference.message_id, message.guild.id, message.channel.id
        )

    def _is_own_reply(
        self, parent: object, reply_id: int, guild_id: int, channel_id: int
    ) -> bool:
        return (
            self.user is not None
            and isinstance(parent, discord.Message)
            and parent.id == reply_id
            and parent.channel.id == channel_id
            and parent.guild is not None
            and parent.guild.id == guild_id
            and parent.author.id == self.user.id
            and parent.webhook_id is None
        )

    async def _historical_reply(
        self, channel: discord.TextChannel, request: MessageRecord
    ) -> RecoveredReply | None:
        target = await asyncio.to_thread(self.receipts.find_historical, request)
        if target is None:
            return None
        try:
            parent = await channel.fetch_message(target.reply_id)
        except discord.HTTPException:
            return None
        if not self._is_own_reply(
            parent, target.reply_id, request.guild_id, request.channel_id
        ):
            return None
        reference = parent.reference
        if (
            reference is None
            or reference.message_id != target.request_id
            or reference.channel_id != request.channel_id
            or reference.guild_id not in (None, request.guild_id)
        ):
            return None
        return await asyncio.to_thread(
            self.receipts.restore,
            request,
            target.reply_id,
            target.request_id,
            parent.content,
            social=self.social.store if self.social is not None else None,
            historical=True,
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
        recovered = None
        social_store = self.social.store if self.social is not None else None
        if bot_reply and (turn := self.assistant_turns.get(parent.id)) is not None:
            cutoff = self._retention_cutoff()
            if (
                (turn.text is None or parent.content == turn.text)
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
                and (
                    self.social is None
                    or await asyncio.to_thread(self.social.valid_turn, turn, request)
                )
            ):
                assistant_turn = turn
        if bot_reply and assistant_turn is None and self.receipts is not None:
            parent_origin = parent.reference
            if (
                parent_origin is not None
                and parent_origin.channel_id == request.channel_id
                and parent_origin.guild_id in (None, request.guild_id)
                and parent_origin.message_id is not None
            ):
                recovered = await asyncio.to_thread(
                    self.receipts.restore,
                    request,
                    parent.id,
                    parent_origin.message_id,
                    parent.content,
                    social=social_store,
                )
                if recovered is not None:
                    assistant_turn = recovered.turn
        context = await asyncio.to_thread(
            prepare_context,
            self.archive,
            self.policy,
            request,
            now=datetime.now(UTC),
            assistant_turn=assistant_turn,
            read_history=can_read_history,
            timeline=self.timeline,
            native_reply=self.timeline and bot_reply,
            prefer_arabic=self.timeline and message.author.id == message.guild.owner_id,
        )
        if (
            self.receipts is not None
            and can_read_history
            and not bot_reply
            and not context.self_recall
            and not (context.style and context.style.situation)
        ):
            recovered = await self._historical_reply(channel, request)
            if recovered is not None:
                context = replace(context, assistant_turn=recovered.turn)
        if recovered is not None and recovered.notes and self.social is not None:
            restored_turn = recovered.turn
            self.social.track_delivery(
                restored_turn.message_id,
                restored_turn,
                ConversationContext(restored_turn.request),
                SocialReply(restored_turn.text or "", recovered.notes),
            )
        if self.timeline:
            context = focus_native_branch(context)
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
        member_plan = (
            await self._member_plan(message, channel, context)
            if can_read_history
            else None
        )
        if member_plan and member_plan.block:
            if not await asyncio.to_thread(self.members.valid, request, member_plan):
                return
            # The extra data path discloses only its bounded member evidence.
            context = replace(
                context,
                parents=(),
                recent=(),
                memory=(),
                style_examples=(),
                group_style=(),
                assistant_turn=None,
                observed_speakers=(),
                style_sources=(),
                self_recall=False,
                recall_question=None,
            )
        member_block = member_plan.block if member_plan else ""
        used_members = False
        learned = None
        grounded = (
            self.identity.reply(context, can_read_history) if self.identity else None
        )
        facts = (
            self.identity.prompt_facts(context, can_read_history)
            if self.identity and grounded is None
            else ""
        )
        if clarify_harmful_parent(context):
            response = "nah. what are you asking me about?"
        elif member_plan is not None and member_plan.local_reply:
            response = member_plan.local_reply
        elif grounded is not None:
            response = grounded
        elif self.social is not None:
            learned = await self.social.respond(
                context, can_read_history, facts, member_block
            )
            response = learned.text.strip()
            used_members = learned.members_used
        elif (facts or member_block) and isinstance(self.respond, ReplyEngine):
            response, used = await respond_with_context(
                self.respond,
                context,
                ("members", member_block),
                ("identity", facts),
            )
            used_members = "members" in used
            response = response.strip()
        else:
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
        if recovered is not None and (
            not can_read_history
            or await asyncio.to_thread(
                self.receipts.restore,
                request,
                recovered.turn.message_id,
                recovered.turn.request.message_id,
                recovered.turn.text,
                social=social_store,
                historical=not bot_reply,
            )
            != recovered
        ):
            return
        if (
            self.social is not None
            and recovered is None
            and context.assistant_turn is not None
            and not await asyncio.to_thread(
                self.social.valid_turn, context.assistant_turn, request
            )
        ):
            return
        if (
            learned is not None
            and learned.notes
            and (
                not can_read_history
                or not await asyncio.to_thread(
                    self.social.valid, context, learned.notes
                )
            )
        ):
            return
        if used_members:
            if (
                not can_read_history
                or await self._visible_member_labels(channel, member_plan.members)
                != dict(member_plan.live_labels)
                or not await asyncio.to_thread(self.members.valid, request, member_plan)
            ):
                return
        if self.members is not None:
            response = render_member_reply(
                response, member_plan if used_members else MemberPlan()
            )
            if not response:
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
        if member_plan is not None:
            # Member aliases and sharing settings have their own lifecycle.
            # A normal social or text turn still uses the ordinary receipt path.
            if type(sent.id) is int and learned is not None and learned.notes:
                self.social.track_feedback(sent.id, request, learned)
            return
        if type(sent.id) is int:
            if len(self.assistant_turns) >= 64:
                self.assistant_turns.pop(next(iter(self.assistant_turns)))
            sources = context.sources
            if learned is not None and learned.notes:
                sources = tuple(
                    dict.fromkeys(
                        (
                            *sources,
                            *(row for note in learned.notes for row in note.sources),
                        )
                    )
                )
            if len(sources) <= 32:
                turn = AssistantTurn(
                    response[:2000],
                    request,
                    sources,
                    context.recall_question,
                    prior_turn=context.assistant_turn,
                    message_id=sent.id,
                    created_at=sent.created_at
                    if isinstance(sent.created_at, datetime)
                    else None,
                )
            else:
                # Keep the verified question without relying on an answer
                # whose full set of supporting sources no longer fits.
                anchors = (request,)
                if context.recall_question not in (None, request):
                    anchors += (context.recall_question,)
                turn = AssistantTurn(None, request, anchors, context.recall_question)
            self.assistant_turns[sent.id] = turn
            if learned is not None and learned.notes:
                self.social.track_delivery(sent.id, turn, context, learned)
            if (
                self.receipts is not None
                and can_read_history
                and context.media == MediaReading()
                and context.assistant_turn is None
            ):
                await asyncio.to_thread(
                    self.receipts.remember,
                    turn,
                    notes=learned.notes if learned is not None else (),
                    social=social_store,
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
                self.control_tree = controls(
                    self,
                    self.archive,
                    self.policy,
                    social=self.social.store if self.social else None,
                    members=self.members,
                )
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
