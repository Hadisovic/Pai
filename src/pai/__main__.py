"""Command-line entry point for an explicitly approved local bot run."""

import argparse
import asyncio
import os
import sqlite3
from contextlib import AsyncExitStack
from pathlib import Path

import aiohttp
import discord

from pai.discord_gateway import PaiDiscordClient, archive_message
from pai.model_router import Router
from pai.policy import PrivacyPolicy, load_policy
from pai.providers import Groq
from pai.reply_engine import ReplyEngine
from pai.storage import Archive


async def _run(
    policy: PrivacyPolicy, archive: Archive, token: str, groq_key: str | None
) -> None:
    async def handle(message: discord.Message) -> bool:
        return await archive_message(
            archive, message, include_media=policy.media_opt_in
        )

    async with AsyncExitStack() as resources:
        client = await resources.enter_async_context(
            PaiDiscordClient(policy, handle, archive=archive)
        )
        if groq_key:
            session = await resources.enter_async_context(
                aiohttp.ClientSession(
                    timeout=aiohttp.ClientTimeout(total=8), trust_env=False
                )
            )
            routes = Groq(session, groq_key, free_plan_confirmed=True).routes()
            client.respond = ReplyEngine(Router(archive, routes))
        await client.start(token)


def main() -> None:
    parser = argparse.ArgumentParser(description="Pai Discord companion")
    parser.add_argument("--policy", type=Path, default=Path(".pai-policy.json"))
    action = parser.add_mutually_exclusive_group()
    action.add_argument(
        "--connect", action="store_true", help="Start authorized live collection"
    )
    action.add_argument(
        "--apply-policy",
        action="store_true",
        help="Purge revoked archive scope offline",
    )
    parser.add_argument(
        "--database", type=Path, help="Private path for the SQLite archive"
    )
    parser.add_argument(
        "--groq-free",
        action="store_true",
        help="Use an approved, verified card-free Groq organization",
    )
    args = parser.parse_args()
    if args.groq_free and not args.connect:
        parser.error("--groq-free requires --connect")
    try:
        policy = load_policy(args.policy)
    except (OSError, ValueError):
        parser.exit(
            2,
            "Unable to load the private policy file. Check its format and permissions.\n",
        )

    if args.apply_policy:
        if (
            args.database is None
            or not args.database.is_file()
            or not args.policy.is_file()
        ):
            parser.error(
                "--apply-policy requires existing private database and policy files"
            )
        os.umask(0o077)
        try:
            count = Archive(args.database).apply_policy(policy)
        except (OSError, sqlite3.Error, ValueError):
            parser.exit(2, "Could not apply the policy to the archive.\n")
        print(f"Purged {count} records outside the approved scope.")
        return

    if not args.connect:
        print(
            "Collection policy is ready."
            if policy.is_enabled
            else "Collection is disabled."
        )
        return
    if not policy.is_enabled:
        parser.error("An approved collection policy is required before connecting")
    if args.database is None:
        parser.error("A private --database path is required")
    groq_key = None
    if args.groq_free:
        if not policy.external_ai_opt_in:
            parser.error("The private policy must explicitly allow external AI")
        groq_key = os.environ.get("PAI_GROQ_KEY", "").strip()
        if not groq_key:
            parser.error("Set the approved Free Groq key in the environment")
    token = os.environ.get("DISCORD_TOKEN", "").strip()
    if not token:
        parser.error("Set the Discord bot token in the environment")
    os.umask(0o077)
    try:
        archive = Archive(args.database)
        archive.apply_policy(policy)
    except (OSError, sqlite3.Error, ValueError):
        parser.exit(
            2, "Unable to open the private archive. Check its path and schema.\n"
        )

    try:
        asyncio.run(_run(policy, archive, token, groq_key))
    except KeyboardInterrupt:
        return
    except discord.DiscordException:
        parser.exit(
            1,
            "Discord connection failed. Check token, intents and application setup.\n",
        )


if __name__ == "__main__":
    main()
