# Cited Facts

Verified on 2026-06-24 against official provider docs. These facts support comparison copy and
scope notes, but they are not runtime registry rows selected by the current code.

## Anthropic

- Claude Mythos 5 appears in the official model and pricing docs, but it is limited availability and is not selected by any current artifact. It is therefore kept out of the runtime registry.
  Source: [Anthropic models](https://platform.claude.com/docs/en/about-claude/models/overview), [Anthropic pricing](https://platform.claude.com/docs/en/about-claude/pricing).
- Web search version `web_search_20260318` supports dynamic filtering and response-inclusion control. `web_search_20250305` remains available for basic search.
  Source: [Anthropic web search](https://platform.claude.com/docs/en/agents-and-tools/tool-use/web-search-tool).
- Code execution version `code_execution_20260521` uses the same runtime as `code_execution_20260120` with the per-cell execution time limit disclosed in the tool description. `code_execution_20250825` remains the documented file-operations path.
  Source: [Anthropic code execution](https://platform.claude.com/docs/en/agents-and-tools/tool-use/code-execution-tool).
- Claude tool use returns a structured `tool_use` request for client tools, and the application executes the tool and returns a `tool_result`. Strict tool use constrains the model's tool input to the declared schema.
  Source: [Anthropic tool use](https://platform.claude.com/docs/en/agents-and-tools/tool-use/how-tool-use-works), [Anthropic strict tool use](https://platform.claude.com/docs/en/agents-and-tools/tool-use/strict-tool-use).

## OpenAI

- OpenAI lists `gpt-5.3-codex` as a specialized Codex model with separate pricing from the general GPT models used by this repo. No current artifact claims Codex-specific coverage. Add a Codex lane only for a coding-specific comparison.
  Source: [OpenAI pricing](https://developers.openai.com/api/docs/pricing).
- GPT-5.5 lists a 1,050,000-token context window and a 128,000-token max output.
  Source: [OpenAI GPT-5.5](https://developers.openai.com/api/docs/models/gpt-5.5).

## Gemini

- Gemini's Interactions API is generally available as of June 2026 and recommended for new projects. The original `generateContent` API remains fully supported and is considered legacy.
  Source: [Gemini Interactions API](https://ai.google.dev/gemini-api/docs/interactions-overview).
- Gemini 3.5 Flash lists a 1,048,576-token input limit and a 65,536-token output limit. The Standard pricing tier is $1.50 input, $9.00 output, and $0.15 cached input per 1M tokens.
  Source: [Gemini 3.5 Flash](https://ai.google.dev/gemini-api/docs/models/gemini-3.5-flash), [Gemini pricing](https://ai.google.dev/gemini-api/docs/pricing).
- Gemini 3.1 Flash-Lite is cheaper than Gemini 3.5 Flash, but the Flash-Lite guide frames it around lightweight tasks and shows router behavior that sends high operational complexity workloads with 4 or more tool calls to Flash or Pro. Use Flash-Lite in a high-tool-call comparison only after an equal-quality receipt exists for the same workload.
  Source: [Gemini 3.1 Flash-Lite](https://ai.google.dev/gemini-api/docs/models/gemini-3.1-flash-lite), [Gemini 3.5 Flash](https://ai.google.dev/gemini-api/docs/models/gemini-3.5-flash).
