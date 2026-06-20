Subject: Congrats on YC! A Claude trick for long agents that keep a running list

Hey {first_name},

Congrats on the batch. Quick builder tip if you are running a long agent: keep your running state in the assistant's own notes, not stuffed back into the prompt every turn, and you give context editing a clean line between the bulky stuff and the state worth keeping.

Here is the problem I kept hitting. An agent reads a long stream of records one at a time (think usage logs per cohort, churn flags, billing exceptions, support tickets) and has to report the exact list of flagged ids at the end. The record text is throwaway after each step, but the running list has to stay exact. As the stream grows, every old record stays in the window, so the carried context and the bill climb with it.

Claude context editing fixes that. It clears the old tool results in place once the context crosses a trigger, so the bulky text leaves the window while the turns holding your running list stay put. Two lines on the request:

```python
extra_headers={"anthropic-beta": "context-management-2025-06-27"},
extra_body={"context_management": {"edits": [
    {"type": "clear_tool_uses_20250919",
     "trigger": {"type": "input_tokens", "value": 30000},
     "keep": {"type": "tool_uses", "value": 1}}
]}},
```

On my key, on a 30-report chain (each report about 20,000 tokens), the agent returned the exact list and held its peak carried context to about 35k tokens instead of letting it balloon. The full run was $0.6700 and 60.7 seconds, about 64% cheaper and 63% faster than the next exact run on the same workload.

Short walkthrough (the gif): https://github.com/cfregly/claude-feature-hits/blob/main/exact_ledger/README.md

To try it: `make exact_ledger` runs a live self-test for about $0.17. To run it on your own data, edit `exact_ledger/run.py` to point the reader at your records and your flag rule, then `python -m exact_ledger.run`.

One note: context editing is in beta, so you set that `anthropic-beta` header on the request.

Happy building! 🚀
{your_name}
Building with Claude
