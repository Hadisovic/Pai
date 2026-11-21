# Discord setup

The live adapter is under development. CI calls it with simulated messages
and requires no bot token. Keep the application disconnected until the owner
approves the test server scope and every listed participant has affirmatively
consented after receiving the current notice.

The operator provisions a private policy file outside the checkout. The
default filename `.pai-policy.json` is ignored as a second line of protection.
Use system file permissions to restrict it. It stores the version of the
notice, an admin opt-in flag, the guild ID, the explicit channel allowlist,
and the Discord IDs of consenting authors. Here are synthetic example values
with collection disabled:

```json
{
  "admin_opt_in": false,
  "notice_version": "",
  "guild_id": null,
  "channel_ids": [],
  "consenting_member_ids": []
}
```

All five settings must be affirmative to start collection. Pai checks the
configured guild, channel and author on every message. Threads, DMs, bot
authors, webhooks, and channels the bot cannot view are excluded. Configure
channel permission overwrites in Discord as an independent scope control.
Do not request Administrator. The guild message and privileged message
content intents must be available for live use. See [Discord evidence](DISCORD.md)
for channel permissions, platform policy and outstanding live checks.

## Running the adapter

Run the policy check without connecting:

```sh
uv run --locked python -m pai --policy /private/path/policy.json
```

An explicitly authorized pilot can use the same command with `--connect`
and `--database /private/path/pai.sqlite`, with `DISCORD_TOKEN` injected from
the operator's secret store. Restrict access to the database directory and
its WAL files. Use a fresh archive for the first test. This stage stores
only new authorized text events and same-channel reply references and has
no model connection. Complete the remaining privacy and retention tasks
before collecting real conversations.

Raw edits update existing authorized text when Discord supplies a newer edit
timestamp. Single and bulk deletes remove the original text and keep a
temporary, scope-bound ID marker to block replays. Pai prunes expired text
and markers on startup and hourly. The private policy accepts an optional
`retention_days` field from 1 through 365, with a 30-day default. The archive
holds up to 20,000 messages and drops the oldest first when full. SQLite may
retain allocated disk pages for reuse, so verify disk headroom in the pilot.
This stage neither stores nor downloads media. A live pilot still needs
explicit approval and the remaining privacy workflows.

The mocked responder requires a literal, Discord-recognized bot mention.
Reply notification pings and code examples do not trigger it. When both
the requester and the bot can read channel history, it can see up to four
authorized reply ancestors and eight recent messages in that same channel.
The CLI leaves model replies disabled unless the operator enables the approved Groq mode.

Search uses SQLite 3.42+ with FTS5 and its secure-delete option. Check
`uv run --locked python -c "import sqlite3; print(sqlite3.sqlite_version)"`
on the host and test archive initialization before importing data. Opening
with an older SQLite build after an FTS5 update may fail. Use the same or a
newer SQLite version for tested backups and restores.

Historical recall searches only the requesting channel. The responder adds
up to four older matching messages with author attribution and Discord jump
links. It fetches current guild membership and checks channel permissions
before selecting history and again before sending. It discards a response if
a source changed or was removed during generation. Use history-enabled
channels only when their audience is authorized to receive the historical
context in an ordinary channel reply. The provider-backed responder requires a separate opt-in.

## Member privacy controls

Only explicit command invocations receive these private responses. Social
replies still require a direct bot mention.

- `/privacy` shows your collection state and the current retention window.
- `/memory` exports up to 100 of your own recent authorized messages in the
  current channel. Ask an administrator for a larger export.
- `/forgetme` removes your active archived messages in this guild along with
  their search and style references. A minimal opt-out record prevents
  collection from restarting after a bot restart or an out-of-order event.
- `/sharestyle` marks one of your own saved messages as a style example.

The operator can update the private allowlist, consent list and retention.
Refresh consent when the notice changes. Stop the bot before changing the
file. It purges revoked scope at startup before connecting. To apply a
revocation without connecting, run `python -m pai --apply-policy --policy
/private/policy.json --database /private/pai.sqlite` in the locked
environment. Applying an explicitly disabled policy clears archived text.
Do not restore an older backup without applying all current revocations and
opt-outs. Backups and restoration need an erasure procedure and drill before
a live launch. Deletion from Pai does not delete original Discord messages,
messages previously posted by the bot, or files users already downloaded.

## Optional model replies

The normal connected mode archives authorized messages without model calls.
A user-approved pilot can add `--groq-free` alongside `--connect` if the
operator has confirmed the Free plan, its limits, no billing information and
ZDR in a dedicated Groq organization. Inject `PAI_GROQ_KEY` via secrets.
Set `external_ai_opt_in: true` only after the current notice and members'
consent cover this provider and the use of selected chat text and display
names. The CLI exits before Discord login when the flag lacks consent or a
key. A local mock verified routing and prompt assembly. Live model access
and conversational quality are still unverified.
