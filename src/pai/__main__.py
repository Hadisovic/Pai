"""Command-line entry point for an explicitly approved local bot run."""

import argparse
import os
import sqlite3
from pathlib import Path

import discord

from pai.discord_gateway import PaiDiscordClient, archive_message
from pai.policy import load_policy
from pai.storage import Archive


def main() -> None:
    parser = argparse.ArgumentParser(description="Pai Discord companion")
    parser.add_argument("--policy", type=Path, default=Path(".pai-policy.json"))
    parser.add_argument(
        "--connect", action="store_true", help="Start authorized live collection"
    )
    parser.add_argument(
        "--database", type=Path, help="Private path for the SQLite archive"
    )
    args = parser.parse_args()
    try:
        policy = load_policy(args.policy)
    except (OSError, ValueError):
        parser.exit(
            2,
            "Unable to load the private policy file. Check its format and permissions.\n",
        )

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
    token = os.environ.get("DISCORD_TOKEN", "").strip()
    if not token:
        parser.error("Set the Discord bot token in the environment")
    os.umask(0o077)
    try:
        archive = Archive(args.database)
    except (OSError, sqlite3.Error, ValueError):
        parser.exit(
            2, "Unable to open the private archive. Check its path and schema.\n"
        )

    async def handle(message: discord.Message) -> None:
        await archive_message(archive, message)

    try:
        PaiDiscordClient(policy, handle, archive=archive).run(token, log_handler=None)
    except discord.DiscordException:
        parser.exit(
            1,
            "Discord connection failed. Check token, intents and application setup.\n",
        )


if __name__ == "__main__":
    main()
