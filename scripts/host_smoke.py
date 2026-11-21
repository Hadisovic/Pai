"""Run a synthetic persistence exercise across two isolated process invocations."""

import argparse
import asyncio
import os
from datetime import UTC, datetime, timedelta
from pathlib import Path

import aiohttp

from pai.backup import create_backup, export_erasures, restore_backup
from pai.policy import PrivacyPolicy
from pai.storage import Archive, MessageRecord

_POLICY = PrivacyPolicy(
    True, "synthetic-host-smoke", 10, frozenset({20}), frozenset({30, 31})
)


def seed(directory: Path) -> None:
    archive = Archive(directory / "active.sqlite")
    now = datetime.now(UTC)
    assert archive.append(
        MessageRecord(1, 10, 20, 30, "Synthetic", "router Waffle", now)
    )
    assert archive.append(
        MessageRecord(2, 10, 20, 31, "Synthetic", "erasable example", now)
    )
    key = os.urandom(32)
    (directory / "test-only.key").write_bytes(key)
    create_backup(archive.path, directory / "snapshot.pai", key)
    assert archive.forget_author(10, 31, now) == 1
    export_erasures(archive.path, directory / "erasures.pai", key)
    print("Synthetic archive, encrypted snapshot and erasure checkpoint created")


def verify(directory: Path) -> None:
    cutoff = datetime.now(UTC) - timedelta(days=1)
    active = Archive(directory / "active.sqlite")
    assert active.get(1).text == "router Waffle"
    assert active.get(2) is None and active.is_opted_out(10, 31)
    restored_path = directory / "recovered.sqlite"
    restore_backup(
        directory / "snapshot.pai",
        directory / "erasures.pai",
        restored_path,
        (directory / "test-only.key").read_bytes(),
        _POLICY,
    )
    restored = Archive(restored_path)
    matches = restored.search(
        "Waffle", guild_id=10, channel_id=20, authors=frozenset({30}), cutoff=cutoff
    )
    assert [record.message_id for record in matches] == [1]
    assert restored.get(2) is None and restored.is_opted_out(10, 31)
    print("Restart persistence, searchable restore and replayed opt-out verified")


async def gateway() -> None:
    # The public handshake ends before Identify. It uses no bot account or guild.
    timeout = aiohttp.ClientTimeout(total=12)
    async with aiohttp.ClientSession(timeout=timeout, trust_env=False) as session:
        async with session.get(
            "https://discord.com/api/v10/gateway", allow_redirects=False
        ) as response:
            response.raise_for_status()
            endpoint = (await response.json())["url"]
        assert endpoint == "wss://gateway.discord.gg"
        async with (
            asyncio.timeout(12),
            session.ws_connect(endpoint + "/?v=10&encoding=json") as socket,
        ):
            packet = await socket.receive_json()
            assert packet["op"] == 10 and packet["d"]["heartbeat_interval"] > 0
    print("Public Discord Gateway v10 WebSocket HELLO received without Identify")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("phase", choices=("seed", "verify", "gateway"))
    parser.add_argument("directory", type=Path, nargs="?")
    options = parser.parse_args()
    os.umask(0o077)
    if options.phase == "gateway":
        asyncio.run(gateway())
    else:
        if options.directory is None:
            parser.error(
                "The seed and verify phases require a private writable directory"
            )
        (seed if options.phase == "seed" else verify)(options.directory)


if __name__ == "__main__":
    main()
