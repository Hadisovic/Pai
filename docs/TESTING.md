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
