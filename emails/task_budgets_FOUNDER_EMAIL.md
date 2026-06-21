Subject: Congrats on YC! Clean handoffs for budgeted agent loops

Hey {first_name},

Congrats on the batch. Quick tip for anyone running agent loops in production: before you cap a task, log `usage.output_tokens` summed across the loop on a few real tasks so you know what one task actually costs.

Here is the problem I keep hitting. An agent runs a long tool loop over your users' data: it fetches records, calls APIs, reasons, writes a result. When it runs low on budget mid-loop, it starts the next tool call anyway and stops in the middle of an action. You get a half-finished job and a bill you never planned for.

Claude's task budget fixes this. You hand the model a token budget for the whole agentic loop (the back-and-forth where it thinks, calls a tool, reads the result, and repeats). The model sees a running countdown for everything it does and paces itself, so as the budget runs low it hands off cleanly instead of starting work it cannot finish. The budget lives in one config block:

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

I measured it on a budget-sensitive audit, same prompt both times. With the budget near zero, Claude made 0 tool calls and handed off before it touched the first record. With budget to spare, the same agent started the loop and made 1 call. The agent stops at the right moment on its own. Live on claude-opus-4-8, 2026-06-19.

Only Claude's task budget gives the model a budget marker for the whole agentic loop, so it is the only one that stopped before the first tool call. Scoped to one avoided tool action on this run.

Reproduce it in a few seconds for about $0.01. One clone, one command:

```bash
git clone https://github.com/cfregly/claude-feature-hits && cd claude-feature-hits
export ANTHROPIC_API_KEY=your-api-key
make task_budgets
```

Full brief, demo GIF, code, and sample output: https://github.com/cfregly/claude-feature-hits/tree/main/task_budgets

Docs: https://platform.claude.com/docs/en/build-with-claude/task-budgets

To run it on your own agent, edit the prompt and tools in `task_budgets/run.py`, then re-run `make task_budgets`.

One note: task budgets are in beta, so set the `task-budgets-2026-03-13` beta header (the `betas=[...]` line above) to opt in. I would still keep your own hard billing and quota stops server-side. The budget is the model's loop-level countdown, not a replacement for your account limits.

If you reply with the bottleneck you are working through, I can point you to the closest Claude pattern.

Happy building,

--Chris Fregly
Building with Claude
