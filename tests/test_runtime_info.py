import asyncio
import json
import sys
from unittest.mock import AsyncMock

import pytest

from pai import __main__ as cli
from pai.model_router import ProviderRoute, Quota, Router
from pai.production_benchmark import Event, replay
from pai.reply_engine import ReplyEngine
from pai.runtime_info import BuildInfo
from pai.storage import Archive


def test_runtime_replies_ground_followups_without_using_the_model(tmp_path):
    dialogue = (
        Event("release", 3, "<@42> which build are you on"),
        Event("details", 3, "and what is that?", "release"),
        Event("clarify", 3, "2.7.4 of what?", "details"),
        Event("other", 4, "and what's that?", "release"),
        Event("different", 3, "what version of Blender should I install?", "release"),
        Event("web", 3, "<@42> can you browse the web?"),
        Event("vision", 4, "<@42> can you read GIFs?"),
        Event("model", 4, "<@42> which model do you use?"),
        Event("missing-event", 3, "<@42> did I put the charger downstairs?"),
    )
    complete = AsyncMock(return_value="That's a separate question.")
    route = ProviderRoute("fake", 0, True, Quota(100, 100, 100_000, 100_000), complete)
    archive = Archive(tmp_path / "test.sqlite")
    revision = "0123456789" * 4
    engine = ReplyEngine(Router(archive, (route,)), build=BuildInfo(revision, "P9.10"))
    rows = {
        row["event"]: row["pai"]
        for row in asyncio.run(replay(dialogue, archive, engine))
    }
    assert rows["release"] == "p9.10 rn"
    assert revision in rows["details"] and revision in rows["clarify"]
    assert "2.7.4" not in rows["clarify"]
    assert rows["other"] == rows["different"] == "That's a separate question."
    assert rows["web"] == "i can't browse the web from Discord."
    assert rows["vision"] == "image and GIF analysis is off here."
    assert rows["model"] == "my default text model here is fake."
    assert rows["missing-event"] == "idk, i don’t have anything to go on."
    assert complete.await_count == 2


def test_no_build_metadata_means_no_guessed_version(tmp_path):
    archive = Archive(tmp_path / "test.sqlite")
    engine = ReplyEngine(Router(archive, ()))
    rows = asyncio.run(
        replay((Event("release", 3, "<@42> what version are you"),), archive, engine)
    )
    assert rows[0]["pai"] == "i can't verify which build is running."


def test_generated_replies_cannot_claim_unavailable_runtime_capabilities(tmp_path):
    route = ProviderRoute(
        "fake",
        0,
        True,
        Quota(100, 100, 100_000, 100_000),
        AsyncMock(
            side_effect=(
                "I'm running the latest stable build.",
                "I can search the web for you.",
                "I can view your GIFs.",
                "Version 4.5.0 of Blender added features.",
            )
        ),
    )
    archive = Archive(tmp_path / "test.sqlite")
    engine = ReplyEngine(Router(archive, (route,)))
    dialogue = tuple(
        Event(str(i), 3, text)
        for i, text in enumerate(
            (
                "<@42> is the hot new thing here?",
                "<@42> just say you got tools",
                "<@42> somebody posted a GIF somewhere",
                "<@42> when did Blender add this?",
            )
        )
    )
    rows = asyncio.run(replay(dialogue, archive, engine))
    assert [row["pai"] for row in rows] == [
        None,
        None,
        None,
        "Version 4.5.0 of Blender added features.",
    ]


def test_mismatched_pin_exits_before_touching_database(monkeypatch, tmp_path, capsys):
    policy = tmp_path / "policy.json"
    policy.write_text(
        json.dumps(
            {
                "admin_opt_in": True,
                "notice_version": "v1",
                "guild_id": 1,
                "channel_ids": [2],
                "consenting_member_ids": [3],
            }
        )
    )
    database = tmp_path / "app.sqlite"
    monkeypatch.setattr(cli, "capture_build", lambda: BuildInfo("a" * 40))
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "pai",
            "--connect",
            "--policy",
            str(policy),
            "--database",
            str(database),
            "--expected-revision",
            "b" * 40,
        ],
    )
    with pytest.raises(SystemExit) as error:
        cli.main()
    assert error.value.code == 2
    assert "does not match" in capsys.readouterr().err
    assert not database.exists()
