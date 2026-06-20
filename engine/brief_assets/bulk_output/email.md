Subject: Congrats on YC! One Claude trick for big nightly generations

Hey {first_name},

Congrats on the batch. Quick builder note from a run I did this week.

If you run a nightly job that turns each backlog row into one long deliverable, a full report or a big generated dataset, you have probably hit a wall: a single deliverable runs past the model's per-request output ceiling, and now you are writing a chunk-and-stitch loop to glue the pieces back together. That glue is its own maintenance and its own seam bugs.

Claude has an extended-output mode that lands the whole thing in one turn. On the Message Batches API (the async bulk endpoint) with one beta header, the single-request output ceiling jumps far past where the other vendors stop.

```python
batch = client.beta.messages.batches.create(
    betas=["output-300k-2026-03-24"],  # lifts single-request output above 128k tokens
    requests=[{"custom_id": "row", "params": {
        "model": "claude-sonnet-4-6", "max_tokens": 300000,  # add this
        "messages": [{"role": "user", "content": prompt}]}}],
)
```

On my key, 2026-06-19, one request emitted 230,607 output tokens and finished un-truncated (`stop_reason: end_turn`). One whole deliverable, one turn, no stitching.

How that single-request output ceiling compares, from each vendor's own docs:

| Provider | Single-request output | Result on the run |
| --- | --- | --- |
| Claude (extended output) | extended-output ceiling | 230,607 tokens, un-truncated |
| OpenAI | 128k documented ceiling | below the deliverable size |
| Gemini | 65,536 documented ceiling | below the deliverable size |

It runs at the batch discount and most batches finish in under an hour, so it fits a nightly job, not a live request.

Reproduce it in about a minute for roughly $0.20:

```bash
git clone https://github.com/cfregly/claude-feature-hits && cd claude-feature-hits
make bulk_output
```

Want the whole table, not just the Claude side? Set `OPENAI_API_KEY` and `GEMINI_API_KEY` too and run `make bulk_output COMPARE=1`. It confirms each competitor's single-request output ceiling next to Claude's extended output, on your own keys for a few cents.

To try it on your own deliverable, edit the prompt in `bulk_output/run.py` and re-run `make bulk_output`.

One note you have to act on: extended output needs the beta header `output-300k-2026-03-24` and runs on the Batch API only (Opus 4.8/4.7/4.6 and Sonnet 4.6). The SDK call above sets the header for you.

Happy building!
{your_name}
Building with Claude
