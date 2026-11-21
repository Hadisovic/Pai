# Free model evaluation · 2026-11-21

This comparison uses official documentation and an unauthenticated OpenRouter
catalog request. No model calls, account creation or payments took place.
Quotas can change and advertised model support does not prove access in an
individual account or deployment region.

| Candidate | Model and capabilities | Free limits and access | Data handling and disposition |
| --- | --- | --- | --- |
| GroqCloud | `qwen/qwen3.8-27b` is text and vision. Up to three images per request, each counted as 2,048 input tokens. `openai/gpt-oss-120b` and `openai/gpt-oss-20b` are candidate text-only fallbacks. | Groq's free table lists 30 requests/min, 1,000 requests/day, 8,000 tokens/min and 200,000 tokens/day for each model. Exact organization limits are shown in its console. Free plan is documented and provider staff describe unpaid use without payment details. Actual card-free signup, Jordan access, and reachability from the eventual host remain unverified. | Inference inputs/outputs may be temporarily logged for abuse/reliability unless ZDR is enabled. Groq says organization admins on all plans can enable ZDR. Check the Free plan and that setting before submitting live data. Document U.S. data location. **Primary synthetic candidate and same-provider text fallback.** |
| OpenRouter | The public catalog returned zero prompt/completion prices and text/image support for `nvidia/nemotron-3.5-super-vl:free` and `google/gemma-4-26b-a4b-it:free`. Their public endpoints respectively listed Nvidia and Google AI Studio. | The documented no-card free plan gives up to 20 requests/min and 50/day for free variants without credit purchase. Failed attempts count toward the daily limit. Actual regional/account access and per-model availability remain unverified. | Account opt-out of provider training plus request-level zero prices, `data_collection: deny`, `zdr: true`, pinned provider and disabled provider fallback are required to consider live use. Public endpoint metadata did not establish ZDR eligibility for either listed endpoint. Disable live routing until a compatible free route and OpenRouter's own logging settings have been verified. **Independent fallback candidate, synthetic testing only for now.** |
| Google Gemini API | `gemini-3.1-flash-lite` supports text, images and video input. | Base pricing lists free input and output. The account dashboard shows active RPM, TPM and RPD limits. Jordan is on the supported-region list. Billing activation requires payment details and a prepayment. Verify that key provisioning stays on the Free tier and stop if payment is requested. | Google's unpaid terms permit product improvement and human review of submitted content, subject to regional and account exceptions. **Synthetic benchmark candidate only. Exclude from default live routing.** |

## Official sources

- Groq [models](https://console.groq.com/docs/models), [vision](https://console.groq.com/docs/vision), [free rate table](https://console.groq.com/docs/rate-limits), [inference data controls](https://console.groq.com/docs/your-data), and [provider staff explanation of the free plan](https://community.groq.com/t/free-tier/419).
- OpenRouter [pricing](https://openrouter.ai/pricing), [free model limits](https://openrouter.ai/collections/free-models), [provider routing](https://openrouter.ai/docs/guides/routing/provider-selection), [provider logging](https://openrouter.ai/docs/guides/privacy/provider-logging), and [live model catalog](https://openrouter.ai/api/v1/models).
- Google [pricing](https://aistudio.google.com/docs/pricing#gemini-3.1-flash-lite), [model capabilities](https://aistudio.google.com/docs/models/gemini-3.1-flash-lite), [rate limits](https://aistudio.google.com/docs/rate-limits), [regions](https://aistudio.google.com/docs/available-regions), [billing](https://aistudio.google.com/docs/billing), and [terms](https://aistudio.google.com/docs/terms).

## Initial routing decision

Start P1.4 with synthetic cases and a deterministic stub. Test candidate model
keys only after the user controls a card-free account. For Groq, cap GIF
sampling to three frames and verify that the text budget, frames and reply
fit the token ceiling together. Try Groq Qwen first for text and vision and
GPT OSS only for text or a request whose media has already been summarized
with provenance. Never silently discard pending vision context. Verify each
candidate with actual text, vision, quota, and 429 tests. Until there is an
authorized live provider, keep archiving and inference independently
switchable and use only mocked AI replies. Avoid paid tools, account
upgrades, and unconstrained routing even when a provider lists a model as free.
