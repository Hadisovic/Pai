# Product requirements, personality and privacy

## Social personality
- Friendly English-first baseline; evolves slowly from server conversation styles, common slang, in-jokes and shared experiences. Understand some Arabic/Arabizi if the selected model can; output English unless explicitly requested otherwise.
- Humor is contextual and spontaneous, not forced. Playful teasing with boundaries; avoid hurtful targeting, pretending to be human, repeating catchphrases, excessive emoji or hallucinating memories.
- Learn from explicit tone feedback such as “you're doing too much”; avoid treating reactions or silence as certain approval.
- Track users by immutable Discord ID, not nickname alone. Distinguish jokes from claims. Every inferred memory is revisable and references actual messages.

## Discord access and behavior
- Observe only authorized allowlisted channels **after member notice/consent**. Archive messages even without mention, but reply only on **direct bot @mentions** or deliberate authorized slash commands.
- Ignore other bot messages, prevent loops, treat replies and nearby context as primary.
- New server: no historical backfill necessary.
- Persistent, searchable near-complete text archive while connected, subject to retention/deletion and storage ceilings. Cannot guarantee messages lost during outages, erased history or inaccessible content.

## Media
- Store image/GIF/sticker/custom emoji metadata and source message links.
- Selectively use vision-capable free AI for relevant memes and frames of animation when directly mentioned, or when explicitly policy-flagged; cache repeated interpretations.
- GIFs need ordered frames/motion where reasonable; acknowledge unknown or inaccessible media. No blanket AI analysis of every image.
- Don't store private media bytes indefinitely without explicit consent and secure storage.

## Privacy/security
- Server-admin explicit allowlist and off-by-default collection; member-facing disclosure and agreement. Never read DMs or unauthorized channels.
- `/privacy`, `/forgetme`, `/memory` under ACL; data export/deletion, retention, correction and source tracing. Deletion of original messages invalidates derived memory/cache in accordance with policy.
- Minimize data sent to external AI providers; document free-tier data handling before choosing a provider.
- Untrusted message text must never alter bot settings, reveal secrets or override instructions. Logs are redacted.
- No private user data, databases, tokens, chat logs, screenshots or backups in the code repository.

## Costs and hosting
- $0 monthly cost **without billing details** is mandatory as a selection constraint, not a guarantee of unlimited usage.
- No paid APIs, trials with automatic billing, forced credit purchases or cloud VM accounts needing billing address.
- Prefer continuously running free container; document daily/weekly manual renewals and operational limits.
- If free 24/7 cannot be proven, be explicit and prefer a candid limited-uptime option over surprise charges.

## Product acceptance
1. Normal messages from allowed channels stored silently with no AI requests.
2. Direct mention produces context-aware reply, correct speaker attribution, parent reply and recent history.
3. Past jokes retrieved from source messages without invented facts or leaking restricted channels.
4. A referenced meme and GIF can be interpreted if accessible; cached recurring media avoids redundant inference.
5. English replies with occasional Arabic comprehension if available.
6. Removed/edited messages and `/forgetme` propagate to search and derived context.
7. Model quota exhaustion keeps ingestion running and gives at most a concise reply.
8. Restart preserves consent, configuration and database; free host constraints documented.
