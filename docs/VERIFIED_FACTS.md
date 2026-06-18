# Verified facts (source of truth)

Every number and parameter in this repo traces to a live doc page and a real API call, captured
on 2026-06-17 against the `anthropic` Python SDK `0.109.2`. The demo itself is the live check for
the beta parameters: it ran, it cleared context, and both runs returned the correct answer. If a
value here disagrees with the code, the code is wrong.

## Models and pricing

Pricing is per million tokens (MTok), verified against
[the pricing page](https://platform.claude.com/docs/en/about-claude/pricing). The demo uses Haiku
4.5 because it is the cheapest, so a founder reproducing the run spends about ninety cents.

| Model | API id | Input | Output | Cache read | Context |
|---|---|--:|--:|--:|--:|
| Claude Opus 4.8 | `claude-opus-4-8` | $5 | $25 | $0.50 | 1M |
| Claude Sonnet 4.6 | `claude-sonnet-4-6` | $3 | $15 | $0.30 | 1M |
| Claude Haiku 4.5 | `claude-haiku-4-5-20251001` | $1 | $5 | $0.10 | 200k |

The full table, including the cache-write tiers, lives in
[`../common/models.py`](../common/models.py).

## Citations (the anchor feature)

Source: [citations](https://platform.claude.com/docs/en/build-with-claude/citations), re-fetched
2026-06-17. GA, no beta header. Supported on all active models except Haiku 3. ZDR-eligible.

- Request: a `document` content block with `"citations": {"enabled": true}`. The source is
  `{"type": "text", "media_type": "text/plain", "data": ...}` for plain text, a base64/url/file PDF,
  or `{"type": "content", "content": [...]}` for custom chunks. Citations must be enabled on all or
  none of the documents in a request.
- Response: text blocks, each optionally carrying a `citations` list. For plain text each citation is
  `{"type": "char_location", "cited_text", "document_index", "start_char_index" (0-indexed),
  "end_char_index" (exclusive)}`. PDFs use `page_location` with 1-indexed `start_page_number` /
  `end_page_number`. Custom content uses `content_block_location` with block indices.
- Doc verbatim: the `cited_text` field "does not count towards output tokens" and (passed back on
  later turns) "is also not counted towards input tokens". The docs also state citations "are
  guaranteed to contain valid pointers to the provided documents."
- Incompatible with Structured Outputs: enabling citations on a user document together with
  `output_config.format` returns a 400.
- Verified live by [`../engine/citations.py`](../engine/citations.py): over 8 questions on 3 plain
  text documents, every returned `char_location` satisfied `source[start:end] == cited_text` (8/8).
  The honest baseline is the DIY path (ask the model for the verbatim quote, resolve it yourself with
  `source.find(quote)`), which also resolves 8/8 on clean text on Claude, OpenAI gpt-5.4-mini, and
  Gemini gemini-3.5-flash. The measured edge is that Claude does the resolving in-API (guaranteed,
  the DIY find returns -1 the moment the model paraphrases), the quote is free of output tokens (308
  versus 586 on the Claude DIY arm), and no competitor ships the primitive. An earlier version of
  this benchmark asked the models to emit the character offset and scored that 0/8, which a scrutiny
  panel correctly flagged as a strawman (a tokenizer cannot count characters). Receipt:
  [`../sample_citations.txt`](../sample_citations.txt).

### Competitor citation surfaces (the parity check)
- OpenAI emits `url_citation` annotations from its web-search tool, not a pointer into a
  user-supplied document.
- Gemini returns web grounding metadata, also web-URL based, not a char/page pointer into an uploaded
  document.
- Neither exposes a document-grounded char/page citation primitive as of 2026-06-17. Sourced in
  [`../briefs/2026-06-17-platform-edge.md`](../briefs/2026-06-17-platform-edge.md).

## Long-horizon autonomy (the second pillar)

Source: METR task time-horizon, [metr.org/time-horizons](https://metr.org/time-horizons/), data file
pulled 2026-06-17 (page updated 2026-05-08). On the 50% task time-horizon, the top released Claude
model carries the only `is_sota` flag at about 12 hours, versus Gemini 3.1 Pro about 6.4 hours and
GPT-5.2 about 5.9 hours, roughly 1.9x the best non-Claude model. METR is an independent referee, not
a vendor. Claude does NOT lead the headline coding boards (SWE-bench Verified is a 79.2% ceiling tie,
GPT-5.5 leads both Terminal-Bench tracks), so this is the only long-horizon claim that survives a
skeptic on neutral data. Full reconciliation, with every source and date, in
[`../briefs/2026-06-17-agentic-landscape.md`](../briefs/2026-06-17-agentic-landscape.md).

## Context editing (a demoted within-Claude value-add)

Source: [context editing](https://platform.claude.com/docs/en/build-with-claude/context-editing).

- Beta header: `anthropic-beta: context-management-2025-06-27`.
- Request parameter (top level of the messages body):

```json
{
  "context_management": {
    "edits": [
      {
        "type": "clear_tool_uses_20250919",
        "trigger": {"type": "input_tokens", "value": 6000},
        "keep": {"type": "tool_uses", "value": 2},
        "exclude_tools": ["memory"]
      }
    ]
  }
}
```

- It clears the oldest tool results once the trigger is crossed, keeping the most recent `keep`
  tool-use pairs. It clears in place, it does not summarize.
- It clears in place, it does not summarize. With the edit on, per-turn input tokens plateau near the
  trigger instead of climbing with the transcript. That divergence (a flat per-turn context with the
  edit on versus a climbing one with it off) is the proof it engaged, and it is what the longhorizon
  receipt shows.
- The value of context editing is measured, isolated to one variable, in
  [`../engine/longhorizon.py`](../engine/longhorizon.py): the same 8-report chain of about 40k-token
  payloads run twice, the memory tool ON in both arms and the identical prompt in both, with only
  context editing toggled. The failure is not deterministic, so it is run three times (`--repeat 3`):
  editing OFF failed 3 of 3 (2 crashed at the 200,000 window, 1 returned a wrong count), editing ON
  finished correctly 3 of 3. One captured editing-OFF run climbed from 1,816 to 187,471 carried tokens
  (per-turn cost up 24.7x) and then exceeded the window, so the API rejected the request (measured:
  `prompt is too long: 203056 tokens > 200000 maximum`). Editing ON held context flat near 34k and
  answered correctly (3 of a true 3) for about thirty-five cents. The win is reliability, caused by
  context editing alone. Correctness is held constant by the memory tool, which is on in both arms, so
  it is the memory tool, not context editing, that makes the count correct. Receipt in
  [`../sample_longhorizon.txt`](../sample_longhorizon.txt).

## The memory tool (the second anchor feature)

Source: [memory tool](https://platform.claude.com/docs/en/agents-and-tools/tool-use/memory-tool).

- Tool definition: `{"type": "memory_20250818", "name": "memory"}`. No separate beta header.
- The model issues commands (`view`, `create`, `str_replace`, `insert`, `delete`, `rename`) over
  a `/memories` path. The client executes them as file operations. The handler is in
  [`../engine/memory_backend.py`](../engine/memory_backend.py), sandboxed to a single root.
- Verified live by the demo: the managed agent created `/memories/urgent.txt`, appended ids to it
  as it read, and viewed it at the end to produce the correct count even though the source
  documents had been cleared from context.

## Using them together

Both are sent on the same request. Context editing carries the beta header, the memory tool does
not. `exclude_tools: ["memory"]` keeps the memory interactions from being cleared. This is the
exact combination the demo runs.

## Usage shape (verified live)

The cost math in [`../common/pricing.py`](../common/pricing.py) reads these fields off the `usage`
object the API returns: `input_tokens`, `output_tokens`, `cache_read_input_tokens`,
`cache_creation_input_tokens` (and the `cache_creation` 5m/1h split when caching runs). Every
dollar figure in this repo is those counts times the verified rates above.

## Token fields differ across vendors (apples to apples)

Carried context must count the same tokens on every side. Claude splits its input into three
disjoint buckets: `input_tokens` (uncached), `cache_read_input_tokens` (read from cache), and
`cache_creation_input_tokens` (written to cache this turn). They sum to the prompt the model actually
processed, so the true carried context on Claude is all three:
`input_tokens + cache_read_input_tokens + cache_creation_input_tokens`. Counting only the first two
undercounts badly on a cold turn or the turn right after context editing clears, where almost the
whole prefix is a write, so `input_tokens` drops to about 1 and `cache_read` is 0 (measured, see the
longhorizon receipt). OpenAI's `input_tokens` and Gemini's `prompt_token_count`
already INCLUDE cached tokens, so those fields are the carried context as is. The benchmark records a
`ctx` field per turn that applies this per vendor, and the peak-context column uses it. Comparing raw
`input_tokens` across vendors would understate Claude's context, the confound recorded in
[`FINDINGS.md`](FINDINGS.md).

## OpenAI comparison (the compare module)

The cross-platform view ([`../engine/compare.py`](../engine/compare.py),
[`../engine/openai_arm.py`](../engine/openai_arm.py), [`../engine/gemini_arm.py`](../engine/gemini_arm.py))
runs OpenAI on the Responses API (compaction plus caching) and Gemini on the google-genai SDK
(implicit caching, no server-side trimming), each best-config. Verified 2026-06-17.

- OpenAI prices per 1M tokens (developers.openai.com): `gpt-5.4-mini` is $0.75 input, $0.075 cached,
  $4.50 output. `gpt-5.4-nano` is $0.20 / $0.02 / $1.25.
- Gemini prices per 1M tokens, paid tier (ai.google.dev/gemini-api/docs/pricing): `gemini-3.5-flash`
  is $1.50 input, $0.15 cached, $9.00 output. `gemini-3.1-flash-lite` is $0.25 / $0.025 / $1.50.
  `gemini-3.1-pro-preview` is $2.00 / $0.20 / $12.00.
- The tool-use loop is `client.chat.completions.create(model, messages, tools, parallel_tool_calls=False)`.
  `parallel_tool_calls=False` forces one step per turn, matching the Claude run.
- Cost reads from `response.usage`: `prompt_tokens` (input, includes cached), `completion_tokens`
  (output), and `prompt_tokens_details.cached_tokens` (the cached subset, billed at the cached rate).
- OpenAI has no in-place context editing and no model-driven memory tool on Chat Completions. Its
  server-side context lever is compaction on the Responses API, which summarizes. Sources:
  [function calling](https://developers.openai.com/api/docs/guides/function-calling),
  [compaction](https://developers.openai.com/api/docs/guides/compaction).
- `openai` is an optional dependency ([`../requirements-compare.txt`](../requirements-compare.txt)),
  needed only for the comparison.

## What is not verified, and is therefore not quoted

- A "roughly 84% context reduction" figure for context editing circulates online but was not found
  on the current doc page. This repo measures its own reduction instead of quoting that number.
- Competitor capabilities are cited from the competitors' own docs in
  [`../briefs/2026-06-17-verified-picture.md`](../briefs/2026-06-17-verified-picture.md),
  dated 2026-06-17. They move monthly. Re-run the scan before reusing them.
