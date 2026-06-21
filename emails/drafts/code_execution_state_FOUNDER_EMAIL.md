Subject: Congrats on YC! Persistent sandbox state for code agents

Hey {first_name},

Congrats on getting into YC. Quick builder tip if you are shipping a multi-step agent that runs code over your users' data.

A real agent works across several separate API calls: turn one ingests a CSV of signups, turn two cleans it, turn three builds a cohort table, turn four renders a churn chart. The painful part is state. If the sandbox does not survive between calls, you re-upload the file and re-run setup on every turn, and you end up writing your own checkpointing glue to stitch it together.

Claude's [code execution tool](https://platform.claude.com/docs/en/agents-and-tools/tool-use/code-execution-tool) keeps its container (the sandbox where your code runs) and its files across separate requests. Save the container id returned by the first response, pass it back as `container=prior_container_id` on the next request, and Claude keeps using the same code-execution workspace. The next step can read the files, logs, fixtures, or intermediate state the previous step created.

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

I ran it using my own API key. After a 31-minute idle, the agent read its file back from the same container and the value matched. Containers live 30 days, so the state is there even after your user steps away for a coffee.

Here is the same write-then-reread, run live on all three platforms:

| Platform | Reread after a 31-minute idle |
| --- | --- |
| Claude | Read the file back from the same container (30-day life) |
| OpenAI | Returned `400 Container is expired` on the dated 31-minute idle run |
| Gemini | No reusable container handle in the tested setup |

Run verified 2026-06-19. Docs rechecked 2026-06-20.

It costs $0.05 and runs in about a minute. One clone, one command:

```
git clone https://github.com/cfregly/claude-feature-hits && cd claude-feature-hits
export ANTHROPIC_API_KEY=your-api-key
make code_execution_state
```

Full brief, demo GIF, code, and sample output: https://github.com/cfregly/claude-feature-hits/tree/main/code_execution_state

Docs: https://platform.claude.com/docs/en/agents-and-tools/tool-use/code-execution-tool

Want the whole table, not just the Claude side? Set `OPENAI_API_KEY` and `GEMINI_API_KEY` too and run `make code_execution_state COMPARE=1`. It runs Claude, OpenAI, and Gemini side by side on the same write-then-reread, so you see Claude reuse its container while the others lose the state, using your own API keys for a few cents.

To run it on your own agent, open `code_execution_state/run.py` and change the two `messages` payloads to your agent's real steps, then run `make code_execution_state` again.

If you reply with the bottleneck you are working through, I can point you to the closest Claude pattern.

Happy building,

--Chris Fregly
Building with Claude
