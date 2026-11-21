"""Discord transport with an explicit opt-in boundary."""

import asyncio
from collections.abc import Awaitable, Callable

import discord

from pai.policy import PrivacyPolicy
from pai.storage import Archive, MessageRecord


class PaiDiscordClient(discord.Client):
    def __init__(
        self,
        policy: PrivacyPolicy,
        handle_message: Callable[[discord.Message], Awaitable[None]],
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
        await self.handle_message(message)


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
