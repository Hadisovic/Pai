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
