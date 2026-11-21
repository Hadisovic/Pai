# Pai pilot and launch runbook

## Current readiness

The offline replay, restore drill, diagnostics, and dependency audit have
been exercised. Pai has no approved live deployment. The remaining gates
are a card-free model quality check, an approved host pilot, real Discord
permission and media checks, member consent, and the owner's decision to
launch. See [status and verified checkpoints](../STATUS.md).

## Prepare an isolated pilot

1. Review the stacked pull requests from their declared bases. Merge only
   with the owner's approval.
2. Use a dedicated Discord bot application in a test server with synthetic
   conversations and fixtures. Set narrow channel overwrites and grant
   only the documented permissions. Enable the privileged message content
   intent only for the authorized purpose. Confirm bot permissions,
   requester permissions and the audience for historical replies.
   [Discord setup and permissions](DISCORD.md)
3. Complete the member notice, obtain active consent, and provision the
   private policy. Check the actual data handling of the host and model
   before enabling either. Inject keys from an owner-controlled secret
   store. Never paste them into chat or add them to GitHub.
   [Member notice](MEMBER-NOTICE.md), [setup](SETUP.md)
4. Run `uv sync --locked --python 3.12`, `uv audit --locked` and
   `uv run --offline --locked python -m pai --doctor`. SQLite 3.42+ with
   FTS5 and secure-delete is required. Maintain free disk space for the
   live archive, its journal and a temporary restore.
5. Confirm the Groq organization is Free with no billing information or
   paid credits and has the stated ZDR settings. Use the synthetic-only
   benchmark to check rates, Arabic comprehension, humor, memory, vision
   and latency. Select live models only on evidence. Do not route to an
   unverified fallback. [Provider evidence](PROVIDER-EVIDENCE.md),
   [benchmark instructions](BENCHMARK.md)

## Check the pilot

- Begin in archive-only mode. Verify a normal message is silently saved,
  a duplicate is ignored, and an unauthorized guild/channel/member or a
  DM is excluded. Check edits, deletion, export, opt-out and restart.
- When approved, turn on model replies and media processing. Verify a
  direct mention gets a contextual reply, a reply ping alone is ignored,
  a historical answer has a correct jump link, and a GIF reply uses
  the correct animated source. Deny History access and verify no
  historical quote. Invalidate a source during generation and check the
  answer is discarded. Test exhausted quotas while ingestion continues.
- Verify host sign-up remains card-free. Capture documented and actual
  renewal frequency, outbound Discord/model reachability, disconnect and
  resume, idle and peak RSS, disk usage, forced restart and redeploy
  persistence. Do not treat a short successful test as an uptime
  guarantee. [Hosting shortlist and acceptance](HOSTING.md)
- Exercise an encrypted restore using synthetic data. Prove both
  retention and erasure survive and record where the key, backups,
  current consent, and erasure records are kept.
  [Backup and recovery](BACKUP.md)
- Record date, release SHA, provider/model and organization plan, hosting
  renewal policy and test outcomes without personal data or secrets.
  Complete production launch only after owner approval.

## Operate and recover

The health command is local and prints no IDs or paths. Runtime logs report
gateway status and generic failure events. Use host process supervision and
operational alerts appropriate to the selected Free plan. Check any manual
renewal, disk allocation, model limits, privacy settings and recent backups
before each renewal window. Downtime can leave permanent gaps in history.

If access, privacy, or billing state becomes uncertain, stop the process.
Remove provider enablement for an archive-only return, or disable collection
and apply the current private policy. Resolve permission or billing issues
before reconnecting. If the clean archive is lost, restore to a new file
with the current erasure checkpoint, check scope and restore results, and
choose the replacement with the owner. Use a clean archive when the latest
erasure record cannot be trusted.

## Reproduce the current checks

```sh
uv sync --locked --python 3.12
uv run --locked ruff check .
uv run --locked ruff format --check .
uv run --offline --locked pytest -q
uv audit --locked
uv run --offline --locked python -m pai --doctor
uv run --offline --locked python -m pai.benchmark
```

The 2026-11-21 locked audit flagged Pillow 12.3.0 and cryptography 49.0.0.
The following audit found no known vulnerabilities or adverse project
statuses across 23 packages after upgrading to Pillow 13.0.0 and
cryptography 50.0.2. This is a point-in-time result. The GitHub matrix
also tests the locked install on Python 3.12 and 3.13.
[Pillow release](https://pypi.org/project/Pillow/13.0.0/),
[cryptography release](https://pypi.org/project/cryptography/50.0.2/)
