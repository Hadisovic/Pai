"""Approved provider adapters. No arbitrary endpoint or model configuration."""

import json
import math
from base64 import b64encode
from collections.abc import Callable
from functools import partial

import aiohttp

from pai.model_router import (
    ModelRequest,
    ProviderCompletion,
    ProviderRateLimited,
    ProviderRoute,
    ProviderUnavailable,
    Quota,
)

_GROQ_CHAT = "https://api.groq.com/openai/v1/chat/completions"
_GROQ_PRIMARY = "qwen/qwen3.8-27b"
_GROQ_FALLBACK = "openai/gpt-oss-120b"
_GROQ_QUOTA = Quota(25, 800, 8000, 180_000)
_RESPONSE_BYTES = 65_536


class Groq:
    def __init__(
        self,
        session: aiohttp.ClientSession,
        key: str,
        *,
        free_plan_confirmed: bool,
        observe_usage: Callable[[int | None], None] | None = None,
    ) -> None:
        self.session = session
        self.key = key
        self.free_plan_confirmed = free_plan_confirmed
        self.observe_usage = observe_usage

    def routes(self) -> tuple[ProviderRoute, ...]:
        if not self.free_plan_confirmed or not self.key.strip():
            return ()
        return (
            ProviderRoute(
                f"groq/{_GROQ_PRIMARY}",
                3,
                True,
                _GROQ_QUOTA,
                partial(self._complete, _GROQ_PRIMARY, "none"),
            ),
            ProviderRoute(
                f"groq/{_GROQ_FALLBACK}",
                0,
                True,
                _GROQ_QUOTA,
                partial(self._complete, _GROQ_FALLBACK, "low"),
            ),
        )

    async def _complete(
        self, model: str, reasoning_effort: str, request: ModelRequest
    ) -> ProviderCompletion:
        content: str | list[dict] = request.payload
        if request.frames:
            content = [
                {"type": "text", "text": request.payload},
                *[
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": "data:image/png;base64,"
                            + b64encode(frame).decode("ascii")
                        },
                    }
                    for frame in request.frames
                ],
            ]
        try:
            async with self.session.post(
                _GROQ_CHAT,
                headers={"Authorization": f"Bearer {self.key}"},
                json={
                    "model": model,
                    "messages": [
                        {"role": "system", "content": request.instructions},
                        {"role": "user", "content": content},
                    ],
                    "max_completion_tokens": request.max_output_tokens,
                    "reasoning_effort": reasoning_effort,
                    "include_reasoning": False,
                    "stream": False,
                },
                allow_redirects=False,
            ) as response:
                if response.status == 429:
                    raise ProviderRateLimited(
                        _retry_after(response.headers.get("Retry-After"))
                    )
                if response.status != 200:
                    raise ProviderUnavailable(f"Groq returned HTTP {response.status}")
                data = bytearray()
                while chunk := await response.content.read(4096):
                    data.extend(chunk)
                    if len(data) > _RESPONSE_BYTES:
                        raise ProviderUnavailable(
                            "Groq response exceeded the size limit"
                        )
            payload = json.loads(data)
            answer = payload["choices"][0]["message"]["content"]
            if not isinstance(answer, str):
                raise TypeError("Expected completion text")
            usage = payload.get("usage")
            tokens = usage.get("total_tokens") if isinstance(usage, dict) else None
            actual = tokens if type(tokens) is int and tokens > 0 else None
            if self.observe_usage is not None:
                self.observe_usage(actual)
            return ProviderCompletion(answer, actual)
        except (aiohttp.ClientError, ValueError, TypeError, KeyError, IndexError):
            raise ProviderUnavailable("Groq did not return a valid response") from None


def _retry_after(value: str | None) -> float:
    try:
        seconds = float(value) if value else 60.0
    except ValueError:
        return 60.0
    if not math.isfinite(seconds) or seconds <= 0:
        return 60.0
    return min(seconds, 30 * 86_400)


class OutageNotice:
    def __init__(self) -> None:
        self.announced: set[int] = set()

    def unavailable(self, channel_id: int) -> str:
        if channel_id in self.announced:
            return ""
        self.announced.add(channel_id)
        return "i hit the free model capacity for now. try me again in a bit"

    def recovered(self, channel_id: int) -> None:
        self.announced.discard(channel_id)
