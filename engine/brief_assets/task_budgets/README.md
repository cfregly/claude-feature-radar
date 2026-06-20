# Stop a runaway agent before it starts a tool call it cannot pay for

![demo](demo.gif)

Your agent runs a long tool loop over your users' data: it fetches records, calls APIs, reasons, and writes a result. When it runs low on budget mid-loop, it starts the next tool call anyway and stops in the middle of an action, leaving a half-finished job and a bill you never planned for. Claude's `task_budget` hands the model a token budget for the whole agentic loop (the cycle where it thinks, calls a tool, reads the result, and repeats), with a server-side countdown it sees the entire time, so it paces itself and hands off cleanly as the budget runs low.

## What you get

On a budget-sensitive audit, I gave Claude a near-exhausted task budget and a fresh one, same prompt both times. With the budget near zero, Claude made **0 tool calls** and handed off cleanly before it touched the first record. With budget to spare, the same agent started the loop and made **1 call**. The agent stops at the right moment on its own, so a long-running job ends with a clean handoff. Measured live on `claude-opus-4-8`, 2026-06-19.

```python
output_config={
    "effort": "high",
    "task_budget": {"type": "tokens", "total": 64000},  # add this: server-side countdown for the whole loop
},
betas=["task-budgets-2026-03-13"],  # add this: opt into the beta
```

## The capability

Only Claude's task budget gives the model a budget marker for the whole agentic loop, so it is the only one that stopped before the first tool call. Scoped to one avoided tool action on this run.

## Run it (about $0.01)

```bash
export ANTHROPIC_API_KEY=sk-ant-...
make task_budgets
```

Two live calls on `claude-opus-4-8`, a few seconds, about $0.01.

## Run it on your own data

Edit the prompt and tools in `task_budgets/run.py`, then re-run `make task_budgets`.

## Learn more

Claude task budgets: https://platform.claude.com/docs/en/build-with-claude/task-budgets
