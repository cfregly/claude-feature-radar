Subject: Congrats on YC! A Claude trick for agents that run too long

Hey {first_name},

Congrats on the batch. Quick tip if you are running agent loops in production: log `usage.output_tokens` summed across the loop for a few real tasks first, so you know what a task actually costs before you cap it.

Here is the problem I keep hitting. An agent runs a long tool loop over user data: it fetches records, calls APIs, reasons, writes a result. When it runs out of budget mid-loop, it keeps calling tools anyway and cuts off in the middle of an action. You get a half-finished job and a bill you did not plan for.

Claude's task budget fixes this. You hand the model a token budget for the whole agentic loop, and it sees a running countdown for everything it does (thinking, tool calls, tool results, output). As the budget runs low, it paces itself and hands off cleanly instead of starting work it cannot finish. Two lines:

```python
output_config={"task_budget": {"type": "tokens", "total": 64000}},  # add this
betas=["task-budgets-2026-03-13"],                                   # add this
```

I measured it on a budget-sensitive 12-record audit, same prompt both times. With the budget near zero, Claude made 0 tool calls and handed off before touching the first record. With budget to spare, the same agent started the loop. The agent stops at the right moment on its own. Live on claude-opus-4-8, 2026-06-19.

Demo and runnable code: https://github.com/cfregly/claude-feature-hits/blob/main/task_budgets/README.md

Run it in about a minute for roughly $0.01:

```bash
make task_budgets
```

To try it on your own agent, edit the prompt and tools in task_budgets/run.py and re-run `python -m task_budgets.run`.

Happy building! 🚀
{your_name}
Building with Claude
