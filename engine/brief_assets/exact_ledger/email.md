Subject: Congrats on YC! Lower-bill long agents with exact state

Hey {first_name},

Congrats on the batch. Here is a quick builder tip if you run a long agent that has to keep an exact running list.

The shape I keep hitting: an agent reads a long stream one record at a time (usage logs, churn flags, support tickets) and has to report the exact set of flagged ids at the end. The record text is throwaway after each step, but the running list has to stay exact. As the stream grows, every old record stays in the window, so the carried context (the tokens you pay for each turn) climbs with it, and so does the bill.

Claude context editing fixes that. It clears the old tool results in place once the context crosses a trigger you set, so the bulky text leaves the window while the turns holding your running list stay put. The whole change is one block on the request:

```python
resp = client.messages.create(
    model="claude-haiku-4-5",
    max_tokens=1024,
    messages=messages,
    tools=[read_tool],
    context_management={"edits": [{"type": "clear_tool_uses_20250919",   # add this
        "trigger": {"type": "input_tokens", "value": 30000},             # add this
        "keep": {"type": "tool_uses", "value": 1}}]},
)
```

Using my API key, on a long report chain, the agent returned the exact 10/10 list and held peak carried context to about 35k tokens while old bulky tool results fell away. The full run was $0.67 and 60.7s.

I ran it head-to-head against the others, same workload (2026-06-19). All three returned the exact list, so this is cost and speed at equal correctness:

| Stack | Cost, full run | Versus Claude |
| --- | --- | --- |
| Claude, context editing | $0.67 | best |
| OpenAI, compaction | $1.84 | Claude 64% cheaper, 63% faster |
| Gemini, full window | $2.57 | Claude 74% cheaper |

To try it, one clone and one command, about $0.17 and a minute on Claude Haiku 4.5:

```bash
git clone https://github.com/cfregly/claude-feature-hits && cd claude-feature-hits
make exact_ledger
```

Full brief, demo GIF, code, and sample output: https://github.com/cfregly/claude-feature-hits/tree/main/exact_ledger

Docs: https://platform.claude.com/docs/en/build-with-claude/context-editing

Want the whole table, not just the Claude side? Set `OPENAI_API_KEY` and `GEMINI_API_KEY` too and run `make exact_ledger COMPARE=1`. It runs all three side by side on the same chain, a few dollars and several minutes since each competitor runs the full agent. The table above is the longer full run, so a quick reproduce lands lower in absolute cost while Claude still keeps the exact list for the lowest bill, and the lead widens as the stream grows.

To run it on your own data, edit `exact_ledger/run.py`: point the reader at your records and your flag rule, then run `make exact_ledger` again.

One note: context editing is in beta, so set the header on the request, `anthropic-beta: context-management-2025-06-27`.

Happy building,
{your_name}
Building with Claude
