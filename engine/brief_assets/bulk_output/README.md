# The largest deliverable in one request, with Claude extended output

![demo](https://raw.githubusercontent.com/cfregly/claude-feature-hits/main/bulk_output/demo.gif)

[![Claude proof: 80% above 128k cap](https://img.shields.io/badge/Claude%20proof-80%25%20above%20128k%20cap-2F855A)](https://github.com/cfregly/claude-feature-hits/blob/main/bulk_output/sample.txt)

You run a nightly job that turns each backlog row into one long deliverable: a full report, a big generated dataset. When a single deliverable runs past a model's per-request output ceiling, you fall back to a chunk-and-stitch loop with its own stitching-failure surface. Claude extended output, on the Message Batches API (the async bulk endpoint) with the beta header `output-300k-2026-03-24`, lifts the single-request `max_tokens` ceiling far past where the other vendors stop, so the whole thing lands in one turn.

## What you get

One un-truncated deliverable per request. In a measured run on 2026-06-19 Claude emitted 230,607 output tokens in ONE request and finished clean (`stop_reason: end_turn`). No chunking, no stitching logic to maintain.

```python
batch = client.beta.messages.batches.create(
    betas=["output-300k-2026-03-24"],  # lifts single-request output above 128k tokens
    requests=[{"custom_id": "bulk", "params": {
        "model": "claude-sonnet-4-6", "max_tokens": 300000,  # add this
        "messages": [{"role": "user", "content": prompt}]}}],
)
```

## Claude vs OpenAI vs Gemini

Single-request output ceiling, from each vendor's own docs:

| Provider | Single-request output ceiling | Result on the run |
| --- | --- | --- |
| Claude (extended output) | 300,000 beta ceiling | 230,607 tokens, un-truncated |
| OpenAI | 128k documented ceiling | below the deliverable size |
| Gemini | 65,536 documented ceiling | below the deliverable size |

## Run it

```bash
export ANTHROPIC_API_KEY=your-api-key   # https://console.anthropic.com/
make bulk_output
```

Default Claude run: $0.20 on my run. The live check submits a moderate extended-output batch and asserts the deliverable comes back un-truncated in one request. The 230,607-token headline is the `python -m bulk_output.run --full` run from the saved full-run output, $3.46. It is designed for async jobs, so allow minutes rather than a live-chat response time.

Full comparison run: also export `OPENAI_API_KEY` and `GEMINI_API_KEY` and run:

```bash
make bulk_output COMPARE=1
```

`COMPARE=1` installs `requirements-compare.txt` (the OpenAI and Gemini SDKs) into the same `.venv` and confirms each competitor's single-request output ceiling directly: it asks the API for a `max_output_tokens` above the documented cap and the API enforces the limit, so you see the 128,000 and 65,536 ceilings without paying for a large generation. Without it, the brief runs the Claude side alone on one dependency.

## Run it on your own data

Edit the prompt in `bulk_output/run.py` (the `_prompt` function) to your own long deliverable, then re-run:

```bash
make bulk_output
```

Beta header: extended output needs `output-300k-2026-03-24` and is batch-only (the Message Batches API, on Opus 4.8/4.7/4.6 and Sonnet 4.6). The SDK call above sets it for you with `betas=[...]`.

## Learn more

Batch processing and extended output (verified 2026-06-20): https://platform.claude.com/docs/en/build-with-claude/batch-processing
