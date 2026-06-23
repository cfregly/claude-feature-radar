Subject: Congrats on YC! 5 production blockers to test this week

Hey YC founders,

Congrats on the batch! I'm Chris Fregly on Anthropic's Applied AI team, focused on startups. I've
worked through 100+ investor-pitch sessions with founders, and the useful pattern is usually the
same: turn this week's production blocker into a runnable proof. I made a small public repo of Claude
patterns you can run in one command using your own API key.

The repo is here: https://github.com/cfregly/claude-feature-hits

Pick the production question you have this week:

| If the blocker is | Start here | What you get |
| --- | --- | --- |
| **cost** from agents that fan out over logs, usage results, accounts, or app APIs | [`make programmatic_tool_calling`](https://github.com/cfregly/claude-feature-hits/tree/main/programmatic_tool_calling) | 28% fewer billed input tokens than the same Claude agent without programmatic tool calling |
| **speed** for large outputs or long-stream work | [`make bulk_output`](https://github.com/cfregly/claude-feature-hits/tree/main/bulk_output) or [`make exact_ledger`](https://github.com/cfregly/claude-feature-hits/tree/main/exact_ledger) | one un-truncated large deliverable, or a faster exact long-stream run |
| **reliability** for multi-step code, data, or build agents | [`make code_execution_state`](https://github.com/cfregly/claude-feature-hits/tree/main/code_execution_state) or [`make task_budgets`](https://github.com/cfregly/claude-feature-hits/tree/main/task_budgets) | sandbox files that survive across separate requests, or loop-level budget handoffs |
| **accuracy** for answers over PDFs, docs, filings, or retrieved chunks | [`make pdf_citations`](https://github.com/cfregly/claude-feature-hits/tree/main/pdf_citations) or [`make citations`](https://github.com/cfregly/claude-feature-hits/tree/main/citations) | page-level pointers for PDFs and character-level pointers for text docs |
| **security** for regulated data, MCP connectors, prompt injection, or agent attack surface | [`make tool_boundary_security`](https://github.com/cfregly/claude-feature-hits/tree/main/tool_boundary_security) + [`make security_controls_map`](https://github.com/cfregly/claude-feature-hits/tree/main/security_controls_map) | a local prompt-injection gate plus a source-backed controls map, both $0.00 |

The code hooks are small:

```py
# Cost: let Claude's sandbox call your custom tool.
tools=[
    {"type": "code_execution_20260120", "name": "code_execution"},
    {"name": "query_usage", "input_schema": {...},
     "allowed_callers": ["code_execution_20260120"]},
]

# Accuracy: enable source pointers on the document.
doc = {
    "type": "document",
    "source": {"type": "base64", "media_type": "application/pdf", "data": pdf_b64},
    "citations": {"enabled": True},
}

# Reliability: keep working in the same code-execution workspace.
container_id = first_response.container.id
next_response = client.beta.messages.create(..., container=container_id)
```

For the many-tool-call path, Claude writes one sandbox script that loops over your tool, crunches the
bulky intermediate results there, and sends only the answer back to the model. On my run, the same usage-style
workload went from 9,451 to 6,828 billed input tokens, 28% fewer than the same Claude agent without
programmatic tool calling. It costs $0.08 to reproduce.

Run it:

```shell
git clone https://github.com/cfregly/claude-feature-hits && cd claude-feature-hits
# Get an API key: https://console.anthropic.com/
export ANTHROPIC_API_KEY=your-api-key
make programmatic_tool_calling   # cost and speed for fan-out agents
make citations                   # accuracy for text-doc answers
make code_execution_state        # reliability for multi-step agents
make security                    # security preflight plus source-backed controls map
```

Each brief has the code, sample output, the exact cost, and a named edit surface for your own
workload, such as `programmatic_tool_calling/my_tool.py`, `citations/cite.py`,
`tool_boundary_security/policy.json`, `security_controls_map/controls.json`, or the brief README's
`Run it on your own data` section. Most also have a short demo GIF.

If you reply with the production blocker you are working through this week, I can point you to the closest
Claude pattern.

Happy building,

--Chris Fregly
Applied AI, Startups, Anthropic
