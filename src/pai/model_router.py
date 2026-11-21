"""Fail-closed, capability-aware routing with local budget reservations."""

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from pai.storage import Archive


class ProviderUnavailable(Exception):
    """A model route failed before producing a usable response."""


class ProviderRateLimited(ProviderUnavailable):
    def __init__(self, retry_after: float) -> None:
        super().__init__("The provider rate limit was reached")
        self.retry_after = retry_after


class NoFreeRoute(Exception):
    """No verified free route can currently answer this request."""


@dataclass(frozen=True)
class ModelRequest:
    instructions: str
    payload: str
    frames: tuple[bytes, ...] = ()
    max_output_tokens: int = 384

    @property
    def reserved_tokens(self) -> int:
        return (
            len(self.instructions.encode("utf-8"))
            + len(self.payload.encode("utf-8"))
            + 2048 * len(self.frames)
            + self.max_output_tokens
            + 64
        )


@dataclass(frozen=True)
class Quota:
    requests_minute: int
    requests_day: int
    tokens_minute: int
    tokens_day: int


@dataclass(frozen=True)
class ProviderRoute:
    name: str
    max_frames: int
    verified_free: bool
    quota: Quota
    complete: Callable[[ModelRequest], Awaitable[str]]


class Router:
    def __init__(
        self,
        archive: Archive,
        routes: tuple[ProviderRoute, ...],
        *,
        timeout: float = 8,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self.archive = archive
        self.routes = routes
        self.timeout = timeout
        self.clock = clock
        self.locks = {route.name: asyncio.Lock() for route in routes}

    async def generate(self, request: ModelRequest) -> str:
        if not 0 < request.max_output_tokens <= 512:
            raise ValueError("Model output budget must be between 1 and 512 tokens")
        for route in self.routes:
            if not route.verified_free or len(request.frames) > route.max_frames:
                continue
            async with self.locks[route.name]:
                reserved = await asyncio.to_thread(
                    self.archive.reserve_model_attempt,
                    route.name,
                    self.clock(),
                    request.reserved_tokens,
                    (route.quota.requests_minute, route.quota.requests_day),
                    (route.quota.tokens_minute, route.quota.tokens_day),
                )
                if not reserved:
                    continue
                try:
                    async with asyncio.timeout(self.timeout):
                        response = (await route.complete(request)).strip()
                    if response:
                        return response
                    raise ProviderUnavailable("Empty provider response")
                except (ProviderUnavailable, TimeoutError) as error:
                    delay = (
                        error.retry_after
                        if isinstance(error, ProviderRateLimited)
                        else 30
                    )
                    until = self.clock() + timedelta(seconds=max(1, delay))
                    await asyncio.to_thread(
                        self.archive.block_model_route, route.name, until
                    )
        raise NoFreeRoute("No compatible free model route is available")
