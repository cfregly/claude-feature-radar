Subject: Congrats on YC! Clean handoffs for many coding agents

Hey Kiet,

First of all, congrats on the batch! Very exciting!!

My name is Chris Fregly, and I'm on the Applied AI team here at Anthropic. I focus on helping AI startups like Superset get past the bottlenecks that show up once agents move from demo to product.

I saw Superset helps engineers run 100s of coding agents in parallel. From one former founder to an active founder, builder to builder, I wanted to share a Claude pattern for coding agents that should stop cleanly before starting tool work they cannot finish.

Claude task budgets give the model a token budget for the whole agent loop: thinking, tool calls, tool results, and output. The model sees a running countdown and can hand off cleanly before starting a tool call it cannot pay for.

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

Using my API key, with the hidden task budget near zero, Claude made 0 tool calls and handed off before touching the first record. With budget to spare, the same agent started the loop and made 1 call. Scoped to one avoided tool action on this run.

Full brief, demo GIF, code, and sample output: https://github.com/cfregly/claude-feature-hits/tree/main/task_budgets

Run it in a few seconds for about $0.01:

```bash
git clone https://github.com/cfregly/claude-feature-hits && cd claude-feature-hits
# Starter credits if you need an API key: https://claude.com/offers?offer_code=bdfcc786-eb41-44f3-9190-e29e6e38209c&signup_code=3a6e0453a611a2c4bd79968fa98e3471
export ANTHROPIC_API_KEY=your-api-key
make task_budgets
```

To try it on your own agent, edit the prompt and tools in `task_budgets/run.py`, then re-run `make task_budgets`.

If I guessed the wrong bottleneck, reply with the real one and I can point you to the closest Claude pattern.

Happy building,

--Chris Fregly
Applied AI, Anthropic
fellow Claude builder and former AI startup founder
