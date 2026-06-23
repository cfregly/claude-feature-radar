# Keep an exact running list across a long agent, with Claude context editing

![demo](https://raw.githubusercontent.com/cfregly/claude-feature-hits/main/exact_ledger/demo.gif)

[![Claude proof: 63% cheaper vs OpenAI](https://img.shields.io/badge/Claude%20proof-63%25%20cheaper%20vs%20OpenAI-2F855A)](https://github.com/cfregly/claude-feature-hits/blob/main/exact_ledger/compare_sample.txt)

The proof badge and table use the current `compare_sample.txt` receipt, so the first comparison matches what `COMPARE=1` reruns.

Your agent reads a long stream one record at a time (usage logs, churn flags, support tickets) and has to report the exact set of flagged ids at the end. The record text is throwaway after each step, but the running list has to stay exact, and as the stream grows the carried context (the tokens you pay for each turn) grows with it. Claude context editing clears the old tool outputs in place once the context crosses a trigger you set, so the bulky text leaves the window while the turns that hold your running list stay put.

## What you get

The carried context stays flat near one record instead of growing with every step, and the list comes
back exact. The default command uses the trigger shown below and costs $0.17. The current comparison
receipt is `compare_sample.txt`. The longer `sample.txt` reference uses the same mechanism on a
30-report chain with a 45,000-token trigger. That run returned the exact 10/10 list, held peak
carried context to about 35k tokens, cost $0.67, and finished in 60.7s.

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

## Claude vs OpenAI vs Gemini

Measured head-to-head (captured 2026-06-20). All three returned the exact list, so this is cost at equal correctness:

| Stack | Cost, this run | Wall time | Correctness | Versus Claude |
| --- | ---: | ---: | --- | --- |
| Claude `claude-haiku-4-5-20251001`, context editing | $0.17 | 14.3s | exact | best |
| OpenAI `gpt-5.5`, compaction | $0.46 | 31.6s | exact | Claude 63% cheaper |
| Gemini `gemini-3.1-pro-preview`, full window | $0.35 | 23.8s | exact | Claude 51% cheaper |

The saved comparison receipt is `exact_ledger/compare_sample.txt`. `make exact_ledger` runs the
Claude side only, currently $0.17. `make exact_ledger COMPARE=1` reproduces the head-to-head: it
installs the optional OpenAI and Gemini SDKs, then runs all three platforms on the same chain.

The longer full-run reference in `sample.txt` is from 2026-06-19. It used a 10-of-10 chain:
Claude $0.67, OpenAI $1.84, Gemini $2.57, all exact. The public proof badge points to the current
committed comparison receipt above.

## Run it

```bash
export ANTHROPIC_API_KEY=your-api-key   # https://console.anthropic.com/
make exact_ledger
```

Default Claude run: $0.17 and a minute on Claude Haiku 4.5. It reads a long stream of bulky records, asserts the list comes back exact, and asserts context editing held the carried context flat.

Full comparison run: also export `OPENAI_API_KEY` and `GEMINI_API_KEY` and run:

```bash
make exact_ledger COMPARE=1
```

`COMPARE=1` installs `requirements-compare.txt` (the OpenAI and Gemini SDKs) into the same `.venv` and runs the same ledger agent over the same chain on each platform: OpenAI with server-side compaction and Gemini carrying the full window, both at their strongest long-agent config. You see all three return the exact list and Claude keep it for the lowest bill. In the captured short comparison, the three rows total $0.98 and take a few minutes. Without it, the brief runs the Claude side alone on one dependency.

## Run it on your own data

Edit `exact_ledger/run.py`: point `build_chain` at your own records (swap in your logs, tickets, or flags and the flag rule), then run `make exact_ledger` again.

## Beta header

Context editing is in beta. Set the header on the request: `anthropic-beta: context-management-2025-06-27`.

## Learn more

Claude context editing: https://platform.claude.com/docs/en/build-with-claude/context-editing
