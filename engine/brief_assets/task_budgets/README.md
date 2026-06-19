# Stop a budget-blown agent before it burns the next tool call, with Claude task budgets

![demo](demo.gif)

Your agent runs a long tool loop over user data: it fetches records, calls APIs, reasons, and writes a result. When it runs out of budget mid-loop, it keeps making tool calls anyway and cuts off in the middle of an action, leaving a half-finished job and a bill you did not plan for. Claude's `task_budget` gives the model a server-side countdown for the whole agentic loop (thinking, tool calls, tool results, and output), so it paces itself and hands off cleanly as the budget runs low instead of starting work it cannot finish.

## What you get

On a budget-sensitive 12-record audit, I gave Claude a near-exhausted task budget and a fresh one, same prompt both times. With the budget near zero, Claude made **0 tool calls** and handed off gracefully before touching the first `fetch_record`. With budget to spare, the same agent started the loop. The agent stops at the right moment on its own, so a long-running job ends with a clean handoff rather than a tool call it cannot pay for. Measured live on `claude-opus-4-8`, 2026-06-19.

```python
resp = client.beta.messages.create(
    model="claude-opus-4-8",
    max_tokens=128000,
    output_config={
        "effort": "high",
        "task_budget": {"type": "tokens", "total": 64000},  # add this
    },
    betas=["task-budgets-2026-03-13"],  # add this
    messages=[{"role": "user", "content": "Audit these records and report findings."}],
    tools=tools,
)
```

## Run it (about $0.01)

```bash
make task_budgets
```

Two live calls on `claude-opus-4-8`, a few seconds, about $0.01.

## Run it on your own workload

Edit the prompt and tools in `task_budgets/run.py`, then re-run:

```bash
python -m task_budgets.run
```

## Beta header

Task budgets are in beta. Set the `task-budgets-2026-03-13` beta header (the `betas=[...]` line above) to opt in. Supported on Claude Opus 4.8, Opus 4.7, Fable 5, and Mythos 5.

## Learn more

Claude task budgets: https://platform.claude.com/docs/en/build-with-claude/task-budgets
