import asyncio

from pai.observability import ReplyLimits, diagnose


def test_reply_queue_waits_and_runs_same_channel_in_order():
    async def scenario():
        queue = ReplyLimits()
        first = asyncio.Event()
        completed = []

        async def reply(index):
            async with queue.slot(20, 30) as admitted:
                assert admitted
                if index == 0:
                    await first.wait()
                completed.append(index)

        jobs = [asyncio.create_task(reply(index)) for index in range(6)]
        await asyncio.sleep(0)
        assert completed == []
        first.set()
        await asyncio.gather(*jobs)
        assert completed == list(range(6))

    asyncio.run(scenario())


def test_diagnostic_checks_real_schema_without_reporting_paths_or_secrets():
    report = diagnose()
    assert report["sqlite_check"] == "ok"
    assert report["fts5"] is True
    assert all(key in {"python", "sqlite", "sqlite_check", "fts5"} for key in report)
