Subject: Token MINNing: removing unused tool results from your context window

Hey {first_name},

Congrats on getting into YC! Quick tip to trim your Claude token bill.

If your app calls your own tool to answer a question and that tool returns a lot of results, every
result it pulls back lands in the model's context, and you pay for all of them, even the ones that turn
out irrelevant.

[Programmatic tool calling](https://platform.claude.com/docs/en/agents-and-tools/tool-use/programmatic-tool-calling) (PTC) fixes that. Claude runs your tool inside a code
sandbox, keeps only the results that matter, and passes just those to the model. The rest never reach
the context, so you are not billed for them.

It is two small additions to the API call you already make:

```python
response = client.messages.create(
    model="claude-sonnet-4-6",
    messages=[...],
    tools=[
        {"type": "code_execution_20260120", "name": "code_execution"},   # add this
        { "name": "query_region_sales", "input_schema": {...},   # your tool, unchanged
          "allowed_callers": ["code_execution_20260120"] },        # add this line
    ],
)
```

Same task and model (Sonnet 4.6), with and without it:

| | input tokens billed | why |
|---|---:|---|
| without PTC | 9,451 | every result lands in the model's context |
| with PTC | 6,828 | only the relevant results reach the model |

28% fewer billed input tokens on this demo, and the saving grows with the size of the fan-out.

Want to watch it first, no clone needed? The brief opens with a gif of the run:
https://github.com/cfregly/claude-feature-briefs/blob/main/ptc/README.md

See it run (about two minutes):

```
git clone https://github.com/cfregly/claude-feature-briefs && cd claude-feature-briefs
export ANTHROPIC_API_KEY=your-key
make ptc        # the example, $0.08
```

To run it on your own tool, open [ptc/my_tool.py](https://github.com/cfregly/claude-feature-briefs/blob/main/ptc/my_tool.py),
drop in your tool, and run `make ptc` again.

Happy building! 🚀
{your_name}
Building with Claude
