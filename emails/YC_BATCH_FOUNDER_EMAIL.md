Subject: Congrats on YC! 3 Claude demos to run this week

Hey YC founders,

Congrats on the batch! Quick builder note from my own testing: I made a small public repo of Claude features that you can run in one command using your own API key.

The repo is here: https://github.com/cfregly/claude-feature-hits

Pick the bottleneck you have this week:

| If you are building | Start here | What you get |
| --- | --- | --- |
| an agent that calls tools many times over logs, accounts, usage rows, or app APIs | [`make programmatic_tool_calling`](https://github.com/cfregly/claude-feature-hits/tree/main/programmatic_tool_calling) | 28% fewer billed input tokens on the measured many-call run |
| a product that answers over user PDFs or docs | [`make document_citations`](https://github.com/cfregly/claude-feature-hits#clone-and-run) | page-level pointers for PDFs and character-level pointers for text docs |
| a multi-step code or data agent | [`make code_execution_state`](https://github.com/cfregly/claude-feature-hits/tree/main/code_execution_state) | sandbox files that survive across separate requests |

The code hooks are small:

```py
# 1. Many-tool-call agents: let Claude's sandbox call your custom tool.
tools=[
    {"type": "code_execution_20260120", "name": "code_execution"},
    {"name": "query_usage", "input_schema": {...},
     "allowed_callers": ["code_execution_20260120"]},
]

# 2. PDF/doc answers: enable source pointers on the document.
doc = {
    "type": "document",
    "source": {"type": "base64", "media_type": "application/pdf", "data": pdf_b64},
    "citations": {"enabled": True},
}

# 3. Multi-step code/data agents: keep working in the same code-execution workspace.
container_id = first_response.container.id  # save this from request 1
next_response = client.beta.messages.create(..., container=container_id)  # request 2 reuses it
```

For the many-tool-call path, Claude writes one sandbox script that loops over your tool, crunches the bulky rows there, and sends only the answer back to the model. On my run, the same usage-style workload went from 9,451 to 6,828 billed input tokens, about $0.08 to reproduce.

Run it:

```shell
git clone https://github.com/cfregly/claude-feature-hits && cd claude-feature-hits
# Starter credits if you need an API key: https://claude.com/offers?offer_code=bdfcc786-eb41-44f3-9190-e29e6e38209c&signup_code=3a6e0453a611a2c4bd79968fa98e3471
export ANTHROPIC_API_KEY=your-api-key
make programmatic_tool_calling   # many tool calls
make document_citations          # PDF and text-doc answers
make code_execution_state        # multi-step agents
```

Each brief has a short demo GIF, the code, sample output, the exact cost, and the one file to edit for your own workload.

If you reply with the bottleneck you are working through this week, I can point you to the closest Claude pattern.

Happy building,

--Chris Fregly
Applied AI, Anthropic
