# Edge: agentic coding, does the model resolve real repo-repair when it can iterate against the tests

Part of [claude-competitive-engine](../../README.md). The claim under test is that Claude separates
from the field on agentic coding when it can propose a patch, see the real test failure, and try
again, where single-shot the frontier ties. The public SWE-bench Verified leaderboard is where this
claim lives. This demonstrator reproduces the SHAPE of that benchmark on a small curated slice, on
your own keys, with a machine-checkable gate and a symmetric loop.

**On this run, the measured result is the honest other direction: Claude is behind on this slice.**
That is why this bundle leads with the product-team note, not a founder pitch. The methodology is the
durable contribution regardless of who wins this week.

## What it measures, and the two things that make it fair

A curated pure-Python slice of SWE-bench Verified (flask, pylint), each instance graded LOCALLY with
no Docker, and solved AGENTICALLY (propose a patch, grade it against the real tests, feed the failure
back, up to 3 rounds), the same loop for every provider.

1. **The grader is proven before it is trusted.** `make validate` rebuilds each instance's pinned
   environment in a `uv` virtualenv (the same per-instance recipe the official Docker image is built
   from, exposed as plain data by the `swebench` package), applies the human GOLD patch, runs the real
   tests, and scores with the harness's OWN parser. All 4 gold patches resolve locally, so a model
   patch gets a real verdict, never a false negative from an environment we reproduced wrong. The
   resolved verdict is computed by the same code the public leaderboard uses, on your machine, for free.

2. **The loop is symmetric.** Every provider gets the issue, the source, and on a miss the exact
   salient test failure, with the SAME accumulated multi-turn history forwarded to Claude, OpenAI, and
   Gemini on every round. The original ship-on-claude loop sent the full history only to Claude, which
   is a confound (a multi-turn Claude against a one-shot competitor). This port routes every arm
   through one provider-blind call with the whole `messages` list, so a difference in resolved K/N is a
   difference in the model, not in who saw more context.

## The measured result (the receipt)

4 instances x 6 models, up to 3 rounds, effort=medium. Full output in [`sample.txt`](sample.txt).

| model | resolved | rounds landed | cost |
|---|:--:|:--:|--:|
| **GPT-5.5** | **4/4** | 1,2,3,3 | $1.3219 |
| Claude Sonnet 4.6 | 2/4 | 1,2 | $0.6305 |
| Claude Opus 4.8 | 2/4 | 1,3 | $1.1527 |
| GPT-5.4 | 2/4 | 1,2 | $0.5886 |
| Gemini 3.1 Pro | 2/4 | 1,2 | $0.9531 |
| Gemini 3.5 Flash | 2/4 | 1,2 | $0.8131 |

Total spend this run: $5.4599, every number off the API `usage` object.

**The honest read.** The two easy instances (flask-5014, pylint-4970) tie the whole field at 6/6, so
they decide nothing. The two HARD pylint instances (4551 and 8898, rated 1-4 hours to fix by hand) are
where the slice separates, and on this run GPT-5.5 resolved BOTH and no Claude model resolved either.
Opus and Sonnet tied the rest of the field at 2/4. So on this slice, with the symmetric loop, the
agentic-coding edge belongs to GPT-5.5, not Claude. We report it exactly as it ran.

This is the opposite of an earlier asymmetric run where Claude led 4/4. The fix is the point: once the
same accumulated history reaches every provider, GPT-5.5 separates here. A rigged win would have hidden
that.

## Scope and what would change the number

A small pure-Python slice that corroborates the public leaderboard's SHAPE, not a 500-instance
reproduction. Requests is excluded because its suite makes live HTTP calls a local offline grader
cannot reproduce, the long tail Docker isolates. The result can move with the model versions, the round
budget, the effort label, and the instances chosen, so re-run it on your own keys before quoting it.

## Run it yourself

```bash
git clone <this-repo> && cd claude-competitive-engine
make setup && make compare-deps   # core deps, then openai, google-genai, datasets, swebench, same venv
cp .env.example .env              # paste your Anthropic, OpenAI, and Gemini keys
make validate                     # prove the local no-Docker grader against the gold patches (no model spend)
make agentic                      # the head-to-head on your own keys, about $4-5 (this run was $5.46)
```

`uv` must be on PATH for the local grader (https://docs.astral.sh/uv). The grader runs the model's
patch against the real test suite in a local uv venv (no Docker, the same posture as the official
LiveCodeBench runner), so run it on a machine you do not mind exposing to the patched repo's tests.

See [`PRODUCT_EMAIL.md`](PRODUCT_EMAIL.md) for the honest other direction (the one that ships for this
run) and [`FOUNDER_EMAIL.md`](FOUNDER_EMAIL.md) for the conditional founder framing the methodology
supports when Claude does lead the slice.
