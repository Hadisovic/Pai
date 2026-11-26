"""Private experimental instance controls, separate from the golden defaults."""

import asyncio
import json
import os
import re
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, replace
from pathlib import Path
from typing import TYPE_CHECKING

import discord

if TYPE_CHECKING:
    from pai.conversation import ConversationContext
    from pai.model_router import ModelRequest, Router
    from pai.policy import PrivacyPolicy

current_name = ContextVar("current_companion_name", default="Pai")
_APP_LABEL = re.compile(r"^(Addressee: |T\d+ is )Pai(?= \(|'s preceding reply)", re.M)


def identity_query(text: str) -> str:
    name = current_name.get()
    if name == "Pai":
        return text
    text = re.sub(r"\bpai\b", "the other companion", text, flags=re.I)
    return re.sub(rf"\b{re.escape(name)}\b", "pai", text, flags=re.I)


@dataclass(frozen=True)
class Instance:
    name: str
    guild_id: int
    channel_id: int
    bot_user_id: int | None
    stable_bot_id: int
    distress_reviewed: bool = False
    isolated_free_quota_verified: bool = False

    @classmethod
    def load(cls, path: Path) -> "Instance":
        data = json.loads(path.read_text(encoding="utf-8-sig"))
        if not isinstance(data, dict):
            raise ValueError("Invalid private instance configuration")
        try:
            instance = cls(**data)
        except TypeError as error:
            raise ValueError("Invalid private instance configuration") from error
        if (
            not isinstance(instance.name, str)
            or not re.fullmatch(r"[A-Za-z][A-Za-z0-9]{1,17}", instance.name)
            or instance.name.casefold() == "pai"
            or any(
                type(x) is not int or not 0 < x < 2**64
                for x in (
                    instance.guild_id,
                    instance.channel_id,
                    instance.stable_bot_id,
                )
            )
            or (
                instance.bot_user_id is not None
                and (
                    type(instance.bot_user_id) is not int
                    or not 0 < instance.bot_user_id < 2**64
                )
            )
            or type(instance.distress_reviewed) is not bool
            or type(instance.isolated_free_quota_verified) is not bool
        ):
            raise ValueError("Invalid private instance configuration")
        return instance

    def validate_start(self, policy: "PrivacyPolicy", *, hosted: bool) -> None:
        if policy.guild_id != self.guild_id or policy.channel_ids != {self.channel_id}:
            raise ValueError(
                "The policy must allow only the designated experimental channel"
            )
        if not self.bot_user_id or self.bot_user_id == self.stable_bot_id:
            raise ValueError(
                "A distinct experimental Discord application ID is required"
            )
        if not self.distress_reviewed:
            raise ValueError(
                "Review the experimental imminent-distress safeguard before connecting"
            )
        if policy.media_opt_in:
            raise ValueError("Experimental media must remain off")
        if hosted and not self.isolated_free_quota_verified:
            raise ValueError(
                "Hosted inference requires approved, independently metered Free quota"
            )

    def brand(self, request: "ModelRequest") -> "ModelRequest":
        return replace(
            request,
            instructions=re.sub(r"\bPai\b", self.name, request.instructions),
            payload=_APP_LABEL.sub(lambda match: match[1] + self.name, request.payload),
        )


class InstanceRouter:
    def __init__(self, router: "Router", instance: Instance) -> None:
        self.router, self.instance = router, instance
        self.routes = router.routes

    async def generate(self, request: "ModelRequest", *, render=None) -> str:
        return await self.router.generate(self.instance.brand(request), render=render)


async def verify_discord(client: discord.Client, instance: Instance) -> None:
    user = client.user
    if (
        user is None
        or not user.bot
        or user.id != instance.bot_user_id
        or user.id == instance.stable_bot_id
        or user.name != instance.name
        or user.avatar is None
    ):
        raise discord.ClientException(
            "Experimental bot identity or custom avatar did not match"
        )
    if {guild.id async for guild in client.fetch_guilds(limit=None)} != {
        instance.guild_id
    }:
        raise discord.ClientException(
            "Experimental bot is installed outside the approved server or is missing"
        )
    guild = await client.fetch_guild(instance.guild_id)
    bot = await guild.fetch_member(user.id)
    if bot.guild_permissions.administrator:
        raise discord.ClientException("Experimental bot has Administrator")
    approved = False
    for channel in await guild.fetch_channels():
        if isinstance(channel, discord.CategoryChannel):
            continue
        permissions = channel.permissions_for(bot)
        if channel.id == instance.channel_id and isinstance(
            channel, discord.TextChannel
        ):
            approved = (
                permissions.view_channel
                and permissions.read_message_history
                and permissions.send_messages
            )
        elif permissions.view_channel:
            raise discord.ClientException("Experimental bot can view another channel")
    if not approved:
        raise discord.ClientException(
            "Experimental bot is missing the approved text channel permissions"
        )


def distress_reply(context: "ConversationContext") -> str | None:
    if not context.style or context.style.situation != "imminent":
        return None
    if context.style.language == "arabic" or re.search(
        r"[\u0621-\u064a]", context.request.text
    ):
        return "آسف إنك بتمر بهالشي. اتصل بالطوارئ المحلية هلا، واحكي لحدا قريب منك ييجي يضل معك."
    return (
        "i’m sorry this is happening. call local emergency services now, "
        "and tell someone nearby you trust so they can stay with you."
    )


@contextmanager
def runtime_lock(root: Path):
    with (root / "run.lock").open("a+b") as file:
        if file.tell() == 0:
            file.write(b"\0")
            file.flush()
        file.seek(0)
        try:
            if os.name == "nt":
                import msvcrt

                msvcrt.locking(file.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl

                fcntl.flock(file, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as error:
            raise ValueError("The experimental instance is already running") from error
        yield


async def run_until_stopped(
    client: discord.Client, token: str, stop_file: Path
) -> None:
    async def wait_for_stop():
        while not stop_file.exists():
            await asyncio.sleep(0.5)

    connection = asyncio.create_task(client.start(token))
    watch = asyncio.create_task(wait_for_stop())
    try:
        done, _ = await asyncio.wait(
            (connection, watch), return_when=asyncio.FIRST_COMPLETED
        )
        if connection in done:
            await connection
        else:
            await client.close()
    finally:
        for task in (watch, connection):
            if not task.done():
                task.cancel()
        await asyncio.gather(watch, connection, return_exceptions=True)
