# Engineering decisions

## 2026-11-21 · Build on proven libraries and keep the Discord application small

Searches covered Discord LLM bots, SQLite agent memory, and local multimodal
chat. We inspected GitHub metadata, upstream dependency files, source,
configuration, licenses and security information. Maintenance dates below are
upstream GitHub push dates checked on 2026-11-21. Resource estimates are based
on dependencies and services. Runtime RAM and security have yet to be tested
under Pai's workload.

| Project | Maintenance and license | Fit, resource and privacy assessment |
| --- | --- | --- |
| [llmcord](https://github.com/jakobdylanc/llmcord/tree/a99de6da16) | MIT, pushed Aug 14, 2026 | Closest small base. A single Python entry point handles reply chains, images, and configurable OpenAI-compatible providers with a short dependency list. Reply history lives in Discord. It lacks the consented archive, source ACLs, retention and removal workflow, and bounded GIF analysis we need. Its configuration also includes paid endpoints. Replacing the event, archive, authorization and provider policy would remove most of the benefit of a fork. |
| [LLM Discord Bot](https://github.com/Adriwin06/LLM-Discord-Bot/tree/682d43b6e1) | BSD-3-Clause, pushed Jul 3, 2026 | Closest feature match for summaries and GIF frames. Ambient inference, autonomous replies, individual profiling, and model-driven server/web tools conflict with the intended privacy and mention behavior. Its broader media stack and provider abstraction add dependencies and data paths. Read as a design reference only. |
| [Discord LLM Chatbot](https://github.com/somewheresy/discord-LLM-chatbot/tree/badba268a2) | Apache-2.0, archived in 2023 | Mention-oriented starter, but built around GPT-4, a scraping API and Brave Search keys. Minimal runtime offers little reuse beyond what discord.py provides. |
| [Mem0](https://github.com/mem0ai/mem0/tree/fff8a64725) | Apache-2.0, pushed Nov 18, 2026 | Maintained long-term memory with an embedder and vector store. Using it would introduce model-dependent extraction and an extra index to keep synchronized with source visibility, edits and deletion. Reconsider only if measured retrieval misses justify the additional runtime and data processing. |
| [Letta](https://github.com/letta-ai/letta/tree/8816d3a851) | Apache-2.0, pushed Oct 18, 2026 | Stateful agent memory and channel integration. The V1 server is retired. The current direction includes an agent runtime and cloud option. This is a larger trust and deployment surface than Pai needs for mention-only generation. |
| [LibreChat](https://github.com/LibreChat-AI/LibreChat/tree/4700c44eb7) | MIT, pushed Nov 21, 2026 | Mature multimodal app. Its web/API stack and sample deployment include MongoDB, Meilisearch and RAG services. Adapting it would add infrastructure and still require a Discord gateway and a consent model. |
| [discord.py](https://github.com/Rapptz/discord.py), [SQLite FTS5](https://www.sqlite.org/fts5.html) and [Pillow](https://github.com/python-pillow/Pillow) | MIT, public domain, and MIT-CMU, respectively. discord.py and Pillow had 2026 pushes. | Adopt as components. Reuse Discord session and permission handling, Python's SQLite with FTS5, and Pillow's image/GIF decoding. Keep the runtime to one bot process and a local SQLite file. Select patched versions, bound media decoding, and test FTS5 availability on the eventual host. |
| [LiteLLM](https://github.com/BerriAI/litellm) | Active Nov 21, 2026. Check component licensing before redistribution. | A broad provider router would be useful at larger scale. Pai needs a narrow allowlist, hard no-paid routing and few endpoints. Direct adapters reduce configuration and the dependency surface. The [2026 PyPI compromise](https://github.com/advisories/GHSA-92x9-889m-jgmw) affected specific releases and reinforces the need for locked versions and security review. |

Use Pai's existing Python baseline. Build only the application behavior
specific to its authorization, source-linked memory and provider budget.
Start retrieval with reply chains and FTS5. Evaluate natural language,
dialect, paraphrases and old in-jokes before deciding whether to add
semantic indexing. Use image/GIF decoding libraries and send a few relevant
ordered frames only to an approved vision provider. Learn conversational
style from authorized current context, deliberate feedback and user-authored
shared examples. Review any persistent group-level adaptation under Discord
policy and avoid individual or relationship profiles.

The roadmap now includes the reuse assessment as P1.R and keeps the rest of
the work open, including measuring memory and GIF quality. No upstream
application code was imported. If we distribute or adapt third-party code,
preserve the applicable licenses, copyrights and notices. Track installed
dependencies and their licenses when introduced. No candidate was given
credentials or run against a server.

## 2026-11-21 · Learn group style from examples shared by their authors

A member can designate their own consented message as an example of the
channel's humor. The archive keeps only a tag and source reference. The
responder sees a small sample labeled as style, separate from factual
evidence. Changes to the text invalidate the tag, and deleting or expiring
the message removes it. Ordinary chat still informs the immediate context.
Provider prompts will need to treat both kinds of context as untrusted and
avoid interpreting jokes or sarcastic statements as established facts.
