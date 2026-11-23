# Pai Windows handoff

See [STATUS.md](STATUS.md) for the latest verified revision and outstanding checks. The Windows runtime uses the existing operator-provisioned test policy, the Groq Free route and SQLite with FTS5. The private working directory contains the configuration, live archive and encrypted backups.

## Active Test Deployment State (2026-11-23)

- **Active Checkpoint**: `54d578b` on branch `codex/P9-companion-conversations` (stacked on PR #41 / PR #42).
- **Process Status**: Single-instance bot daemon actively running and verified connected (`Discord gateway is ready`) at `C:\Users\Hadi\Documents\ChatGPT\New project\Pai-test-live-28bad66` using `pai.sqlite` in `C:\Users\Hadi\Documents\ChatGPT\New project\Pai`.
- **Pre-cutover Snapshot**: Encrypted backup verified at `backups/p9-personality-20261123-151036.pai`.
- **Core Fixes Implemented**:
  1. Methodological benchmark alignment: [scripts/run_production_benchmark.py](scripts/run_production_benchmark.py) executes genuine end-to-end production context, `build_prompt` JSON serialization, Groq API completion, and `render_answer` validation.
  2. Conversational pragmatics: Solved "distract me? pause" innuendo misinterpretation and natural recovery without robotic AI excuses ("my brain was buffering", "glitched", "dumb bot").
  3. Slang shorthand: Resolved internet/Discord shorthand like `smo` (someone) in gaming contexts without AI self-deprecation.
  4. Grounding: Fixed hallucinated past hostility; grounded replies strictly in real thread context.
  5. Emoji & flag recognition: Flag emojis (`🇵🇸`, `🇸🇦`) acknowledged with respect/vibe; never misinterpreted as insults or user names.
  6. Memory citations: Stated facts cite sources; unstated facts admitted casually with zero fake citations.
  7. Vision budget preserved: All prompt rules strictly constrained to <= 8,000 reserved tokens across 3 media frames.
  8. Authentic Production Benchmark Score: **140 / 140 (100.0%)** documented in [docs/PRODUCTION_BENCHMARK_REPORT.json](docs/PRODUCTION_BENCHMARK_REPORT.json).

For a single-instance Windows rollout:

1. Verify the target Git revision, locked install and doctor check. Keep the previous installed version available.
2. Stop the existing Pai connector if it is running. Confirm its process tree has exited before proceeding.
3. Create a fresh encrypted backup with the operator's existing backup key. Keep the existing policy, environment file, database and previous snapshots in place.
4. Start one bot with the private runtime paths, then confirm the Gateway ready signal and verify behavior in the authorized Discord test scope. If startup fails, stop the new process before restoring the previous release.

Use the tracked code-only bundle described in [docs/HOSTING.md](docs/HOSTING.md) for future authorized deployments. A legacy locally staged archive can contain private configuration and SQLite data. Keep it local. Enzonic provisioning and any production launch are separate from Windows test rollouts.
