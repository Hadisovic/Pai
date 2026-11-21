# Durable handoff state

- Active task: P4.1, free-only, capability-aware routing and persistent quota reservations.
- Active branch: `codex/P4.1-provider-safety` (base: `codex/P3.4-privacy-controls`, [PR #23](https://github.com/Hadisovic/Pai/pull/23)).
- Changed `docs/PROVIDER-EVIDENCE.md`, `src/pai/model_router.py`, `src/pai/storage.py`, `tests/test_model_router.py`. The model interface skips incompatible or unverified routes and accounts for requests and tokens in rolling windows. Timeouts and 429s persist cooldowns in SQLite.
- Resume: verify remote SHA and CI, then implement the Groq text/vision adapter and same-provider free text fallback with mocked HTTP (P4.2).

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
| 2026-11-21 | P2.2 | DONE | `codex/P2.2-sqlite-ingestion` | `aedea2b205010f3f7e8afc050f2f0a41dd3b1e34` | Ruff lint, formatting, pytest (19 tests), diff check, and [CI](https://github.com/Hadisovic/Pai/actions/runs/44915500591) passed.  |
| 2026-11-21 | P2.3 | DONE | `codex/P2.3-edits-deletes-retention` | `e8e76e0278ea6d7c71dd05a5fddac575bc66db7b` | Ruff lint, formatting, pytest (23 tests), diff check, and [CI](https://github.com/Hadisovic/Pai/actions/runs/44915751232) passed.  |
| 2026-11-21 | P2.4 | DONE | `codex/P2.4-mention-and-context` | `275b737f946cde62d9662e1c443846b305ed181b` | Ruff lint, formatting, pytest (33 tests), diff check, and [CI](https://github.com/Hadisovic/Pai/actions/runs/44915923499) passed.  |
| 2026-11-21 | P3.1 | DONE | `codex/P3.1-fts-index` | `731a7b9a8fe752aae25952133dd0f06a9e1555e0` | Ruff lint, formatting, pytest (34 tests), diff check, and [CI](https://github.com/Hadisovic/Pai/actions/runs/44916046542) passed.  |
| 2026-11-21 | P3.2 | DONE | `codex/P3.2-retrieval-and-provenance` | `7aee93389057101db930f6e33c064812f8c7697f` | Ruff lint, formatting, pytest (37 tests), diff check, and [CI](https://github.com/Hadisovic/Pai/actions/runs/44916209251) passed.  |
| 2026-11-21 | P3.3 | DONE | `codex/P3.3-shared-style` | `25488fbb163ac02eb237f221c6b04c05122df865` | Ruff lint, formatting, pytest (38 tests), diff check, and [CI](https://github.com/Hadisovic/Pai/actions/runs/44916397118) passed.  |
| 2026-11-21 | P3.4 | DONE | `codex/P3.4-privacy-controls` | `b6387203b711bfd76630fed5456409e73ff39e78` | Ruff lint, formatting, pytest (41 tests), diff check, and [CI](https://github.com/Hadisovic/Pai/actions/runs/44916639967) passed.  |
| 2026-11-21 | P4.1 | IN_PROGRESS | `codex/P4.1-provider-safety` | See next checkpoint for verified SHA | Ruff lint, formatting, pytest (44 tests) and diff check passed. CI pending. No provider network calls or model account. Discord connection remains untested. |
