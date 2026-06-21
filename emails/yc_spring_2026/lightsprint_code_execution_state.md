Subject: Congrats on YC! Persistent state for AI build agents

Hey Ben,

Congrats on the batch, and on getting Lightsprint in front of YC.

I'm Chris Fregly. I focus on the agent-product details that start mattering once teams expect agents to keep real work moving across sessions.

I saw Lightsprint is building collaborative product development with cloud agents so teams can plan, preview, and ship with agents. The Claude pattern that maps to that workload is persistent code-execution state for build agents that need generated files, test output, and scratch state to survive when a user steps away.

The practical version: have Claude write generated files during one request, save `r1.container.id`, then pass that value back as `container=container_id` on the next request. Claude keeps using the same code-execution workspace, so the next build step can read the files, test output, or scratch state the previous step created instead of rebuilding them from scratch.

```python
CODE_EXEC_BETA = "code-execution-2025-08-25"
tools = [{"type": "code_execution_20250825", "name": "code_execution"}]

r1 = client.beta.messages.create(
    model="claude-sonnet-4-6",
    max_tokens=1024,
    betas=[CODE_EXEC_BETA],
    tools=tools,
    messages=[{"role": "user", "content": "...write the generated app files..."}],
)
container_id = r1.container.id

r2 = client.beta.messages.create(
    model="claude-sonnet-4-6",
    max_tokens=1024,
    betas=[CODE_EXEC_BETA],
    container=container_id,  # keep building in the same code-execution workspace
    tools=tools,
    messages=[{"role": "user", "content": "...run tests and patch the files..."}],
)
```

Using my API key, after a 31-minute idle, Claude read the file back from the same container and the value matched. Containers live 30 days, so the build state survives when a user steps away and comes back.

Full brief, demo GIF, code, and sample output: https://github.com/cfregly/claude-feature-hits/tree/main/code_execution_state

Run it in about a minute for $0.05:

```bash
git clone https://github.com/cfregly/claude-feature-hits && cd claude-feature-hits
# Starter credits if you need an API key: <starter-credit-link>
export ANTHROPIC_API_KEY=your-api-key
make code_execution_state
```

To try it on your own builder, edit `code_execution_state/run.py` with two real build-agent steps and re-run the same command.

If the state boundary in Lightsprint is somewhere else, reply with the rough workflow and I can point you to the more relevant Claude pattern.

Happy building,

--Chris Fregly
Building with Claude
