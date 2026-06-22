Subject: Congrats on YC! Persistent state for test agents

Hey Phillip,

Congrats on the YC batch.

I'm Chris Fregly on Anthropic's Applied AI team, focused on startups. I work with teams moving agents
from demo to product.

I saw Arga Labs is building real-world sandboxes to test agents and agent-facing software. The Claude
pattern that maps to that workload is persistent code-execution state for test agents that need
generated files, fixtures, logs, or intermediate state to survive across separate API calls.

The practical version: have Claude write a file during one request, save `r1.container.id`, then pass
that value back as `container=container_id` on the next request. Claude keeps using the same
code-execution workspace, so the next test step can read the files, logs, or fixtures the previous
step created instead of rebuilding them from scratch.

```python
CODE_EXEC_BETA = "code-execution-2025-08-25"
tools = [{"type": "code_execution_20250825", "name": "code_execution"}]

r1 = client.beta.messages.create(
    model="claude-sonnet-4-6",
    max_tokens=1024,
    betas=[CODE_EXEC_BETA],
    tools=tools,
    messages=[{"role": "user", "content": "...write test state to /tmp/state.txt..."}],
)
container_id = r1.container.id

r2 = client.beta.messages.create(
    model="claude-sonnet-4-6",
    max_tokens=1024,
    betas=[CODE_EXEC_BETA],
    container=container_id,
    tools=tools,
    messages=[{"role": "user", "content": "...read /tmp/state.txt and continue testing..."}],
)
```

Using my API key, after a 31-minute idle, Claude read the file back from the same container and the
value matched. Containers live 30 days.

Full brief, demo GIF, code, and sample output: https://github.com/cfregly/claude-feature-hits/tree/main/code_execution_state

Run it in about a minute for $0.05:

```bash
git clone https://github.com/cfregly/claude-feature-hits && cd claude-feature-hits
# Get an API key: https://console.anthropic.com/
export ANTHROPIC_API_KEY=your-api-key
make code_execution_state
```

To try it on your own workflow, edit `code_execution_state/run.py` with two real test-agent steps and
re-run the same command.

The security-testing follow-up is the sharper Arga conversation. I would separate the reliability
primitive above from the security test plan, then run the public preflight and source map before
turning any of it into copy.

If the harder Arga blocker is a different part of the eval loop, reply with that shape and I can
point you to a closer Claude pattern.

Happy building,

--Chris Fregly
Applied AI, Startups, Anthropic
