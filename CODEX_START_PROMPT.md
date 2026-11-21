# Paste into Codex — Pai startup

You are implementing the Discord AI companion in https://github.com/Hadisovic/Pai.

FIRST read `AGENTS.md`, `README.md`, `PLAN.md`, `STATUS.md`, and all `docs/` material. These are authoritative and reflect agreed product choices.

Implement the roadmap in order, autonomously progressing through bounded tasks while permissions and context allow. Before each task, inspect git status/log/remote, fetch without clobbering local edits, and recover the earliest unfinished task. Implement, test, document real evidence, update PLAN.md and STATUS.md, scan for secrets, commit and PUSH, then VERIFY remote HEAD matches. Open a PR per coherent task, but DO NOT merge without approval. Never force-push or mark DONE on unverified work. If near limits, push an honest partial checkpoint and leave exact resume steps for another session.

Requirements: Friendly English-first social companion; understands some Arabic if model supports it; evolving natural playful humor; archives authorized new messages while silently observing; only responds when directly mentioned; recalls nearly all accessible historical text with provenance; tracks reply chains; selectively understands memes, images, stickers and sampled GIF frames; private-by-design with user access/forget/retention controls. No old-history import required because the server is new.

Strict budget: $0, no billing card/address, no paid AI endpoints. Hosting 24/7 is aspirational: verify renewal and reliability limits, never promise guarantees. Provider choices must be evidence-based with free text/vision tests and fallback support.

Start with P0.1/P0.2 mocked development baseline, no credentials or Discord connection needed. Proceed to P1 official provider/hosting research, then implement what is testable without secrets. Stop only on truly necessary user-only external steps, document precise blockers and continue other independent tasks if possible.


## Engineering freedom and open-source acceleration
The architecture and task sequence are starting proposals, **not strict implementation rules**. Make independent engineering choices that maximize quality and speed, provided the bot stays genuinely free with **no billing address/payment card**, preserves privacy, learns the group's humor, remembers conversations, handles relevant images/GIFs, and replies only on mention.

**Before writing the core from scratch, research existing open-source Discord AI bots and related memory/vision frameworks.** Evaluate maintenance, licensing, security, resource usage, free API compatibility, and how well they fit our requirements. Clone/fork/adapt permissively licensed projects where beneficial, keeping legal notices and attribution; otherwise implement from scratch. Avoid reinventing useful, well-tested components.

Explain your choice and any justified architecture/roadmap deviations in `docs/DECISIONS.md` or `STATUS.md`. Adjust the implementation plan when warranted, without silently dropping key features or the no-cost/no-billing constraint. Keep the existing push-test-verify checkpoint system mandatory.


## Current owner priority — actual launch
The owner explicitly wants Pai **operational**, not additional offline-only testing. Follow [P8 live deployment issue #40](https://github.com/Hadisovic/Pai/issues/40) as the active execution objective. Attempt real no-card hosting, free-model account and authenticated Discord test integration using available tools, requesting only unavoidable owner verification/consent, and keep checkpointing. Do not declare complete until the verified live acceptance conditions in #40 pass.
