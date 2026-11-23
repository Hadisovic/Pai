# Testing and launch evidence requirements

## Before accounts
Use fake Discord gateway/events, fake AI providers, temp SQLite databases and synthetic message/media fixtures. No live credentials for CI or unit tests. Record commands and actual output; never fake successful tests.

## Test matrix
- **Trigger:** direct mention vs plain messages, replied-to text, self and other bot messages, simultaneous mentions, authorized slash commands.
- **Authorization:** allowlisted guild/channel, disabled channel, missing consent, inaccessible channel, mixed member permissions and quoted references.
- **Database:** duplicate deliveries, message edits/deletes, restart, concurrent ingest, migrations, FTS updates, storage/retention.
- **Context:** correct author ID, reply chain resolution, recent window, historical search relevance, supporting source links, avoiding joke-as-fact.
- **Media:** image text, reaction GIF motion, stickers, cache reuse, expire/remove, malicious URL, oversize media, corrupted bytes.
- **Provider:** 429/timeouts, rate-limit counters, fallback capability, no paid endpoint, privacy minimization and prompt injection.
- **Privacy:** `/privacy`, `/memory`, `/forgetme`, export/delete, admin scope, backups and source-dependent memory invalidation.
- **Deployment:** connection/reconnection, host restart, measured RAM/disk, durable SQLite, free renewal, provider quota and restore drill.

## Checkpoints
For every implemented task save in STATUS.md: task identifier, branch, change, exact commands and outcomes, remote SHA verification, unresolved bugs and next action. PR descriptions include evidence. Don't use GitHub Actions as a forever-running bot host.

## Production go/no-go
- User and server members explicitly approve scope/notice.
- No billed accounts or paid fallbacks.
- Provider/host actual terms documented with dates.
- Bot token and AI keys stored in environment or host secrets (never Git).
- Restart persistence and deletion flow verified.
- End-to-end mention/image/GIF/recall tests pass.
- User approves deployment and any required manual free-plan renewals.

## Offline end-to-end replay

`uv run --offline --locked pytest -q tests/test_end_to_end.py` exercises the
production dispatcher, archive, recall, prompt creation and media decoder.
Synthetic messages replace Discord events and deterministic stubs replace
downloads and model inference. The scenario covers silent archive,
restricted-channel rejection, historical recall with a jump link, three
ordered GIF frames, and removal from search after Discord deletion.
Actual permissions, Gateway behavior, live model quality and host capacity
still require the approved pilot.

## Held-out conversation replay

`uv run --offline --locked pytest -q tests/test_production_replay.py` uses
synthetic Discord events and a stub model on the production gateway,
SQLite, prompt and reply path. It checks silent ingestion, consent,
native reply targets, current-speaker recall and citation isolation.
It also exercises the evidence limit of long reply chains.

For a transcript from the approved Qwen Free route, provide the Free
key through `PAI_GROQ_KEY` and give the runner a separate private quota
ledger. The live bot's config and archive are unnecessary.

```powershell
uv run --offline --locked python -m pai.production_benchmark --groq-free --quota-db /private/path/pai-replay-quota.sqlite
```

Review each transcript for grounded humor, literal vs playful intent,
recovery from corrections, tone changes, and the requested language.
The runner prints actual replies for review without scoring tone.
