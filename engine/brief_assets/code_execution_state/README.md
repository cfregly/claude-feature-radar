# Keep your agent's sandbox state between turns with code execution

![demo](https://raw.githubusercontent.com/cfregly/claude-feature-hits/main/code_execution_state/demo.gif)

[![Claude proof: 31 min idle kept](https://img.shields.io/badge/Claude%20proof-31%20min%20idle%20kept-2F855A)](https://github.com/cfregly/claude-feature-hits/blob/main/code_execution_state/sample.txt)

The GIF replays the saved `sample.txt` output in under ten seconds, so you can see the command and value before running a live call. The default command proves same-container reuse without making you wait. The linked long-idle output shows the long-idle comparison.

A multi-step agent that runs code does real work across several separate API calls: ingest a CSV of signups, clean it, build a cohort table, render a churn chart. The hard part is state. If the sandbox does not survive between calls, you re-upload the file and re-run setup every turn, plus write your own checkpointing glue. Claude's code execution tool keeps the container (the sandbox where your code runs) and its files across separate requests, so a file written in one turn is there in the next.

## What you get

Save the container id returned by the first response, pass it back as `container=prior_container_id`
on the next request, and Claude keeps using the same code-execution workspace. The next step can
read the files, logs, fixtures, or intermediate state the previous step created. No re-upload, no
checkpointing glue.

```python
CODE_EXEC_BETA = "code-execution-2025-08-25"
tools = [{"type": "code_execution_20250825", "name": "code_execution"}]

r1 = client.beta.messages.create(
    model="claude-sonnet-4-6",
    max_tokens=1024,
    betas=[CODE_EXEC_BETA],
    tools=tools,
    messages=[{"role": "user", "content": "...write the cohort table to /tmp/state.txt..."}],
)
prior_container_id = r1.container.id  # keep this between turns

r2 = client.beta.messages.create(
    model="claude-sonnet-4-6",
    max_tokens=1024,
    betas=[CODE_EXEC_BETA],
    container=prior_container_id,  # reuse the same sandbox on a later request
    tools=tools,
    messages=[{"role": "user", "content": "...read /tmp/state.txt and chart it..."}],
)
```

Measured on a live run: after a 31-minute idle, the agent read its file back from the same container and the value matched. Containers live 30 days, so the state holds even after your user steps away.

## Claude vs OpenAI vs Gemini

Measured head-to-head, all three run live, the same write-then-reread:

| Platform | Reread after a 31-minute idle |
| --- | --- |
| Claude | Read the file back from the same container (30-day life) |
| OpenAI | Returned `400 Container is expired` on the dated 31-minute idle run |
| Gemini | No reusable container handle in the tested setup |

Run verified 2026-06-19. Docs rechecked 2026-06-20.

## Run it

```
export ANTHROPIC_API_KEY=your-api-key   # https://console.anthropic.com/
make code_execution_state
```

Default Claude run: about a minute and $0.05. It writes a file in one request and reads it from the reused container in the next. Full comparison run: also export `OPENAI_API_KEY` and `GEMINI_API_KEY` and run:

```
make code_execution_state COMPARE=1
```

`COMPARE=1` installs `requirements-compare.txt` (the OpenAI and Gemini SDKs) into the same `.venv`
and runs the same write-then-reread on each platform's code sandbox. Claude reuses its container by
id with a 30-day life. The dated comparison run records OpenAI returning an expired-container error
after the idle wait, consistent with its documented 20-minute idle expiration, and Gemini exposing no
reusable container handle in the tested setup. Add `--idle-minutes 21` to wait and re-read each
container live. Without it, the brief runs the Claude side alone on one dependency.

## Run it on your own data

Open `code_execution_state/run.py`, the one file you edit. Change the two `messages` payloads to your agent's real steps: write whatever your first step produces into the container in request one, then do the next step in request two with `container=prior_container_id` set. Re-run `make code_execution_state`.

## Learn more

- [Code execution docs](https://platform.claude.com/docs/en/agents-and-tools/tool-use/code-execution-tool)
