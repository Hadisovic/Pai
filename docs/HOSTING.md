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
## 2026-11-21 · Public plan recheck and constrained Linux evidence

Enzonic is the first third-party pilot candidate based on its published
Python plan. It advertises a capacity-limited allocation with 512 MB RAM,
half a CPU core, 10 GB SSD, no payment details, and an always-on bot
process. Verify the actual allocation, absence of a card or billing address,
and bot-specific renewal and persistence terms after sign-in. Keep Kerit
as the smaller fallback at 256 MB and 2 GB. Bot-Hosting.net and FPS.ms
require more frequent manual renewal. [Enzonic Python plan](https://www.enzonic.com/python)
· [Enzonic Discord plan](https://enzonic.com/discord-bots/discord-py)
· [Kerit Free Bot Hosting](https://kerit.cloud/bot/free/)

The synthetic Linux job used two separate containers on a standard
public GitHub runner. Both had a 256 MiB cgroup memory limit, no extra
swap and half a CPU. A private disposable volume persisted across the
containers. Locked install, SQLite 3.46.1/FTS5, active archive reopen,
searchable encrypted restore, an existing opt-out, and the public
Discord Gateway v10 TLS/WebSocket HELLO all passed. It never identified a
bot or received guild events. Install plus seed peaked at 174,661,632
bytes (166.6 MiB). Restart, restore and the handshake peaked at 37,044,224
bytes (35.3 MiB). The volume used 58 MiB including the environment and
download cache. Windows also passed the public handshake and split-process
restore. [Linux job](https://github.com/Hadisovic/Pai/actions/runs/44942850593/job/136963641961)

This validates the isolated lab. Third-party allocation, bill-free
signup, bot login, deployment persistence, long-running load, renewals and
service uptime still need testing on the selected account. GitHub Actions
is used for short tests only.

## 2026-11-22 · Live host inspection and deployment packaging

Live browser inspection verified both primary and fallback cloud host offerings:

1. **Enzonic** (`https://panel.enzonic.com`):
   - Confirmed free plan: 512 MB RAM, 10 GB disk, 50% CPU, $0.00 cost, no card or billing details.
   - Server created: `Pai` under Discord Bot -> Python (startup file: `main.py`).
   - Provisioning Status: the Free allocation was queued at the time of inspection.
   - Uptime & Sleep Policy Reconciliation:
     - Official product pages (`https://www.enzonic.com/python` and `https://enzonic.com/discord-bots`) explicitly advertise 24/7 always-on hosting without sleep for Python Discord bots.
     - General platform terms (`https://enzonic.com/legal/tos`) define inactivity sleep rules for game servers (e.g. Minecraft) when zero players are connected.
     - Conclusion: Discord bots maintain an outbound Gateway connection rather than inbound player ports. Actual runtime persistence and whether the free container is kept alive indefinitely will be verified empirically once the container is provisioned.
   - Control architecture: Hydrodactyl V6.1 (Pterodactyl fork) with console, file manager, and SFTP access once assigned.

2. **Kerit Cloud** (`https://kerit.cloud`):
   - Confirmed free plan: 256 MB RAM, 1 GB NVMe, 30% CPU, 7-day heartbeat renewal, card-free.
   - Panel: Pterodactyl at `https://panel.kerit.cloud/` (login protected by reCAPTCHA).
   - Claim requirements & gates verified:
     - Account created and logged in.
     - Discord OAuth linking required (Discord account must be 30+ days old).
     - Must join Kerit Discord community (`https://discord.gg/7x9MQgFrCT`) and remain a member for **at least 1 full day (24h)** before the claim button unlocks.
     - Form submission requires solving an hCaptcha challenge.
     - Node status currently reported as `free-node · discord bot hosting · offline`.

3. **Deployment Bundle**:
   - Build a code-only bundle from the verified revision using Git's tracked paths.

     ```powershell
     git archive --format=zip --output=deploy-code.zip HEAD -- main.py requirements.txt .pai-policy.json.example src/pai/
     ```

   - Keep the existing private archive, encrypted snapshots and credentials local. Provision a fresh synthetic scope for any authorized future host validation.

## 2026-11-22 · Permanent Free Hosting Architectural Review & Decision

Per owner directive, the project prioritizes **long-term stability, persistent SQLite integrity, automatic restarts, and zero credit-card/billing requirements** over temporary workarounds:

1. **Kerit Cloud Dropped as Workaround**:
   - Verified that Kerit Cloud requires continuous heartbeats, manual anti-bot solving, a mandatory 24h Discord server waiting gate, and currently has offline free nodes. It is rejected as an unstable short-term workaround.

2. **Enzonic Allocation Preserved in Queue**:
   - The allocation was queued when inspected. Enzonic offers 512 MB RAM, 10 GB disk, and no manual renewal button or fee, with official product documentation explicitly advertising 24/7 always-on uptime for Python Discord bots. Runtime sleep behavior will be verified directly once the node assigns the container.

3. **Structural Analysis of Card-Free Cloud Hosting**:
   - **True 24/7 Always-On Cloud VMs** (Oracle Cloud Always Free, Fly.io, Google Cloud e2-micro): All require a valid credit card on file for identity verification.
   - **Card-Free Community Bot Hosts** (Wispbyte, HyeHost, Bot-Hosting.net, FPS.ms): All enforce periodic manual check-ins (14 days, 30 days, 4 days, or 24 hours) under penalty of container deletion.
   - **Ephemeral Web Hosts** (Render, Koyeb free, Glitch): Filesystems reset on restarts, destroying SQLite databases without paid external database add-ons.
   - **Dedicated Local/Self-Host Service**: Zero credit card, zero renewals, zero third-party privacy leakage, and 100% persistent SQLite. Ideal baseline while cloud allocation queues process.
