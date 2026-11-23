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
    for label in ("ordinary", "first-fact", "second-fact", "distractor", "unconsented"):
        assert by_event[label]["pai"] is None
    assert not by_event["unconsented"]["archived"]
    assert by_event["ordinary"]["archived"]

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
