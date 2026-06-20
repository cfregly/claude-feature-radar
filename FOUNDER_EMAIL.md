Subject: Congrats on YC! A Claude tool-calling pattern for fan-out agents

Hey {first_name},

Congrats on YC.

Quick builder note if your product has an agent that calls the same tool across many accounts,
cohorts, regions, logs, or plan-limit checks.

The expensive shape is simple: the tool returns a lot of rows, the model only needs the aggregate,
and every row still lands in the model context before it can answer.

Claude has a feature for that shape called programmatic tool calling. Add the code execution tool
and allow it to call your custom tool. Claude writes a sandbox script that loops over the tool,
filters and aggregates there, then returns only the answer to the model.

```python
tools=[
    {"type": "code_execution_20260120", "name": "code_execution"},
    {
        "name": "query_usage_events",
        "input_schema": {...},
        "allowed_callers": ["code_execution_20260120"],
    },
]
```

I measured the same fan-out task two ways on Sonnet 4.6: 4 regions, 60 rows each, 240 rows total,
find the highest-revenue region.

| mode | billed input tokens | what changed |
|---|---:|---|
| plain tool use | 9,451 | every row reached the model context |
| programmatic | 6,828 | the sandbox did the aggregation |

That is about 28% fewer billed input tokens on this workload. The scope line matters: this pays when
the model calls a tool many times over data it then crunches. If your tool returns one small object,
this is not the pattern.

Run it yourself:

```bash
git clone https://github.com/cfregly/claude-feature-hits && cd claude-feature-hits
export ANTHROPIC_API_KEY=your-key
make programmatic_tool_calling
```

It costs about $0.08 on Sonnet for the two runs. To try your own tool, edit `programmatic_tool_calling/my_tool.py` and run
`make programmatic_tool_calling` again.

Go build! 🚀

{your_name}
Building with Claude
