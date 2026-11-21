# No-card hosting shortlist · 2026-11-21

Public plan and terms review only. A Discord bot needs a sustained outbound
Gateway WebSocket and outbound HTTPS to the approved model provider. A
marketing claim about bot hosting does not prove WebSocket reliability,
SQLite persistence or a specific uptime. No host received accounts, code,
credentials, or messages during this review.

| Candidate | Published free offer | Downtime, renewal and disk considerations | Decision |
| --- | --- | --- | --- |
| [Kerit Cloud](https://kerit.cloud/free-discord-bot-hosting/) | 256 MB RAM, 2 GB NVMe, Python and no card. | Advertises no sleep and auto-restart. Signup instructions include email verification, Discord linking and joining its community. Check the actual renewal policy, support access, backup slots and restart/redeploy persistence in the panel. | First hosted pilot if the owner approves third-party storage and the account confirms the advertised terms. |
| [Bot-Hosting.net](https://bot-hosting.net/pricing) | The current panel lists 256 MB RAM, 25% CPU, 512 MB disk and one deployment, no card. | Manual renewal every four days. Service stops when missed. The [legal terms](https://bot-hosting.net/legal) describe a three-day free grace period followed by deletion and a final 30-day backup. The [panel migration guide](https://bot-hosting.net/docs/guides/the-new-panel) distinguishes the older coin plans. Verify restore, backup retention and handling of erasure requests separately. | Second hosted pilot if renewal and backup retention are acceptable. |
| [FPS.ms](https://fps.ms/free-discord-bot-hosting) | 128 MB RAM, 25% CPU, 250 MB disk, Python, no card. | Renewal every 24 hours. It says files are removed after 28 days without renewal and lists no free backup slot. Auto-restart is advertised. | Reserve option for a measured low-memory deployment. Daily renewal makes it a poor fit for continuous history. |
| [Enzonic](https://enzonic.com/discord-bots/discord-py) | Advertises 512 MB RAM, 50% CPU, 10 GB disk and card-free Python bot hosting. | Provider advertises automatic restart. The [general terms](https://enzonic.com/legal/tos) describe inactivity rules for Minecraft, so check bot-specific renewal, persistence and backups in the panel. | Alternate pilot if the bot-specific terms and data controls are clear. |
| Existing owner-controlled computer | No additional hosting subscription or billing setup if an existing machine and connection are suitable. | Local persistent storage and control of backups. Uptime depends on power, internet, restarts and sleep settings. Adds electricity usage if the machine is kept awake. | Preferred for private testing and fallback if third-party storage terms or renewal are unsuitable. |
| [Render free web services](https://render.com/docs/free) | HTTP web hosting with idle spin-down and ephemeral filesystem. | No persistent disk on free web services. An outbound Discord connection does not meet the documented inbound HTTP activity rule. | Exclude from the SQLite bot deployment. |

## Pilot acceptance

With user approval, use synthetic data and start with the selected free
allocation. Confirm no payment details, Python 3.12+, FTS5 availability,
provider reachability, and a sustained Gateway session after reconnects.
Measure idle and peak RSS and disk during archive replay and a three-frame
vision request. Prove that SQLite survives process kill, host restart and
redeploy, then restore an encrypted off-host backup. Verify secret access,
server and backup locations, renewal notices, deletion and host support
access before any private data. Keep the service on the free tier. A missing
renewal can leave gaps in history and no host in this table has measured
availability yet.

## Offline validation before hosting

Run `uv run --offline --locked python -m pai --doctor` after the locked
install. It checks the SQLite schema and FTS5 with a temporary archive and
prints runtime versions and integrity state without credentials. Pai caps
replies to eight per rolling minute for the configured guild, a 12-second
per-member interval, and two active responders. These limits apply to model
work and replies, while normal messages continue through the archive gate.
The library manages Gateway reconnects. The process handles Ctrl+C and
POSIX SIGTERM and closes its connections. Configure the eventual host's
normal restart-on-failure policy and verify it with synthetic data.

P6.1 remains blocked without an owner-selected Free account and approval
to conduct the real host pilot. No persistence, memory or uptime claim is
made for an untested host.
