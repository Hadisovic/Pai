# Synthetic quality benchmark

Install the locked development environment and run:

```sh
uv run --offline --locked python -m pai.benchmark
```

The command creates six synthetic cases and reports their adapter results as
JSON. It includes a meme drawn in memory and three ordered frames decoded
from an in-memory animated GIF. The default adapter is a deterministic stub.
Its latency measures only local stub calls and the output contains no quality
scores. Pillow is used for fixture generation and runtime image decoding. Its
[MIT-CMU license](https://github.com/python-pillow/Pillow/blob/main/LICENSE)
ships with the installed package.

A future approved model adapter takes a `Case`, sends only its `prompt` and
ordered `frames`, and returns a `Completion` with the response and reported
token use. Use a fresh context per case, keep model settings consistent,
record failures separately and save the JSON outside version control if it
contains operational details. Use only synthetic data in provider tests.

Have an evaluator score 0 through 5 using each case's rubric. Weight humor
and fit 30%, memory accuracy 30%, natural English 25%, Arabic comprehension
10% and measured latency 5%. Define the latency scale before comparing models.
Report the two media cases separately and require both to pass before calling
a model vision-ready. Publish model ID, evaluation date, scores, token use
and time together. Live runs and human scoring remain pending an approved
card-free account.

## Approved synthetic Groq run

After verifying a dedicated Free organization, its no-billing status and
privacy controls, set `PAI_GROQ_KEY` using the local secret store and run:

```sh
uv run --locked python -m pai.benchmark --groq-free --quota-db /private/benchmark.sqlite
```

This sends only the generated cases and runs independently of Discord. It
uses one primary route without fallback, records the provider's total
tokens when returned, and waits up to just over one minute before the
three-frame case to respect the rolling quota. Use the same private quota
database on repeat runs. Record human rubric scores after the run. The
command stops if the route cannot complete within the free limits.
## 2026-11-21 · Model comparison without an account

Ran real inference against two public GGUFs through llama.cpp b12612 on
separate standard GitHub-hosted Linux CPU runners. The server listened
only on loopback. It used four threads, a 4,096-token context, temperature
zero, seed 21 and at most 128 generated tokens. The job checked the
runtime, weight and projector digests. Each model received the same six
synthetic cases. No external AI API, provider account, or Discord data
was used. [GitHub benchmark run](https://github.com/Hadisovic/Pai/actions/runs/44942991533)

The assistant scored the actual responses on the documented rubric from 0
to 5. The latency buckets were defined before reviewing outputs. Median
seconds of up to 3, 6, 12, 25, and 60 earned 5, 4, 3, 2, and 1 respectively.
Longer medians earned zero. Both media cases needed at least 4 out of 5
and were recorded separately. Scores are exploratory results from one
seed and one case per skill.

| Candidate | English | Humor | Recall | Arabic | Latency | Weighted score | Meme | GIF | Median | Reported total tokens |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Qwen3.5-4B Q4_K_M + Q8_0 projector | 3.5 | 3 | 4 | 3 | 3 | 68.5/100 | 4 | 5 | 7.25 s | 1,042 |
| Gemma 4 E4B IT Q4_0 + Q8_0 projector | 4 | 2.5 | 4 | 2 | 3 | 66/100 | 5 | 5 | 8.92 s | 1,021 |

Both named Waffle and attributed it to Sam, without supplying the
historical source label. This benchmark did not explicitly request a
citation in the recall question. Recheck citation compliance with the
production prompt before relying on real historical claims. Qwen extended
the running weather joke but got verbose. Gemma was briefer and explained
the exact meme text. Both described left-to-right motion. Qwen recognized
the router was still disconnecting but called the lab an app. Gemma called
the lab a laptop and referred to images in the text-only case.

Qwen3.5-4B is the provisional local candidate. Gemma is a reasonable
alternative for shorter English and literal meme interpretation. Neither
model fits the shortlisted 256–512 MB bot hosting plans. The scores do
not measure the hosted Groq Qwen3.8 model, actual group humor, or
production accuracy. Windows Vulkan and CUDA binaries exited before
model loading in the local setup, so these are Linux CPU measurements.
[Qwen outputs](https://github.com/Hadisovic/Pai/actions/runs/44942991533/job/136964074141)
· [Gemma outputs](https://github.com/Hadisovic/Pai/actions/runs/44942991533/job/136964074388)
