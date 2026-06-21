Subject: A Claude tool-calling pattern for fan-out agents

Hey {first_name},

Congrats on the batch. Quick builder note if you are running an agent that calls a tool many times
over data it then crunches: usage summaries across a cohort, plan-limit checks across accounts, log or
trace triage.

The problem is the bill. Every tool result flows into the model's context, so you pay input tokens for
all of it, even the rows the model only sums and throws away.

Claude has one change for this, no beta header. Mark your tool so the model can call it from a sandbox
script, and add the code execution tool. The model writes one script that loops your tool, aggregates
in the sandbox, and returns only the answer. The bulky rows stay in the sandbox.

```python
tools = [
    {"type": "code_execution_20260120", "name": "code_execution"},   # add this
    {
        "name": "get_usage",
        "description": "Return the usage rows for one account.",
        "input_schema": {...},
        "allowed_callers": ["code_execution_20260120"],              # and this
    },
]
```

I measured it on the same fan-out twice, same model (Sonnet 4.6), same answer required (240 rows across
4 cohorts, find the top one):

| mode | billed input tokens |
|---|--:|
| plain tool use | 9,451 |
| programmatic | 6,828 |

About 28% fewer billed input tokens, and the sandbox returned the exact winner. It pays off on the
fan-out shape, many calls over data the model then crunches.

Run it on your own tool: edit one file, programmatic_tool_calling/my_tool.py, paste your tool dict and
the Python that runs it, then `make programmatic_tool_calling` ($0.08 using your API key).

Full brief, demo GIF, code, and sample output: https://github.com/cfregly/claude-feature-hits/tree/main/programmatic_tool_calling

Docs: https://platform.claude.com/docs/en/agents-and-tools/tool-use/programmatic-tool-calling

If you reply with the bottleneck you are working through, I can point you to the closest Claude pattern.

Happy building,

--Chris Fregly
Building with Claude
