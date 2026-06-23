Subject: Congrats on YC! A sandbox pattern for work-app agents

Hey Jonny,

Congrats on getting Tasklet into YC.

I'm Chris Fregly on Anthropic's Applied AI team, focused on startups. I spend my time on the
mechanics that make agents cheaper, faster, safer, and easier to ship.

I saw Tasklet is building agents that call work-app APIs to get tasks done. The Claude pattern that
maps to that workload is app-API fan-out where the agent makes many calls, inspects bulky
intermediate results, and returns one action.

Without a filter point, every API result flows into the model context. Claude programmatic tool
calling gives you that filter point. Mark your tool as callable from code execution, then Claude can
write a sandbox script that loops over the tool and returns only the answer the model needs.

```python
tools=[
    {"type": "code_execution_20260120", "name": "code_execution"},
    {"name": "fetch_workspace_task", "input_schema": {...},
     "allowed_callers": ["code_execution_20260120"]},
]
```

Using my API key, the measured fan-out run went from 9,451 to 6,828 billed input tokens, with the
exact winner returned from the sandbox. That is 28% fewer billed input tokens than the same Claude
agent without programmatic tool calling. That is the shape: many tool calls, bulky results, one final
answer.

Full brief, demo GIF, code, and sample output: https://github.com/cfregly/claude-feature-hits/tree/main/programmatic_tool_calling

Run it in about two minutes for $0.08:

```bash
git clone https://github.com/cfregly/claude-feature-hits && cd claude-feature-hits
# Get an API key: https://console.anthropic.com/
export ANTHROPIC_API_KEY=your-api-key
make programmatic_tool_calling
```

To try it on Tasklet's shape, edit `programmatic_tool_calling/my_tool.py` with one of your work-app
tools and the inputs it fans out over.

If a different app-agent loop is the sharper blocker, reply with the flow and I can point you to the
closest Claude pattern, including the tool-boundary path for app-agent risk.

Happy building,

--Chris Fregly
Applied AI, Startups, Anthropic
