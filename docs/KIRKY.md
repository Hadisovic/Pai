# Kirky private experiment

Kirky is a separate Discord installation from Pai P9.15 at `67521265c30137d2e0b0682d3ce03e67c413ed80`. Its per-instance name is applied to application-authored identity and prompt labels. The golden card, user utterances, historical roles, voice, sampling, route order, and Pai defaults retain their existing behavior.

## Discord owner setup

1. In the Discord Developer Portal, create a **new application** named Kirky. Place the prepared local image on the new application's **Bot** avatar and set the bot username to **Kirky**. Enable **Message Content Intent** for the new bot. Keep the app private. Copy its Application ID into `bot_user_id` in Kirky's private `instance.json`. Do this inside the local file. The existing Pai application remains separate. [Discord application setup](https://docs.discord.com/developers/quick-start/getting-started)
2. Create/reset the **Kirky** bot token in the portal. Run `pwsh -NoProfile -File "$env:LOCALAPPDATA/Kirky/Set-KirkySecret.ps1" -Kind discord` and enter it only when the private PowerShell prompt appears. It saves a Windows user-bound encrypted value and injects it only into the Kirky process. It needs no ChatGPT message, command-line value or Git file.
3. Install Kirky in the designated test guild only. Use Guild Install with `bot` and `applications.commands` and no broad server permissions. In Discord, give the Kirky bot member a channel-specific overwrite granting **View Channel**, **Read Message History** and **Send Messages** only in the designated experiment text channel. Remove effective view access in all other channels through the applicable role/category/member overwrites. Verify using role view. Do not give Administrator. Keep Pai's permissions under the owner's manual control. The launch preflight rejects the wrong bot, missing custom avatar, other guilds, Administrator and effective view access to another channel. It does not inspect other channel messages. [Discord channel permissions](https://docs.discord.com/developers/topics/permissions)
4. Obtain an affirmative opt-in on Kirky's notice from each person in the exact test channel. Set `admin_opt_in`, `notice_version` and `consenting_member_ids` in Kirky's private policy only after that review. Use a separate affirmative scope before setting `external_ai_opt_in`, `assistant_continuity_opt_in`, or the optional social and member-awareness flags and their respective member-ID lists. Keep media and postponed diagnostics off. Review the imminent-distress response below before setting `distress_reviewed`.

## Quota priority and safety review

Groq limits apply at the organization level. The default Kirky setup makes zero hosted requests, reserving the entire shared organization budget for Pai. Two different keys in one organization still share limits. A project cap can limit consumption without reserving all shared capacity for Pai. Leave hosted inference off when independent metering cannot be verified. Do not open extra accounts to evade a provider limit. Only if an already approved, independently metered card-free and notice-compatible Free quota is available, record that verification in Kirky's private instance configuration and use `Set-KirkySecret.ps1 -Kind groq` for its dedicated key. Qwen remains primary and GPT-OSS remains fallback. [Groq organization limits](https://console.groq.com/docs/rate-limits)

P9.14.1's test found that both model variants omitted immediate outside help for synthetic imminent distress. On experimental instances, the existing imminent flag now triggers a local reply directing the person to local emergency services and a trusted nearby person. It makes no promise that Kirky will stay available. The scope is the current detector, which can miss indirect and multilingual wording. Review that limit and test using synthetic cases before live activation. Existing Pai deployments retain their behavior. [Social media crisis response guidance](https://988lifeline.org/help-someone-else/support-on-social-media/)

## Local operation

```powershell
pwsh -NoProfile -File "$env:LOCALAPPDATA/Kirky/Start-Kirky.ps1" -Check
pwsh -NoProfile -File "$env:LOCALAPPDATA/Kirky/Start-Kirky.ps1"
pwsh -NoProfile -File "$env:LOCALAPPDATA/Kirky/Stop-Kirky.ps1"
pwsh -NoProfile -File "$env:LOCALAPPDATA/Kirky/Backup-Kirky.ps1"
```

The private directory holds the pinned source checkout, scope policy, independent SQLite archive, logs, avatar and encrypted backups. Kirky uses its own process lock and a local shutdown request. The same gateway excludes bot-authored and webhook messages, including Pai's messages. Kirky commands are prefixed with `kirky_` and accept only the dedicated channel. A launch message confirms process creation. Verify actual Gateway readiness in Kirky's own log.

After approval, verify the profile picture in Discord, the single running Kirky instance, mention and ping-off reply in the experiment channel, two clickable non-notifying member references, distinct authorized memories, current consent and media settings, and lack of bot-to-bot replies. Verify there is no response in other channels. Use synthetic chat for this smoke. Record the two bot pins and process IDs separately.

## Optional memory migration and rollback

Kirky starts empty. For a later migration, ask each source author to approve specific items and their use in the new channel and provider context. Review those items against Pai's current erasures and expiry while using the authorized export or an encrypted backup. Let consenting authors restate selected facts or explanations in Kirky's channel. That preserves actual new-channel source identities and supports later withdrawal. A bulk import would require a separate cross-channel provenance and erasure design. This setup performs no data copy from Pai.

Stop Kirky using its own stop script. Keep its encrypted backup and independent erasure ledger private, and restore only to a separate file with Kirky's current policy and current erasures. To roll back the experiment, the owner can remove the Kirky app's guild installation independently. No Pai stop or restore is involved. [Existing encrypted backup procedure](BACKUP.md)
