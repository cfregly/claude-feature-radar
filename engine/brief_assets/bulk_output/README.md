# The largest deliverable in one request, with Claude extended output

![demo](demo.gif)

You run a nightly job that turns each backlog row into one long deliverable: a full report, a large structured extraction, a long code scaffold. When a single deliverable runs past a model's per-request output ceiling, you fall back to a chunk-and-stitch loop with its own seam-failure surface. Claude extended output, on the Message Batches API with the beta header `output-300k-2026-03-24`, raises the single-request `max_tokens` ceiling to 300,000 output tokens so the whole thing lands in one turn.

## What you get

One un-truncated deliverable per request, far above the 128k single-request output ceiling of the strongest frontier models. In a measured run on 2026-06-19 Claude emitted 230,607 output tokens in ONE request and finished clean (`stop_reason: end_turn`), about 1.8x a 128k ceiling. No chunking, no stitching, no seam logic to maintain. The number traces to [`receipt.json`](receipt.json).

```python
batch = client.beta.messages.batches.create(
    betas=["output-300k-2026-03-24"],                          # add this
    requests=[{"custom_id": "bulk", "params": {
        "model": "claude-sonnet-4-6", "max_tokens": 300000,    # add this
        "messages": [{"role": "user", "content": prompt}]}}],
)
```

## Run it (about $0.20)

```bash
make bulk_output
```

The live check submits a moderate extended-output batch and asserts the deliverable comes back un-truncated in one request, for about $0.20. The full 230,607-token receipt run costs about $3.46 at the 50% batch discount and the batch can take many minutes.

## Run it on your own deliverable

Edit the prompt in `bulk_output/run.py` (the `_prompt` function) to your own long deliverable, then re-run:

```bash
python -m bulk_output.run --check
```

Beta header: extended output needs `anthropic-beta: output-300k-2026-03-24` and is batch-only (the Message Batches API, on Opus 4.8/4.7/4.6 and Sonnet 4.6). The SDK call above sets it for you with `betas=[...]`.

## Learn more

Batch processing and extended output (verified 2026-06-19): https://platform.claude.com/docs/en/build-with-claude/batch-processing
