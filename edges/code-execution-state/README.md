# Edge: Code-execution state that survives, files kept across requests for 30 days

Part of [claude-feature-radar](../../README.md). This is a measured agentic-reliability edge: Claude's
code-execution sandbox keeps your files across separate requests, and keeps them when the user steps
away, where the competitors lose them.

## What It Is

Claude's code execution tool persists its sandbox container and the files in it across separate
Messages API requests. Capture `response.container.id`, pass it as `container=<id>` on the next call,
and a file written in turn 1 is readable in turn 2. Containers live 30 days. So a multi-step data agent
uploads a dataset once, builds up intermediate files and state across a conversation, and never
re-uploads or re-runs setup, even if the user is idle for a while.

## The Measured Proof

Run: `make code-execution-state` (write a unique nonce to `/tmp/state.txt` in each vendor's sandbox, read it
back from the reused container), wait past the idle window, then `make code-execution-state-verify`
(re-read the same container). Measured 2026-06-19 with a 31-minute idle gap:

| vendor | persists across requests | survives a 31-min idle |
|---|:---:|:---:|
| Claude Sonnet 4.6 (`code_execution_20250825`) | yes | yes, read the file back |
| OpenAI GPT-5.5 (`code_interpreter`) | yes, while warm | no, `400 Container is expired` |
| Gemini 3.5 Flash (code execution) | no reusable container | not applicable |

All three ran. Claude and OpenAI both persist a file across requests while the container is warm. After
a 31-minute idle, Claude read the nonce back from the same container, while OpenAI's container had been
discarded (a real `400 Container is expired`, the documented 20-minute idle expiry). Gemini has no
reusable container handle, so a file written in one call is gone in the next. Machine receipt:
[`receipt.json`](receipt.json).

## Honest Scope

- While warm (same working session, no long idle), OpenAI reuses its container too, so the across-
  requests persistence is parity in that window. The edge is durability: Claude's 30-day container life
  versus OpenAI's 20-minute idle discard (unrecoverable), and Gemini having no reusable sandbox at all.
- This is a two-phase measurement: the write phase, then a re-read after the idle window elapses.
- Code execution is beta (`code-execution-2025-08-25`) and not ZDR-eligible.

## Run It Yourself

```bash
git clone https://github.com/cfregly/claude-feature-radar && cd claude-feature-radar
make setup
make compare-deps
cp .env.example .env        # paste ANTHROPIC_API_KEY, OPENAI_API_KEY, and GEMINI_API_KEY
make code-execution-state        # write phase: write a nonce, warm read-back, save container ids
# wait > 20 minutes (OpenAI's documented idle expiry)
make code-execution-state-verify # re-read: Claude survives, OpenAI's container is expired
```

Sources, fetched 2026-06-19:

- Claude code execution tool: https://platform.claude.com/docs/en/agents-and-tools/tool-use/code-execution-tool
- OpenAI code interpreter: https://developers.openai.com/api/docs/guides/tools-code-interpreter
- Gemini code execution: https://ai.google.dev/gemini-api/docs/code-execution
