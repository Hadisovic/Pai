# Durable handoff state

- Active task: P2.2, versioned SQLite archive wired to Discord message creates.
- Active branch: `codex/P2.2-sqlite-ingestion` (base: `codex/P2.1-discord-authorization`, [PR #16](https://github.com/Hadisovic/Pai/pull/16)).
- Changed `docs/SETUP.md`, `src/pai/storage.py`, `src/pai/discord_gateway.py`, `src/pai/__main__.py`, `tests/test_archive.py`, `tests/test_discord_gateway.py`. Archive uses UTC, stores full-range Discord IDs as text, deduplicates, and stores scoped reply references.
- Resume: verify remote SHA and CI, then add raw edits, deletions and retention (P2.3). Keep live collection off until privacy controls and pilot approval.

## Checkpoint log

| Date | Task | Status | Branch | Commit / verified remote SHA | Checks and blockers |
| --- | --- | --- | --- | --- | --- |
| 2026-11-21 | P0.1 | DONE | `codex/P0.1-project-baseline` | `c3f8f6f8710fba1fd60756b2b1ee50023c1f37c3` | Clean `uv sync --locked --python 3.12` installed 8 packages. `uv run --locked ruff check .`, `uv run --locked ruff format --check .`, `uv run --locked pytest -q` (1 passed), and `git diff --check` passed. [GitHub CI](https://github.com/Hadisovic/Pai/actions/runs/44914344412) passed on Python 3.12 and 3.13. |
| 2026-11-21 | P0.2 | DONE | `codex/P0.2-mock-smoke` | `cbf1f5c10ade0ba9a6dc0321e38a99053e334569` | Locked sync, lint, formatting and diff check passed. Full pytest passed (3 tests). Offline smoke passed (2 tests). [GitHub CI](https://github.com/Hadisovic/Pai/actions/runs/44914472585) passed on Python 3.12 and 3.13. |
| 2026-11-21 | P1.1 | DONE | `codex/P1.1-discord-research` | `a60511d6c4bf14c232a99f2d3696d5127e71ee12` | Official Discord API and policy findings documented. Ruff lint, formatting, pytest (3 tests), diff check and [CI](https://github.com/Hadisovic/Pai/actions/runs/44914612930) passed. Live application access remains unverified. |
| 2026-11-21 | P1.R | DONE | `codex/P1.R-open-source-review` | `82d0ac657c887ed9d2643e5447286f8fd4bb72a6` | GitHub reuse assessment and decision recorded. Ruff lint, formatting, pytest (3 tests), diff check, and [CI](https://github.com/Hadisovic/Pai/actions/runs/44914791325) passed. |
| 2026-11-21 | P1.2 | DONE | `codex/P1.2-free-provider-research` | `c4fbcbb6d91504af16f05c09a175468e0fc83783` | Official provider research and unauthenticated OpenRouter catalog check completed. Ruff lint, formatting, pytest (3 tests), diff check, and [CI](https://github.com/Hadisovic/Pai/actions/runs/44914911794) passed. Live eligibility and quality pending. |
| 2026-11-21 | P1.3 | DONE | `codex/P1.3-no-card-hosting` | `83d5e709b9ea0176ea54de903f6a7e61a3f7e8c9` | Public no-card hosting comparison completed. Ruff lint, formatting, pytest (3 tests), diff check, and [CI](https://github.com/Hadisovic/Pai/actions/runs/44915021860) passed. Host runtime proof deferred to P6.1. |
| 2026-11-21 | P1.4 | DONE | `codex/P1.4-synthetic-benchmark` | `5296d3371e54eea701a33eb057619d45dbec2971` | Ruff lint, formatting, pytest (5 tests), diff check, and [CI](https://github.com/Hadisovic/Pai/actions/runs/44915171413) passed. Six unscored synthetic stub cases ran offline. P1.L live benchmark remains blocked. |
| 2026-11-21 | P2.1 | DONE | `codex/P2.1-discord-authorization` | `b11a59523ea2aecbc50ba45ce738373576d0719a` | Ruff lint, formatting, pytest (17 tests), diff check, and [CI](https://github.com/Hadisovic/Pai/actions/runs/44915312630) passed.  |
| 2026-11-21 | P2.2 | IN_PROGRESS | `codex/P2.2-sqlite-ingestion` | See next checkpoint for verified SHA | Ruff lint, formatting, pytest (19 tests) and diff check passed. CI pending. Offline startup reports collection disabled. No live Discord connection. |
