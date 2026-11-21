# Discord API findings

Reviewed 2026-11-21 against Discord's official documentation. These are design
inputs for the adapter and its tests. Live intent approval, channel access,
and behavior with a real bot still need verification.

| Area | Documented behavior and Pai decision | Official source |
| --- | --- | --- |
| Guild message events | `GUILD_MESSAGES` covers new messages, edits and single/bulk deletes. Enable `GUILDS` for channel/guild state. Leave DM, member and presence intents disabled. Check guild/channel authorization in the handler before any storing or external request. Subscribe only after the live setup is authorized. | [Gateway intents](https://docs.discord.com/developers/events/gateway#list-of-intents) |
| Message content | `MESSAGE_CONTENT` is privileged and controls user-input fields, including ordinary content, embeds and attachments. Self-authored messages, DMs, direct mentions and qualifying interaction targets are exceptions. Enable it in the Developer Portal before identifying and obtain approval when Discord requires it. A mention-only trial cannot prove silent archiving. | [Message content intent](https://docs.discord.com/developers/events/gateway#message-content-intent) |
| Permissions | Grant `VIEW_CHANNEL` in the authorized channels. Add `SEND_MESSAGES` where replies are enabled and `READ_MESSAGE_HISTORY` for fetching referenced messages or sending native replies. Threads require their own permission and authorization handling. Keep Administrator and unrelated permissions off. Application consent remains a separate gate. | [Permissions](https://docs.discord.com/developers/topics/permissions), [Create Message](https://docs.discord.com/developers/resources/message#create-message) |
| Mutations and replay | Process update fields as patches so an omitted field preserves the stored value. Single and bulk delete carry IDs and scope. Use Discord snowflakes to deduplicate creates and apply mutations even if the library has no message cached. Resume can replay missed events within a resumable session. A fresh session can leave gaps. Pai does not backfill. | [Message events](https://docs.discord.com/developers/events/gateway-events#messages), [Gateway resume](https://docs.discord.com/developers/events/gateway#resuming) |
| Mentions and replies | Require a literal bot mention in content and the corresponding parsed mention target. A Discord reply can ping its author independently. Store the referenced message ID and scope. An omitted resolved message means its state is unknown, while an explicit null means deletion. Recheck authorization and visibility before resolving context. Set outbound allowed mentions explicitly to prevent incidental pings. | [Message object, references and allowed mentions](https://docs.discord.com/developers/resources/message) |
| Media | Attachment objects expose IDs, file names, size, URLs and optional content type or dimensions. Embeds may include image, thumbnail or video fields. Use `sticker_items` for sticker ID, name and format. Signed attachment URLs expire, so retain IDs and re-fetch the message only while authorized. Validate actual downloaded bytes and constrain fetches separately. | [Message resource](https://docs.discord.com/developers/resources/message), [Signed attachment CDN URLs](https://docs.discord.com/developers/reference#signed-attachment-cdn-urls) |
| Rate limits | HTTP limits include dynamic buckets and a global limit. Honor the library's handling and Discord's `Retry-After` or `retry_after` on 429s. Bound the work queue. Outbound Gateway commands and Identify have separate limits. Avoid manual reconnect loops and attempts to bypass quotas. | [HTTP rate limits](https://docs.discord.com/developers/topics/rate-limits), [Gateway rate limits](https://docs.discord.com/developers/events/gateway#rate-limiting) |

## Live data policy

Discord restricts API data use to what the stated application needs and
prohibits mining, scraping and profiling users or relationships. Its policy
also requires express Discord permission to use API message content to train
AI models. Keep synthetic research separate from live data. Confirm that the
specific retention and retrieval scope fits the policy before enabling an
archive. Scope future memory to necessary, source-linked conversation context.
Keep user profiling and automated mining disabled during design and launch
review. Exclude model-training providers from live traffic unless the relevant
permission and data handling requirements have been satisfied. Provide a way
to report problems with the app. [Discord Developer Policy](https://support-dev.discord.com/hc/en-us/articles/8563934450327-Discord-Developer-Policy)
