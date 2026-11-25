from dataclasses import replace
from datetime import UTC, datetime

import pytest

from pai.conversation import AssistantTurn, ConversationContext
from pai.identity import Identity
from pai.policy import PrivacyPolicy
from pai.runtime_info import BuildInfo, runtime_reply
from pai.storage import MessageRecord
from pai.voice import ReplyStyle


def _context(text, *, author=3, parent=None):
    return ConversationContext(
        MessageRecord(5, 1, 2, author, "Fictional", text, datetime.now(UTC)),
        assistant_turn=parent,
    )


@pytest.mark.parametrize("text", ["what version are u", "shu versionak", "شو إصدارك"])
def test_colloquial_build_question_uses_verified_revision(text):
    assert (
        runtime_reply(
            _context(text),
            BuildInfo("a" * 40, "P9.14"),
            vision=False,
            primary_model="fixture",
        )
        == "p9.14 rn"
    )


def test_identity_distinguishes_creator_models_and_live_features():
    policy = PrivacyPolicy(True, "v1", 1, frozenset({2}), frozenset({3}))
    identity = Identity(policy, ("fixture-qwen", "fixture-oss"))
    assert "Hadisovic" in identity.reply(_context("who built u"))
    assert "Hadisovic" in identity.reply(_context("مين طورك"))
    assert (
        identity.reply(
            replace(_context("who built u"), style=ReplyStyle(language="arabizi"))
        )
        == "Hadisovic 3amalni."
    )
    assert identity.reply(_context("ur fallback model?")) == (
        "fixture-oss is my text fallback."
    )
    assert "saved" in identity.reply(_context("do u remember our conversations"))
    assert "off" in identity.reply(_context("do u learn from this chat"))
    assert identity.reply(_context("when's ur birthday")) is None
    assert identity.reply(_context("imagine a toaster is our mayor")) is None
    assert identity.reply(_context("who built the moon base")) is None
    assert identity.reply(_context("who built u", author=4)) is None


def test_model_followup_is_tied_to_verified_same_speaker_turn():
    policy = PrivacyPolicy(True, "v1", 1, frozenset({2}), frozenset({3, 4}))
    identity = Identity(policy, ("fixture-primary", "fixture-fallback"))
    previous = _context("are u qwen").request
    turn = AssistantTurn(
        identity.reply(ConversationContext(previous)), previous, (previous,)
    )
    followup = "and the fallback?"
    assert "fixture-fallback" in identity.reply(_context(followup, parent=turn))
    assert identity.reply(_context(followup, author=4, parent=turn)) is None
    assert identity.reply(_context(followup)) is None
