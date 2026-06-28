Subject: Congrats on YC! A sandbox pattern for customer-evidence agents

Hey {first_name},

Congrats on the batch, that is a real milestone. Quick builder tip in case it helps.

If your agent decides which customers are at risk, it often has to fan out across support tickets,
product logs, usage metering, CRM notes, and compliance docs. Direct tool use sends every raw row
back through the model context. You pay for the rows, even when the final answer only needs a compact
decision packet.

[Programmatic tool calling](https://platform.claude.com/docs/en/agents-and-tools/tool-use/programmatic-tool-calling)
moves that reduction into Claude's code sandbox. Claude writes Python that calls your own tool,
rejects malformed rows, joins evidence by account, sums risk points, preserves evidence IDs and
caveats, and returns only the top accounts to the model.

You add the code execution tool, then one field to the tool you already pass:

```python
response = client.messages.create(
    model="claude-sonnet-4-6",
    messages=[...],
    tools=[
        {"type": "code_execution_20260120", "name": "code_execution"},
        { "name": "query_customer_evidence", "input_schema": {...},
          "allowed_callers": ["code_execution_20260120"] },
    ],
)
```

Same task, same model, the only change is the feature on or off:

| run | billed input tokens | what it means |
|---|---:|---|
| without programmatic tool calling | 54,989 | every raw evidence row lands in the model context |
| with programmatic tool calling | 14,299 | only the compact decision packet reaches the model |

That is 74% fewer billed input tokens on my run, with the same three accounts returned:
`acct_1842`, `acct_2199`, and `acct_7731`.

I ran it using my own API key for estimated $0.08 token/API cost. To see it yourself:

```
git clone https://github.com/cfregly/claude-feature-hits && cd claude-feature-hits
export ANTHROPIC_API_KEY=your-api-key
make programmatic_tool_calling
```

Full artifact, demo GIF, code, and sample output:
https://github.com/cfregly/claude-feature-hits/tree/main/programmatic_tool_calling

Docs: https://platform.claude.com/docs/en/agents-and-tools/tool-use/programmatic-tool-calling

To run it on your own data, open `programmatic_tool_calling/founder_workload.py`, drop in your tool and
fan-out task, and run `make programmatic_tool_calling` again.

Happy building,
{your_name}
Building with Claude
