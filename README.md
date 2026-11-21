# Pai — Discord AI Companion

Pai is a friendly Discord companion in development. The project starts with local development and synthetic tests.

## Product contract
- Observe and archive messages only in explicitly allowlisted channels after members are informed and consent is configured. No DMs or other servers.
- Respond **only on direct bot mentions** or explicit authorized slash commands. Understand Discord reply chains, nearby context, and user attribution.
- English-first replies with occasional Arabic/Arabizi comprehension if supported. Personality starts friendly and develops naturally from the group's humor; teasing should be light, responsive to feedback, and never forced.
- Searchable long-term message archive, evidence-backed memories, selective image/GIF/sticker handling, cached meme understanding.
- **Zero-cost and no billing information** are hard product constraints. Free 24/7 hosting is a goal, not a guarantee; validate provider terms and renewals rather than claiming permanent uptime.
- Build with Codex using small verified and remotely pushed checkpoints. No secrets, conversation dumps, attachments or databases in Git.

## Read in order
1. [Agent checkpoint protocol](AGENTS.md)
2. [Roadmap](PLAN.md)
3. [Current status](STATUS.md)
4. [Architecture](docs/ARCHITECTURE.md)
5. [Detailed requirements](docs/REQUIREMENTS.md)
6. [Provider research gates](docs/PROVIDERS.md)
7. [Testing and launch](docs/TESTING.md)
8. [Codex start prompt](CODEX_START_PROMPT.md)

## Local development

Use Python 3.12 or newer and uv 0.12.21. From the repository root:

```sh
uv sync --locked --python 3.12
uv run --locked ruff check .
uv run --locked ruff format --check .
uv run --locked pytest -q
```

Development and CI use the committed lockfile. The baseline needs no Discord
account, token, or AI credentials. See [the roadmap](PLAN.md) for live setup prerequisites.


## Privacy
Repository should preferably be **private**. Never commit private chat logs, AI API keys, tokens, databases, caches, logs, screenshots or identifiable member information. Keep operational data in private off-repo storage. Read-only publicly visible planning documentation contains no server credentials.

## Non-goals
No fine-tuning on member messages, voice recording, unsolicited responses, DM monitoring, bypassing Discord permissions, or paid APIs.
