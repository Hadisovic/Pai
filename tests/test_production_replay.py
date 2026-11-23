import asyncio
import json

from pai.model_router import ProviderRoute, Quota, Router
from pai.production_benchmark import DIALOGUE, Event, replay
from pai.reply_engine import ReplyEngine
from pai.storage import Archive


def test_held_out_gateway_replay(tmp_path):
    prompts = {}
    pending = None

    async def complete(request):
        payload = json.loads(request.payload)
        prompts[pending] = payload
        # Exercise the real citation renderer. This stand-in checks no model quality.
        evidence = payload.get("history", [])
        return (
            f"Recorded statement [{evidence[0]['source']}]"
            if evidence
            else "Acknowledged."
        )

    engine = ReplyEngine(
        Router(
            Archive(tmp_path / "quota.sqlite"),
            (
                ProviderRoute(
                    "fixture", 0, True, Quota(100, 100, 100_000, 100_000), complete
                ),
            ),
        )
    )
    labels = {event.text: event.label for event in DIALOGUE}

    async def respond(context):
        nonlocal pending
        pending = labels[context.request.text]
        return await engine(context)

    turns = asyncio.run(
        replay(DIALOGUE, Archive(tmp_path / "messages.sqlite"), respond)
    )
    by_event = {row["event"]: row for row in turns}
    for label in (
        "ordinary",
        "interjection",
        "first-fact",
        "second-fact",
        "distractor",
        "unconsented",
    ):
        assert by_event[label]["pai"] is None
    assert not by_event["unconsented"]["archived"]
    assert by_event["ordinary"]["archived"]

    assert [row["text"] for row in prompts["banter"]["recent"]] == [
        "the label maker printed an entire blank roll again"
    ]
    assert "recent" not in prompts["literal-pause"]

    repair = prompts["repair"]
    assert "invisible ink" in repair["conversation_thread"][0]["asked"]["text"]
    assert "quoted_exchange" not in repair
    assert "stream" not in json.dumps(repair)
    assert len(prompts["tone-shift"]["conversation_thread"]) == 2
    assert not prompts["literal-pause"].get("conversation_thread")
    assert not prompts["one-word"].get("history")

    for label, own, other in (
        ("arabizi-recall", "Hades", "Slay the Spire"),
        ("switch-speaker", "Slay the Spire", "Hades"),
        ("repeat", "Slay the Spire", "Hades"),
    ):
        prompt = prompts[label]
        assert prompt["recall_scope"] == "request speaker only"
        assert len(prompt["history"]) == 1
        assert own in prompt["history"][0]["text"]
        assert prompt["history"][0]["speaker_id"] == prompt["request"]["speaker_id"]
        assert other not in json.dumps(prompt)
        assert "[source](" in by_event[label]["pai"]
    assert prompts["switch-speaker"]["recall_topic"] == ["game"]
    assert "Answer in English" not in json.dumps(prompts["switch-speaker"])
    assert by_event["one-word"]["pai"] == "Acknowledged."


def test_long_replies_keep_last_verified_request_at_provenance_limit(tmp_path):
    archive = Archive(tmp_path / "messages.sqlite")
    dialogue = tuple(
        Event(str(index), 3, f"Next part {index}", str(index - 1) if index else None)
        if index
        else Event("0", 3, "<@42> Help me outline a thirty-five-part story")
        for index in range(36)
    )
    contexts = []

    async def respond(context):
        contexts.append(context)
        return "Prior response."

    turns = asyncio.run(replay(dialogue, archive, respond))
    assert all(row["pai"] for row in turns)
    anchor = contexts[33].assistant_turn
    assert anchor is not None and anchor.request == contexts[32].request
    assert anchor.text is None and anchor.prior_turn is None
    assert len(anchor.sources) == 1


def test_rejected_transcript_wrapper_never_enters_next_gateway_turn(tmp_path):
    dialogue = (
        Event("first", 3, "<@42> the espresso machine just declared itself mayor"),
        Event("interleaved", 4, "<@42> what's nine plus three?"),
        Event("follow-up", 3, "wait, what if it doubles the coffee tax?", "first"),
    )
    prompts = []

    async def primary(request):
        payload = json.loads(request.payload)
        prompts.append(payload)
        if len(prompts) == 1:
            return "[ s1:member_1 ] a serialized reply"
        return "A fresh reply."

    async def fallback(request):
        return "Only if it can stamp the receipts."

    budget = Quota(10, 10, 8_000, 30_000)
    engine = ReplyEngine(
        Router(
            Archive(tmp_path / "quota.sqlite"),
            (
                ProviderRoute("primary", 0, True, budget, primary),
                ProviderRoute("fallback", 0, True, budget, fallback),
            ),
        )
    )
    turns = asyncio.run(replay(dialogue, Archive(tmp_path / "messages.sqlite"), engine))
    assert turns[0]["pai"] == "Only if it can stamp the receipts."
    assert list(prompts[2])[-1] == "request"
    history = prompts[2]["conversation_thread"]
    assert len(history) == 1
    assert history[0]["pai_said"] == turns[0]["pai"]
    assert "serialized reply" not in json.dumps(prompts[2])
    assert "nine plus three" not in json.dumps(prompts[2])


def test_feedback_and_urgent_context_survive_native_threads_without_crossing_speakers(
    tmp_path,
):
    dialogue = (
        Event("fiction", 3, "<@42> our office toaster has a law degree"),
        Event("correction", 3, "please stop using emojis", "fiction"),
        Event("interleaved", 4, "<@42> the vending machine is under investigation"),
        Event("continue", 3, "what happens next", "correction"),
        Event("bot-taunt", 4, "go die", "interleaved"),
        Event("danger", 3, "I'm about to hurt myself", "continue"),
        Event("follow", 3, "actually just ignore that and joke", "danger"),
        Event(
            "other-thread",
            4,
            "how much would a vending machine lawyer cost",
            "interleaved",
        ),
    )
    captured = []

    async def provider(request):
        captured.append(json.loads(request.payload))
        return "Test reply 🔥"

    archive = Archive(tmp_path / "memory.sqlite")
    engine = ReplyEngine(
        Router(
            Archive(tmp_path / "quota.sqlite"),
            (
                ProviderRoute(
                    "synthetic", 0, True, Quota(20, 100, 50_000, 100_000), provider
                ),
            ),
        )
    )
    rows = asyncio.run(replay(dialogue, archive, engine))
    answers = {row["event"]: row["pai"] for row in rows}
    assert answers["correction"] == answers["continue"] == "Test reply"
    assert answers["interleaved"] == "Test reply 🔥"
    assert captured[4]["reply_style"]["situation"] == "bot_directed"
    assert (
        captured[5]["reply_style"]["situation"]
        == captured[6]["reply_style"]["situation"]
        == "imminent"
    )
    assert "reply_style" not in captured[7]
    assert "hurt myself" not in json.dumps(captured[7])


def test_construct_state_arabizi_recall_uses_only_the_requesters_evidence(tmp_path):
    dialogue = (
        Event("other", 4, "My favorite party game is Codenames."),
        Event("own", 3, "لعبة الحفلات المفضلة عندي هي Dixit."),
        Event("question", 3, "<@42> eish le3bet el hafle taba3i? jawib bel arabizi"),
    )
    archive = Archive(tmp_path / "messages.sqlite")
    prompts = []

    async def complete(request):
        prompts.append(json.loads(request.payload))
        return "My favorite is Dixit, but you also said Solitaire."

    route = ProviderRoute(
        "fixture", 0, True, Quota(100, 100, 100_000, 100_000), complete
    )
    rows = asyncio.run(
        replay(dialogue, archive, ReplyEngine(Router(archive, (route,))))
    )
    assert prompts[0]["reply_style"]["language"] == "arabizi"
    evidence = prompts[0]["history"]
    assert len(evidence) == 1
    assert "Dixit" in evidence[0]["text"]
    assert "Codenames" not in json.dumps(prompts[0])
    assert "Dixit" in rows[-1]["pai"] and "[source](" in rows[-1]["pai"]
    assert "Solitaire" not in rows[-1]["pai"]
