# Durable handoff state

- Active task: P1.2, free model and privacy evidence.
- Active branch: `codex/P1.2-free-provider-research` (base: `codex/P1.R-open-source-review`, [PR #12](https://github.com/Hadisovic/Pai/pull/12)).
- Changed `docs/PROVIDER-EVIDENCE.md`, `PLAN.md` and `STATUS.md`. Groq is the first synthetic multimodal candidate. Independent OpenRouter fallback is conditional on a free privacy-compatible route. Gemini is synthetic-only under the observed free terms.
- Resume: verify remote SHA and CI. Then research no-card host candidates in P1.3. Live model quality, free account eligibility and exact limits remain unverified.

## Checkpoint log

| Date | Task | Status | Branch | Commit / verified remote SHA | Checks and blockers |
| --- | --- | --- | --- | --- | --- |
| 2026-11-21 | P0.1 | DONE | `codex/P0.1-project-baseline` | `c3f8f6f8710fba1fd60756b2b1ee50023c1f37c3` | Clean `uv sync --locked --python 3.12` installed 8 packages. `uv run --locked ruff check .`, `uv run --locked ruff format --check .`, `uv run --locked pytest -q` (1 passed), and `git diff --check` passed. [GitHub CI](https://github.com/Hadisovic/Pai/actions/runs/44914344412) passed on Python 3.12 and 3.13. |
| 2026-11-21 | P0.2 | DONE | `codex/P0.2-mock-smoke` | `cbf1f5c10ade0ba9a6dc0321e38a99053e334569` | Locked sync, lint, formatting and diff check passed. Full pytest passed (3 tests). Offline smoke passed (2 tests). [GitHub CI](https://github.com/Hadisovic/Pai/actions/runs/44914472585) passed on Python 3.12 and 3.13. |
| 2026-11-21 | P1.1 | DONE | `codex/P1.1-discord-research` | `a60511d6c4bf14c232a99f2d3696d5127e71ee12` | Official Discord API and policy findings documented. Ruff lint, formatting, pytest (3 tests), diff check and [CI](https://github.com/Hadisovic/Pai/actions/runs/44914612930) passed. Live application access remains unverified. |
| 2026-11-21 | P1.R | DONE | `codex/P1.R-open-source-review` | `82d0ac657c887ed9d2643e5447286f8fd4bb72a6` | GitHub reuse assessment and decision recorded. Ruff lint, formatting, pytest (3 tests), diff check, and [CI](https://github.com/Hadisovic/Pai/actions/runs/44914791325) passed. |
| 2026-11-21 | P1.2 | IN_PROGRESS | `codex/P1.2-free-provider-research` | See next checkpoint for verified SHA | Official provider requirements and public OpenRouter catalog inspected. Ruff lint, formatting, pytest (3 tests) and diff check passed. CI pending. Live free plan, quality and privacy settings pending user-controlled credentials. |
