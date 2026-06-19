# Keep an exact running list across a long agent, with Claude context editing

![demo](demo.gif)

Your agent reads a long stream of bulky records one at a time (incident reports, fraud flags, billing exceptions, support escalations) and has to report the exact list of flagged ids at the end. The record text is disposable after each step, but the running list has to stay exact, and as the stream grows the carried context (and the bill) grows with it. Claude context editing clears the old tool results in place once the context crosses a trigger, so the bulky text leaves the window while the assistant turns that hold your running list stay intact.

## What you get

The carried context stays flat near one record instead of growing with every step, and the list comes back exact. On a 30-report chain with each report about 20,000 tokens, the agent returned the exact sorted list of every urgent id and held its peak carried context to 35,186 tokens. The full long-stream run cost $0.6700 and finished in 60.7 seconds, about 64% cheaper and 63% faster than the next exact run on the same workload (receipt below).

```python
resp = client.messages.create(
    model="claude-haiku-4-5",
    max_tokens=1024,
    messages=messages,
    tools=[read_tool],
    extra_headers={"anthropic-beta": "context-management-2025-06-27"},   # add this
    extra_body={"context_management": {"edits": [                        # add this
        {"type": "clear_tool_uses_20250919",
         "trigger": {"type": "input_tokens", "value": 30000},
         "keep": {"type": "tool_uses", "value": 1}}
    ]}},
)
```

## Run it (about $0.17)

```bash
make exact_ledger
```

That runs a live self-test: it reads a long stream of bulky records, asserts the list comes back exact, and asserts context editing held the carried context flat. About $0.17 on Claude Haiku 4.5.

## Run it on your own data

Edit `exact_ledger/run.py`: point `build_chain` at your own records (swap in your reports, tickets, or transactions and the flag rule), then run:

```bash
python -m exact_ledger.run
```

## Beta header

Context editing is in beta. Set the header on the request: `anthropic-beta: context-management-2025-06-27`.

## Learn more

Claude context editing: https://platform.claude.com/docs/en/build-with-claude/context-editing
