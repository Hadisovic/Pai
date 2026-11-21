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
