from datetime import UTC, datetime, timedelta, timezone

from pai.storage import Archive, MessageRecord


def test_archive_persists_new_events_deduplicates_and_keeps_provenance(tmp_path):
    path = tmp_path / "pai.sqlite"
    archive = Archive(path)
    timestamp = datetime(2026, 4, 6, 3, 15, tzinfo=timezone(timedelta(hours=3)))
    parent = MessageRecord(1, 3, 4, 5, "Sam", "Bread", timestamp)
    child = MessageRecord(2**64 - 1, 3, 4, 6, "Jo", "Toast", timestamp, reply_to_id=1)
    assert archive.append(parent)
    assert archive.append(child)
    assert not archive.append(child)
    reopened = Archive(path)
    assert reopened.get(2**64 - 1) == child
    assert reopened.get(1).created_at.tzinfo == UTC
    assert reopened.get(2**64 - 2) is None


def test_scoped_edits_and_deletes_survive_restart(tmp_path):
    path = tmp_path / "pai.sqlite"
    archive = Archive(path)
    timestamp = datetime(2026, 11, 21, tzinfo=UTC)
    original = MessageRecord(1, 3, 4, 5, "Sam", "Before", timestamp)
    assert archive.append(original)
    edited = timestamp + timedelta(minutes=2)
    assert not archive.edit(1, 3, 7, frozenset({5}), "Foreign scope", edited)
    assert not archive.edit(1, 3, 4, frozenset({6}), "Revoked author", edited)
    assert archive.edit(1, 3, 4, frozenset({5}), "After", edited)
    assert not archive.edit(1, 3, 4, frozenset({5}), "Stale", timestamp)
    assert archive.get(1).text == "After"
    assert archive.delete(3, 7, [1], edited) == 0
    assert archive.delete(3, 4, [1, 2], edited) == 1
    reopened = Archive(path)
    assert reopened.get(1) is None
    assert not reopened.append(original)
    assert not reopened.append(MessageRecord(2, 3, 4, 5, "Sam", "Delayed", timestamp))


def test_maintenance_enforces_retention_and_row_budget(tmp_path):
    archive = Archive(tmp_path / "pai.sqlite", max_messages=2)
    now = datetime(2026, 11, 21, tzinfo=UTC)
    for index, days in enumerate((50, 2, 1, 0), start=1):
        archive.append(
            MessageRecord(index, 3, 4, 5, "Sam", "Example", now - timedelta(days=days))
        )
    archive.prune(now - timedelta(days=30))
    assert archive.get(1) is None
    assert archive.get(2) is None
    assert archive.get(3) is not None
    assert archive.get(4) is not None


def test_version_one_archive_migrates_without_losing_messages(tmp_path):
    import sqlite3
    from contextlib import closing

    path = tmp_path / "pai.sqlite"
    with closing(sqlite3.connect(path)) as old, old:
        old.executescript("""
            CREATE TABLE messages (
                message_id TEXT PRIMARY KEY NOT NULL, guild_id TEXT NOT NULL,
                channel_id TEXT NOT NULL, author_id TEXT NOT NULL,
                author_display TEXT NOT NULL, text TEXT NOT NULL,
                created_at TEXT NOT NULL, reply_to_id TEXT
            );
            INSERT INTO messages VALUES
                ('1', '3', '4', '5', 'Sam', 'Before', '2026-11-21T00:00:00.000000+00:00', NULL);
            PRAGMA user_version = 1;
            """)
    migrated = Archive(path)
    assert [
        row.message_id
        for row in migrated.search(
            "Before",
            guild_id=3,
            channel_id=4,
            authors=frozenset({5}),
            cutoff=datetime(2026, 11, 1, tzinfo=UTC),
        )
    ] == [1]
    assert migrated.edit(
        1, 3, 4, frozenset({5}), "After", datetime(2026, 11, 22, tzinfo=UTC)
    )
    assert migrated.get(1).text == "After"
