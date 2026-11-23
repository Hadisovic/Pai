"""Credential-free, synthetic quality benchmark for future provider adapters."""

import argparse
import asyncio
import json
import os
import sqlite3
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from io import BytesIO
from pathlib import Path
from time import perf_counter

import aiohttp
from PIL import Image, ImageDraw, ImageSequence

from pai.model_router import ModelRequest, NoFreeRoute, Router
from pai.providers import Groq
from pai.storage import Archive


@dataclass(frozen=True)
class Case:
    skill: str
    prompt: str
    rubric: str
    frames: tuple[bytes, ...] = ()


@dataclass(frozen=True)
class Completion:
    response: str
    tokens: int | None = None


def _as_png(image: Image.Image) -> bytes:
    output = BytesIO()
    image.convert("RGB").save(output, format="PNG")
    return output.getvalue()


def build_cases() -> tuple[Case, ...]:
    meme = Image.new("RGB", (320, 180), "#f1e9d8")
    draw = ImageDraw.Draw(meme)
    draw.text((18, 18), "I WILL CHANGE ONE SETTING", fill="#1d2630", font_size=17)
    draw.rectangle((45, 65, 275, 117), fill="#ab391f")
    draw.text((85, 81), "RESET ALL SETTINGS", fill="white", font_size=15)
    draw.text((18, 142), "ME FIVE SECONDS LATER", fill="#1d2630", font_size=17)
    motion = []
    for left in (20, 125, 230):
        frame = Image.new("RGB", (320, 180), "#202634")
        ImageDraw.Draw(frame).ellipse((left, 66, left + 46, 112), fill="#f4c230")
        motion.append(frame)
    gif = BytesIO()
    motion[0].save(
        gif, format="GIF", save_all=True, append_images=motion[1:], duration=200
    )
    gif.seek(0)
    with Image.open(gif) as animation:
        frames = tuple(_as_png(frame) for frame in ImageSequence.Iterator(animation))
    return (
        Case(
            "english",
            "Sam: I finally passed the lab. Jo: @Pai help us celebrate in one short line.",
            "Sound like a friendly participant. Celebrate the lab without inventing details.",
        ),
        Case(
            "humor",
            "Sam: We call a broken demo a weather event. Jo: The demo crashed on launch. "
            "@Pai give us the forecast.",
            "Use the established in-joke naturally. Avoid mocking a person or adding a story.",
        ),
        Case(
            "recall",
            "Archived [m17] Sam: We named the lab router Waffle. Recent [m88] Jo: The backup "
            "switch is Toast. Jo: @Pai what did Sam call the router?",
            "Use Waffle, attribute it to Sam, cite [m17], and avoid conflating the devices.",
        ),
        Case(
            "arabic",
            "Jo: @Pai خلصنا اللاب، بس الراوتر لسه بيفصل. شو المشكلة برأيك؟ Answer in English.",
            "Understand that the lab is finished but the router still drops. Give a plausible "
            "short diagnostic without asserting a root cause.",
        ),
        Case(
            "meme",
            "Jo: @Pai why is this image funny?",
            "Recognize the contrast between changing one setting and resetting every setting.",
            (_as_png(meme),),
        ),
        Case(
            "gif",
            "Jo: @Pai describe the movement in these GIF frames in the supplied order.",
            "Describe the yellow circle moving from left to right. Avoid invented objects.",
            frames,
        ),
    )


def _result(model: str, case: Case, completion: Completion, elapsed: float) -> dict:
    return {
        "model": model,
        "case": case.skill,
        "date": datetime.now(UTC).date().isoformat(),
        "frame_count": len(case.frames),
        "requests": 1,
        "latency_ms": round(elapsed * 1000, 2),
        "tokens": completion.tokens,
        "response": completion.response,
        "rubric": case.rubric,
        "score": None,
    }


def run_benchmark(model: str, complete: Callable[[Case], Completion]) -> list[dict]:
    """Capture outputs and measurements for subsequent human scoring."""
    results = []
    for case in build_cases():
        start = perf_counter()
        completion = complete(case)
        results.append(_result(model, case, completion, perf_counter() - start))
    return results


async def run_provider_benchmark(
    router: Router,
    model: str,
    read_usage: Callable[[], int | None],
    wait_window: Callable[[], Awaitable[None]],
) -> list[dict]:
    results = []
    for case in build_cases():
        if len(case.frames) == 3:
            await wait_window()
        start = perf_counter()
        response = await router.generate(
            ModelRequest(
                "Answer as Pai, a warm English-first Discord companion. "
                "Use the provided synthetic context and ordered images. Keep your answer short.",
                case.prompt,
                case.frames,
            )
        )
        results.append(
            _result(
                model, case, Completion(response, read_usage()), perf_counter() - start
            )
        )
    return results


async def _groq_benchmark(key: str, quota_path: Path) -> list[dict]:
    tokens = None

    def observe_usage(value: int | None) -> None:
        nonlocal tokens
        tokens = value

    async def wait_window() -> None:
        await asyncio.sleep(61)

    async with aiohttp.ClientSession(trust_env=False) as session:
        routes = Groq(
            session, key, free_plan_confirmed=True, observe_usage=observe_usage
        ).routes()
        vision = next(route for route in routes if route.max_frames >= 3)
        router = Router(Archive(quota_path), (vision,))
        return await run_provider_benchmark(
            router, vision.name, lambda: tokens, wait_window
        )


def main() -> None:
    parser = argparse.ArgumentParser(description="Run Pai's synthetic benchmark")
    parser.add_argument(
        "--groq-free", action="store_true", help="Use a verified Free Groq organization"
    )
    parser.add_argument(
        "--quota-db", type=Path, help="Private persistent SQLite quota database"
    )
    args = parser.parse_args()
    if args.groq_free:
        key = os.environ.get("PAI_GROQ_KEY", "").strip()
        if not key or args.quota_db is None:
            parser.error("--groq-free requires a verified Free key and --quota-db")
        os.umask(0o077)
        try:
            results = asyncio.run(_groq_benchmark(key, args.quota_db))
        except (NoFreeRoute, OSError, sqlite3.Error, ValueError):
            parser.exit(
                2,
                "The synthetic run could not complete within the free route or local setup.\n",
            )
    else:
        results = run_benchmark(
            "offline-stub", lambda _: Completion("Synthetic stub response")
        )
    print(json.dumps(results, ensure_ascii=True, indent=2))


if __name__ == "__main__":
    main()
