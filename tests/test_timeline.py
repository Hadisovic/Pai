import asyncio
import json

from pai.model_router import ProviderRoute, Quota, Router
from pai.production_benchmark import Event, replay
from pai.reply_engine import ReplyEngine
from pai.storage import Archive


def test_timeline_keeps_intervening_speaker_and_native_target(tmp_path):
    scenario = (
        Event("first", 3, "<@42> how do we know if tonight is still on"),
        Event("correction", 4, "if i say the kettle sank, they moved it to saturday"),
        Event("callback", 4, "the kettle sank"),
        Event("private", 5, "i was never part of these plans"),
        Event("target", 3, "do i head out now?", "first"),
    )
    prompts = []

    async def complete(request):
        prompts.append(request)
        return "wait for saturday"

    route = ProviderRoute("fake", 0, True, Quota(100, 100, 100_000, 100_000), complete)
    archive = Archive(tmp_path / "timeline.sqlite")
    engine = ReplyEngine(Router(archive, (route,)), conversation_engine="timeline")
    rows = asyncio.run(
        replay(scenario, archive, engine, conversation_engine="timeline")
    )
    first, follow = prompts
    assert "kettle sank" not in first.payload
    assert "they moved it to saturday" in follow.payload
    assert follow.payload.index("wait for saturday") < follow.payload.index(
        "they moved it"
    )
    assert "reply to T" in follow.payload
    assert "Addressee: Pai (native reply)" in follow.payload
    assert "never part" not in follow.payload
    assert rows[-1]["pai"] == "wait for saturday"


def test_baseline_stays_legacy_and_owner_override_is_scoped(tmp_path):
    scenario = (
        Event("owner", 3, "<@42> shu ra2yak?"),
        Event("other", 4, "<@42> shu ra2yak?"),
        Event("explicit", 3, "<@42> shu ra2yak? reply in Arabizi"),
    )
    prompts = []

    async def complete(request):
        prompts.append(request.payload)
        return "yep"

    route = ProviderRoute("fake", 0, True, Quota(100, 100, 100_000, 100_000), complete)
    archive = Archive(tmp_path / "scope.sqlite")
    engine = ReplyEngine(Router(archive, (route,)), conversation_engine="timeline")
    asyncio.run(replay(scenario, archive, engine, conversation_engine="timeline"))
    assert "If replying in Arabic, use Arabic script" in prompts[0]
    assert "If replying in Arabic" not in prompts[1]
    assert "Language: arabizi" in prompts[2]
    assert "If replying in Arabic" not in prompts[2]

    archive = Archive(tmp_path / "legacy.sqlite")
    asyncio.run(replay(scenario, archive, ReplyEngine(Router(archive, (route,)))))
    assert json.loads(prompts[-1])["request"]["text"].endswith("reply in Arabizi")


def test_role_variant_keeps_message_roles_and_citations_bound(tmp_path):
    from pai.providers import Groq

    scenario = (
        Event("favorite", 3, "My favorite game is Balatro."),
        Event("other", 4, "My favorite game is Scythe."),
        Event("begin", 3, "<@42> anyone home?"),
        Event("variant", 4, "wait where did my backpack go"),
        Event("follow", 3, "no more jokes or emojis please", "begin"),
        Event("recall", 3, "<@42> whats my favorite game"),
    )
    prompts = []

    async def complete(request):
        prompts.append(request)
        if "Current speaker" in request.payload and "recall:" in request.payload:
            return "Balatro [s1]"
        return "sure 🔥"

    route = ProviderRoute("fake", 0, True, Quota(100, 100, 100_000, 100_000), complete)
    archive = Archive(tmp_path / "roles.sqlite")
    engine = ReplyEngine(
        Router(archive, (route,)), conversation_engine="timeline-roles"
    )
    rows = asyncio.run(
        replay(scenario, archive, engine, conversation_engine="timeline-roles")
    )
    _, follow, recall = prompts
    assert tuple(role for role, _ in follow.prior_messages) == ("user", "assistant")
    assert follow.prior_messages[-1] == ("assistant", "sure 🔥")
    assert "backpack" in follow.payload
    assert "Emoji: off" in follow.payload and rows[-2]["pai"] == "sure"
    assert "Evidence [s1] from member_1:" in recall.payload
    assert "Scythe" not in recall.payload and "[source](" in rows[-1]["pai"]
    assert follow.reserved_tokens > len(follow.payload)
    single_provider = Groq(None, "test-key", free_plan_confirmed=True)
    first, second = single_provider.routes("qwen")
    assert first.max_frames == 3 and "qwen" in first.name and second.max_frames == 0
    assert tuple(r.name for r in single_provider.routes()) == (second.name, first.name)


def test_timeline_recall_cannot_quote_an_unrelated_favorite(tmp_path):
    archive = Archive(tmp_path / "strict.sqlite")
    scenario = (
        Event("own", 3, "My favorite sport is fencing."),
        Event("other", 4, "My favorite podcast is The Indicator."),
        Event("ask", 3, "<@42> whats my favorite podcast then?"),
    )
    prompts = []

    async def complete(request):
        prompts.append(request)
        return "you never told me"

    route = ProviderRoute("fake", 0, True, Quota(100, 100, 100_000, 100_000), complete)
    engine = ReplyEngine(Router(archive, (route,)), conversation_engine="timeline")
    rows = asyncio.run(
        replay(scenario, archive, engine, conversation_engine="timeline")
    )
    assert rows[-1]["pai"] == "i can’t pin that down from what i have."
    assert not prompts
