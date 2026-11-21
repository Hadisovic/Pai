# Durable handoff state

- Active task: P0.2 (IN_PROGRESS while GitHub CI is pending).
- Active branch: `codex/P0.2-mock-smoke` (base: `codex/P0.1-project-baseline`, [PR #9](https://github.com/Hadisovic/Pai/pull/9)).
- P0.2 files: `src/pai/mock_gateway.py`, `tests/test_mock_gateway.py`, and `README.md`.
- Discord, provider and hosting accounts are unconfigured. The public repository contains only code, documentation and synthetic development material.
- Resume: compare the P0.2 remote SHA to its local head, check its CI matrix, record the verified SHA, and continue with P1.1 official Discord research from that branch.

## Checkpoint log

| Date | Task | Status | Branch | Commit / verified remote SHA | Checks and blockers |
| --- | --- | --- | --- | --- | --- |
| 2026-11-21 | P0.1 | DONE | `codex/P0.1-project-baseline` | `c3f8f6f8710fba1fd60756b2b1ee50023c1f37c3` | Clean `uv sync --locked --python 3.12` installed 8 packages. `uv run --locked ruff check .`, `uv run --locked ruff format --check .`, `uv run --locked pytest -q` (1 passed), and `git diff --check` passed. [GitHub CI](https://github.com/Hadisovic/Pai/actions/runs/44914344412) passed on Python 3.12 and 3.13. |
| 2026-11-21 | P0.2 | IN_PROGRESS | `codex/P0.2-mock-smoke` | See next checkpoint for this commit's verified SHA | Locked sync, lint, formatting and `git diff --check` passed. `uv run --locked pytest -q` passed (3 tests). `uv run --offline --locked pytest -q tests/test_mock_gateway.py` passed (2 smoke tests). No account or service required. CI pending. |
