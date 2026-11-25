import asyncio
from contextlib import closing
from datetime import UTC, datetime
from unittest.mock import AsyncMock

import pytest

from pai.handover import Handover
from pai.model_router import ModelRequest, ProviderRoute, ProviderUnavailable, Quota
from pai.storage import Archive, _utc_text


def test_seed_preserves_reservations_and_rejects_a_changed_snapshot(
    tmp_path, monkeypatch
):
    old, fresh = (Archive(tmp_path / name) for name in ("old.sqlite", "new.sqlite"))
    monkeypatch.setattr(Handover, "verify_exclusive", lambda self: None)
    handover = Handover(tmp_path / "old.exe", old.path)
    now = _utc_text(datetime.now(UTC))
    with closing(old.connect()) as db, db:
        db.execute("INSERT INTO model_attempts VALUES(?,?,?)", ("qwen", now, 7900))
    extra = [["fallback", now, 400]]
    handover.seed(fresh, extra)
    handover.seed(fresh, extra)
    with closing(fresh.connect()) as db:
        assert db.execute(
            "SELECT route,tokens FROM model_attempts ORDER BY rowid"
        ).fetchall() == [("qwen", 7900), ("fallback", 400)]
    assert (
        fresh.reserve_model_attempt(
            "qwen", datetime.now(UTC), 200, (25, 800), (8000, 180000)
        )
        is None
    )
    with pytest.raises(ValueError, match="no longer matches"):
        handover.seed(fresh, [])


def test_provider_guard_does_not_call_provider_if_pai_is_active(tmp_path, monkeypatch):
    def blocked(self):
        raise ValueError("Pai active")

    monkeypatch.setattr(Handover, "verify_exclusive", blocked)
    complete = AsyncMock()
    route = ProviderRoute("qwen", 0, True, Quota(25, 800, 8000, 180000), complete)
    wrapped = Handover(tmp_path / "old.exe", tmp_path / "old.db").guard(route)
    with pytest.raises(ProviderUnavailable):
        asyncio.run(wrapped.complete(ModelRequest("card", "hello")))
    complete.assert_not_awaited()
