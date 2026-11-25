# P9.13 social learning

P9.13 extends the owner-approved P9.11 build at `e678e60966a524cf19f6470c346534b5da652462`. The `v9.11` branch and tag pin that release. The character card, provider routes, prior message roles, sampling and reply engine are unchanged. The extension is off by default. Draft PR #48 holds the deferred GIF implementation.

## Research and architecture

- Contextual example selection can affect model performance. We retrieve a short meaning only when the addressed turn or its direct human parent contains the expression. We keep Pai's existing approved style examples and member preferences. [Demonstration selection research](https://aclanthology.org/2024.acl-long.492/) · [SillyTavern World Info](https://docs.sillytavern.app/usage/core-concepts/worldinfo/)
- Informal usage varies with context. Reactions and laughter lack enough information to authorize a meaning. We accept a human explanation, an explicit native-reply confirmation, or a correction. Negative feedback suppresses injection of that expression for the member who gave it. [Slang comprehension research](https://aclanthology.org/2024.naacl-long.94/) · [User feedback research](https://aclanthology.org/2025.emnlp-main.133/)
- Memory research highlights updates, abstention and relevance. SQLite already has consented message identity, deletion, expiry and retention. Reuse it with source-linked evidence and current consent checks. Periodic model reflections and embeddings add hosted quota or storage costs. [LongMemEval](https://arxiv.org/abs/2410.10813) · [Reflective memory management](https://aclanthology.org/2025.acl-long.413/) · [Generative Agents](https://arxiv.org/abs/2304.03442)
- Reviewed SillyTavern's selective lorebook injection and TomoriBot's layered Discord behavior on 2026-11-25. Adopted the selective retrieval concept using Pai's existing Python gateway and SQLite. A TomoriBot fork would add a broader tool and multi-server surface, a different runtime, a larger migration and AGPL obligations. No external code was copied. This extension stores group expressions and explicit member feedback. It does not infer member traits or train models on Discord data. [TomoriBot](https://github.com/Bredrumb/TomoriBot) · [Discord Developer Policy](https://support-dev.discord.com/hc/en-us/articles/8563934450327-Discord-Developer-Policy)

## Learning and withdrawal

| Evidence | Effect |
| --- | --- |
| One new explanation such as `"porch weather" means meet outside` | Candidate only |
| A second consenting member confirms the same meaning after at least 20 minutes | Corroborated |
| A member explicitly confirms their own explanation through the private control | Confirmed |
| Two different active meanings | Hold the expression until a correction or withdrawal resolves the disagreement |
| `stop using "porch weather"` | Suppress the expression's retrieved context for that speaker |
| Source edit, deletion, expiry, consent withdrawal or `/forgetme` | Reevaluate remaining support and invalidate affected cached reply context |

An explanation such as `عنا "🙃" يعني موافقة بس بسخرية` can establish a local emoji meaning with a native reply such as `بالضبط هيك قصدنا`. Quoted Arabizi definitions with `ya3ni` work too. No ordinary event generates a reply unless Pai is addressed. When Pai is addressed, the extension can pass up to two matching notes and 780 UTF-8 bytes of untrusted context to the existing model call. It withholds notes on known serious turns, personal recall, or when read-history access is unavailable. It does not send the source IDs, display names or raw evidence excerpts as part of the social block.

Members can use `/social_memory action:inspect` in the approved channel to see their own recent contributions and source links. Use `action:confirm message_id:…` on your own explanation, `action:withdraw expression:…` to remove your contributions to an expression, or make a new explicit correction in chat. Replies to this control are private. A withdrawal can leave a meaning supported by other authorized sources. For all stored data and future collection, use `/forgetme`. Operators can also revoke just the social opt-in in the policy. Previously posted Discord messages follow Discord's separate deletion controls.

This deliberately favors clear language over guesses. It misses oblique jokes and implicit corrections, uses lexical matching, and covers a narrow English, Levantine and Arabizi grammar. It does not learn humor preferences from reactions, infer emotion or sarcasm from standalone emoji, or build personal profiles. It can withhold a note after a user's feedback, but the existing model can still see the discussion in ordinary authorized conversation context. The local storage measurement and four-call experiment do not represent usage at Discord scale.

## Synthetic evaluation

On 2026-11-25, each synthetic scene stored a definition and a second member's confirmation in a separate session. A fresh connection reopened each archive before the callback. The experiment used the P9.11 `timeline-roles` text path with Qwen3.8-27B through the existing Groq Free policy and quota checks. Each pair used the same current turn. The social block was the only difference in model input. The control went first in the English scene and second in the Arabic scene.

| Addressed turn | Learning off, actual reply | Learning on, actual reply | Grounding |
| --- | --- | --- | --- |
| pocket lighthouse again today. what door do i tell the driver? | you telling the driver the door to your soul? | side gate | Two members established that deliveries use the side gate. |
| موزة الدرج رجعت؟ طب أطلع هسا ولا أستنى لبكرا؟ | أنت مش هتقدر تطلع. | اتأجل لبكرة. | One member explained the meeting moved to tomorrow and another confirmed in a native reply. |

There were four model calls, one per answer, and zero for learning, retrieval or deletion. The provider reported 1,722 total tokens. Enabling the notes added 64 and 70 reported tokens for the respective pairs, with reservation estimates up by 328 and 334. End-to-end generation measured 285 → 251 ms and 200 → 425 ms. Four calls cannot establish a latency or conversational quality gain. The Arabic answer communicates the postponement and leaves the instruction to wait implicit. Both pairs used the primary model in isolation.

On this Windows machine, adding 192 evidence rows to the same synthetic SQLite archive allocated 24 KiB of extra database pages. Median local observation, matching retrieval and archive source deletion were 5.84, 4.81 and 7.86 ms over 192, 96 and 96 operations respectively. The deletion includes normal archive work. Network, Discord delivery and SQLite WAL size are outside these figures. Offline coverage includes irrelevant turns, conflicting evidence, injection attempts, consent revocation, expiry and the golden reply contract.

## Operator setup after separate approval

1. Pin the clean reviewed revision in an isolated checkout. Confirm private TEST scope, current channel ACLs, and the existing no-billing Groq Free and ZDR configuration. Take and verify the existing encrypted backup and erasure checkpoint before stopping the old process. Keep the live database and private configuration outside the source tree. See [Setup and privacy controls](SETUP.md).
2. Issue an updated notice describing the derived group meanings, member-specific feedback, selected meanings sent to Groq, retention, and withdrawal. Refresh consent for the updated notice. Keep the existing text consent list and explicitly enable `social_learning_opt_in` with only the new affirmative opt-ins in `social_consenting_member_ids`. Missing keys disable social learning. Keep `media_opt_in` off. Existing messages are not backfilled.
3. Stop the previous connector and verify it exited. Launch the same private configuration with `--connect --groq-free --conversation-engine timeline-roles --text-model qwen --expected-revision <reviewed-full-sha>`. Reuse the private database, policy and existing secrets. Verify one connector and the expected revision, routes, ACL and quotas.
4. Use consenting synthetic participants to check silence on ordinary messages, a direct mention, a ping-off reply, and a withdrawn callback. Confirm that the control is private and an opted-out account cannot inspect or contribute. Observe natural conversation only under that approval.

## Rollback

Stop P9.13 and confirm that it exited. Restore the current approved text-only policy and remove the social keys. Preserve all newer revocations and opt-outs. From P9.13, run `uv run --locked python -m pai --apply-policy --policy <private-policy> --database <private-database>` while disconnected. This removes the derived social rows while preserving still-authorized text and preferences. The optional evidence table does not change the archive schema version.

Start `e678e60966a524cf19f6470c346534b5da652462` on the same database and policy with the prior P9.11 launch flags and expected revision. Confirm one connector, model routing, and a synthetic mention. If the archive is damaged, restore the verified encrypted backup and apply current erasures and consent restrictions before reconnecting. See [Setup and privacy controls](SETUP.md).
