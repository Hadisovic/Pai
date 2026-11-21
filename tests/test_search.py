from datetime import UTC, datetime, timedelta

from pai.storage import Archive, MessageRecord


def test_search_tracks_edits_deletes_scope_and_unsafe_query_text(tmp_path):
    archive = Archive(tmp_path / "pai.sqlite")
    now = datetime(2026, 11, 21, tzinfo=UTC)
    for identifier, channel, author, text, age in (
        (1, 2, 8, "The router is Waffle.", 1),
        (2, 3, 8, "Waffle private channel", 0),
        (3, 2, 9, "Waffle nonconsenting author", 0),
        (4, 2, 8, "Waffle older than cutoff", 60),
        (5, 2, 8, "Unique toasted switch", 0),
    ):
        assert archive.append(
            MessageRecord(
                identifier,
                1,
                channel,
                author,
                "Synthetic",
                text,
                now - timedelta(days=age),
            )
        )

    def find(query):
        return [
            row.message_id
            for row in archive.search(
                query,
                guild_id=1,
                channel_id=2,
                authors=frozenset({8}),
                cutoff=now - timedelta(days=30),
            )
        ]

    assert find('Waffle" NEAR(*;') == [1]
    assert find('()""') == []
    assert archive.edit(1, 1, 2, frozenset({8}), "The router is Pancake.", now)
    assert find("Waffle") == []
    assert find("Pancake") == [1]
    assert archive.delete(1, 2, [1], now) == 1
    assert find("Pancake") == []
    assert find("toasted") == [5]
