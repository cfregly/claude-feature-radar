# Edge: Cache diagnostics, root cause for silent cache misses

Part of [claude-feature-radar](../../README.md). This is a measured observability edge, not a claim
that Claude is cheaper on every cached prompt.

## What It Is

A long cached-prefix request is sent twice. The second request silently changes the system prefix, the
kind of bug a production app gets from timestamps, routing metadata, or non-deterministic schema
serialization. All three providers expose cache-related token counters. Claude additionally returns a
typed `diagnostics.cache_miss_reason`.

## The Measured Proof

Run: `make cache-diagnostics`, 2026-06-19, same changed-prefix workload plus all documented
Claude cache-miss reason variants.

| arm | root cause known | miss reason | missed tokens | cost | wall time |
|---|:---:|---|---:|---:|---:|
| Claude Haiku 4.5 cache diagnostics | yes | `system_changed` | 6,827 | $0.0694 | 12.7s |
| OpenAI GPT-5.5 prompt caching | no | none exposed | 0 | $0.0515 | 2.7s |
| Gemini 3.1 Pro cache counters | no | none exposed | 0 | $0.0242 | 3.5s |

Claude identified 4/4 documented cache-miss reason variants:

| expected miss reason | observed miss reason | matched | missed tokens |
|---|---|:---:|---:|
| `system_changed` | `system_changed` | yes | 6,827 |
| `tools_changed` | `tools_changed` | yes | 7,360 |
| `messages_changed` | `messages_changed` | yes | 6,836 |
| `model_changed` | `model_changed` | yes | 6,827 |

Claude reduced the manual cache-miss suspect list from
4 possible prompt-prefix surfaces to
1: `system_changed`.

Full receipt: [`sample.txt`](sample.txt). Machine receipt: [`receipt.json`](receipt.json).

## Honest Scope

- This is an observability edge for debugging prompt-cache misses.
- The win is not lower cost on this probe. The win is that Claude names the changed prefix surface and
  estimates missed input tokens.
- OpenAI and Gemini still have prompt or context caching. Their closest live surfaces exposed cache
  counters, not a root-cause diagnostic field, on this workload.

## Run It Yourself

```bash
git clone https://github.com/cfregly/claude-feature-radar && cd claude-feature-radar
make setup
make compare-deps
cp .env.example .env   # paste ANTHROPIC_API_KEY, OPENAI_API_KEY, and GEMINI_API_KEY
make cache-diagnostics # full receipt, cents-scale on the 2026-06-19 run
```

`make cache-diagnostics` also writes the latest local machine receipt to
`data/last_cache_diagnostics.json`.

Sources:

- Claude cache diagnostics: https://platform.claude.com/docs/en/build-with-claude/cache-diagnostics
- OpenAI prompt caching: https://developers.openai.com/api/docs/guides/prompt-caching
- Gemini context caching: https://ai.google.dev/gemini-api/docs/caching
