from datetime import UTC, datetime

import pytest

from pai.backup import BackupError, create_backup, export_erasures, restore_backup
from pai.policy import PrivacyPolicy
from pai.storage import Archive, MessageRecord


def test_encrypted_restore_applies_newer_deletions_and_opt_outs(tmp_path):
    source = tmp_path / "source.sqlite"
    backup = tmp_path / "backup.pai"
    erasures = tmp_path / "erasures.pai"
    restored = tmp_path / "restored.sqlite"
    key = bytes(range(32))
    now = datetime.now(UTC)
    archive = Archive(source)
    for index, author in [(1, 4), (2, 5), (3, 6)]:
        archive.append(
            MessageRecord(
                index, 2, 3, author, "Synthetic", f"Secret example {index}", now
            )
        )
    create_backup(source, backup, key)
    assert b"Secret example" not in backup.read_bytes()
    archive.delete(2, 3, [1], now)
    archive.forget_author(2, 5, now)
    export_erasures(source, erasures, key)
    policy = PrivacyPolicy(True, "v1", 2, frozenset({3}), frozenset({4, 5, 6}))

    with pytest.raises(BackupError):
        restore_backup(backup, erasures, restored, b"Z" * 32, policy)
    assert not restored.exists()
    restore_backup(backup, erasures, restored, key, policy)
    new = Archive(restored)
    assert new.get(1) is None
    assert new.get(2) is None
    assert new.get(3).text == "Secret example 3"
    assert new.is_opted_out(2, 5)
    assert not new.append(MessageRecord(4, 2, 3, 5, "Jo", "new", now))


def test_backup_tampering_and_overwrite_are_rejected(tmp_path):
    source = tmp_path / "source.sqlite"
    key = b"K" * 32
    Archive(source)
    backup = tmp_path / "sealed.pai"
    erasures = tmp_path / "erasures.pai"
    target = tmp_path / "restored.sqlite"
    policy = PrivacyPolicy()
    create_backup(source, backup, key)
    export_erasures(source, erasures, key)
    with pytest.raises(BackupError):
        create_backup(source, backup, key)
    data = bytearray(backup.read_bytes())
    data[-20] ^= 1
    backup.write_bytes(data)
    with pytest.raises(BackupError):
        restore_backup(backup, erasures, target, key, policy)
    assert not target.exists()
