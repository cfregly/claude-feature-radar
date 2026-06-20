Subject: Congrats on YC! One Claude trick for big nightly generations

Hey {first_name},

Congrats on the batch. Quick builder note from a run I did this week.

If you generate long deliverables on a nightly job, one per row in a backlog, a report or a big structured extraction or a code scaffold, you have probably hit a wall: a single deliverable runs past the model's per-request output ceiling, and now you are writing a chunk-and-stitch loop to glue the pieces back together. That glue is its own maintenance and its own seam bugs.

Claude has an extended-output mode that lands the whole thing in one turn. On the Message Batches API with one beta header, the single-request output cap goes to 300,000 tokens.

```python
batch = client.beta.messages.batches.create(
    betas=["output-300k-2026-03-24"],                       # add this
    requests=[{"custom_id": "row", "params": {
        "model": "claude-sonnet-4-6", "max_tokens": 300000, # add this
        "messages": [{"role": "user", "content": prompt}]}}],
)
```

On my key, 2026-06-19, one request emitted 230,607 output tokens and finished clean, about 1.8x a 128k ceiling. One un-truncated turn, no stitching. It runs at the 50% batch discount, and the batch takes a few minutes, so it fits a nightly job, not a live request.

Demo and runnable code: https://github.com/cfregly/claude-feature-hits/blob/main/bulk_output/README.md

Run the live check (about $0.20):

    make bulk_output

To try it on your own deliverable, edit the prompt in bulk_output/run.py and re-run:

    python -m bulk_output.run --check

One note: extended output needs the beta header above and runs on the Batch API only (Opus 4.8/4.7/4.6 and Sonnet 4.6). The SDK call sets the header for you.

Happy building! 🚀
{your_name}
Building with Claude
