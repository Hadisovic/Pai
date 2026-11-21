"""Explicit ephemeral privacy operations for the configured guild."""

import asyncio
import json
from datetime import UTC, datetime, timedelta
from io import BytesIO

import discord
from discord import app_commands

from pai.conversation import share_style_example
from pai.observability import LOG
from pai.policy import PrivacyPolicy
from pai.storage import Archive


class PrivateCommandTree(app_commands.CommandTree):
    async def on_error(
        self, interaction: discord.Interaction, error: app_commands.AppCommandError
    ) -> None:
        LOG.warning("A privacy command failed")
        if not interaction.response.is_done():
            await interaction.response.send_message(
                "This action could not be completed.", ephemeral=True
            )


def controls(
    client: discord.Client, archive: Archive, policy: PrivacyPolicy
) -> app_commands.CommandTree:
    tree = PrivateCommandTree(client)
    guild = discord.Object(id=policy.guild_id) if policy.guild_id is not None else None
    if guild is None:
        return tree

    def visible(interaction: discord.Interaction) -> bool:
        return (
            interaction.guild_id == guild.id
            and isinstance(interaction.channel, discord.TextChannel)
            and interaction.permissions.view_channel
        )

    async def unavailable(interaction: discord.Interaction) -> None:
        await interaction.response.send_message(
            "This privacy action is unavailable in this channel.", ephemeral=True
        )

    @tree.command(guild=guild, description="See how Pai handles your messages")
    async def privacy(interaction: discord.Interaction) -> None:
        if not visible(interaction):
            return await unavailable(interaction)
        author = interaction.user.id
        opted_out = await asyncio.to_thread(archive.is_opted_out, guild.id, author)
        collecting = (
            policy.permits(guild.id, interaction.channel_id, author) and not opted_out
        )
        state = "enabled" if collecting else "disabled"
        await interaction.response.send_message(
            f"Collection for you in this channel is {state}. "
            f"Messages are retained for up to {policy.retention_days} days, subject to room "
            "in the archive. /memory exports your recent saved messages in this channel. "
            "/forgetme removes your saved messages and stops future collection for you. "
            "Ask a server administrator for the current notice or to report a privacy concern.",
            ephemeral=True,
        )

    @tree.command(
        guild=guild, description="Export your recent saved messages in this channel"
    )
    async def memory(interaction: discord.Interaction) -> None:
        channel_id = interaction.channel_id
        author = interaction.user.id
        if (
            channel_id is None
            or not visible(interaction)
            or not interaction.permissions.read_message_history
            or not policy.permits(guild.id, channel_id, author)
        ):
            return await unavailable(interaction)
        records = await asyncio.to_thread(
            archive.export_author,
            guild.id,
            channel_id,
            author,
            datetime.now(UTC) - timedelta(days=policy.retention_days),
        )
        if not records:
            await interaction.response.send_message(
                "No saved messages here.", ephemeral=True
            )
            return
        payload = [
            {
                "source": row.jump_url,
                "text": row.text,
                "created_at": row.created_at.isoformat(),
            }
            for row in records
        ]
        if not await asyncio.to_thread(archive.records_unchanged, records):
            await interaction.response.send_message(
                "The archive changed. Try again.", ephemeral=True
            )
            return
        filename = discord.File(
            BytesIO(json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")),
            filename="pai-memory.json",
        )
        await interaction.response.send_message(
            "Your most recent saved messages in this channel, up to 100.",
            file=filename,
            ephemeral=True,
        )

    @tree.command(
        guild=guild, description="Remove your saved messages and opt out of collection"
    )
    async def forgetme(interaction: discord.Interaction) -> None:
        if not visible(interaction):
            return await unavailable(interaction)
        await interaction.response.defer(ephemeral=True, thinking=True)
        count = await asyncio.to_thread(
            archive.forget_author, guild.id, interaction.user.id, datetime.now(UTC)
        )
        await interaction.followup.send(
            f"Removed {count} saved messages. Collection for you has stopped.",
            ephemeral=True,
        )

    @tree.command(
        guild=guild,
        description="Share your own saved message as a channel style example",
    )
    @app_commands.describe(
        message_id="Discord ID of your saved message in this channel"
    )
    async def sharestyle(interaction: discord.Interaction, message_id: str) -> None:
        channel_id = interaction.channel_id
        if (
            channel_id is None
            or not visible(interaction)
            or not interaction.permissions.read_message_history
            or not message_id.isascii()
            or not message_id.isdecimal()
            or len(message_id) > 20
        ):
            return await unavailable(interaction)
        saved = await asyncio.to_thread(
            share_style_example,
            archive,
            policy,
            guild.id,
            channel_id,
            interaction.user.id,
            int(message_id),
        )
        await interaction.response.send_message(
            "Shared as a style example."
            if saved
            else "This message is unavailable or already shared.",
            ephemeral=True,
        )

    return tree
