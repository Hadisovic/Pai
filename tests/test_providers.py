import asyncio
from unittest.mock import AsyncMock, Mock

import pytest

from pai.model_router import ModelRequest, ProviderRateLimited, Router
from pai.providers import Groq, OutageNotice
from pai.storage import Archive


class Response:
    def __init__(self, status, data=None, retry_after=None):
        self.status = status
        self.data = data
        self.headers = {"Retry-After": retry_after} if retry_after is not None else {}
        self.content = Mock()
        self.content.read = AsyncMock(side_effect=[data or b"", b""])

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return None


def test_groq_uses_fixed_api_and_verified_free_model_list():
    session = Mock()
    session.post.return_value = Response(
        200, b'{"choices": [{"message": {"content": "Synthetic reply"}}]}'
    )
    assert Groq(session, "placeholder", free_plan_confirmed=False).routes() == ()
    client = Groq(session, "placeholder", free_plan_confirmed=True)
    primary, fallback = client.routes()
    assert primary.name == "groq/openai/gpt-oss-120b"
    assert fallback.name == "groq/qwen/qwen3.8-27b"
    assert primary.max_frames == 0
    assert fallback.max_frames == 3
    request = ModelRequest("rules", "synthetic payload", (b"frame-a", b"frame-b"))
    assert asyncio.run(fallback.complete(request)).text == "Synthetic reply"
    assert session.post.call_args.args == (
        "https://api.groq.com/openai/v1/chat/completions",
    )
    kwargs = session.post.call_args.kwargs
    assert not kwargs["allow_redirects"]
    assert kwargs["json"]["model"] == "qwen/qwen3.8-27b"
    parts = kwargs["json"]["messages"][1]["content"]
    assert [part["type"] for part in parts] == ["text", "image_url", "image_url"]
    assert parts[1]["image_url"]["url"].startswith("data:image/png;base64,")


def test_groq_429_propagates_retry_without_reading_response_body():
    session = Mock()
    response = Response(429, retry_after="12.5")
    session.post.return_value = response
    primary, _ = Groq(session, "placeholder", free_plan_confirmed=True).routes()
    with pytest.raises(ProviderRateLimited) as error:
        asyncio.run(primary.complete(ModelRequest("rules", "text")))
    assert error.value.retry_after == 12.5
    response.content.read.assert_not_awaited()


def test_each_channel_receives_one_notice_per_outage():
    notice = OutageNotice()
    assert notice.unavailable(1)
    assert notice.unavailable(1) == ""
    assert notice.unavailable(2)
    notice.recovered(1)
    assert notice.unavailable(1)


def test_groq_routes_text_to_gpt_oss_and_vision_to_qwen(tmp_path):
    session = Mock()
    result = b'{"choices":[{"message":{"content":"Reply"}}]}'
    session.post.side_effect = [
        Response(200, result),
        Response(429, retry_after="30"),
        Response(200, result),
        Response(200, result),
    ]
    client = Groq(session, "placeholder", free_plan_confirmed=True)
    router = Router(Archive(tmp_path / "pai.sqlite"), client.routes())

    async def scenario():
        text = ModelRequest("rules", "text")
        assert await router.generate(text) == "Reply"
        assert await router.generate(text) == "Reply"
        assert (
            await router.generate(ModelRequest("rules", "image", (b"frame",)))
            == "Reply"
        )

    asyncio.run(scenario())
    assert [call.kwargs["json"]["model"] for call in session.post.call_args_list] == [
        "openai/gpt-oss-120b",
        "openai/gpt-oss-120b",
        "qwen/qwen3.8-27b",
        "qwen/qwen3.8-27b",
    ]
    assert [
        call.kwargs["json"]["reasoning_effort"] for call in session.post.call_args_list
    ] == ["low", "low", "none", "none"]
