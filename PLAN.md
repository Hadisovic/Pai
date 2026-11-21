# Pai Implementation Roadmap

Statuses: `TODO`, `IN_PROGRESS`, `BLOCKED`, `DONE`. A task is DONE only after its acceptance checks pass, a commit is pushed, and the remote branch SHA is verified. Record results in STATUS.md. Never treat planning completion as implemented functionality.

## P0 — Reproducible development baseline [DONE]
- **P0.1 [DONE]** Initialize Python 3.12+ project, `src/`, `tests/`, `pyproject.toml`, locked dependencies, `.env.example`, lint/format/tests, CI, and concise developer instructions. No credentials.
- **P0.2 [DONE]** Mock Discord gateway/events and fake AI providers; synthetic chat fixtures and a complete local smoke test independent of network or accounts.
- **Acceptance:** clean install; unit tests and CI pass; `git diff --check`; verified remote checkpoint.

## P1 — Free provider and hosting research [IN_PROGRESS]
- **P1.1 [DONE]** Confirm official Discord intent, bot permission, message content, edit/delete, reply reference, embed, attachment, sticker and rate-limit semantics.
- **P1.R [DONE]** Evaluate open-source foundations and dependency reuse before core implementation. Record the decision and license obligations.
- **P1.2 [DONE]** Verify current Gemini, Groq, OpenRouter free provider offerings, actual model IDs and text/vision capability, request and token limits, account/card restrictions, privacy/data-use and region rules. No paid accounts.
- **P1.3 [DONE]** Verify no-card hosting candidates Kerit Cloud, Bot-Hosting.net and FPS.ms and alternatives: RAM, storage, persistence, websockets, renewal, inactivity policy, uptime and backup. Claims are not proof.
- **P1.4 [DONE]** Build repeatable **synthetic** model benchmark for natural English conversation, humor, contextual recall, some Arabic comprehension and memes/GIFs. Never send real private messages without permission.
- **P1.L [BLOCKED]** Run live synthetic model calls and human scoring after the owner controls an approved card-free account. Continue independently with the mocked gateway, storage and retrieval.
- **Acceptance:** dated official links and decision matrix, verified or explicitly unknown free quotas, recommended primary text+vision, fallback, and host candidates. Real live tests require user-controlled credentials.

## P2 — Discord connection, authorization and ingestion [DONE]
- **P2.1 [DONE]** Connect with `discord.py` and minimal permissions. Persist allowlisted guild/channel IDs only after admin opt-in and member notice/consent, disabled by default.
- **P2.2 [DONE]** Store new messages in SQLite with UTC timestamps, immutable Discord IDs, author ID/display name, channel ID, reply linkage; deduplicate on reconnect. No history backfill needed.
- **P2.3 [DONE]** Process edits/deletions, expired/inaccessible media, storage budgets and retention; no leaks from disallowed channels.
- **P2.4 [DONE]** Direct mention gate: never reply on ordinary chat or bot-authored messages; resolve quoted/replied-to message and bounded recent context.
- **Acceptance:** opt-in, idempotency, restart persistence, ACL, mention gate and edit/delete tests. No AI call for normal ingestion.

## P3 — Long-term searchable memory [DONE]
- **P3.1 [DONE]** SQLite migrations, FTS5 for content search, indexes, safe queries. Introduce message-linked media metadata and cache in P5 alongside their invalidation rules.
- **P3.2 [DONE]** Source-backed retrieval of old messages plus conversational context, correct user attribution and Discord jump links. Verify viewing permissions before quoting.
- **P3.3 [DONE]** Source-linked, group-level conversation context and explicit style feedback, within the platform policy documented in docs/DISCORD.md; preserve supporting message IDs, inference status, confidence, corrections and expiry. Avoid treating sarcasm as factual profile.
- **P3.4 [DONE]** `/privacy`, `/memory`, `/forgetme`; admin configurable allowlist/retention; delete/export and backup-deletion policy. Ensure restricted-channel isolation.
- **Acceptance:** tests for history retrieval, provenance, cross-channel ACL, sarcasm, corrections, deleted memories, retention and account removal.

## P4 — Natural model-assisted conversation [DONE]
- **P4.1 [DONE]** Provider interface with model capabilities (text/image/frames), timeouts, quota counters, backoff and circuit breakers; reject all paid endpoints and unverified billing.
- **P4.2 [DONE]** Select primary/fallback from P1 evidence; route to compatible free provider only; on exhausted quotas give one brief notice while ingestion continues.
- **P4.3 [DONE]** Assemble bounded prompts from direct mention, reply chain, current channel context and authorized memory search; trim tokens, minimize sensitive content and provide provenance.
- **P4.4 [DONE]** Hybrid English-first personality; understand occasional Arabic/Arabizi where possible; naturally adapt to server humor, tease lightly, avoid repetitive catchphrases; support tone correction/feedback and resist chat prompt injection.
- **Acceptance:** deterministic fake-provider dialogue tests and human-scored quality, provider failover, data minimization and no cross-channel leaks.

## P5 — Images, memes, stickers and GIFs [DONE]
- **P5.1 [DONE]** Store Discord attachment IDs and metadata, embed/GIF provider links, original message context; enforce URL allowlists, MIME, size, pixel and time bounds. Avoid SSRF.
- **P5.2 [DONE]** Selectively analyze relevant images on mentions or explicitly approved importance rules; don't call AI for every attachment; stickers and custom emoji descriptions when feasible.
- **P5.3 [DONE]** Sample bounded meaningful GIF frames, preserve ordering/motion explanation, cache with fingerprint and provenance, reuse analysis for recurring memes.
- **P5.4 [DONE]** Re-fetch authorized media via message ID when URLs expire; handle removed/unavailable content honestly; invalidate caches on deletion/forget.
- **Acceptance:** synthetic still and animated fixtures, corrupted/oversize defense, no unrequested mass vision calls, analysis reuse and deletion safety.

## P6 — No-card hosting proof and resilience [IN_PROGRESS]
- **P6.1 [BLOCKED]** Test minimally sized host only with user approval/account. Verify egress/websocket, process restarts, RAM/storage limits, volume persistence and renewal restrictions. No false 24/7 promises.
- **P6.2 [IN_PROGRESS]** Health diagnostic, safe logs, secret redaction, per-user/per-guild limits, provider daily budget, graceful shutdown, reconnection and restart policies.
- **P6.3** Encrypted off-host private backup/export and restore drill. Never store live member data in GitHub, public CI artifacts or logs.
- **Acceptance:** verified host evidence, explicit downtime/renewal behavior, successful persistence/restore proof or recorded blocker.

## P7 — Consent, privacy review and launch [TODO]
- **P7.1** Provide member-facing consent/notice describing channel scope, recording, AI vendors, media handling, retention, deletion and opt-out. Do not ingest without authorization.
- **P7.2** E2E proof: ordinary chat archived silently; direct mention answered contextually; reply to meme/GIF analyzed; old joke retrieved with source; deletion and permission isolation pass.
- **P7.3** Security, provider quota/billing, persistent storage, backup, restart, operations and renewal runbook; user authorizes launch.
- **Acceptance:** verifiable E2E results and user approval; no claims without evidence.

## Later, not MVP
Optional richer dashboards, opt-in per-person profiles, embeddings if feasible under hard free limits, and additional guilds. No voice recording or unsolicited messages.

## Task procedure
Each task: inspect repository/STATUS -> implement limited scope -> run real checks -> write STATUS/PLAN -> scan for private data -> commit -> push -> verify remote SHA -> open evidence-backed PR -> continue. If interrupted, push partial `IN_PROGRESS` handoff and identify exact next step. Never force-push or auto-merge.
