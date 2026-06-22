Subject: Congrats on YC! Lower-bill long agents with exact state

Hey {first_name},

Congrats on the batch. Here is a quick builder tip if you run a long agent that has to keep an exact running list.

The shape I keep hitting: an agent reads a long stream one record at a time (usage logs, churn flags, support tickets) and has to report the exact set of flagged ids at the end. The record text is throwaway after each step, but the running list has to stay exact. As the stream grows, every old record stays in the window, so the carried context (the tokens you pay for each turn) climbs with it, and so does the bill.

Claude context editing fixes that. It clears the old tool results in place once the context crosses a trigger you set, so the bulky text leaves the window while the turns holding your running list stay put. The whole change is one block on the request:

```python
resp = client.beta.messages.create(
    model="claude-haiku-4-5-20251001",
    max_tokens=1024,
    messages=messages,
    tools=[read_tool],
    betas=["context-management-2025-06-27"],                       # add this
    context_management={"edits": [{"type": "clear_tool_uses_20250919",   # add this
        "trigger": {"type": "input_tokens", "value": 30000},             # add this
        "keep": {"type": "tool_uses", "value": 1}}]},
)
```

I keep two measured outputs separate because they answer different questions. The longer stress run used a
30-report chain: the agent returned the exact 10/10 list, held peak carried context to about 35k
tokens, and finished at $0.67 in 60.7s.

The head-to-head table below uses a shorter 8-report chain so the comparison is cheap to rerun with
your own API keys. All three returned the exact list, so this is cost at equal accuracy on the
same 8-report comparison workload:

| Stack | Cost, this run | Wall time | Accuracy | Versus Claude |
| --- | ---: | ---: | --- | --- |
| Claude `claude-haiku-4-5-20251001`, context editing | $0.17 | 14.3s | exact | best |
| OpenAI `gpt-5.5`, compaction | $0.46 | 31.6s | exact | Claude 63% cheaper |
| Gemini `gemini-3.1-pro-preview`, full window | $0.35 | 23.8s | exact | Claude 51% cheaper |

To try the short Claude-side check, one clone and one command, $0.17 and a minute on Claude Haiku
4.5:

```bash
git clone https://github.com/cfregly/claude-feature-hits && cd claude-feature-hits
export ANTHROPIC_API_KEY=your-api-key
make exact_ledger
```

Full brief, demo GIF, code, and sample output: https://github.com/cfregly/claude-feature-hits/tree/main/exact_ledger
Committed comparison output: https://github.com/cfregly/claude-feature-hits/blob/main/exact_ledger/compare_sample.txt

Docs: https://platform.claude.com/docs/en/build-with-claude/context-editing

Want the whole table, not just the Claude side? Set `OPENAI_API_KEY` and `GEMINI_API_KEY` too and run `make exact_ledger COMPARE=1`. It runs all three side by side on the same short chain. In the captured comparison, the three rows total $0.98 because each competitor runs the full agent. The table above is the committed comparison output.

To run it on your own data, edit `exact_ledger/run.py`: point the reader at your records and your flag rule, then run `make exact_ledger` again.

One note: context editing is in beta, so set the header on the request, `anthropic-beta: context-management-2025-06-27`.

If you reply with the bottleneck you are working through, I can point you to the closest Claude pattern.

Happy building,

--Chris Fregly
Building with Claude
