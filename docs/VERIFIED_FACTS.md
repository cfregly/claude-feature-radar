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

## Context editing (the first anchor feature)

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
- Verified live by [`../engine/demo.py`](../engine/demo.py): with this edit on, per-turn input
  tokens plateau near the trigger instead of climbing with the transcript. Without it, on the same
  task, they climb linearly to 35,206 by turn 32. That divergence is the proof it engaged.

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

## OpenAI comparison (the compare module)

The cross-platform view ([`../engine/compare.py`](../engine/compare.py),
[`../engine/openai_arm.py`](../engine/openai_arm.py)) runs on OpenAI's Chat Completions API,
verified 2026-06-17 against developers.openai.com.

- Models and prices per 1M tokens, from the pricing page: `gpt-5.4-mini` is $0.75 input, $0.075
  cached input, $4.50 output. `gpt-5.4-nano` is $0.20 / $0.02 / $1.25. The older `gpt-4o-mini` and
  `gpt-5-mini` are no longer listed.
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
