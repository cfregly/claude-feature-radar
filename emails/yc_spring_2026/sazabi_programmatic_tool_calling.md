Subject: Congrats on YC! Cost and speed for log-triage agents

Hey Sherwood,

Congrats on YC.

I'm Chris Fregly on Anthropic's Applied AI team, focused on startups. I help teams turn promising
agent demos into production systems where cost, speed, reliability, accuracy, and security are all
designed in early.

I saw Sazabi is building AI-native observability around logs, Slack, and agent-driven
investigations. The Claude pattern that maps to that workload is log-triage fan-out without dragging
every row into the model context.

That workload can get expensive and slow fast. Every log slice or trace payload your tool returns
becomes model context unless you move the crunching somewhere else. Claude programmatic tool calling
lets the model write one sandbox script that calls your own tool in a loop, filters and aggregates
there, and returns only the fix-relevant answer.

```python
response = client.messages.create(
    model="claude-sonnet-4-6",
    messages=[...],
    tools=[
        {"type": "code_execution_20260120", "name": "code_execution"},
        {"name": "query_logs", "input_schema": {...},
         "allowed_callers": ["code_execution_20260120"]},
    ],
)
```

Using my API key, the same fan-out task on 240 rows went from 9,451 to 6,828 billed input tokens,
with the exact winner returned from the sandbox. That is 28% fewer billed input tokens than the same
Claude agent without programmatic tool calling.

Full brief, demo GIF, code, and sample output: https://github.com/cfregly/claude-feature-hits/tree/main/programmatic_tool_calling

Run it in about two minutes for $0.08:

```bash
git clone https://github.com/cfregly/claude-feature-hits && cd claude-feature-hits
# Get an API key: https://console.anthropic.com/
export ANTHROPIC_API_KEY=your-api-key
make programmatic_tool_calling
```

To try it on your own workload, edit `programmatic_tool_calling/my_tool.py` with your log query tool
and re-run the same command.

If Sazabi's heavier bottleneck is accuracy over incident context or security around tool access,
send me the rough workflow and I can point you to the closest Claude pattern.

Happy building,

--Chris Fregly
Applied AI, Startups, Anthropic
