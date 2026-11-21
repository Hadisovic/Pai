# Architecture and data model

## Event flow
1. Discord gateway events from **allowlisted guilds/channels** -> privacy/consent gate -> idempotent SQLite ingestion. **Zero AI calls** for ordinary text messages.
2. Direct bot mention -> resolve referenced reply chain and bounded recent channel window -> authorized FTS5 retrieval -> selective relevant media interpretation -> free-provider model router -> short natural English reply.
3. Feedback/correction -> auditable memory candidate or personality adjustment; do not rewrite original messages.
4. Occasional quota-limited maintenance -> evidence-linked summaries, cached meme descriptions, retention and deletion processing.

## Proposed Python modules
`bot/discord_gateway.py`, `bot/policy.py`, `bot/config.py`, `bot/storage.py`, `bot/memory.py`, `bot/retrieval.py`, `bot/personality.py`, `bot/model_router.py`, `bot/providers/{gemini,groq,openrouter}.py`, `bot/media.py`, `bot/commands.py`, `bot/observability.py`.

## SQLite schema sketch
- `guild_config(guild_id, enabled, retention_days, notice_version, ...)`
- `channel_allowlist(guild_id, channel_id, enabled, ...)`
- `messages(message_id PRIMARY KEY, guild_id, channel_id, author_id, author_display, reply_to_id, text, created_at, edited_at, deleted_at, ...)`
- `message_fts`: FTS5 index of currently authorized/nondeleted message text
- `media(media_id, message_id, kind, external_id, mime, fingerprint, availability, ...)`
- `media_analysis(media_id, model_id, descriptor, evidence, created_at, expires_at, ...)`
- `memory_items(memory_id, scope, text, kind, confidence, status, created_at, revised_at, expires_at, ...)`
- `memory_sources(memory_id, message_id)`
- `feedback(feedback_id, author_id, scope, target_id, type, created_at, ...)`
- `provider_usage(provider, model, date, requests, tokens, failures, ...)`
- versioned migrations and indices.

## Ground truth and retrieval
Original messages are ground truth; AI-inferred memories are separate, labeled, reversible and linked to supporting messages. Never promote jokes or sarcasm to facts. Search prefers current mention, referenced message and parent reply chain, recent authorized same-channel context, then relevant older authorized FTS matches. Rank time/relevance and deduplicate, respecting channel visibility on **every retrieval**, not just ingestion. Never send full server archives to a model.

## Media
Record attachment and embed metadata first; avoid immediate vision calls for most messages. Analyze only when directly mentioned or selective policy says worthwhile. Sample 3–5 frames as a starting heuristic for short GIFs, adapting to content while enforcing limits. Cache descriptions with source IDs and delete derived analyses when the source is erased. URLs may expire; re-fetch only through authorized Discord APIs; external media might disappear.

## Reliability
Bound queues, prompt sizes, image pixels, downloads, disk and RAM; target low-resource free hosting with actual profiling. SQLite WAL + safe migrations, reconnection and idempotent writes, daily free request caps, 429 backoff and capability-aware fallback. Keep encrypted private backups off-repo and test restore. No invented guaranteed 24/7 uptime.

## Threat model
Discord messages/media descriptions are untrusted instructions. Prevent prompt injection, accidental token disclosure, cross-channel/cross-user privacy leaks, server-wide scraping, unsafe image URL fetches, unauthorized slash commands and vendor data oversharing. No DMs or private channel ingestion without explicit policy.
