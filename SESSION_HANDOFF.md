# Pai Session Handoff · 2026-11-22

This handoff document captures the exact runtime, deployment, and codebase state for resuming Pai without repeating research or rebuilding existing work.

---

## 1. Current Verified System State

- **Bot Status**: **Online & Serving Discord**.
  - Bot Application ID: `1573805310785880264` (`Pai#6435`).
  - Active Test Server: `|| Hadi ||'s server` (Guild ID: `823208040764538901`).
  - Active Channels: `#moments` (`1220389554289250526`), `#study` (`1036614013527801876`), `#januar-2024`, `#februar-2024`, `#march-2024`.
  - Permissions Note: `#study` has an explicit channel overwrite denying `@everyone` Send Messages; in `#moments`, Pai has direct permission and replies live.
- **Active Process**: Running in background on local host via `scripts/start.ps1` with Python 3.12, SQLite 3.49.1 with FTS5, and Discord Gateway v10.
- **AI Route**: Groq Free organization (`org_01k2z2yx9qepsr0gtb22mexw3r`) routing to `qwen/qwen3.8-27b` with sub-second latencies and local token rate-limit reservation protection.
- **Personality & Learning**:
  - Grounded companion persona: casual English, conversational banter, zero assistant boilerplate, no biological/human claims, no mode announcements.
  - Multi-author group expression learning implemented via `group_style` in `storage.py` and `conversation.py` with SQLite window partitioning (`author_rank = 1`).
  - 76/76 automated tests passing (`uv run pytest`).

---

## 2. Free Cloud Hosting State (Enzonic)

- **Provider**: [Enzonic](https://panel.enzonic.com/) (Pterodactyl / Hydrodactyl V6.1 fork).
- **Free Allocation Specs**:
  - Memory: 512 MiB RAM.
  - CPU: 50% CPU / 1 Core.
  - Disk: 10 GB tier.
  - Cost: $0.00, no credit card or billing address required.
  - Uptime terms: Official Enzonic product documentation explicitly advertises 24/7 always-on hosting without sleeping for Python Discord bots (general ToS inactivity rules apply to game servers). Runtime behavior will be verified directly once the node is assigned.
- **Server "Pai" Queue Status**:
  - Server created under Discord Bot -> Python (`main.py`).
  - Current Queue ID: `9980`, Position `#123` in line (estimated wait time: ~2 hours / standard queue).
  - Node capacity expansion in progress; notification email will be sent to `hadiouss4@gmail.com` when container is provisioned.
- **Fallback Host (Kerit Cloud)**:
  - Inspected at `https://billing.kerit.cloud/`.
  - Specs: 256 MB RAM, 1 GB Disk, 30% CPU, card-free.
  - Eligibility gates verified: account registered (`hadiouss4@gmail.com`), but claiming requires Discord linking, 30+ day account age, joining Kerit Discord server with a **mandatory 1-day (24h) membership waiting period**, hCaptcha completion, and current node status is reported offline.

---

## 3. Data & Artifact Locations

| Artifact | Location | Purpose |
| :--- | :--- | :--- |
| **Active SQLite Database** | `Pai/pai.sqlite` | Stores verified conversation history, FTS5 indexes, quota records |
| **Encrypted Snapshot** | `Pai/backups/snapshot.pai` | AES-256-GCM encrypted backup of active database |
| **Backup Key** | `Pai/.env` (`PAI_BACKUP_KEY`) | 32-byte key for backup creation/restoration (never in Git) |
| **Turnkey Bundle** | `Pai/deploy.zip` (39.7 KB) | Pre-packaged `main.py`, `requirements.txt`, `src/pai/`, `.pai-policy.json`, `pai.sqlite` |
| **Staged Upload** | `<ArtifactDir>/browser_sandbox/uploads/deploy.zip` | Pre-staged for direct upload to Pterodactyl File Manager |
| **Turnkey Runner** | `Pai/scripts/start.ps1` | PowerShell launcher that checks doctor, policy, and connects |

---

## 4. Known Deferred Issues (Post-MVP)

1. **External GIF links (e.g. Klipy)**: Outside Discord/Giphy CDN, not currently decoded for vision.
2. **Custom Discord emojis/emotes**: Stripped during minimization and not semantically understood.
3. **Implicit replies without mentions**: Reply chains without explicit `@Pai` mention tag do not trigger response under strict direct-mention gate.

---

## 5. Instructions for Resuming ("Resume Pai")

When the user says **"Resume Pai"**:

1. Read `SESSION_HANDOFF.md` and `STATUS.md`.
2. Inspect Enzonic panel at `https://beta.panel.enzonic.com/` or `https://panel.enzonic.com/`:
   - Check if server `Pai` (Queue ID `9980`) has completed provisioning and has an active server control panel (`/server/<uuid>`).
3. If Enzonic container is assigned:
   - Go to File Manager on the Enzonic panel.
   - Upload `deploy.zip` (or staged files) and extract.
   - In panel Startup / Environment settings, set `DISCORD_TOKEN` and `PAI_GROQ_KEY`.
   - Start the hosted server and verify the console log displays `Discord gateway is ready`.
   - Send a test mention in Discord `#moments` to verify response from the hosted bot.
   - Stop the local Windows bot process (`scripts/start.ps1`) cleanly to prevent duplicate Gateway connections.
   - Verify the bot continues responding independently of the PC.
4. If Enzonic queue is still pending:
   - Check current position and estimated remaining time.
   - Keep the local bot process running as primary so Pai remains online without interruption.
