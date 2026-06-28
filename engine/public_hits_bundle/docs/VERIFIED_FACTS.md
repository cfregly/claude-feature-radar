# Verified Facts

Verified on 2026-06-24 against official provider docs. This is the tracked public receipt layer for
the runtime registry in `*/common/model_catalog.py`. Local `PROVENANCE.md` files are intentionally ignored
and are not required by a public clone.

## Runtime Model Registry

| Key | Runtime id | Provider | Input per 1M | Output per 1M | Cached input per 1M | Context | Max output | Source |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | --- |
| `opus` | `claude-opus-4-8` | Anthropic | $5.00 | $25.00 | $0.50 | 1,000,000 | 128,000 | [Anthropic models](https://platform.claude.com/docs/en/about-claude/models/overview), [Anthropic pricing](https://platform.claude.com/docs/en/about-claude/pricing) |
| `sonnet` | `claude-sonnet-4-6` | Anthropic | $3.00 | $15.00 | $0.30 | 1,000,000 | 128,000 | [Anthropic models](https://platform.claude.com/docs/en/about-claude/models/overview), [Anthropic pricing](https://platform.claude.com/docs/en/about-claude/pricing) |
| `haiku` | `claude-haiku-4-5-20251001` | Anthropic | $1.00 | $5.00 | $0.10 | 200,000 | 64,000 | [Anthropic models](https://platform.claude.com/docs/en/about-claude/models/overview), [Anthropic pricing](https://platform.claude.com/docs/en/about-claude/pricing) |
| `fable` | `claude-fable-5` | Anthropic | $10.00 | $50.00 | $1.00 | 1,000,000 | 128,000 | [Anthropic models](https://platform.claude.com/docs/en/about-claude/models/overview), [Anthropic pricing](https://platform.claude.com/docs/en/about-claude/pricing) |
| `gpt-nano` | `gpt-5.4-nano` | OpenAI | $0.20 | $1.25 | $0.02 | 400,000 | not used by current ceiling tables | [OpenAI pricing](https://developers.openai.com/api/docs/pricing) |
| `gpt-mini` | `gpt-5.4-mini` | OpenAI | $0.75 | $4.50 | $0.075 | 400,000 | not used by current ceiling tables | [OpenAI pricing](https://developers.openai.com/api/docs/pricing) |
| `gpt-mid` | `gpt-5.4` | OpenAI | $2.50 | $15.00 | $0.25 | 1,050,000 | not used by current ceiling tables | [OpenAI pricing](https://developers.openai.com/api/docs/pricing) |
| `gpt-top` | `gpt-5.5` | OpenAI | $5.00 | $30.00 | $0.50 | 1,050,000 | 128,000 | [OpenAI GPT-5.5](https://developers.openai.com/api/docs/models/gpt-5.5) |
| `gem-lite` | `gemini-3.1-flash-lite` | Gemini | $0.25 | $1.50 | $0.025 | 1,000,000 | not used by current ceiling tables | [Gemini pricing](https://ai.google.dev/gemini-api/docs/pricing) |
| `gem-flash` | `gemini-3.5-flash` | Gemini | $1.50 | $9.00 | $0.15 | 1,048,576 | 65,536 | [Gemini 3.5 Flash](https://ai.google.dev/gemini-api/docs/models/gemini-3.5-flash), [Gemini pricing](https://ai.google.dev/gemini-api/docs/pricing) |
| `gem-pro` | `gemini-3.1-pro-preview` | Gemini | $2.00 | $12.00 | $0.20 | 1,000,000 | not used by current ceiling tables | [Gemini pricing](https://ai.google.dev/gemini-api/docs/pricing) |

## Reasoning Effort Values

- OpenAI `gpt-5.5` supports `none`, `low`, `medium`, `high`, and `xhigh` for `reasoning.effort`, with `medium` as the default. The runtime registry includes those values on the `gpt-top` row.
  Source: [OpenAI GPT-5.5](https://developers.openai.com/api/docs/models/gpt-5.5), [OpenAI reasoning](https://developers.openai.com/api/docs/guides/reasoning).

## Billing Rules

- Anthropic Message Batches are billed at 50% of standard API prices.
  Source: [Anthropic batch processing](https://platform.claude.com/docs/en/build-with-claude/batch-processing).
- Anthropic prompt-caching cost uses separate token buckets: cache reads are 0.1x base input price,
  5-minute cache writes are 1.25x base input price, and 1-hour cache writes are 2x base input price.
  Source: [Anthropic prompt caching](https://platform.claude.com/docs/en/build-with-claude/prompt-caching), [Anthropic pricing](https://platform.claude.com/docs/en/about-claude/pricing).
- Anthropic web search bills in addition to token usage at $10 per 1,000 searches. The API reports this under `usage.server_tool_use.web_search_requests`, and `cost_usd` includes it when present.
  Source: [Anthropic web search](https://platform.claude.com/docs/en/agents-and-tools/tool-use/web-search-tool).
- Anthropic code execution can bill by execution time when not paired with `web_search_20260209` or later, or `web_fetch_20260209` or later.
  Current pricing has a 5-minute minimum, 1,550 free hours per org per month, and $0.05 per hour per container after that allowance.
  Source: [Anthropic code execution](https://platform.claude.com/docs/en/agents-and-tools/tool-use/code-execution-tool).
- Gemini Standard tier values are used for registry rows. Priority, Batch, and Flex rates are different and are not the default comparison cost model.
  Source: [Gemini pricing](https://ai.google.dev/gemini-api/docs/pricing).
- Gemini 3.1 Flash-Lite is tracked as a cheap Gemini row, but `programmatic_tool_calling_cache_context` does not use it as
  the default high-tool-call executor. The Flash-Lite guidance frames it around lightweight tasks and
  shows router behavior that sends high operational complexity workloads with 4 or more tool calls to
  Flash or Pro. `programmatic_tool_calling_cache_context` is a 100-turn high-tool-call workload, so Gemini 3.5 Flash is the
  fair Gemini row unless a live Flash-Lite receipt proves equal quality.
  Source: [Gemini 3.1 Flash-Lite](https://ai.google.dev/gemini-api/docs/models/gemini-3.1-flash-lite), [Gemini 3.5 Flash](https://ai.google.dev/gemini-api/docs/models/gemini-3.5-flash).

## API Freshness Notes

- Gemini's Interactions API is generally available as of June 2026 and recommended for new projects. `generateContent` remains supported. Current comparison arms that still use `generateContent` are a migration queue item, not evidence that those arms are broken.
  Source: [Gemini Interactions API](https://ai.google.dev/gemini-api/docs/interactions-overview).
- Newer web-search versions add dynamic filtering and response-inclusion controls.
  Source: [Anthropic web search](https://platform.claude.com/docs/en/agents-and-tools/tool-use/web-search-tool).
- Newer code-execution versions add REPL state persistence, programmatic tool calling support, and per-cell execution-time-limit disclosure.
  Source: [Anthropic code execution](https://platform.claude.com/docs/en/agents-and-tools/tool-use/code-execution-tool).
