# Durable handoff state

## Current priority · P9 friend-group conversations (2026-11-22)

- The P9 branch starts from Antigravity's verified `e0cdaa7` checkpoint on `codex/P8-live-account-access`. Stack its PR on P8 [PR #41](https://github.com/Hadisovic/Pai/pull/41).
- Pai accepts authorized direct mentions and native same-channel replies to its own messages. Ordinary chat still passes through the silent archive gate. Short bursts use a bounded FIFO queue with up to two active channels. The verified Free route retains per-minute and daily budget checks and uses reported token usage to reconcile reservations.
- First-person recall uses the asking member's immutable Discord ID. Prompts use request-local speaker labels that preserve attribution through display-name collisions and renames. The voice uses recurring cross-member expressions as group context. Pai keeps no inferred per-person humor profiles.
- Recent Pai turns are transient and used only while their authorized sources are current. After a restart, native replies still trigger Pai and can use eligible human chat history. The exact prior Pai output requires that turn's in-process source tracking.
- Local validation passed 81 tests, Ruff, the SQLite/FTS5 doctor and a locked dependency audit. In the final synthetic model run, Groq Free completed seven calls using 4,777 reported tokens. Both favorite games were attributed correctly after a display-name collision and rename. Banter and sincerity were recognizable, while Arabic phrasing and continuity varied. The model recognized the yellow object in a three-frame GIF but invented an extra movement. The calls sent only synthetic data.
- The Windows deployment and Enzonic queue were left in place. The P9 Gateway behavior is covered by synthetic Discord events. For an authorized live rollout, use a controlled single-instance cutover in the existing test scope, then check mentions, ping-off replies, ordinary-chat silence, separate recall, and media. See [SESSION_HANDOFF.md](SESSION_HANDOFF.md) for the P8 baseline.

## Historical · P8 session pause checkpoint (2026-11-22)

Pai is fully online and active in Discord. Today's live development session is paused per owner instruction.

### Current Verified System State:
1. **Live Discord Bot**: Pai#6435 (Application ID `1573805310785880264`) is connected to Discord Gateway and actively serving the authorized test guild `|| Hadi ||'s server` (ID `823208040764538901`).
2. **Current Local Process**: Running continuously in background via PowerShell turnkey runner `scripts/start.ps1` (Task 868) with Python 3.12, SQLite 3.49.1 with FTS5, and Discord Gateway v10.
3. **Groq Model Router**: Live authenticated inference on Groq Free organization (`org_01k2z2yx9qepsr0gtb22mexw3r`) routing to `qwen/qwen3.8-27b` with sub-second response times.
4. **Natural Persona & Group Style**: Updated `prompts.py` and `reply_engine.py` to enforce natural casual banter, prohibiting generic assistantisms, mode announcements, and biological claims. Implemented `group_style` in `storage.py` and `conversation.py` with multi-author window partitioning (`author_rank = 1`). 76/76 automated tests pass.
5. **Enzonic Cloud Allocation**:
   - Free Python tier verified: 512 MiB RAM, 50% CPU (1 core), 10 GB disk tier, $0.00 cost, zero payment/card details required.
   - Server `Pai` created and currently queued in Enzonic's Standard Queue (Queue ID `9980`, Position `#121`).
   - Uptime terms: Official Enzonic product documentation explicitly advertises 24/7 always-on hosting without sleeping for Python Discord bots (general ToS inactivity rules apply to game servers). Runtime behavior will be verified directly once the node is assigned.
6. **Encrypted Backup & Storage**:
   - AES-256-GCM encrypted snapshot created at `backups/snapshot.pai`.
   - Random 32-byte backup key preserved in private `.env` (`PAI_BACKUP_KEY`).
   - Private database `pai.sqlite` preserved locally with full conversational history and memories.
7. **Staged Deployment**: Standalone bundle `deploy.zip` (39.7 KB) pre-staged and ready for direct upload to Enzonic Pterodactyl panel upon queue completion.
8. **Hosting Architecture Decision**: Kerit Cloud was evaluated and rejected due to its mandatory 24h Discord gate, daily heartbeat renewals, and offline free node. Enzonic allocation (Queue ID 9980) remains the designated cloud candidate, prioritizing stability and zero renewals over temporary workarounds. Local process (Task 868) serves as the persistent primary baseline.

### Outstanding Next Steps Upon Resume ("Resume Pai"):
1. Check Enzonic panel (`https://beta.panel.enzonic.com/` or `https://panel.enzonic.com/`) for server `Pai` container assignment.
2. Upload `deploy.zip` to the Pterodactyl File Manager and extract.
3. Inject `DISCORD_TOKEN` and `PAI_GROQ_KEY` in panel environment / startup settings.
4. Start the hosted cloud server.
5. Verify response from the hosted bot in `#moments`.
6. Terminate the local Windows bot (Task 868) cleanly to prevent duplicate gateway connections.
7. Confirm Pai continues operating 100% independently of the local PC.


### Live Discord Verification

On 2026-11-22, Pai was brought fully online and verified in the live Discord server (guild ID: 823208040764538901):
1. Discord Application Pai#6435 (ID: 1573805310785880264) joined with Message Content Intent enabled.
2. User consent policy configured in .pai-policy.json for consenting members (779984379836891136 and 605162723566813262).
3. Real-time mentions verified in #moments (ID: 1220389554289250526):
   - User Hash ✦ asked @Pai hello -> Pai replied Hey there! 👋.
   - User asked how are u nga @Pai -> Pai replied I’m good, thanks for asking! I just woke up, though. How are you doing?.
   - User tested companion role: @Pai I am testing u before putting u in my friends server -> Pai replied: Testing away! I'm ready when you are. Just let me know who I can be once I'm in.
4. Unmentioned messages (u should be natural af u feel me?) were archived silently to pai.sqlite without spamming or replying, exactly adhering to privacy and direct-mention gating rules.

### Known Deferred Issues (Post-MVP)

The following known issues are documented and explicitly deferred for future milestones:
1. **External GIF links (e.g. Klipy)**: External GIF URLs outside Discord's direct CDN/Giphy are not currently decoded for vision analysis.
2. **Custom Discord emojis/emotes**: Custom server emotes (`<:name:id>`) are stripped during prompt minimization and not semantically understood.
3. **Implicit replies without mentions**: Discord reply chains where Pai is replied to without an explicit `@Pai` mention tag do not trigger an automatic response under the strict direct-mention gate.

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
| 2026-11-21 | P4.1 | DONE | `codex/P4.1-provider-safety` | `6f065ddad5f19501adeaeb82325df206c0f9bff0` | Ruff lint, formatting, pytest (44 tests), diff check, and [CI](https://github.com/Hadisovic/Pai/actions/runs/44916783466) passed.  |
| 2026-11-21 | P4.2 | DONE | `codex/P4.2-groq-adapter` | `b552ea3ae2d62adf722004de45d3003dc1f7fc7f` | Ruff lint, formatting, pytest (47 tests), diff check, and [CI](https://github.com/Hadisovic/Pai/actions/runs/44916968582) passed.  |
| 2026-11-21 | P4.3 | DONE | `codex/P4.3-bounded-prompts` | `7ef9c9fa92dd47bbc62685b3fea3f44d3783e915` | Ruff lint, formatting, pytest (49 tests), diff check, and [CI](https://github.com/Hadisovic/Pai/actions/runs/44917104590) passed.  |
| 2026-11-21 | P4.4 | DONE | `codex/P4.4-personality-and-replies` | `8e954f01de1f1244e68342aa05c96ace306c7c7b` | Ruff lint, formatting, pytest (51 tests), diff check, and [CI](https://github.com/Hadisovic/Pai/actions/runs/44917267765) passed.  |
| 2026-11-21 | P5.1 | DONE | `codex/P5.1-media-boundaries` | `99604c5e3b428ce3fe291ef8a2b345c68e67e932` | Ruff lint, formatting, pytest (63 tests), diff check, and [CI](https://github.com/Hadisovic/Pai/actions/runs/44917468577) passed.  |
| 2026-11-21 | P5.2 | DONE | `codex/P5.2-selective-still-vision` | `cc99ab684c6af274cd2a331e6617c1d7b7430f6b` | Ruff lint, formatting, pytest (64 tests), diff check, and [CI](https://github.com/Hadisovic/Pai/actions/runs/44917634053) passed.  |
| 2026-11-21 | P5.3 | DONE | `codex/P5.3-gif-and-cache` | `a60c335405da51805fd37768980cf1aa65699abd` | Ruff lint, formatting, pytest (67 tests), diff check, and [CI](https://github.com/Hadisovic/Pai/actions/runs/44917952870) passed.  |
| 2026-11-21 | P5.4 | DONE | `codex/P5.4-refresh-and-invalidation` | `3dc5596c8dfbd3a52e7b8c176ecf7cb65494293c` | Ruff lint, formatting, pytest (69 tests), diff check, and [CI](https://github.com/Hadisovic/Pai/actions/runs/44918154107) passed.  |
| 2026-11-21 | P6.2 | DONE | `codex/P6.2-runtime-reliability` | `682a35027ffec77c0fdc620be87b0c9cae87cc3a` | Ruff lint, formatting, pytest (71 tests), diff check, and [CI](https://github.com/Hadisovic/Pai/actions/runs/44918341393) passed.  |
| 2026-11-21 | P6.3 | DONE | `codex/P6.3-encrypted-restore` | `2bc855465c6cff47f040acfd976cc732c7fe11a0` | Ruff lint, formatting, pytest (73 tests), diff check, and [CI](https://github.com/Hadisovic/Pai/actions/runs/44918539920) passed.  |
| 2026-11-21 | P7.1 | DONE | `codex/P7.1-member-notice` | `c3783e292c832369b06e7665fb391d7a1062aa9c` | Ruff lint, formatting, pytest (73 tests), diff check, and [CI](https://github.com/Hadisovic/Pai/actions/runs/44918619053) passed.  |
| 2026-11-21 | P7.2a | DONE | `codex/P7.2a-offline-end-to-end` | `fbb82b3a931ba02b6ea8aac3a84ad493931b3231` | Ruff lint, formatting, pytest (74 tests), diff check, and [CI](https://github.com/Hadisovic/Pai/actions/runs/44918767018) passed.  |
| 2026-11-21 | P7.3 | DONE | `codex/P7.3-launch-readiness` | `3989da3241b328fae8ffde2fb4a98d88c133b416` | Ruff lint, format, pytest (75 tests), diff check, runtime doctor and offline six-case benchmark passed. Locked audit found no known vulnerabilities or adverse package statuses in 23 packages. [GitHub CI](https://github.com/Hadisovic/Pai/actions/runs/44941578162) passed on Python 3.12 and 3.13. |
| 2026-11-21 | P1.L | DONE | `codex/P8-live-account-access` | Verified live Groq Qwen3.8-27b | Real authenticated inference passed 6/6 synthetic cases (English, humor, memory, Arabic, meme vision, 3-frame GIF). |
| 2026-11-22 | P6.1 / P8.2 | IN_PROGRESS | `codex/P8-live-account-access` | Enzonic server Pai queued (#122) | Free 512 MiB allocation verified ($0/card-free). Server in node queue. Inactivity sleep terms documented. Local bot running continuously as primary until cloud activation. |
| 2026-11-21 | Stack integration | DONE | `main` | `ec9834e0e62139b1f0dae206c34becf6236a8408` | Verified dependencies, file scopes and per-PR CI. Merged #36 through #9 to their declared parents. The final main tree and CI passed. |
| 2026-11-21 | P6.1a | DONE | `main` | `9c4d5434311b4af40295c9776cbb03f04cd63dd7` | Ruff, formatting, pytest (75), [Windows/Linux synthetic task via PR #37](https://github.com/Hadisovic/Pai/pull/37), [Linux host smoke](https://github.com/Hadisovic/Pai/actions/runs/44942850593) and [main CI](https://github.com/Hadisovic/Pai/actions/runs/44943143660) passed. Public Gateway only. |
| 2026-11-21 | P1.La | DONE | `main` | `3cc31f63d5d098def4438deb2817ca177d795519` | Ruff, formatting, pytest (75), and [12 real synthetic completions on Linux](https://github.com/Hadisovic/Pai/actions/runs/44942991533) passed. Two public models, SHA-256 checks and no provider account. |
