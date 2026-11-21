import sqlite3
from contextlib import closing

from pai.mock_gateway import FakeAIProvider, FakeDiscordGateway, Message, run_smoke


def test_mock_gateway_archives_silently_until_direct_mention(tmp_path):
    ordinary = Message("m1", "g1", "study", "Sam", "The lab router is called Waffle.")
    mention = Message(
        "m2", "g1", "study", "Jo", "What is it called?", ("pai",), reply_to_id="m1"
    )
    unrelated = Message("m3", "g1", "private", "Jo", "Private", ("pai",))
    dm = Message("m4", None, "study", "Jo", "Direct message", ("pai",))
    other_bot = Message("m5", "g1", "study", "Other bot", "Ping", ("pai",), bot=True)
    wrong_mention = Message("m6", "g1", "study", "Jo", "Hey <@pai>", ("someone-else",))
    gateway = FakeDiscordGateway(
        (ordinary, unrelated, dm, other_bot, wrong_mention, mention, mention)
    )
    provider = FakeAIProvider(response="Waffle.")
    archive_path = tmp_path / "smoke.sqlite"

    with closing(sqlite3.connect(archive_path)) as archive:
        run_smoke(gateway, provider, archive, authorized_channel=("g1", "study"))

    with closing(sqlite3.connect(archive_path)) as reopened:
        ids = reopened.execute(
            "SELECT message_id FROM messages ORDER BY rowid"
        ).fetchall()
    assert ids == [("m1",), ("m6",), ("m2",)]
    assert provider.requests == [(mention, "The lab router is called Waffle.")]
    assert gateway.replies == [("m2", "Waffle.")]


def test_mock_gateway_fails_closed_by_default():
    mention = Message("m1", "g1", "study", "Jo", "Hello", ("pai",))
    gateway = FakeDiscordGateway((mention,))
    provider = FakeAIProvider(response="Hi.")

    with closing(sqlite3.connect(":memory:")) as archive:
        run_smoke(gateway, provider, archive)
        rows = archive.execute("SELECT message_id FROM messages").fetchall()

    assert rows == []
    assert provider.requests == []
    assert gateway.replies == []
