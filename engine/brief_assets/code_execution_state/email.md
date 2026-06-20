Subject: Congrats on YC! A Claude trick to keep your agent's sandbox state between turns

Hey {first_name},

Congrats on getting into YC. Quick builder tip if you are shipping a multi-step agent that runs code over your users' data.

A real agent works across several separate API calls: turn one ingests a CSV of signups, turn two cleans it, turn three builds a cohort table, turn four renders a churn chart. The painful part is state. If the sandbox does not survive between calls, you re-upload the file and re-run setup on every turn, and you end up writing your own checkpointing glue to stitch it together.

Claude's [code execution tool](https://platform.claude.com/docs/en/agents-and-tools/tool-use/code-execution-tool) keeps its container (the sandbox where your code runs) and its files across separate requests. Grab `response.container.id` from one call, pass it back on the next, and a file written in turn one is right there in turn two.

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

I ran it on my own key. After a 31-minute idle, the agent read its file back from the same container and the value matched. Containers live 30 days, so the state is there even after your user steps away for a coffee.

Here is the same write-then-reread, run live on all three platforms:

| Platform | Reread after a 31-minute idle |
| --- | --- |
| Claude | Read the file back from the same container (30-day life) |
| OpenAI | Returned 400 Container is expired (20-minute idle) |
| Gemini | No reusable container |

Run and docs verified 2026-06-19.

It costs about $0.05 and runs in about a minute. One clone, one command:

```
git clone https://github.com/cfregly/claude-feature-hits && cd claude-feature-hits
export ANTHROPIC_API_KEY=your-key
make code_execution_state
```

To run it on your own agent, open `code_execution_state/run.py` and change the two `messages` payloads to your agent's real steps, then run `make code_execution_state` again.

Happy building 🚀
{your_name}
Building with Claude
