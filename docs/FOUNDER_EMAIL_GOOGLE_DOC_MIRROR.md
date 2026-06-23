# Congrats on YC! 5 production blockers to test this week

Subject: Congrats on YC! 5 production blockers to test this week

Hey YC founders,

Congrats on the batch! I'm Chris Fregly on Anthropic's Applied AI team, focused on startups. I made a small public repo of Claude patterns you can run in one command with your own API key.

The repo is here: https://github.com/cfregly/claude-feature-hits

Pick the production blocker you have this week:

- Cost from agents that fan out over logs, usage events, accounts, or app APIs: run `make programmatic_tool_calling`. The measured fan-out run used 28% fewer billed input tokens than the same Claude agent without programmatic tool calling.
- Speed for large outputs or long-stream work: run `make bulk_output` or `make exact_ledger`.
- Reliability for multi-step code, data, or build agents: run `make code_execution_state` or `make task_budgets`.
- Accuracy for answers over PDFs, docs, filings, or retrieved chunks: run `make pdf_citations` or `make citations`.
- Security for regulated data, MCP connectors, prompt injection, or agent attack surface: run `make security`.

The cost pattern is the one I would test first when an agent makes many tool calls and only needs one final answer:

```python
tools=[
    {"type": "code_execution_20260120", "name": "code_execution"},
    {"name": "query_usage", "input_schema": {...},
     "allowed_callers": ["code_execution_20260120"]},
]
```

For that path, Claude writes one sandbox script, calls your tool in a loop, crunches the bulky intermediate results there, and sends only the answer back to the model. On my run, the same usage-style workload went from 9,451 to 6,828 billed input tokens. That is 28% fewer billed input tokens than the same Claude agent without programmatic tool calling. It costs $0.08 to reproduce.

One important scope line: `allowed_callers` guides Claude to invoke the tool from code execution. It is not a security boundary. Keep authorization, policy checks, and dangerous-action handling in your client or tool layer.

Run it:

```shell
git clone https://github.com/cfregly/claude-feature-hits && cd claude-feature-hits
# Get an API key: https://console.anthropic.com/
export ANTHROPIC_API_KEY=your-api-key
make programmatic_tool_calling
```

Each brief has the code, sample output, exact cost, and a named edit surface for your own workload. For the cost path, edit `programmatic_tool_calling/my_tool.py` with your real tool and inputs, then run the same command.

If you reply with the production blocker you are working through this week, I can point you to the closest Claude pattern.

Happy building,

--Chris Fregly

Applied AI, Startups, Anthropic

## Appendix: Routing Snapshot

This routing snapshot explains why the batch email points to a menu instead of one generic demo. Each company maps to one production blocker and one public brief. The three routed drafts below are representative examples, not extra required deliverables.

Source list: [TechCrunch, "The 11 standout startups from YC's Demo Day, according to VCs," published 2026-06-18](https://techcrunch.com/2026/06/18/the-11-standout-startups-from-ycs-demo-day-according-to-vcs/).

Company pages and founder greetings were last reviewed from public YC pages on 2026-06-22.

| Company | Workload | Primary blocker | Public pattern |
| --- | --- | --- | --- |
| Sazabi | Observability over logs, Slack, and agent investigations | Cost + speed | Programmatic tool calling |
| Tasklet | Work agents calling APIs, MCP servers, browsers, and code sandboxes | Cost + security follow-up | Programmatic tool calling |
| Complir | Compliance agents over regulations, product data, and documentation | Accuracy + security | PDF citations |
| Arga Labs | Real-world sandboxes to test agents and agent-facing software | Reliability + security testing | Code execution state |
| Superset | IDE for running hundreds of coding agents in parallel | Reliability + cost + speed | Task budgets |
| Lightsprint | Collaborative product development with cloud agents | Reliability | Code execution state |
| Silmaril | Prompt-injection defense for AI-native applications and agents | Security | Tool-boundary security + controls map |

## Representative Routed Drafts

### Sazabi: cost and speed for log-triage agents

Subject: Congrats on YC! Cost and speed for log-triage agents

Hey Sherwood,

Congrats on YC.

I saw Sazabi is building AI-native observability around logs, Slack, and agent-driven investigations. The Claude pattern that maps to that workload is log-triage fan-out without dragging every intermediate result into the model context.

That workload gets expensive fast. Every log slice or trace payload your tool returns becomes model context unless you move the crunching somewhere else. Claude programmatic tool calling lets the model write one sandbox script, call your tool in a loop, filter and aggregate there, and return only the fix-relevant answer.

```python
tools=[
    {"type": "code_execution_20260120", "name": "code_execution"},
    {"name": "query_logs", "input_schema": {...},
     "allowed_callers": ["code_execution_20260120"]},
]
```

Using my API key, the same fan-out task over 240 returned results went from 9,451 to 6,828 billed input tokens, with the exact winner returned from the sandbox. That is 28% fewer billed input tokens than the same Claude agent without programmatic tool calling.

Full brief, demo GIF, code, and sample output: https://github.com/cfregly/claude-feature-hits/tree/main/programmatic_tool_calling

Run it in about two minutes for $0.08:

```bash
git clone https://github.com/cfregly/claude-feature-hits && cd claude-feature-hits
export ANTHROPIC_API_KEY=your-api-key
make programmatic_tool_calling
```

To try it on your own workload, edit `programmatic_tool_calling/my_tool.py` with your log query tool and re-run the same command.

Happy building,

--Chris Fregly

Applied AI, Startups, Anthropic

### Tasklet: a sandbox pattern for work-app agents

Subject: Congrats on YC! A sandbox pattern for work-app agents

Hey Jonny,

Congrats on getting Tasklet into YC.

I saw Tasklet is building agents that call work-app APIs to get tasks done. The Claude pattern that maps to that workload is app-API fan-out where the agent makes many calls, inspects bulky intermediate results, and returns one action.

Without a filter point, every API result flows into the model context. Claude programmatic tool calling gives you that filter point. Mark your tool as callable from code execution, then Claude can write a sandbox script that loops over the tool and returns only the answer the model needs.

```python
tools=[
    {"type": "code_execution_20260120", "name": "code_execution"},
    {"name": "fetch_workspace_task", "input_schema": {...},
     "allowed_callers": ["code_execution_20260120"]},
]
```

Using my API key, the measured fan-out run went from 9,451 to 6,828 billed input tokens, with the exact winner returned from the sandbox. That is 28% fewer billed input tokens than the same Claude agent without programmatic tool calling.

Full brief, demo GIF, code, and sample output: https://github.com/cfregly/claude-feature-hits/tree/main/programmatic_tool_calling

Run it in about two minutes for $0.08:

```bash
git clone https://github.com/cfregly/claude-feature-hits && cd claude-feature-hits
export ANTHROPIC_API_KEY=your-api-key
make programmatic_tool_calling
```

To try it on Tasklet's shape, edit `programmatic_tool_calling/my_tool.py` with one work-app tool and the inputs it fans out over.

Happy building,

--Chris Fregly

Applied AI, Startups, Anthropic

### Silmaril: security route for prompt-injection defense

Subject: Congrats on YC! A security route for prompt-injection defense

Hey Aum,

Congrats on YC.

I saw Silmaril is building prompt-injection defense that self-improves for AI-native applications and agents. I made two small public security artifacts for this boundary question: which tool action is high risk, which injected instructions should block or ask, what evidence gets logged, and which official source supports each security-control line.

The security surface I would map first is the exact boundary your product defends: model input, retrieved content, tool call, action policy, operator review, and buyer evidence.

The prompt-injection preflight is here:

https://github.com/cfregly/claude-feature-hits/tree/main/tool_boundary_security

The source-backed controls map is here:

https://github.com/cfregly/claude-feature-hits/tree/main/security_controls_map

Run both with `make security`. The run is zero-spend and catches every injected instruction in the test set: 4/4 cases blocked and 0 dangerous actions allowed, with a source-backed controls map behind it.

The test I would build with you is not generic:

```text
attacker input -> model/tool boundary -> allowed action?
expected: block, ask, or continue
evidence: tool call, refusal, source, and audit event
```

If useful, reply with one prompt-injection workflow you use in demos. I can point you to the closest Claude security pattern, the eval shape, and the source line I would map it to.

Happy building,

--Chris Fregly

Applied AI, Startups, Anthropic
