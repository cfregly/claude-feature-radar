# Stop a runaway agent before it starts a tool call it cannot pay for

![demo](https://raw.githubusercontent.com/cfregly/claude-feature-hits/main/task_budgets/demo.gif)

[![Claude proof: 1 to 0 tool calls](https://img.shields.io/badge/Claude%20proof-1%20to%200%20tool%20calls-2F855A)](https://github.com/cfregly/claude-feature-hits/blob/main/task_budgets/sample.txt)

The GIF replays the saved `sample.txt` output in under ten seconds, so you can see the command and value before running a live call.

Your agent runs a long tool loop over your users' data: it fetches records, calls APIs, reasons, and writes a result. When it runs low on budget mid-loop, it starts the next tool call anyway and stops in the middle of an action, leaving a half-finished job and a bill you never planned for. Claude's `task_budget` hands the model a token budget for the whole agentic loop (the cycle where it thinks, calls a tool, reads the result, and repeats), with a server-side countdown it sees the entire time, so it paces itself and hands off cleanly as the budget runs low.

## What you get

On a budget-sensitive audit, I gave Claude a near-exhausted task budget and a fresh one, same prompt both times. With the budget near zero, Claude made **0 tool calls** and handed off cleanly before it touched the first record. With budget to spare, the same agent started the loop and made **1 call**. The agent stops at the right moment on its own, so a long-running job ends with a clean handoff. Measured live on `claude-opus-4-8`, 2026-06-19.

```python
msg = client.beta.messages.create(
    model="claude-opus-4-8",
    max_tokens=256,
    betas=["task-budgets-2026-03-13"],  # opt into the beta
    tools=tools,
    messages=messages,
    output_config={
        "effort": "low",
        "task_budget": {"type": "tokens", "total": 20000},  # budget for the whole loop
    },
)
```

## The capability

Claude's task budget is the control surface this brief proves. On this run, the near-exhausted budget stopped before the first tool call, while the fresh-budget control started the loop. Scoped to one avoided tool action, it shows how to hand off before launching work the agent no longer has budget to finish.

## Run it ($0.01)

```bash
export ANTHROPIC_API_KEY=your-api-key   # https://console.anthropic.com/
make task_budgets
```

Two live calls on `claude-opus-4-8`, a few seconds, $0.01.

## Run it on your own data

Edit the prompt and tools in `task_budgets/run.py`, then re-run `make task_budgets`.

## Learn more

Claude task budgets: https://platform.claude.com/docs/en/build-with-claude/task-budgets
