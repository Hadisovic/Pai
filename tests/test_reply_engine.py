import asyncio
import json
from datetime import UTC, datetime
from unittest.mock import AsyncMock

from pai.conversation import ConversationContext
from pai.model_router import ProviderRoute, Quota, Router
from pai.reply_engine import ReplyEngine
from pai.storage import Archive, MessageRecord


def context():
    now = datetime.now(UTC)
    ask = MessageRecord(2, 10, 20, 30, "Sam", "ذكّرني باسم الراوتر", now)
    older = MessageRecord(1, 10, 20, 30, "Sam", "The lab router is Waffle.", now)
    return ConversationContext(ask, memory=(older,))


def test_reply_engine_uses_bounded_english_first_prompt_and_renders_source(tmp_path):
    generate = AsyncMock(return_value="You called it Waffle. [s1]")
    route = ProviderRoute("test", 0, True, Quota(10, 10, 8000, 30_000), generate)
    engine = ReplyEngine(Router(Archive(tmp_path / "pai.sqlite"), (route,)))
    reply = asyncio.run(engine(context()))
    assert (
        reply
        == "You called it Waffle. [source](<https://discord.com/channels/10/20/1>)"
    )
    request = generate.call_args.args[0]
    assert "English" in request.instructions and "Arabizi" in request.instructions
    assert "الراوتر" in json.loads(request.payload)["request"]["text"]


def test_reply_engine_reports_an_outage_only_once(tmp_path):
    engine = ReplyEngine(Router(Archive(tmp_path / "pai.sqlite"), ()))
    assert "free model capacity" in asyncio.run(engine(context()))
    assert asyncio.run(engine(context())) == ""


def test_unusable_completion_falls_back_without_leaking_a_field_or_payload(
    tmp_path, caplog
):
    primary = AsyncMock(return_value="[pai_said] private-placeholder")
    fallback = AsyncMock(return_value="We need a better plan. [s1]")
    quota = Quota(10, 10, 8000, 30_000)
    engine = ReplyEngine(
        Router(
            Archive(tmp_path / "pai.sqlite"),
            (
                ProviderRoute("primary", 0, True, quota, primary),
                ProviderRoute("fallback", 0, True, quota, fallback),
            ),
        )
    )

    async def dialogue():
        assert (await engine(context())).startswith("We need a better plan.")
        primary.return_value = "Waffle. [s1]"
        assert (await engine(context())).startswith("Waffle.")

    with caplog.at_level("INFO", logger="pai"):
        asyncio.run(dialogue())
    assert "route=primary outcome=rejected" in caplog.text
    assert "route=fallback outcome=accepted" in caplog.text
    assert "private-placeholder" not in caplog.text
    assert "We need a better plan." not in caplog.text
    assert "الراوتر" not in caplog.text
    assert primary.await_count == 2
    assert fallback.await_count == 1


def test_rejected_only_route_does_not_emit_a_canned_reply(tmp_path):
    complete = AsyncMock(return_value="I'm just a bot.")
    route = ProviderRoute("primary", 0, True, Quota(10, 10, 8_000, 30_000), complete)
    engine = ReplyEngine(Router(Archive(tmp_path / "pai.sqlite"), (route,)))
    assert asyncio.run(engine(context())) == ""
