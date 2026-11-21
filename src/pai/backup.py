"""Encrypted SQLite backup and privacy-aware recovery. No network access."""

import argparse
import base64
import json
import os
import sqlite3
from contextlib import closing
from datetime import UTC, datetime, timedelta
from pathlib import Path
from tempfile import NamedTemporaryFile, TemporaryDirectory
from time import time_ns

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

from pai.policy import PrivacyPolicy, load_policy
from pai.storage import Archive

_MAGIC = b"PAI1"
_HEADER_BYTES = 25
_TAG_BYTES = 16
_CHUNK = 64 * 1024
_DATABASE_LIMIT = 1024**3
_LEDGER_LIMIT = 8 * 1024**2


class BackupError(Exception):
    """A backup could not be created or safely restored."""


def _seal(source: Path, destination: Path, key: bytes, kind: bytes, limit: int) -> None:
    if len(key) != 32 or source.stat().st_size > limit:
        raise BackupError("Invalid key or backup size")
    nonce = os.urandom(12)
    header = _MAGIC + kind + time_ns().to_bytes(8, "big") + nonce
    encryptor = Cipher(algorithms.AES(key), modes.GCM(nonce)).encryptor()
    encryptor.authenticate_additional_data(header)
    with NamedTemporaryFile(dir=destination.parent, delete=False) as partial:
        path = Path(partial.name)
        try:
            with source.open("rb") as payload:
                partial.write(header)
                while chunk := payload.read(_CHUNK):
                    partial.write(encryptor.update(chunk))
                partial.write(encryptor.finalize())
                partial.write(encryptor.tag)
                partial.flush()
                os.fsync(partial.fileno())
            partial.close()
            _publish(path, destination)
        finally:
            partial.close()
            path.unlink(missing_ok=True)


def _publish(private: Path, destination: Path) -> None:
    try:
        os.link(private, destination)
    except FileExistsError:
        raise BackupError("Destination already exists") from None


def _unseal(
    source: Path, destination: Path, key: bytes, kind: bytes, limit: int
) -> int:
    if len(key) != 32:
        raise BackupError("Invalid backup key")
    with source.open("rb") as sealed:
        length = os.fstat(sealed.fileno()).st_size - _HEADER_BYTES - _TAG_BYTES
        header = sealed.read(_HEADER_BYTES)
        if not 0 < length <= limit or not header.startswith(_MAGIC + kind):
            raise BackupError("Invalid backup format or size")
        sealed.seek(-_TAG_BYTES, os.SEEK_END)
        tag = sealed.read(_TAG_BYTES)
        sealed.seek(_HEADER_BYTES)
        decryptor = Cipher(
            algorithms.AES(key), modes.GCM(header[-12:], tag)
        ).decryptor()
        decryptor.authenticate_additional_data(header)
        with destination.open("xb") as output:
            remaining = length
            while remaining:
                chunk = sealed.read(min(_CHUNK, remaining))
                if not chunk:
                    raise BackupError("Backup was truncated")
                output.write(decryptor.update(chunk))
                remaining -= len(chunk)
            try:
                output.write(decryptor.finalize())
            except InvalidTag:
                raise BackupError("Backup authentication failed") from None
    return int.from_bytes(header[5:13], "big")


def _readonly(path: Path) -> sqlite3.Connection:
    return sqlite3.connect(path.resolve().as_uri() + "?mode=ro", uri=True)


def create_backup(source: Path, destination: Path, key: bytes) -> None:
    with TemporaryDirectory(prefix="pai-snapshot-") as directory:
        snapshot = Path(directory) / "snapshot.sqlite"
        with (
            closing(_readonly(source)) as original,
            closing(sqlite3.connect(snapshot)) as copy,
        ):
            original.backup(copy, pages=128)
            if copy.execute("PRAGMA quick_check").fetchone()[0] != "ok":
                raise BackupError("Archive integrity check failed")
        _seal(snapshot, destination, key, b"D", _DATABASE_LIMIT)


def export_erasures(source: Path, destination: Path, key: bytes) -> None:
    with TemporaryDirectory(prefix="pai-erasures-") as directory:
        payload = Path(directory) / "erasures.json"
        with closing(_readonly(source)) as original:
            original.execute("BEGIN")
            members = original.execute(
                "SELECT guild_id, author_id, recorded_at FROM member_opt_outs"
            ).fetchall()
            deletes = original.execute(
                "SELECT message_id, guild_id, channel_id, deleted_at FROM deleted_messages"
            ).fetchall()
        payload.write_text(
            json.dumps({"members": members, "messages": deletes}), encoding="utf-8"
        )
        _seal(payload, destination, key, b"E", _LEDGER_LIMIT)


def restore_backup(
    backup: Path, erasures: Path, destination: Path, key: bytes, policy: PrivacyPolicy
) -> None:
    if destination.exists():
        raise BackupError("Restore destination must be new")
    with TemporaryDirectory(prefix="pai-restore-", dir=destination.parent) as directory:
        snapshot = Path(directory) / "restored.sqlite"
        ledger = Path(directory) / "erasures.json"
        captured = _unseal(backup, snapshot, key, b"D", _DATABASE_LIMIT)
        ledger_time = _unseal(erasures, ledger, key, b"E", _LEDGER_LIMIT)
        if ledger_time < captured:
            raise BackupError("The erasure checkpoint predates the backup")
        records = json.loads(ledger.read_text(encoding="utf-8"))
        archive = Archive(snapshot)
        with closing(archive.connect()) as db, db:
            if db.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
                raise BackupError("Restored archive integrity check failed")
            db.executemany(
                """
                INSERT OR IGNORE INTO member_opt_outs (guild_id, author_id, recorded_at)
                VALUES (?, ?, ?)
                """,
                records["members"],
            )
            db.executemany(
                """
                INSERT OR IGNORE INTO deleted_messages (message_id, guild_id, channel_id, deleted_at)
                VALUES (?, ?, ?, ?)
                """,
                records["messages"],
            )
            db.execute("""
                DELETE FROM messages
                WHERE EXISTS (
                    SELECT 1 FROM member_opt_outs AS revoked
                    WHERE revoked.guild_id = messages.guild_id AND revoked.author_id = messages.author_id
                ) OR EXISTS (
                    SELECT 1 FROM deleted_messages AS revoked
                    WHERE revoked.guild_id = messages.guild_id AND revoked.channel_id = messages.channel_id
                      AND revoked.message_id = messages.message_id
                )
            """)
        archive.apply_policy(policy)
        archive.prune(datetime.now(UTC) - timedelta(days=policy.retention_days))
        with closing(archive.connect()) as db:
            db.execute("PRAGMA wal_checkpoint(TRUNCATE)")
            db.execute("PRAGMA journal_mode = DELETE")
        _publish(snapshot, destination)


def main() -> None:
    parser = argparse.ArgumentParser(description="Local encrypted Pai archive tooling")
    commands = parser.add_subparsers(dest="action", required=True)
    for name in ("backup", "erasures", "restore"):
        sub = commands.add_parser(name)
        sub.add_argument("source", type=Path)
        sub.add_argument("destination", type=Path)
        if name == "restore":
            sub.add_argument("--erasures", required=True, type=Path)
            sub.add_argument("--policy", required=True, type=Path)
    args = parser.parse_args()
    try:
        key = base64.b64decode(
            os.environ.get("PAI_BACKUP_KEY", ""), altchars=b"-_", validate=True
        )
        if len(key) != 32:
            raise BackupError("The key must encode 32 random bytes")
        os.umask(0o077)
        if args.action == "backup":
            create_backup(args.source, args.destination, key)
        elif args.action == "erasures":
            export_erasures(args.source, args.destination, key)
        else:
            if not args.policy.is_file():
                raise BackupError("An existing private policy file is required")
            restore_backup(
                args.source,
                args.erasures,
                args.destination,
                key,
                load_policy(args.policy),
            )
    except (BackupError, OSError, sqlite3.Error, ValueError, KeyError):
        parser.exit(
            2, "Backup action failed. Check keys, files, SQLite and erasure state.\n"
        )
    print("Backup action completed.")


if __name__ == "__main__":
    main()
