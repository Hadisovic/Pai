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
