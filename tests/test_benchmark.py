from io import BytesIO

from PIL import Image

from pai.benchmark import Completion, build_cases, run_benchmark


def test_synthetic_benchmark_covers_conversation_and_ordered_media():
    cases = build_cases()
    assert {case.skill for case in cases} == {
        "english",
        "humor",
        "recall",
        "arabic",
        "meme",
        "gif",
    }
    for skill, frame_count in [("meme", 1), ("gif", 3)]:
        case = next(case for case in cases if case.skill == skill)
        assert len(case.frames) == frame_count
        for frame in case.frames:
            with Image.open(BytesIO(frame)) as image:
                assert image.format == "PNG"
                image.verify()
    gif = next(case for case in cases if case.skill == "gif")
    assert len(set(gif.frames)) == 3


def test_benchmark_preserves_evidence_and_leaves_quality_unscored():
    calls = []

    def complete(case):
        calls.append(case)
        return Completion("Synthetic response")

    results = run_benchmark("synthetic-test", complete)
    assert len(results) == len(calls) == 6
    for result, case in zip(results, calls, strict=True):
        assert result["model"] == "synthetic-test"
        assert result["case"] == case.skill
        assert result["rubric"] == case.rubric
        assert result["response"] == "Synthetic response"
        assert result["latency_ms"] >= 0
        assert result["tokens"] is None
        assert result["score"] is None


def test_provider_benchmark_sends_only_fixture_prompt_and_frames(tmp_path):
    import asyncio
    from unittest.mock import AsyncMock

    from pai.benchmark import run_provider_benchmark
    from pai.model_router import ProviderRoute, Quota, Router
    from pai.storage import Archive

    complete = AsyncMock(return_value="Synthetic completion")
    route = ProviderRoute(
        "synthetic", 3, True, Quota(20, 100, 30_000, 100_000), complete
    )
    router = Router(Archive(tmp_path / "quota.sqlite"), (route,))
    wait = AsyncMock()
    results = asyncio.run(run_provider_benchmark(router, "synthetic", lambda: 42, wait))
    assert len(results) == 6
    for case, call, result in zip(
        build_cases(), complete.await_args_list, results, strict=True
    ):
        request = call.args[0]
        assert request.payload == case.prompt
        assert request.frames == case.frames
        assert case.rubric not in request.instructions
        assert result["tokens"] == 42
    wait.assert_awaited_once()
