Subject: Congrats on YC! A cool Claude feature to help you build

Hey {first_name},

Congrats on getting into YC! Quick tip to trim your Claude token bill.

If your app calls your own tool to answer a question and that tool returns a lot of records, every
record it pulls back lands in the model's context, and you pay for all of them, even the ones that turn
out irrelevant.

[Programmatic tool calling](https://platform.claude.com/docs/en/agents-and-tools/tool-use/programmatic-tool-calling) (PTC) fixes that. Claude runs your tool inside a code
sandbox, keeps only the records that matter, and passes just those to the model. The rest never reach
the context, so you are not billed for them.

It is one change to the API call you already make:

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
| without PTC | 9,451 | every record lands in the model's context |
| with PTC | 6,819 | only the relevant records reach the model |

28% cheaper on this demo, and it compounds across every fan-out.

See it run (about two minutes):

```
git clone {repo_url} && cd claude-feature-briefs
export ANTHROPIC_API_KEY=your-key
make ptc        # the example, $0.06
```

To run it on your own tool, open [ptc/my_tool.py]({repo_url}/blob/main/ptc/my_tool.py),
drop in your tool, and run `make ptc` again.

Happy building!
Chris Fregly
Applied AI, Startups @ Anthropic
