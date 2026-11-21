"""Benchmark fixed synthetic fixtures through a loopback-only llama.cpp server."""

import argparse
import asyncio
import base64
import json
from pathlib import Path
from tempfile import TemporaryDirectory

import aiohttp

from pai.benchmark import run_provider_benchmark
from pai.model_router import ModelRequest, ProviderRoute, Quota, Router
from pai.storage import Archive


async def run(model: str, port: int) -> list[dict]:
    usage = None
    endpoint = f"http://127.0.0.1:{port}/v1/chat/completions"

    async with aiohttp.ClientSession(trust_env=False) as session:

        async def complete(request: ModelRequest) -> str:
            nonlocal usage
            content = request.payload
            if request.frames:
                content = [{"type": "text", "text": content}]
                for frame in request.frames:
                    uri = "data:image/png;base64," + base64.b64encode(frame).decode(
                        "ascii"
                    )
                    content.append({"type": "image_url", "image_url": {"url": uri}})

            body = {
                "model": "pai-local",
                "messages": [
                    {"role": "system", "content": request.instructions},
                    {"role": "user", "content": content},
                ],
                "temperature": 0,
                "seed": 21,
                "max_tokens": 128,
                "chat_template_kwargs": {"enable_thinking": False},
                "stream": False,
            }
            async with session.post(
                endpoint, json=body, allow_redirects=False
            ) as response:
                if response.status != 200:
                    raise RuntimeError(
                        f"Local inference failed with HTTP {response.status}"
                    )
                result = await response.json()
            usage = result.get("usage", {}).get("total_tokens")
            return result["choices"][0]["message"]["content"]

        async def no_network_quota_wait() -> None:
            return None

        with TemporaryDirectory(prefix="pai-benchmark-") as directory:
            route = ProviderRoute(
                model, 3, True, Quota(20, 25, 100_000, 200_000), complete
            )
            router = Router(
                Archive(Path(directory) / "quota.sqlite"), (route,), timeout=150
            )
            return await run_provider_benchmark(
                router, model, lambda: usage, no_network_quota_wait
            )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("model", help="Label for the GGUF being served")
    parser.add_argument("--port", default=18547, type=int)
    options = parser.parse_args()
    if not 1 <= options.port <= 65_535:
        parser.error("Invalid loopback port")
    print(
        json.dumps(
            asyncio.run(run(options.model, options.port)), ensure_ascii=True, indent=2
        )
    )


if __name__ == "__main__":
    main()
