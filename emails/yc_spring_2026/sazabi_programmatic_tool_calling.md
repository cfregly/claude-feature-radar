Subject: Congrats on YC! A sandbox pattern for log-triage agents

Hey Sherwood,

Congrats on YC - very exciting!!

I'm Chris Fregly on the Applied AI team here at Anthropic. I focus on helping AI startups turn promising agent demos into production systems that stay fast and affordable.

I saw Sazabi is building AI-native observability around logs, Slack, and agent-driven investigations. From one former founder to an active founder, builder to builder, I wanted to share a Claude pattern for log-triage agents that need to fan out over many log slices without dragging every row into the model context.

That workload can get expensive fast. Every log slice or trace payload your tool returns becomes model context unless you move the crunching somewhere else. Claude programmatic tool calling lets the model write one sandbox script that calls your own tool in a loop, filters and aggregates there, and returns only the fix-relevant answer.

```python
response = client.messages.create(
    model="claude-sonnet-4-6",
    messages=[...],
    tools=[
        {"type": "code_execution_20260120", "name": "code_execution"},  # add this
        {"name": "query_logs", "input_schema": {...},
         "allowed_callers": ["code_execution_20260120"]},               # log rows stay in the sandbox
    ],
)
```

Using my API key, the same fan-out task on 240 rows went from 9,451 to 6,828 billed input tokens, with the exact winner returned from the sandbox. That is 28% fewer billed input tokens on the measured run.

Full brief, demo GIF, code, and sample output: https://github.com/cfregly/claude-feature-hits/tree/main/programmatic_tool_calling

Run it in about two minutes for about $0.08:

```bash
git clone https://github.com/cfregly/claude-feature-hits && cd claude-feature-hits
# Starter credits if you need an API key: https://claude.com/offers?offer_code=bdfcc786-eb41-44f3-9190-e29e6e38209c&signup_code=3a6e0453a611a2c4bd79968fa98e3471
export ANTHROPIC_API_KEY=your-api-key
make programmatic_tool_calling
```

To try it on your own workload, edit `programmatic_tool_calling/my_tool.py` with your log query tool and re-run the same command.

If Sazabi's biggest agent cost is not log fan-out, send me the bottleneck and I can point you to the closest Claude pattern.

Happy building,

--Chris Fregly
Applied AI, Anthropic
