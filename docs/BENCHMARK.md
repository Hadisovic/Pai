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
