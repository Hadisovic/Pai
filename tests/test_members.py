import asyncio
from dataclasses import replace
from datetime import UTC, datetime, timedelta

from pai.members import MemberDirectory, member_intent, render_member_reply
from pai.model_router import ProviderRoute, Quota, Router
from pai.policy import PrivacyPolicy
from pai.production_benchmark import Event, replay
from pai.reply_engine import ReplyEngine
from pai.social_memory import SocialStore
from pai.storage import Archive, MessageRecord


def fixtures(tmp_path):
    archive = Archive(tmp_path / "members.sqlite")
    policy = PrivacyPolicy(
        True,
        "synthetic",
        1,
        frozenset({2}),
        frozenset({3, 4, 5}),
        external_ai_opt_in=True,
        member_awareness_opt_in=True,
        member_awareness_member_ids=frozenset({3, 4}),
    )
    now = datetime.now(UTC)
    first = MessageRecord(
        21,
        1,
        2,
        3,
        "Jun",
        "my favorite game is Hollow Knight",
        now - timedelta(hours=2),
    )
    second = replace(
        first,
        message_id=22,
        author_id=4,
        author_display="Jun",
        text="my favorite game is Hades",
    )
    directory = MemberDirectory(archive, policy)
    for row in (first, second):
        archive.append(row)
        assert directory.observe(row, f"jun{row.author_id}", row.author_display)
    return archive, directory, first, second, now


def test_canonical_identity_renames_and_owner_controls(tmp_path):
    archive, directory, first, second, now = fixtures(tmp_path)
    request = replace(first, message_id=30, created_at=now, text='about "Jun"')
    assert directory.lookup(request, alias="Jun") == ()
    renamed = replace(
        second,
        message_id=23,
        author_display="Juno",
        text="hey",
        created_at=now - timedelta(minutes=5),
    )
    archive.append(renamed)
    assert directory.observe(renamed, "quietjun", "Juno")
    assert [(m.id, m.label) for m in directory.lookup(request, ids=(4,))] == [
        (4, "Juno")
    ]
    assert [m.id for m in directory.lookup(request, alias="Jun")] == []
    assert [m.id for m in directory.lookup(request, alias="quietjun")] == [4]
    assert directory.configure(
        renamed, nickname="Orbit", references=False, teasing=True
    )
    reopened = MemberDirectory(Archive(archive.path), directory.policy)
    assert [
        (m.id, m.label, m.references, m.teasing)
        for m in reopened.lookup(request, alias="Orbit")
    ] == [(4, "Orbit", False, True)]
    archive.forget_author(1, 4, now)
    assert not reopened.lookup(request, alias="Orbit")
    assert not reopened.lookup(request, ids=(4, 5))


def test_reference_plan_uses_first_person_current_evidence_and_bounded_markers(
    tmp_path,
):
    archive, directory, first, second, now = fixtures(tmp_path)
    correction = replace(
        second,
        message_id=23,
        text="actually my favorite game is Portal 2",
        created_at=now - timedelta(minutes=5),
    )
    hearsay = replace(
        first,
        message_id=24,
        text="my favorite game is Terraria",
        created_at=now - timedelta(minutes=1),
    )
    archive.append(correction)
    archive.append(hearsay)
    request = replace(
        first, message_id=30, created_at=now, text="<@42> what's <@4>'s favorite game?"
    )
    intent = member_intent(request.text, 42, {4, 42})
    plan = directory.plan(request, intent, directory.lookup(request, ids=(4,)), {3})
    assert plan.sources == (correction,)
    assert "Portal 2" in plan.block and "Terraria" not in plan.block
    assert "<@4>" not in plan.block and "<@42>" not in plan.block
    assert "Portal 2" in render_member_reply("[[m1]] said Portal 2 [[e1]]", plan)
    assert "<@4>" in render_member_reply(
        "[[m1]] [[m1]] and <@5> @everyone <@&10> [[m9]]", plan
    )
    rendered = render_member_reply(
        "[[m1]] [[m1]] and <@5> @everyone <@&10> [[m9]]", plan
    )
    assert (
        rendered.count("<@4>") == 1
        and "<@5>" not in rendered
        and "@everyone" not in rendered
    )
    archive.delete(1, 2, (23,), now)
    assert not directory.valid(request, plan)


def test_member_intent_ignores_unrelated_turns_and_distinguishes_group_and_targets():
    assert member_intent("<@42> hello", 42, {42}) is None
    plan = member_intent("<@42> who would win, <@4> or <@5>?", 42, {42, 4})
    assert plan.ids == (4,) and plan.unavailable == 1
    assert member_intent(
        "<@42> rank us by who could build a funny robot", 42, {42}
    ).group
    assert member_intent('<@42> what about "Orbit"?', 42, {42}).alias == "Orbit"


def test_gateway_member_context_with_social_and_continuity(tmp_path):
    archive = Archive(tmp_path / "gateway.sqlite")
    optin = PrivacyPolicy(
        True,
        "synthetic",
        1,
        frozenset({2}),
        frozenset({3, 4}),
        external_ai_opt_in=True,
        social_learning_opt_in=True,
        social_consenting_member_ids=frozenset({3, 4}),
    )
    teach = MessageRecord(
        60,
        1,
        2,
        3,
        "Synthetic",
        '"cloud bell" means we swap teams',
        datetime.now(UTC) - timedelta(hours=2),
    )
    archive.append(teach)
    store = SocialStore(archive, optin)
    assert store.observe(teach) and store.confirm(teach, 60)
    seen = []

    async def complete(req):
        seen.append(req)
        return (
            "paper comet",
            "[[m1]] said Hades [[e1]]",
            "Grey builds. Fern runs the cloud bell. <@5> @here [[m999]]",
            "paper comet",
        )[len(seen) - 1]

    route = ProviderRoute(
        "fixture", 0, True, Quota(50, 100, 100_000, 200_000), complete
    )
    engine = ReplyEngine(
        Router(archive, (route,)), conversation_engine="timeline-roles"
    )
    rows = asyncio.run(
        replay(
            (
                Event("mine", 3, "my favorite game is Celeste"),
                Event("theirs", 4, "my favorite game is Hades"),
                Event("ordinary", 3, "<@42> name my kite"),
                Event("recall", 3, "<@42> what's <@4>'s favorite game?"),
                Event(
                    "two",
                    4,
                    "<@42> pick jobs for <@3> and <@4> at a cloud bell party. mention them both",
                ),
                Event(
                    "unauthorized", 4, "<@42> can you remember <@5>'s favorite game?"
                ),
                Event("resume", 3, "say it again", "ordinary"),
            ),
            archive,
            engine,
            conversation_engine="timeline-roles",
            social_learning=True,
            assistant_continuity=True,
            member_awareness=True,
            member_names={3: ("grey", "Grey"), 4: ("fern", "Fern")},
            restart_before="resume",
        )
    )
    assert [row["pai"] for row in rows[:2]] == [None, None]
    assert "Member context" not in seen[0].payload
    assert "Member context" in seen[1].payload
    assert '"name":"Fern"' in seen[1].payload and "Hades" in seen[1].payload
    assert "Celeste" not in seen[1].payload
    assert "<@4>" in rows[3]["pai"] and "[source]" in rows[3]["pai"]
    assert (
        "Member context" in seen[2].payload
        and "Optional group context" in seen[2].payload
    )
    assert "<@3>" in rows[4]["pai"] and "<@4>" in rows[4]["pai"]
    assert all(value not in rows[4]["pai"] for value in ("<@5>", "@here", "[[m999]]"))
    assert "Discord mention" in rows[5]["pai"]
    assert ("assistant", "paper comet") in seen[3].prior_messages


def test_group_labels_are_bounded_and_privacy_controls_are_enforced(tmp_path):
    archive, directory, first, _, now = fixtures(tmp_path)
    rows = directory.lookup(replace(first, created_at=now))
    assert len(rows) == 2 and rows[0].label == rows[1].label
    group = replace(
        first,
        text="<@42> rank us by who would survive as a fictional duck",
        created_at=now,
    )
    intent = member_intent(group.text, 42, {42})
    plan = directory.plan(group, intent, rows, {3})
    assert "authorized group sample" in plan.block
    assert '"speaker":true' in plan.block and '"present":false' in plan.block
    assert not plan.sources
    assert render_member_reply("hmm [[spoiler]]", plan) == "hmm [[spoiler]]"
    roast = member_intent("<@42> roast us", 42, {42})
    assert directory.plan(group, roast, rows, {3}).local_reply
    appearance = member_intent("<@42> which of us is the hottest", 42, {42})
    assert directory.plan(group, appearance, rows, {3}).local_reply
    disabled = replace(directory.policy, member_awareness_opt_in=False)
    archive.apply_policy(disabled)
    assert not MemberDirectory(archive, disabled).lookup(group)
    assert all(not member.display for member in directory.lookup(group))


def test_gateway_drops_pending_member_reply_after_target_withdraws(tmp_path):
    archive = Archive(tmp_path / "withdrawal.sqlite")
    calls = []

    async def complete(req):
        calls.append(req)
        assert "Hades" in req.payload
        archive.forget_author(1, 4, datetime.now(UTC))
        return "[[m1]] plays Hades [[e1]]"

    route = ProviderRoute(
        "fixture", 0, True, Quota(50, 100, 100_000, 200_000), complete
    )
    engine = ReplyEngine(
        Router(archive, (route,)), conversation_engine="timeline-roles"
    )
    rows = asyncio.run(
        replay(
            (
                Event("fact", 4, "my favorite game is Hades"),
                Event("ask", 3, "<@42> what's <@4>'s favorite game?"),
            ),
            archive,
            engine,
            conversation_engine="timeline-roles",
            member_awareness=True,
        )
    )
    assert len(calls) == 1
    assert rows[-1]["pai"] is None
