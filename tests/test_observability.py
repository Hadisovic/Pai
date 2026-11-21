from pai.observability import ReplyLimits, diagnose


def test_reply_limits_cap_concurrency_and_per_member_cooldown():
    now = [0.0]
    limiter = ReplyLimits(clock=lambda: now[0])
    with limiter.slot(1) as first, limiter.slot(2) as second, limiter.slot(3) as third:
        assert first and second and not third
    with limiter.slot(1) as repeated:
        assert not repeated
    now[0] += 12
    with limiter.slot(1) as later:
        assert later


def test_diagnostic_checks_real_schema_without_reporting_paths_or_secrets():
    report = diagnose()
    assert report["sqlite_check"] == "ok"
    assert report["fts5"] is True
    assert all(key in {"python", "sqlite", "sqlite_check", "fts5"} for key in report)
