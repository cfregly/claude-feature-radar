# Keep an exact running list across a long agent, with Claude context editing

![demo](demo.gif)

Your agent reads a long stream one record at a time (usage logs, churn flags, support tickets) and has to report the exact set of flagged ids at the end. The record text is throwaway after each step, but the running list has to stay exact, and as the stream grows the carried context (the tokens you pay for each turn) grows with it. Claude context editing clears the old tool results in place once the context crosses a trigger you set, so the bulky text leaves the window while the turns that hold your running list stay put.

## What you get

The carried context stays flat near one record instead of growing with every step, and the list comes back exact. On a long report chain the agent returned the exact 10/10 list and held peak carried context to about 35k tokens. The full run cost $0.67 and finished in 60.7s.

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

## Claude vs OpenAI vs Gemini

Measured head-to-head (2026-06-19). All three returned the exact list, so this is cost and speed at equal correctness:

| Stack | Cost, full run | Versus Claude |
| --- | --- | --- |
| Claude, context editing | $0.67 | best |
| OpenAI, compaction | $1.84 | Claude 64% cheaper, 63% faster |
| Gemini, full window | $2.57 | Claude 74% cheaper |

## Run it (about $0.17)

```bash
export ANTHROPIC_API_KEY=sk-ant-...
make exact_ledger
```

That runs a live self-test: it reads a long stream of bulky records, asserts the list comes back exact, and asserts context editing held the carried context flat. About $0.17 and a minute on Claude Haiku 4.5.

To reproduce the whole table on your own keys, not just the Claude side, also export `OPENAI_API_KEY` and `GEMINI_API_KEY` and run:

```bash
make exact_ledger COMPARE=1
```

`COMPARE=1` installs `requirements-compare.txt` (the OpenAI and Gemini SDKs) into the same `.venv` and runs the same ledger agent over the same chain on each platform: OpenAI with server-side compaction and Gemini carrying the full window, both at their strongest long-agent config. You see all three return the exact list and Claude keep it for the lowest bill. Because each competitor runs the full multi-turn agent over bulky records, this run costs a few dollars and takes several minutes. Without it, the brief runs the Claude side alone on one dependency.

## Run it on your own data

Edit `exact_ledger/run.py`: point `build_chain` at your own records (swap in your logs, tickets, or flags and the flag rule), then run `make exact_ledger` again.

## Beta header

Context editing is in beta. Set the header on the request: `anthropic-beta: context-management-2025-06-27`.

## Learn more

Claude context editing: https://platform.claude.com/docs/en/build-with-claude/context-editing
