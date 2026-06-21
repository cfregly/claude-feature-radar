Subject: Congrats on YC! A sandbox pattern for usage-metering agents

Hey {first_name},

Congrats on the batch, that is a real milestone. Quick builder tip in case it helps.

If you meter usage per cohort or run analytics across regions, your agent calls one of your own tools many times, then crunches what comes back. Every one of those calls dumps its rows into the model's context, and you pay input tokens for all of them, even the rows the agent never uses to answer.

[Programmatic tool calling](https://platform.claude.com/docs/en/agents-and-tools/tool-use/programmatic-tool-calling) moves that work off the model. Claude writes one script that loops over your tool inside a code sandbox (a server-side scratchpad that runs the rows), keeps only what matters, and passes just the answer back. The rows stay in the sandbox, so they never hit the context.

You add the code execution tool, then one line to the tool you already pass. `allowed_callers` is the one that does the work: it tells Claude your tool can be called from the sandbox instead of through the model.

```python
response = client.messages.create(
    model="claude-sonnet-4-6",
    messages=[...],
    tools=[
        {"type": "code_execution_20260120", "name": "code_execution"},   # add this
        { "name": "query_region_sales", "input_schema": {...},   # your tool, unchanged
          "allowed_callers": ["code_execution_20260120"] },        # add this line: rows run in the sandbox, not the model context
    ],
)
```

Same task, same model (Sonnet 4.6), the only change is the feature on or off:

| your run | input tokens billed | what it means |
|---|---:|---|
| without programmatic tool calling | 9,451 | every row lands in the model's context |
| with programmatic tool calling | 6,828 | only the answer reaches the model |

28% fewer input tokens on my run, with the exact winner returned from the sandbox. The saving grows with the size of the fan-out (an agent calling one tool many times over data it then crunches).

Why I am sending this for your workload: no other major provider keeps your own custom-tool output out of the model context the way `allowed_callers` does. Their code interpreters and tool search do not, checked 2026-06-18. For metering across many cohorts, that is the difference between paying for every row and paying for the answer.

I ran it using my own API key for about $0.08, takes around two minutes. To see it yourself, one clone and one command:

```
git clone https://github.com/cfregly/claude-feature-hits && cd claude-feature-hits
export ANTHROPIC_API_KEY=your-api-key
make programmatic_tool_calling
```

Full brief, demo GIF, code, and sample output: https://github.com/cfregly/claude-feature-hits/tree/main/programmatic_tool_calling

Docs: https://platform.claude.com/docs/en/agents-and-tools/tool-use/programmatic-tool-calling

To run it on your own data, open `programmatic_tool_calling/my_tool.py`, drop in your tool, and run `make programmatic_tool_calling` again.

If you reply with the bottleneck you are working through, I can point you to the closest Claude pattern.

Happy building,

--Chris Fregly
Building with Claude
