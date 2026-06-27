# Edge: Programmatic Tool Calling, keep your tool outputs out of the model's token bill

Part of [claude-feature-radar](../../README.md), the internal engine. This note is the internal
both-directions read, not founder copy. The wins-only founder brief is
[`claude-feature-hits/programmatic_tool_calling`](https://github.com/cfregly/claude-feature-hits). This is the sharpest
edge the engine found, and it needs no beta header.

**What it is.** Add `allowed_callers: ["code_execution_20260120"]` to one of your tools and include the
code execution tool. Instead of one model round-trip per tool call, Claude writes a script in a sandbox
that calls your tool in a loop, filters and aggregates the results there, and returns only the answer.
The bulky tool outputs go to the sandbox, not the model, so you are not billed input tokens for data
the model never reads. No beta header required (verified 2026-06-18). Supported on Fable 5, Mythos 5
(limited availability), Opus 4.5 to 4.8, and Sonnet 4.5 to 4.6 (not Haiku).

## The measured proof

The same fan-out task two ways on the same model (Sonnet 4.6), with an identical-answer check: across 4
regions of 60 sales rows each (240 rows), find the highest-revenue region.

| mode | billed input tokens | answer | round-trips | token/API cost |
|---|--:|:--:|:--:|--:|
| Mode A: plain tool use (every row through context) | 9,494 | east | 2 | $0.06 |
| **Mode B: programmatic (`allowed_callers`)** | **6,910** | **east (correct)** | 5 | $0.02 |

**The honest read.** Mode B billed about **27% fewer input tokens** because the 240 rows went to the
sandbox, not the model context (Anthropic's own docs report about 24% on agentic-search benchmarks, so
ours is in line). Both modes answered `east` on this saved run. The deterministic reducer eval pins the
exact local winner. Full saved output in [`sample.txt`](sample.txt).

## The honest scope

- **Fan-out-shaped.** The win only appears when the model calls a tool many times. The doc notes a
  sequential single-call task (tau2-bench) is flat to about 8% more expensive.
- **It adds round-trips.** Here Mode B made more model round-trips than Mode A because the model called
  the tool serially from code, so on an instant mock tool it ran slower. The token saving is the win.
  On a real slow tool you also save the per-call model round-trip.
- **The dollar column is not all-in COGS.** PTC uses code execution. Code execution runtime can bill
  separately after the monthly free allowance, so production savings need token/API cost plus runtime
  charge, correctness, latency, fallback rate, and container failures.
- **No named competitor equivalent.** OpenAI ships a code interpreter and tool search but neither keeps
  your own custom-tool outputs out of context. This is absence-of-evidence, not a head-to-head loss.
- **Not everywhere.** Not on Amazon Bedrock or Vertex AI, and not ZDR-eligible.

Source: [programmatic tool calling](https://platform.claude.com/docs/en/agents-and-tools/tool-use/programmatic-tool-calling),
re-fetched 2026-06-18.

## Run it yourself

```bash
git clone https://github.com/cfregly/claude-feature-radar && cd claude-feature-radar
make setup
cp .env.example .env   # paste your Anthropic key
make programmatic-tool-calling               # this edge, about $0.08 token/API cost on Sonnet 4.6
# or directly: python edges/programmatic-tool-calling/demo.py
```
