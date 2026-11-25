import asyncio
from contextlib import closing
from dataclasses import replace
from datetime import UTC, datetime, timedelta

import pytest

from pai.continuity import AssistantReceipts
from pai.conversation import AssistantTurn
from pai.model_router import ProviderRoute, Quota, Router
from pai.policy import PrivacyPolicy
from pai.production_benchmark import Event, replay
from pai.reply_engine import ReplyEngine
from pai.social_memory import SocialStore
from pai.storage import Archive, MessageRecord


def _seed(archive, *, social=True, continuity=True, age=timedelta(hours=2)):
    policy = PrivacyPolicy(
        True,
        "synthetic",
        1,
        frozenset({2}),
        frozenset({3, 4, 5}),
        external_ai_opt_in=social,
        social_learning_opt_in=social,
        social_consenting_member_ids=frozenset({3, 4}) if social else frozenset(),
        assistant_continuity_opt_in=continuity,
    )
    now = datetime.now(UTC) - age
    row = MessageRecord(
        81, 1, 2, 3, "Synthetic", '"sock orbit" means use the green crate', now
    )
    archive.append(row)
    store = SocialStore(archive, policy)
    if social:
        assert store.observe(row)
        assert store.confirm(row, row.message_id)
    return policy, store, row


@pytest.mark.parametrize("continuity", [False, True])
@pytest.mark.parametrize("social", [False, True])
def test_gateway_restart_all_feature_combinations(tmp_path, continuity, social):
    archive = Archive(tmp_path / "combo.sqlite")
    _seed(archive, social=social, continuity=continuity)
    prompts = []

    async def complete(req):
        prompts.append(req)
        return ("paper hat", "sock orbit, got it", "sure", "yep")[len(prompts) - 1]

    route = ProviderRoute("free", 0, True, Quota(30, 40, 100_000, 200_000), complete)
    engine = ReplyEngine(
        Router(archive, (route,)), conversation_engine="timeline-roles"
    )
    rows = asyncio.run(
        replay(
            (
                Event("ordinary", 3, "<@42> name the costume"),
                Event("learned", 4, "<@42> sock orbit again?"),
                Event("restart", 3, "say it again", "ordinary"),
                Event("after", 4, "got that?", "learned"),
            ),
            archive,
            engine,
            conversation_engine="timeline-roles",
            assistant_continuity=continuity,
            social_learning=social,
            restart_before="restart",
        )
    )
    assert all(row["pai"] for row in rows)
    assert ("Optional group context" in prompts[1].payload) == social
    assert (("assistant", "paper hat") in prompts[2].prior_messages) == continuity
    assert (
        ("assistant", "sock orbit, got it") in prompts[3].prior_messages
    ) == continuity


def test_social_receipt_preserves_scope_and_evidence(tmp_path):
    archive = Archive(tmp_path / "sources.sqlite")
    policy, store, source = _seed(archive)
    now = datetime.now(UTC) - timedelta(seconds=20)
    request = replace(
        source, message_id=82, author_id=4, text="sock orbit again?", created_at=now
    )
    archive.append(request)
    notes = store.retrieve(request)
    assert len(notes) == 1
    reply = AssistantTurn(
        "sock orbit, yep",
        request,
        (request, source),
        message_id=83,
        created_at=now + timedelta(seconds=1),
    )
    receipts = AssistantReceipts(archive, policy)
    assert receipts.remember(reply, notes=notes, social=store)
    next_request = replace(
        request,
        message_id=84,
        reply_to_id=83,
        text="is that settled?",
        created_at=now + timedelta(seconds=2),
    )

    def restored(current=next_request, active=store):
        return receipts.restore(current, 83, 82, reply.text, social=active)

    assert restored().turn == reply
    assert restored().notes == notes
    assert restored(active=None) is None
    assert restored(replace(next_request, author_id=5)) is None
    assert restored(replace(next_request, channel_id=9)) is None
    consent_removed = replace(policy, social_consenting_member_ids=frozenset({3}))
    assert restored(active=SocialStore(archive, consent_removed)) is None
    assert store.withdraw(source, "sock orbit") == 1
    assert archive.get(source.message_id) == source
    assert restored() is None
    with closing(archive.connect()) as db:
        assert not db.execute(
            "SELECT 1 FROM assistant_receipts_v1 WHERE reply_id='83'"
        ).fetchone()


@pytest.mark.parametrize("change", ["suppress", "correct", "delete"])
def test_recovery_revalidates_changes_without_rewriting_the_reply(tmp_path, change):
    archive = Archive(tmp_path / "changed.sqlite")
    policy, store, source = _seed(archive)
    now = datetime.now(UTC) - timedelta(seconds=20)
    request = replace(source, message_id=82, text="sock orbit again?", created_at=now)
    archive.append(request)
    reply = AssistantTurn(
        "sock orbit, yep",
        request,
        (request, source),
        message_id=83,
        created_at=now + timedelta(seconds=1),
    )
    receipts = AssistantReceipts(archive, policy)
    assert receipts.remember(reply, notes=store.retrieve(request), social=store)
    incoming = replace(
        request,
        author_id=4,
        message_id=84,
        reply_to_id=83,
        text="what happened?",
        created_at=now + timedelta(seconds=5),
    )
    assert receipts.restore(incoming, 83, 82, reply.text, social=store)
    if change == "delete":
        archive.delete(1, 2, (source.message_id,), now)
    else:
        changed = replace(
            incoming,
            message_id=85,
            reply_to_id=None,
            created_at=now + timedelta(seconds=3),
            author_id=4 if change == "suppress" else 3,
            text='stop using "sock orbit"'
            if change == "suppress"
            else 'actually "sock orbit" means use the brown crate',
        )
        archive.append(changed)
        assert store.observe(changed)
    assert not receipts.restore(incoming, 83, 82, reply.text, social=store)
    if change == "suppress":
        assert receipts.restore(
            replace(incoming, author_id=3), 83, 82, reply.text, social=store
        )


def test_reply_feedback_applies_to_persisted_note_after_restart(tmp_path):
    archive = Archive(tmp_path / "feedback.sqlite")
    _seed(archive)
    prompts = []

    async def complete(req):
        prompts.append(req)
        return ("sock orbit, got it", "fair", "ok")[len(prompts) - 1]

    route = ProviderRoute("free", 0, True, Quota(30, 40, 100_000, 200_000), complete)
    engine = ReplyEngine(
        Router(archive, (route,)), conversation_engine="timeline-roles"
    )
    asyncio.run(
        replay(
            (
                Event("learned", 3, "<@42> sock orbit again?"),
                Event("feedback", 4, "that joke is annoying", "learned"),
                Event("again", 4, "<@42> sock orbit again?"),
            ),
            archive,
            engine,
            conversation_engine="timeline-roles",
            assistant_continuity=True,
            social_learning=True,
            restart_before="feedback",
        )
    )
    assert "Optional group context" in prompts[0].payload
    assert ("assistant", "sock orbit, got it") not in prompts[1].prior_messages
    assert "Optional group context" not in prompts[2].payload


def test_expiry_and_disabling_social_leave_ordinary_receipts_available(tmp_path):
    archive = Archive(tmp_path / "retention.sqlite")
    policy, store, source = _seed(archive, age=timedelta(days=2))
    current = datetime.now(UTC) - timedelta(seconds=20)
    original = replace(
        source, message_id=82, text="sock orbit again?", created_at=current
    )
    archive.append(original)
    receipts = AssistantReceipts(archive, policy)
    turn = AssistantTurn(
        "sock orbit, yep",
        original,
        (original, source),
        message_id=83,
        created_at=current + timedelta(seconds=1),
    )
    assert receipts.remember(turn, notes=store.retrieve(original), social=store)
    ordinary = replace(turn, text="okay", sources=(original,), message_id=85)
    assert receipts.remember(ordinary)
    query = replace(
        original,
        message_id=84,
        reply_to_id=83,
        text="sure?",
        created_at=current + timedelta(seconds=2),
    )
    short_policy = replace(policy, retention_days=1)
    assert not AssistantReceipts(archive, short_policy).restore(
        query, 83, 82, turn.text, social=SocialStore(archive, short_policy)
    )
    assert AssistantReceipts(archive, short_policy).recover(
        replace(query, reply_to_id=85), 85, 82, ordinary.text
    )
    disabled = replace(policy, social_learning_opt_in=False)
    archive.apply_policy(disabled)
    assert (
        receipts.restore(
            query, 83, 82, turn.text, social=SocialStore(archive, disabled)
        )
        is None
    )
    assert receipts.recover(replace(query, reply_to_id=85), 85, 82, ordinary.text)


def test_unavailable_route_does_not_create_social_dependencies(tmp_path):
    from pai.conversation import ConversationContext
    from pai.social import SocialLearning

    archive = Archive(tmp_path / "quota.sqlite")
    _, store, source = _seed(archive)
    request = replace(
        source, message_id=82, text="sock orbit?", created_at=datetime.now(UTC)
    )
    feature = SocialLearning(
        store, ReplyEngine(Router(archive, ()), conversation_engine="timeline-roles")
    )
    assert store.retrieve(request)
    output = asyncio.run(feature.respond(ConversationContext(request), True))
    assert not output.notes
