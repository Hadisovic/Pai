# Pai member notice

Draft for the server owner to complete before posting. Replace the
bracketed fields with the approved pilot details.

Pai is a bot that helps us remember conversations and responds when someone
tags it. We will enable it only in **[list channels]**. It saves new
messages from people who explicitly agree. It can save an agreed message
without replying to it. It will only reply to chat when directly tagged.
The privacy commands are deliberate requests and their replies are private.

The archive can hold your text, display name, Discord IDs, timestamps, and
reply links. It records new activity from the time collection is enabled.
When media is enabled, Pai can record a small amount of attachment or
sticker metadata and may check an image or a few ordered GIF frames
connected to a direct mention. It keeps short, source-linked descriptions
for repeated media. You can explicitly share one of your own saved messages
as an example of the channel's humor.

**AI processing [enabled or disabled].** If enabled, Pai sends selected
messages, display names, and relevant images or GIF frames to **[approved
provider and region]** for an answer. Sources are limited to the current
channel. The provider and its privacy settings for this pilot are
**[describe verified retention, training and region]**. Replies may refer
to authorized older posts, and people in the channel can read those
replies. Model responses can make mistakes. Check linked messages for
important details.

**Retention.** Records stay in the active archive for at most **[days]**
and can expire sooner as it fills. **[Explain whether backups are enabled,
who can access them, and how long old generations are kept.]** Deleting a
Discord message removes the corresponding active record when Pai receives
the event. Pai may miss activity or deletions while offline. Notify
**[private administrator contact]** if this happens.

Use `/privacy` to see your current settings, `/memory` to download your
recent saved messages from the active channel, or `/forgetme` to remove
your active records and stop future collection. A minimal opt-out record
prevents collection from restarting. Contact **[private administrator
contact]** for a larger export, a correction, a concern, or backup erasure.
Removing Pai's record does not erase the original Discord message or a
reply or file someone has already received.

If you want to participate, tell **[private administrator contact]** that
you agree to **[notice version]** and the listed archive, AI and media
settings. Declining or doing nothing leaves collection off for you. You
can change your mind and opt out later.

## Owner checklist

1. Select channels whose audience may receive same-channel historical
   references. Confirm channel history permissions for the pilot.
2. Fill the notice with actual data locations, free provider controls,
   retention, backups and a private contact. Keep a restricted consent
   record by notice version and Discord account.
3. Collect explicit agreement outside the bot before listing a member.
   Keep cloud or media features off unless every included member has
   agreed to the corresponding processing in the current notice.
4. Apply the private policy with a narrow channel allowlist. Require new
   affirmative consent when scope, vendors or processing materially change.
5. Do not enable collection on live conversations before the owner approves
   the pilot and the privacy, cost and restore gates in the runbook pass.
