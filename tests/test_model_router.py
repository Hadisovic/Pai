import asyncio
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock

import pytest

from pai.model_router import (
    ModelRequest,
    NoFreeRoute,
    ProviderRateLimited,
    ProviderRoute,
    Quota,
    Router,
)
from pai.storage import Archive


def route(name, callback, *, frames=0, free=True, quota=None):
    return ProviderRoute(
        name, frames, free, quota or Quota(30, 100, 8000, 100_000), callback
    )


def test_router_uses_compatible_verified_free_fallback_and_honors_cooldown(tmp_path):
    archive = Archive(tmp_path / "pai.sqlite")
    throttled = AsyncMock(side_effect=ProviderRateLimited(90))
    text = AsyncMock(return_value="text")
    paid = AsyncMock(return_value="paid")
    router = Router(
        archive,
        (
            route("paid-vision", paid, frames=3, free=False),
            route("free-vision", throttled, frames=3),
            route("free-text", text),
        ),
    )
    assert asyncio.run(router.generate(ModelRequest("system", "text"))) == "text"
    assert asyncio.run(router.generate(ModelRequest("system", "text"))) == "text"
    with pytest.raises(NoFreeRoute):
        asyncio.run(
            router.generate(ModelRequest("system", "vision", frames=(b"frame",)))
        )
    throttled.assert_awaited_once()
    paid.assert_not_awaited()
    assert text.await_count == 2


def test_budget_survives_reopen_and_resets_after_rolling_day(tmp_path):
    path = tmp_path / "pai.sqlite"
    now = datetime.now(UTC)
    time = [now]
    model = AsyncMock(return_value="ok")
    choice = route("free", model, quota=Quota(1, 1, 8000, 8000))
    router = Router(Archive(path), (choice,), clock=lambda: time[0])
    assert asyncio.run(router.generate(ModelRequest("system", "text"))) == "ok"
    reopened = Router(Archive(path), (choice,), clock=lambda: time[0])
    time[0] = now + timedelta(minutes=2)
    with pytest.raises(NoFreeRoute):
        asyncio.run(reopened.generate(ModelRequest("system", "text")))
    time[0] = now + timedelta(days=1, seconds=1)
    assert asyncio.run(reopened.generate(ModelRequest("system", "text"))) == "ok"
    assert model.await_count == 2


def test_timeout_marks_route_temporarily_unavailable(tmp_path):
    async def slow(_):
        await asyncio.sleep(1)
        return "too late"

    fast = AsyncMock(return_value="fallback")
    router = Router(
        Archive(tmp_path / "pai.sqlite"),
        (route("slow", slow), route("fast", fast)),
        timeout=0.01,
    )
    assert asyncio.run(router.generate(ModelRequest("system", "text"))) == "fallback"


def test_verified_usage_reconciles_reservations_for_rapid_replies(tmp_path):
    from pai.model_router import ProviderCompletion

    async def reply(request):
        return ProviderCompletion("ok", 60)

    async def scenario():
        archive = Archive(tmp_path / "pai.sqlite")
        router = Router(
            archive,
            (ProviderRoute("synthetic", 0, True, Quota(12, 12, 1700, 1700), reply),),
        )
        request = ModelRequest("rules", "x" * 1000)
        assert await router.generate(request) == "ok"
        assert await router.generate(request) == "ok"
        assert await router.generate(request) == "ok"

    asyncio.run(scenario())
