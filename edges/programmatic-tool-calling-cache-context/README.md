# Prove the programmatic tool calling plus cache plus 1M context cost cliff

![demo](https://raw.githubusercontent.com/cfregly/claude-feature-radar/main/edges/programmatic-tool-calling-cache-context/demo.gif)

[![Claude proof: 36% lower than Gemini 3.5 Flash cache+1M without programmatic tool calling](https://img.shields.io/badge/Claude%20proof-36%25%20lower%20than%20Gemini%203.5%20Flash%20cache%2B1M-2F855A)](https://github.com/cfregly/claude-feature-radar/blob/main/edges/programmatic-tool-calling-cache-context/sample.txt)

This artifact shows how programmatic tool calling changes the cost of a tool-heavy agent when the
same workflow also uses prompt caching and a 1M-token context window.

## What you get

Cache and a 1M context window help with a large stable prefix, but they do not make fresh tool outputs
free. If an agent receives 200,000 raw tool-output tokens on every turn, those tokens still enter the
model context and get billed as fresh input. Programmatic tool calling changes that leg: the raw tool
outputs stay in the code sandbox and only a small answer returns to the model.

The receipt models a 700,000-token stable prefix, 100 turns, and 200,000 raw tool-output tokens per
turn. GPT-5.5 and Gemini 3.5 Flash both get the favorable assumption: 1M context plus cache hits
after the first turn, but no programmatic tool calling equivalent.

| scenario | estimated model-token cost |
| --- | ---: |
| Claude Sonnet 4.6, no cache, no programmatic tool calling | $270.45 |
| Claude Sonnet 4.6 cache, no programmatic tool calling | $85.44 |
| GPT-5.5 best cache+1M, no programmatic tool calling | $135.55 |
| Gemini 3.5 Flash cache+1M, no programmatic tool calling | $40.67 |
| Claude Sonnet 4.6 cache + programmatic tool calling | $26.04 |

Claude cache + programmatic tool calling is $109.51 cheaper than GPT-5.5 best cache+1M without programmatic tool calling and $14.63 cheaper than
Gemini 3.5 Flash cache+1M without programmatic tool calling. That is 80.8% lower than the OpenAI row and 36.0% lower than
the Gemini row. The radar and public feature-hits commands both read the committed programmatic tool calling receipt, then apply the checked price table to the larger workload.

## Best-available comparison

The current receipt gives OpenAI its best available cost path for this declared workload: GPT-5.5,
1M context, and cache hits after the first turn, but no programmatic leg. The Gemini row uses Gemini 3.5 Flash
with its 1M-token input limit, cached-input pricing, code execution, and function calling.

Gemini 3.1 Flash-Lite is cheaper, but it is not the fair executor row for this workload by default.
Google's Flash-Lite guidance frames it around lightweight tasks and a router that sends high
operational complexity work with 4 or more tool calls to Flash or Pro. This artifact is a 100-turn,
high-tool-call agent workload. If a founder proves Flash-Lite handles their workload at equal
quality, rerun the receipt and use that row. Until then, Gemini 3.5 Flash is the fair Gemini
best-available row.

## Dimension matrix

| Dimension | Status | Receipt |
| --- | --- | --- |
| Cost | Measured | Claude cache + programmatic tool calling is $26.04, which is 80.8% lower than GPT-5.5 and 36.0% lower than Gemini 3.5 Flash on the declared workload. |
| Speed | Not measured | The receipt models token cost only. It does not claim latency or throughput. |
| Accuracy | Guarded, not promoted | The cited programmatic-tool-calling receipt checks the correct account list, but the larger table is a cost model. |
| Reliability | Guarded, not promoted | The cited receipt includes caller path, container, fallback, and correctness checks before the cost table is trusted. |
| Operations | Not claimed | The artifact does not count app code or runbook surfaces removed. |
| Security | Not claimed | No security property is claimed. |

Cost scope: this table is model-token arithmetic over a declared workload. Cache reads and cache
writes are included at their weighted token rates. Because programmatic tool calling uses code execution, code-execution
runtime can bill separately after the monthly free allowance. At current pricing, one newly billed
container has $0.0042 of 5-minute floor exposure at $0.05 per hour. Treat that as a separate
production COGS line item alongside token/API cost, backend cost, latency, failures, and correctness.

## Run it in radar ($0)

```
make programmatic-tool-calling-cache-context
```

`make programmatic-tool-calling-cache-context` is deterministic in radar. It parses `edges/programmatic-tool-calling/sample.txt`, recalculates the larger cache plus 1M-context table, and writes `edges/programmatic-tool-calling-cache-context/receipt.json` plus `data/last_programmatic_tool_calling_cache_context.json`. The public bundle under `engine/public_hits_bundle/programmatic_tool_calling_cache_context` is deterministic too and validates the same committed basis.

## Why this is separate from plain programmatic tool calling

`programmatic-tool-calling` proves the live mechanism on a real fan-out task. This artifact adds the
larger agent shape: a huge cached prefix, a 1M-context requirement, and recurring raw tool outputs.
programmatic tool calling removes the recurring raw-output leg from the model context.
