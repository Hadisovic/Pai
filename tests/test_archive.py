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
