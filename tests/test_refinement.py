import asyncio
from datetime import UTC, datetime

from pai.conversation import ConversationContext
from pai.identity import Identity
from pai.model_router import ProviderRoute, Quota, Router
from pai.policy import PrivacyPolicy
from pai.production_benchmark import Event, replay
from pai.reply_engine import ReplyEngine
from pai.runtime_info import BuildInfo
from pai.storage import Archive, MessageRecord


def test_indirect_identity_facts_respect_scope_and_runtime():
    policy = PrivacyPolicy(True, "synthetic", 1, frozenset({2}), frozenset({3}))
    identity = Identity(
        policy, ("fixture-primary", "fixture-fallback"), BuildInfo("a" * 40, "P9.14.1")
    )

    def fact(text, actor=3, history=True):
        request = MessageRecord(12, 1, 2, actor, "Synthetic", text, datetime.now(UTC))
        return identity.prompt_facts(ConversationContext(request), history)

    inferred = fact("Honestly, was Qwen the human behind this bot or just its model?")
    assert all(
        value in inferred
        for value in ("Hadisovic", "Pai", "fixture-primary", "P9.14.1")
    )
    assert "fixture-fallback" in inferred
    assert fact("يعني انت مجرد موديل ولا في حدا صنعك؟")
    assert not fact("Honestly who is behind this bot?", actor=4)
    assert "false" in fact("Honestly who is behind this bot?", history=False)
    for text in (
        "would u rather be a lonely jukebox",
        "when's ur birthday",
        "yo pai",
        "tell me a story",
        "did the Qwen model get updated",
    ):
        assert fact(text) == ""


def test_identity_hint_leaves_system_roles_and_off_topic_input_exact(tmp_path):
    archives = [Archive(tmp_path / f"{i}.sqlite") for i in range(2)]
    prompts = []

    async def complete(req):
        prompts.append(req)
        return "yep"

    route = ProviderRoute("fixture", 0, True, Quota(30, 40, 100_000, 200_000), complete)
    for enabled, archive in zip((False, True), archives, strict=True):
        respond = ReplyEngine(
            Router(archive, (route,)), conversation_engine="timeline-roles"
        )
        asyncio.run(
            replay(
                (
                    Event("fiction", 3, "<@42> invent a story about a grumpy breadbox"),
                    Event(
                        "identity",
                        4,
                        "<@42> who is the person behind this bot, is that Qwen?",
                    ),
                ),
                archive,
                respond,
                conversation_engine="timeline-roles",
                identity_context=enabled,
            )
        )
    control, decorated = prompts[1], prompts[3]
    assert prompts[0] == prompts[2]
    assert decorated.instructions == control.instructions
    assert decorated.prior_messages == control.prior_messages
    assert decorated.max_output_tokens == control.max_output_tokens
    assert decorated.payload.endswith(control.payload)
    assert "Verified Pai runtime facts" in decorated.payload


def test_historical_assistant_recall_survives_restart_with_speaker_scope(tmp_path):
    archive = Archive(tmp_path / "history.sqlite")
    prompts = []

    async def complete(req):
        prompts.append(req)
        return ("feather map", "gold scissors", "noted", "noted", "noted")[
            len(prompts) - 1
        ]

    route = ProviderRoute("fixture", 0, True, Quota(30, 40, 100_000, 200_000), complete)
    respond = ReplyEngine(
        Router(archive, (route,)), conversation_engine="timeline-roles"
    )
    asyncio.run(
        replay(
            (
                Event("paper", 3, "<@42> pick a name for the Nebula book"),
                Event("other", 4, "<@42> title the Quartz book for me"),
                Event("restart", 3, "<@42> شو سميت كتاب nebula؟"),
                Event(
                    "wrong-speaker", 4, "<@42> what did you call the Nebula book again?"
                ),
                Event("unrelated", 3, "<@42> do you like dancing?"),
            ),
            archive,
            respond,
            conversation_engine="timeline-roles",
            assistant_continuity=True,
            restart_before="restart",
        )
    )
    assert ("assistant", "feather map") in prompts[2].prior_messages
    assert ("assistant", "gold scissors") not in prompts[2].prior_messages
    assert not prompts[3].prior_messages
    assert not prompts[4].prior_messages
