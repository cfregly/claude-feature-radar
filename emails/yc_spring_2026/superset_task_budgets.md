Subject: Congrats on YC! Clean handoffs for many coding agents

Hey Kiet,

Congrats on the YC batch.

I'm Chris Fregly on Anthropic's Applied AI team, focused on startups. I work on the operational edges that appear once agents are running in parallel, not just in a demo.

I saw Superset helps engineers run 100s of coding agents in parallel. The Claude pattern that maps to that workload is loop-level task budgeting, so each agent can stop cleanly before it starts tool work it cannot finish.

Claude task budgets give the model a token budget for the whole agent loop: thinking, tool calls, tool results, and output. The model sees a running countdown and can hand off cleanly before starting work it cannot pay for. At Superset scale, that matters because a small overshoot multiplied across hundreds of parallel coding agents becomes real latency, queue pressure, and bill variance.

```python
msg = client.beta.messages.create(
    model="claude-opus-4-8",
    max_tokens=256,
    betas=["task-budgets-2026-03-13"],
    tools=tools,
    messages=messages,
    output_config={
        "effort": "low",
        "task_budget": {"type": "tokens", "total": 20000},  # budget for the full loop
    },
)
```

Using my API key, with the task budget exhausted, Claude made 0 tool calls and handed off before touching the first record. With budget to spare, the same agent started the loop and made 1 call. Scoped to one avoided tool action on this run, the point is the control surface: many agents can stop before launching work they no longer have budget to complete.

Full brief, demo GIF, code, and sample output: https://github.com/cfregly/claude-feature-hits/tree/main/task_budgets

Run it in a few seconds for $0.01:

```bash
git clone https://github.com/cfregly/claude-feature-hits && cd claude-feature-hits
# Get an API key: https://console.anthropic.com/
export ANTHROPIC_API_KEY=your-api-key
make task_budgets
```

To try it on your own agent, edit the prompt and tools in `task_budgets/run.py`, then re-run `make task_budgets`. I would still keep Superset's own hard billing and quota stops server-side. The task budget is the agent's loop-level countdown, not a replacement for your account limits.

If Superset is hitting a different many-agent failure mode, reply with the pattern and I can send the closest Claude example.

Happy building,

--Chris Fregly
Applied AI, Startups, Anthropic
