import asyncio
from dataclasses import replace
from datetime import UTC, datetime, timedelta

from pai.continuity import (
    AssistantReceipts,
    clarify_harmful_parent,
    focus_native_branch,
)
from pai.conversation import AssistantTurn, ConversationContext
from pai.policy import PrivacyPolicy
from pai.production_benchmark import Event, replay
from pai.storage import Archive, MessageRecord
from pai.timeline import build_timeline_prompt


def _fixture(tmp_path):
    archive = Archive(tmp_path / "memory.sqlite")
    policy = PrivacyPolicy(
        True,
        "synthetic",
        1,
        frozenset({2, 6}),
        frozenset({3, 4}),
        assistant_continuity_opt_in=True,
    )
    now = datetime.now(UTC)
    original = MessageRecord(10, 1, 2, 3, "Fictional A", "name our kite", now)
    evidence = MessageRecord(11, 1, 2, 4, "Fictional B", "it has spots", now)
    turn = AssistantTurn(
        "spot rocket",
        original,
        (original, evidence),
        message_id=12,
        created_at=now + timedelta(seconds=1),
    )
    request = MessageRecord(
        13, 1, 2, 3, "Fictional A", "use the name above", now + timedelta(seconds=2), 12
    )
    for record in (original, evidence, request):
        archive.append(record)
    return archive, policy, turn, request


def test_receipt_survives_restart_only_for_verified_native_reply(tmp_path):
    archive, policy, turn, request = _fixture(tmp_path)
    store = AssistantReceipts(archive, policy)
    assert store.remember(turn)
    restarted = AssistantReceipts(Archive(archive.path), policy)
    assert restarted.recover(request, 12, 10, "spot rocket") == turn
    assert restarted.recover(request, 12, 10, "edited text") is None
    assert restarted.recover(request, 12, 11, "spot rocket") is None
    assert (
        restarted.recover(replace(request, channel_id=6), 12, 10, "spot rocket") is None
    )
    assert (
        restarted.recover(replace(request, author_id=5), 12, 10, "spot rocket") is None
    )
    assert (
        restarted.recover(replace(request, reply_to_id=None), 12, 10, "spot rocket")
        is None
    )
    assert (
        restarted.recover(
            replace(request, created_at=request.created_at + timedelta(days=31)),
            12,
            10,
            "spot rocket",
        )
        is None
    )


def test_receipts_invalidate_on_edit_delete_and_policy_change(tmp_path):
    archive, policy, turn, request = _fixture(tmp_path)
    store = AssistantReceipts(archive, policy)
    assert store.remember(turn)
    assert archive.edit(11, 1, 2, frozenset({4}), "no spots", request.created_at)
    assert store.recover(request, 12, 10, "spot rocket") is None
    assert not store.remember(turn)
    assert store.remember(replace(turn, sources=(turn.request,)))
    archive.delete(1, 2, (12,), request.created_at)
    assert store.recover(request, 12, 10, "spot rocket") is None
    assert not store.remember(replace(turn, sources=(turn.request,)))
    changed = replace(policy, notice_version="reissued")
    assert store.remember(replace(turn, message_id=14, sources=(turn.request,)))
    archive.apply_policy(changed)
    assert (
        store.recover(replace(request, reply_to_id=14), 14, 10, "spot rocket") is None
    )
    assert store.remember(replace(turn, message_id=15, sources=(turn.request,)))
    archive.forget_author(1, 3, request.created_at)
    assert (
        store.recover(replace(request, reply_to_id=15), 15, 10, "spot rocket") is None
    )


def test_native_branch_focus_keeps_corrections_and_unthreaded_context(tmp_path):
    _, _, turn, request = _fixture(tmp_path)
    row = replace(request, author_id=4)
    wrong = replace(row, message_id=18, text="defrost the freezer", reply_to_id=8)
    correct = replace(row, message_id=19, text="actually it's striped", reply_to_id=12)
    ambient = replace(row, message_id=20, text="mine just arrived", reply_to_id=None)
    context = ConversationContext(
        request,
        recent=(wrong, correct, ambient),
        assistant_turn=turn,
        native_reply=True,
    )
    focused = focus_native_branch(context)
    assert focused.recent == (correct, ambient)
    assert focused.assistant_turn is turn
    unanchored = replace(context, assistant_turn=None)
    assert focus_native_branch(unanchored) == unanchored


def test_ambiguous_ping_does_not_endorse_a_harmful_human_parent(tmp_path):
    _, _, turn, request = _fixture(tmp_path)
    parent = replace(turn.request, text="go die")
    request = replace(request, text="<@42>", reply_to_id=parent.message_id)
    context = ConversationContext(request, parents=(parent,))
    assert clarify_harmful_parent(context)
    assert not clarify_harmful_parent(replace(context, parents=()))
    assert not clarify_harmful_parent(
        replace(
            context, request=replace(request, text="<@42> write a silly kite story")
        )
    )


def test_restarted_gateway_recovers_target_and_omits_competing_native_branch(tmp_path):
    dialogue = (
        Event("kite", 3, "<@42> name our kite"),
        Event("freezer", 4, "<@42> help our other team"),
        Event("side", 4, "defrost the freezer", "freezer"),
        Event("callback", 3, "what name did you pick?", "kite"),
    )
    prompts = []

    async def respond(ctx):
        prompts.append(build_timeline_prompt(ctx, native_roles=True).request)
        return "spot rocket" if len(prompts) in (1, 5) else "ok"

    for enabled in (False, True):
        rows = asyncio.run(
            replay(
                dialogue,
                Archive(tmp_path / f"{enabled}.sqlite"),
                respond,
                conversation_engine="timeline-roles",
                assistant_continuity=enabled,
                restart_before="callback",
            )
        )
        assert rows[-1]["pai"] == "ok"
        request = prompts[-1]
        assert (("assistant", "spot rocket") in request.prior_messages) == enabled
        assert ("defrost the freezer" in request.payload) != enabled
