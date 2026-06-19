# Edge: Bulk extended output, the largest deliverable in one request

Part of [claude-feature-radar](../../README.md). This is a measured capability edge: a single batch
turn emits a deliverable larger than the competitors' per-request output ceiling.

## What It Is

On the Message Batches API with the beta header `output-300k-2026-03-24`, Claude raises the
single-request `max_tokens` ceiling to 300,000 output tokens (batch-only, on Opus 4.8/4.7/4.6 and
Sonnet 4.6). A nightly job that turns each backlog row into one long deliverable (a full report, a
large structured extraction, a long scaffold) lands it in one turn. The competitors' best models cap a
single request lower: GPT-5.5 at 128,000 output tokens, Gemini 3.5 Flash at 65,536. Any deliverable
above those caps forces a chunk-and-stitch loop with its own seam-failure surface.

## The Measured Proof

Run: `make bulk-output`, 2026-06-19, one request per arm asking for a 3,000-entry enumerated document
with a strict no-abbreviation instruction.

| arm | output tokens in one request | finished | documented single-request cap |
|---|--:|:---:|--:|
| Claude Sonnet 4.6, batch + 300k beta | 230,607 | yes (`end_turn`) | 300,000 |
| OpenAI GPT-5.5 | 764 | yes, stopped early | 128,000 |
| Gemini 3.5 Flash | 32,263 | yes, stopped early | 65,536 |

Claude emitted 230,607 output tokens in one request and finished the deliverable un-truncated, about
1.8x GPT-5.5's documented ceiling and 3.5x Gemini's. On the same prompt the competitors returned short
answers (764 and 32,263 tokens), well inside their caps. Machine receipt:
[`receipt.json`](receipt.json).

Per output token at the 50% batch discount the three are close, so the win is the single un-truncated
turn above 128k output, not the dollar figure. The full per-arm dollars are in the machine receipt.

## Honest Scope

- The win is one un-truncated deliverable per request above 128k output tokens. Below 128k every
  vendor fits one turn, so there is no edge there.
- Extended output is beta (`output-300k-2026-03-24`), batch-only, and not on Bedrock, Vertex, or
  Foundry. The Batch API is asynchronous, so a 230k-token generation takes minutes, not seconds.
- Frontier models decline to enumerate to their cap, so the competitor numbers are short answers, not
  truncations. The comparison is against their documented single-request output ceilings.

## Run It Yourself

```bash
git clone https://github.com/cfregly/claude-feature-radar && cd claude-feature-radar
make setup
make compare-deps
cp .env.example .env   # paste ANTHROPIC_API_KEY, OPENAI_API_KEY, and GEMINI_API_KEY
make bulk-output       # a few dollars, and the Claude batch can take many minutes
```

`make bulk-output` writes the latest local machine receipt to `data/last_bulk_extended_output.json`.

Sources, fetched 2026-06-19:

- Claude batch processing (300k extended output): https://platform.claude.com/docs/en/build-with-claude/batch-processing
- OpenAI GPT-5.5 model card (128k output): https://developers.openai.com/api/docs/models/gpt-5.5
- Gemini 3.5 Flash model card (65,536 output): https://ai.google.dev/gemini-api/docs/models/gemini-3.5-flash
