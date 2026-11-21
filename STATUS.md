# Durable handoff state

- Active task: P0.1 (IN_PROGRESS while GitHub CI is pending).
- Active branch: `codex/P0.1-project-baseline` (base: `main`).
- P0.1 files: `pyproject.toml`, `uv.lock`, `src/pai/__init__.py`, `tests/test_installation.py`, `.env.example`, `.github/workflows/ci.yml` and `README.md`.
- Discord, provider and hosting accounts are unconfigured. The public repository contains only code, documentation and synthetic development material.
- Resume: compare the remote branch to the local head, find its P0.1 pull request and verify the CI matrix. Record the verified implementation SHA, then continue from P0.2 on a stacked branch.

## Checkpoint log

| Date | Task | Status | Branch | Commit / verified remote SHA | Checks and blockers |
| --- | --- | --- | --- | --- | --- |
| 2026-11-21 | P0.1 | IN_PROGRESS | `codex/P0.1-project-baseline` | See next checkpoint for this commit's verified SHA | Clean `uv sync --locked --python 3.12` created the environment and installed 8 packages; `uv run --locked ruff check .` passed; `uv run --locked ruff format --check .` passed; `uv run --locked pytest -q` passed (1 test); `git diff --check` passed. The install test first failed with missing package metadata. CI requires the pushed commit. |
