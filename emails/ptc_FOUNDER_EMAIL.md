Subject: Congrats on YC! 🎉 A Claude tool-calling pattern for fan-out agents

Hey {first_name},

Congrats on YC.

Quick builder note if your product has an agent that calls the same tool across many accounts,
cohorts, regions, logs, or plan-limit checks.

The expensive shape is simple: the tool returns a lot of rows, the model only needs the aggregate,
and every row still lands in the model context before it can answer.

[Programmatic tool calling](https://platform.claude.com/docs/en/agents-and-tools/tool-use/programmatic-tool-calling)
fits that shape. Add the code execution tool and allow it to call your custom tool. Claude writes a
sandbox script that loops over the tool, filters and aggregates there, then returns only the answer to
the model.

```python
response = client.messages.create(
    model="claude-sonnet-4-6",
    messages=[...],
    tools=[
        {"type": "code_execution_20260120", "name": "code_execution"},
        {
            "name": "query_usage_events",
            "input_schema": {...},
            "allowed_callers": ["code_execution_20260120"],
        },
    ],
)
```

Same task and model, with and without it:

| mode | input tokens billed | what changed |
|---|---:|---|
| without PTC | 9,451 | every row reached the model context |
| with PTC | 6,828 | the sandbox did the aggregation |

That is 28% cheaper on this demo. The scope line matters: it pays when your agent calls a tool many
times over data it then crunches. If your tool returns one small object, this is not the pattern.

Want to watch it first, no clone needed? The brief opens with a gif of the run:
https://github.com/cfregly/claude-feature-briefs/blob/main/ptc/README.md

See it run:

```bash
git clone https://github.com/cfregly/claude-feature-briefs && cd claude-feature-briefs
export ANTHROPIC_API_KEY=your-key
make ptc        # the example, $0.08
```

To run it on your own tool, open [ptc/my_tool.py](https://github.com/cfregly/claude-feature-briefs/blob/main/ptc/my_tool.py), drop in your
tool, and run `make ptc` again.

Go build! 🚀
{your_name}
Building with Claude
