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
