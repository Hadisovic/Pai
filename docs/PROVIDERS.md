# Provider and hosting evaluation — research required

**Nothing here constitutes a verified deployment or a guarantee of current free limits.** Codex must check official, dated terms and run accessible tests. No account creation, billing information or payment.

## AI provider candidates

| Candidate | Why test | Required evidence |
|---|---|---|
| Google Gemini API | Text + images, reasoning, occasional Arabic comprehension | Current free model IDs, RPM/RPD/token quotas, region, card requirement, free data-use policy and retention |
| GroqCloud | Fast conversational text and potential fallback | Free model IDs, limits, capabilities (vision if offered), account requirements, privacy |
| OpenRouter free models | Model choice and optional fallback | Current free request ceilings, vision models, credits requirement, provider routing and privacy |

Use a model adapter so switching free providers requires config only. Capability-aware routing: never send a GIF/vision request to a text-only fallback. Cache media analysis and do not run LLM inference on every chat message.

### Model testing
Synthetic conversations and permissibly sourced memes/GIF fixtures only. Score: humor + fit (30%), memory accuracy (30%), natural English chat (25%), Arabic comprehension (10%), latency (5%). Keep raw anonymized/synthetic examples, model IDs, dates, token/request consumption, and evaluator observations. Model “winner” requires measured evidence; never claim universal best.

### Primary documentation
- https://discord.com/developers/docs
- https://ai.google.dev/gemini-api/docs/pricing
- https://console.groq.com/docs/rate-limits
- https://openrouter.ai/pricing

## No-billing hosting candidates

| Provider | Validate | Possible constraints |
|---|---|---|
| Kerit Cloud | Free no-card Discord bot process; memory/disk/websocket, renewals | Weekly renewal, plan availability, persistence |
| Bot-Hosting.net | Free Python bot hosting without card | Periodic manual renewal, credit/points limitations |
| FPS.ms | Free Python container | Small RAM/disk, renewals |
| Other alternatives | Card-free free compute with persistent background processes | Sleep, account eligibility, limited egress |

### Tests before deployment
Check no-card creation, exact plan and ToS, outbound Discord websocket, RAM/disk, permanent SQLite directory and restart survival, process supervision, automatic reconnect, renewal expiry, APIs, encryption/backup. A brief healthy interval does not prove guaranteed 24/7 uptime.

### Hosting documentation
- https://kerit.cloud/free-discord-bot-hosting/
- https://bot-hosting.net/
- https://fps.ms/free-discord-bot-hosting

## Decision rule
Prioritize **no billing card, no paid resources, reasonable memory and reliability** over claimed 24/7 marketing. If no provider satisfies all, record which requirement cannot be met and ask before changing it. Never quietly use Google/Oracle services requiring billing accounts.
