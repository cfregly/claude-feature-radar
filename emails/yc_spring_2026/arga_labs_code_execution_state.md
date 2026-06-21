Subject: Congrats on YC! Persistent sandbox state for test agents

Hey Phillip,

Congrats on the YC batch - very exciting!!

I'm Chris Fregly on the Applied AI team here at Anthropic, where I work with AI startups moving agents from demo to product.

I saw you're building real-world sandboxes to test agents and agent-facing software. From one former founder to an active founder, builder to builder, I wanted to share a Claude pattern for test agents that need generated files, fixtures, logs, or intermediate state to survive across separate API calls.

The practical version: have Claude write a file during one request, save `r1.container.id`, then pass that value back as `container=container_id` on the next request. Claude keeps using the same code-execution workspace, so the next test step can read the files, logs, or fixtures the previous step created instead of rebuilding them from scratch.

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
    container=container_id,  # reuse the same code-execution workspace
    tools=tools,
    messages=[{"role": "user", "content": "...read /tmp/state.txt and continue testing..."}],
)
```

Using my API key, after a 31-minute idle, Claude read the file back from the same container and the value matched. Containers live 30 days.

Full brief, demo GIF, code, and sample output: https://github.com/cfregly/claude-feature-hits/tree/main/code_execution_state

Run it in about a minute for about $0.05:

```bash
git clone https://github.com/cfregly/claude-feature-hits && cd claude-feature-hits
# Starter credits if you need an API key: https://claude.com/offers?offer_code=bdfcc786-eb41-44f3-9190-e29e6e38209c&signup_code=3a6e0453a611a2c4bd79968fa98e3471
export ANTHROPIC_API_KEY=your-api-key
make code_execution_state
```

To try it on your own workflow, edit `code_execution_state/run.py` with two real test-agent steps and re-run the same command.

If the harder Arga bottleneck is a different part of the eval loop, reply with that shape and I can point you to a closer Claude pattern.

Happy building,

--Chris Fregly
Applied AI, Anthropic
