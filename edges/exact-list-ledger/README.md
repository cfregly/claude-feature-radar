# Edge: Exact-list ledger, long streams with precise accumulated state

Part of [claude-feature-radar](../../README.md). This is a measured head-to-head edge, not a broad
claim that only Claude can solve the task. On this run, all three frontier arms returned the exact
same list. Claude won because it did the exact long-stream job for less cost and less time.

## What It Is

A long agent reads 30 large incident reports through a tool. Each report is about 20,000 tokens and
points to the next report. The agent must keep the exact sorted list of every URGENT report id and
print the list after the final report.

That shape maps to founder workloads where the bulky input is disposable after each step, but the
running ledger must stay exact: fraud flags, billing exceptions, compliance findings, incident ids, or
support escalations.

The mechanism matters:

- Claude context editing clears old tool results in place, so bulky report text leaves context while
  the assistant turns that carry the running ledger stay intact.
- OpenAI Responses compaction summarizes prior context and carries forward the state through its
  compacted item.
- Gemini Pro carries the full context.

## The Measured Proof

Run: `make ledger`, 2026-06-19, same deterministic corpus and same exact-list prompt.

| arm | exact list | cost | wall time | peak context |
|---|:---:|---:|---:|---:|
| Claude Haiku 4.5 with context editing | yes | $0.6700 | 60.7s | 35,186 |
| OpenAI GPT-5.5 with Responses compaction | yes | $1.8425 | 164.3s | 41,548 |
| Gemini 3.1 Pro Preview with full context | yes | $2.5690 | 201.0s | 434,629 |

Claude was exact, and it was about 64% cheaper and 63% faster than the exact OpenAI run. It was about
74% cheaper and 70% faster than the exact Gemini run.

Full receipt: [`sample.txt`](sample.txt). Machine receipt: [`receipt.json`](receipt.json).

## Honest Scope

- This is a long-stream exact-ledger edge. It is not a generic context-editing claim.
- The win is not that competitors failed. They both got the exact list on the full run.
- The win is that Claude got the exact list with less cost and time on this workload.
- The edge depends on the workload shape: large disposable tool results plus a precise accumulated
  state that must stay exact.

## Run It Yourself

```bash
git clone https://github.com/cfregly/claude-feature-radar && cd claude-feature-radar
make setup
make compare-deps
cp .env.example .env   # paste ANTHROPIC_API_KEY, OPENAI_API_KEY, and GEMINI_API_KEY
make ledger            # full receipt, about $5 on the 2026-06-19 run
make ledger-smoke      # cheap harness check without the full comparison
```

`make ledger` also writes the latest local machine receipt to `data/last_ledger_compare.json`.

Sources:

- Claude context editing: https://platform.claude.com/docs/en/build-with-claude/context-editing
- OpenAI compaction: https://developers.openai.com/api/docs/guides/compaction
- Gemini long context: https://ai.google.dev/gemini-api/docs/long-context
