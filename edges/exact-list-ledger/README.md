# Edge: Exact-list ledger, long streams with precise accumulated state

Part of [claude-feature-radar](../../README.md). This is a measured head-to-head edge, not a broad
claim that only Claude can solve the task. On the headline run all three frontier arms returned the
exact same list, and Claude did the exact long-stream job for less cost and less time. A 5-run repeat
then confirmed the Claude-versus-OpenAI result holds, not a single lucky run (see below).

## What It Is

A long agent reads 30 large incident reports through a tool. Each report is about 20,000 tokens and
points to the next report. The agent must keep the exact sorted list of every URGENT report id and
print the list after the final report.

That shape maps to founder workloads where the bulky input is disposable after each step, but the
running ledger must stay exact: fraud flags, billing exceptions, compliance findings, incident ids, or
support escalations.

The mechanism matters:

- Claude context editing clears old tool outputs in place, so bulky report text leaves context while
  the assistant turns that carry the running ledger stay intact.
- OpenAI Responses compaction summarizes prior context and carries forward the state through its
  compacted item.
- Gemini Pro carries the full context.

## The Measured Proof

Run: `make ledger`, 2026-06-19, same deterministic corpus and same exact-list prompt.

| arm | exact list | cost | wall time | peak context |
|---|:---:|---:|---:|---:|
| Claude Haiku 4.5 with context editing | yes | $0.67 | 60.7s | 35,186 |
| OpenAI GPT-5.5 with Responses compaction | yes | $1.84 | 164.3s | 41,548 |
| Gemini 3.1 Pro Preview with full context | yes | $2.57 | 201.0s | 434,629 |

Claude was exact, and it was about 64% cheaper and 63% faster than the exact OpenAI run. It was about
74% cheaper and 70% faster than the exact Gemini run.

Full receipt: [`sample.txt`](sample.txt). Machine receipt: [`receipt.json`](receipt.json).

## Confirmed Across Five Runs

A single run of a 30-step agent is close to a coin flip, so the headline was re-run 5 times per arm on
the same seeded corpus, for the two arms with server-side context management at this scale (Claude and
OpenAI). Every cell stayed exact.

| config | Claude (context editing) | OpenAI gpt-5.5 (compaction) | cost gap |
|---|---|---|---|
| keep=1 (the headline config) | 5/5 exact, $0.67/run | 5/5 exact, $1.90/run | Claude ~65% cheaper |
| keep=3 | 5/5 exact, $1.73/run | 5/5 exact, $1.88/run | Claude ~8% cheaper |
| keep=3, Sonnet 4.6 executor | 5/5 exact, $4.23/run | 5/5 exact, $1.93/run | strong-tier check, also exact |

Both arms are reliably exact in all 5 runs of every config, so the correctness is not a fluke and the
cost win is not one lucky run. The size of the cost gap depends on the context-editing `keep` setting:
aggressive clearing (keep=1) carries less context per turn, which is where the large gap comes from.
Receipt: [`repeated_runs.json`](repeated_runs.json).

## Honest Scope

- This is a long-stream exact-ledger edge. It is not a generic context-editing claim.
- The win is not that competitors failed. They both got the exact list on the full run.
- The win is that Claude got the exact list with less cost and time on this workload.
- The edge depends on the workload shape: large disposable tool outputs plus a precise accumulated
  state that must stay exact.
- The cost margin is config-sensitive: about 65% cheaper at keep=1 and about 8% at keep=3, with every
  arm exact across 5 runs in both. Aggressive clearing is where the large gap comes from.

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
