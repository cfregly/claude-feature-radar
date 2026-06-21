# Keep an exact running list across a long agent, with Claude context editing

![demo](https://raw.githubusercontent.com/cfregly/claude-feature-hits/main/exact_ledger/demo.gif)

[![Claude proof: 64% cheaper vs OpenAI](https://img.shields.io/badge/Claude%20proof-64%25%20cheaper%20vs%20OpenAI-2F855A)](https://github.com/cfregly/claude-feature-hits/tree/main/exact_ledger#claude-vs-openai-vs-gemini)

The GIF replays the saved `sample.txt` output in under ten seconds, so you can see the command and value before running a live call.

Your agent reads a long stream one record at a time (usage logs, churn flags, support tickets) and has to report the exact set of flagged ids at the end. The record text is throwaway after each step, but the running list has to stay exact, and as the stream grows the carried context (the tokens you pay for each turn) grows with it. Claude context editing clears the old tool results in place once the context crosses a trigger you set, so the bulky text leaves the window while the turns that hold your running list stay put.

## What you get

The carried context stays flat near one record instead of growing with every step, and the list comes
back exact. The default command uses the trigger shown below and costs about $0.17. The saved full-run
receipt uses the same mechanism on a longer chain with a 45,000-token trigger; that run returned the
exact 10/10 list, held peak carried context to about 35k tokens, cost $0.67, and finished in 60.7s.

```python
resp = client.messages.create(
    model="claude-haiku-4-5-20251001",
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

These are the saved full-run figures on the longer chain. `make exact_ledger` runs the shorter
default check, currently about $0.17. `make exact_ledger COMPARE=1` reproduces the head-to-head at
that shorter scale: the absolute cost comes out lower, Claude still keeps the exact list for the
lowest bill, and Claude's lead widens as the stream grows.

## Run it

```bash
export ANTHROPIC_API_KEY=your-api-key   # https://console.anthropic.com/
make exact_ledger
```

Default Claude run: about $0.17 and a minute on Claude Haiku 4.5. It reads a long stream of bulky records, asserts the list comes back exact, and asserts context editing held the carried context flat.

Full comparison run: also export `OPENAI_API_KEY` and `GEMINI_API_KEY` and run:

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
