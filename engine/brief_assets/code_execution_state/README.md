# Keep your agent's sandbox state between turns with code execution

![demo](demo.gif)

A multi-step agent that runs code does real work across several separate API calls: ingest a CSV of signups, clean it, build a cohort table, render a churn chart. The hard part is state. If the sandbox does not survive between calls, you re-upload the file and re-run setup every turn, plus write your own checkpointing glue. Claude's code execution tool keeps the container (the sandbox where your code runs) and its files across separate requests, so a file written in one turn is there in the next.

## What you get

Grab `response.container.id` from one call, pass it back on the next, and the file your first step wrote is still there. No re-upload, no checkpointing glue.

```python
r1 = client.messages.create(model="claude-opus-4-8",
    tools=[{"type": "code_execution_20250825", "name": "code_execution"}],
    messages=[{"role": "user", "content": "...write the cohort table to /tmp/state.txt..."}])
prior_container_id = r1.container.id                    # keep this between turns

r2 = client.messages.create(model="claude-opus-4-8",
    container=prior_container_id,  # reuse the same sandbox on a later request
    tools=[{"type": "code_execution_20250825", "name": "code_execution"}],
    messages=[{"role": "user", "content": "...read /tmp/state.txt and chart it..."}])
```

Measured on a live run: after a 31-minute idle, the agent read its file back from the same container and the value matched. Containers live 30 days, so the state holds even after your user steps away.

## Claude vs OpenAI vs Gemini

Measured head-to-head, all three run live, the same write-then-reread:

| Platform | Reread after a 31-minute idle |
| --- | --- |
| Claude | Read the file back from the same container (30-day life) |
| OpenAI | Returned 400 Container is expired (20-minute idle) |
| Gemini | No reusable container |

Run and docs verified 2026-06-19.

## Run it (about $0.05)

```
export ANTHROPIC_API_KEY=your-key   # https://console.anthropic.com/
make code_execution_state
```

Runs in about a minute. To reproduce the comparison, also set `OPENAI_API_KEY` and `GEMINI_API_KEY`.

## Run it on your own data

Open `code_execution_state/run.py`, the one file you edit. Change the two `messages` payloads to your agent's real steps: write whatever your first step produces into the container in request one, then do the next step in request two with `container=prior_container_id` set. Re-run `make code_execution_state`.

## Learn more

- [Code execution docs](https://platform.claude.com/docs/en/agents-and-tools/tool-use/code-execution-tool)
