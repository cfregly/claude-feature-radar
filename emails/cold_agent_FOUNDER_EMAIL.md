Subject: A Claude sandbox that keeps your agent's state between turns

Hey {first_name},

Congrats on the batch. Quick note if you are building a multi-step data or analytics agent over a
user's files.

A real agent runs across several turns: it ingests a CSV, cleans it, builds intermediate tables, fits a
model, renders a chart. The annoying part is state. If the sandbox does not persist between turns, you
re-upload the file and re-run setup on every call, and you write glue to checkpoint the work yourself.

Claude's code execution sandbox keeps its container and its files across separate requests. Capture the
container id from one response, pass it back on the next, and a file written in one turn is there in the
next. Containers live 30 days, so the state is there even after the user steps away for a while.

```python
r1 = client.beta.messages.create(model=..., betas=["code-execution-2025-08-25"],
    tools=[{"type": "code_execution_20250825", "name": "code_execution"}], messages=[...])
container_id = r1.container.id                       # keep this

r2 = client.beta.messages.create(model=..., betas=["code-execution-2025-08-25"],
    container=container_id,                          # reuse it: the file from r1 is still here
    tools=[{"type": "code_execution_20250825", "name": "code_execution"}], messages=[...])
```

I measured it: I wrote a file in one request, then read it back from the same container after a
31-minute idle, and it was still there.

Run it: `make code-execution-state`, wait past the idle window, then `make code-execution-state-verify` (cents on
your key).

Docs: https://platform.claude.com/docs/en/agents-and-tools/tool-use/code-execution-tool

Go build,
{your_name}
Building with Claude
