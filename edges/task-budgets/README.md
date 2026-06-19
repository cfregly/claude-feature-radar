# Edge: Task budgets, stop before a budget-exhausted tool loop

Part of [claude-feature-radar](../../README.md). This is a measured tool-loop control edge, not a claim that Claude is cheaper on every budgeted task.

## What It Is

A long-running agent is about to start a tool loop. With Claude `task_budget`, the model sees a provider-side remaining-budget marker for the full loop, including thinking, tool calls, tool results, and output. When the marker is near exhaustion, Claude can hand off before starting a tool action that should not begin under an exhausted budget.

## The Measured Proof

Run: `make task-budget`, 2026-06-19, same first-tool-call workload.

| arm | hidden low-budget stop | first tool calls | wall time |
|---|:---:|---:|---:|
| Claude claude-opus-4-8 low budget | yes | 0 | 1.6s |
| Claude claude-opus-4-8 high-budget control | n/a | 1 | 3.0s |
| OpenAI gpt-5.5 closest controls | no | 1 | 2.1s |
| Gemini gemini-3.1-pro-preview closest controls | no | 1 | 3.3s |

Claude stopped before the first `fetch_record` call at low remaining budget. The high-budget Claude control, OpenAI closest controls, and Gemini closest controls all started the tool loop.

Full receipt: [`sample.txt`](sample.txt). Machine receipt: [`receipt.json`](receipt.json).

## Honest Scope

- This is a full-loop budget-control edge for agent handoff before external tool actions.
- The measured win is one avoided tool action at the point the task is already near budget exhaustion.
- OpenAI and Gemini have adjacent output, reasoning, or thinking controls. The fetched docs and live workload did not expose an equivalent hidden full-loop remaining-budget marker.

## Run It Yourself

```bash
git clone https://github.com/cfregly/claude-feature-radar && cd claude-feature-radar
make setup
make compare-deps
cp .env.example .env   # paste ANTHROPIC_API_KEY, OPENAI_API_KEY, and GEMINI_API_KEY
make task-budget       # bounded live receipt
```

Sources:

- Claude task budgets: https://platform.claude.com/docs/en/build-with-claude/task-budgets
- OpenAI reasoning controls: https://developers.openai.com/api/docs/guides/reasoning
- Gemini thinking budgets: https://ai.google.dev/gemini-api/docs/thinking
