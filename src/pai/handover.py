"""Exclusive Windows quota handover for the temporary Kirky cutover."""

import asyncio
import json
import os
import sqlite3
import subprocess
from contextlib import closing
from dataclasses import dataclass, replace
from datetime import UTC, datetime, timedelta
from hashlib import sha256
from pathlib import Path

from pai.model_router import ModelRequest, ProviderRoute, ProviderUnavailable
from pai.storage import Archive, _utc_text

_PROCESS_CHECK = """
$ErrorActionPreference='Stop'
$path=$env:KIRKY_STABLE_EXE
$db=$env:KIRKY_STABLE_DB
$matchesFound=@(Get-CimInstance Win32_Process -Filter "Name = 'python.exe' OR Name = 'pythonw.exe'" | Where-Object {
    $_.ExecutablePath -eq $path -or
    ($_.CommandLine -and $_.CommandLine.IndexOf($db,[StringComparison]::OrdinalIgnoreCase) -ge 0)
})
if ($matchesFound.Count) { exit 2 }
exit 0
"""


@dataclass(frozen=True)
class Handover:
    stable_exe: Path
    stable_db: Path

    def verify_exclusive(self) -> None:
        if (
            os.name != "nt"
            or not self.stable_exe.is_file()
            or not self.stable_db.is_file()
        ):
            raise ValueError("Stable runtime cannot be verified")
        try:
            check = subprocess.run(
                [
                    "powershell.exe",
                    "-NoProfile",
                    "-NonInteractive",
                    "-Command",
                    _PROCESS_CHECK,
                ],
                env={
                    **{
                        k: v
                        for k, v in os.environ.items()
                        if k not in {"KIRKY_GROQ_KEY", "KIRKY_DISCORD_TOKEN"}
                    },
                    "KIRKY_STABLE_EXE": str(self.stable_exe),
                    "KIRKY_STABLE_DB": str(self.stable_db),
                },
                timeout=6,
                capture_output=True,
                creationflags=0x08000000,
            )
        except (OSError, subprocess.TimeoutExpired) as error:
            raise ValueError("Exclusive quota could not be verified") from error
        if check.returncode:
            raise ValueError(
                "Stable Pai is active or exclusive quota could not be verified"
            )

    @classmethod
    def load(cls, root: Path) -> "Handover":
        config = json.loads(
            (root / "quota-handover.json").read_text(encoding="utf-8-sig")
        )
        if (
            not isinstance(config, dict)
            or config.get("operator_verified_exclusive") is not True
        ):
            raise ValueError("Exclusive quota handover is not approved")
        paths = tuple(
            Path(config[k]).resolve(strict=True) for k in ("stable_exe", "stable_db")
        )
        if any(p.is_relative_to(root) for p in paths):
            raise ValueError("Stable and experimental files must be separate")
        return cls(*paths)

    def seed(self, target: Archive, extra: list[list]) -> None:
        self.verify_exclusive()
        cutoff = _utc_text(datetime.now(UTC) - timedelta(days=1))
        with closing(
            sqlite3.connect(self.stable_db.as_uri() + "?mode=ro", uri=True)
        ) as source:
            source.execute("PRAGMA query_only=ON")
            attempts = source.execute(
                "SELECT route,occurred_at,tokens FROM model_attempts ORDER BY rowid",
            ).fetchall()
            blocks = source.execute(
                "SELECT route,until_at FROM model_backoff ORDER BY route"
            ).fetchall()
        digest = sha256(json.dumps((attempts, blocks, extra)).encode()).hexdigest()
        self.verify_exclusive()
        with closing(target.connect()) as db, db:
            db.execute("BEGIN IMMEDIATE")
            db.execute(
                "CREATE TABLE IF NOT EXISTS quota_handover_seed_v1 (digest TEXT PRIMARY KEY)"
            )
            if existing := db.execute(
                "SELECT digest FROM quota_handover_seed_v1"
            ).fetchone():
                if existing[0] != digest:
                    raise ValueError(
                        "Previous quota handover no longer matches its source"
                    )
                return
            db.executemany(
                "INSERT INTO model_attempts VALUES(?,?,?)",
                (r for r in (*attempts, *extra) if r[1] >= cutoff),
            )
            db.executemany(
                """INSERT INTO model_backoff VALUES(?,?) ON CONFLICT(route)
                   DO UPDATE SET until_at=max(until_at,excluded.until_at)""",
                blocks,
            )
            db.execute("INSERT INTO quota_handover_seed_v1 VALUES (?)", (digest,))

    def guard(self, route: ProviderRoute) -> ProviderRoute:
        async def guarded(request: ModelRequest):
            try:
                await asyncio.to_thread(self.verify_exclusive)
            except ValueError as error:
                raise ProviderUnavailable("Exclusive quota check failed") from error
            return await route.complete(request)

        return replace(route, complete=guarded)
