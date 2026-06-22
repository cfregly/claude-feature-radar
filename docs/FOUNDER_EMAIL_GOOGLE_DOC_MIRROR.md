# Founder Email Google Doc Mirror

This committed mirror is the repo-gated text surface for the submitted Google Doc. Update the live Doc from this content, then read it back before submission.

## Batch Email

Subject: Congrats on YC! 5 Claude bottlenecks to test this week

Hey YC founders,

Congrats on the batch! I'm Chris Fregly on Anthropic's Applied AI team, focused on startups. I've
worked through 100+ investor-pitch sessions with founders, and the useful pattern is usually the
same: turn this week's bottleneck into a runnable proof. I made a small public repo of Claude
patterns you can run in one command using your own API key.

The repo is here: https://github.com/cfregly/claude-feature-hits

Pick the bottleneck you have this week:

| If the bottleneck is | Start here | What you get |
| --- | --- | --- |
| **cost** from agents that fan out over logs, usage rows, accounts, or app APIs | [`make programmatic_tool_calling`](https://github.com/cfregly/claude-feature-hits/tree/main/programmatic_tool_calling) | 28% fewer billed input tokens than the same Claude agent without programmatic tool calling |
| **speed** for large outputs or long-stream work | [`make bulk_output`](https://github.com/cfregly/claude-feature-hits/tree/main/bulk_output) or [`make exact_ledger`](https://github.com/cfregly/claude-feature-hits/tree/main/exact_ledger) | one un-truncated large deliverable, or a faster exact long-stream run |
| **reliability** for multi-step code, data, or build agents | [`make code_execution_state`](https://github.com/cfregly/claude-feature-hits/tree/main/code_execution_state) or [`make task_budgets`](https://github.com/cfregly/claude-feature-hits/tree/main/task_budgets) | sandbox files that survive across separate requests, or loop-level budget handoffs |
| **accuracy** for answers over PDFs, docs, filings, or retrieved chunks | [`make pdf_citations`](https://github.com/cfregly/claude-feature-hits/tree/main/pdf_citations) or [`make citations`](https://github.com/cfregly/claude-feature-hits/tree/main/citations) | page-level pointers for PDFs and character-level pointers for text docs |
| **security** for regulated data, MCP connectors, prompt injection, or agent attack surface | [`make security`](https://github.com/cfregly/claude-feature-hits#clone-and-run) | a local prompt-injection gate plus a source-backed controls map, both $0.00 |

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
bulky rows there, and sends only the answer back to the model. On my run, the same usage-style
workload went from 9,451 to 6,828 billed input tokens, 28% fewer than the same Claude agent without
programmatic tool calling. It costs $0.08 to reproduce.

Run it:

```shell
git clone https://github.com/cfregly/claude-feature-hits && cd claude-feature-hits
# Get an API key: https://console.anthropic.com/
# If this send has a startup credit code, include it here: <insert-credit-code>
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

If you reply with the bottleneck you are working through this week, I can point you to the closest
Claude pattern.

Happy building,

--Chris Fregly
Applied AI, Startups, Anthropic

## Routing Appendix

# YC Spring 2026 standouts, routed to a specific Claude bottleneck

Source list: TechCrunch, "The 11 standout startups from YC's Demo Day, according to VCs," published
2026-06-18: https://techcrunch.com/2026/06/18/the-11-standout-startups-from-ycs-demo-day-according-to-vcs/

Company pages and founder greetings last reviewed from public YC pages on 2026-06-22.

The batch-level email is `emails/YC_BATCH_FOUNDER_EMAIL.md`. In the submitted founder-email Google
Doc, put the batch email first, then include this routing table and the routed drafts below as an
appendix. Each routed company draft names the workload in the opener and points to the exact
public brief README, demo GIF, code, and sample output when a public runnable brief exists. Reused
numbers are intentional: each routed draft points to the same reproducible public run for that Claude
pattern, measured once using my API key, so a founder can rerun the brief before swapping in their
own workload.

The five pillars are cost, speed, reliability, accuracy, and security. The public repo carries the
wins and preflight gates that are already runnable. Security routes now have two public pieces: the
measured prompt-injection tool-boundary preflight and the source-backed controls map. Keep the email
copy narrow and let the controls map carry the official-source caveats.

## Routed

Founder names come from the public YC company page. Use the first listed active founder unless the
page clearly marks a CEO founder. Re-check the page before sending because founder pages can change.

| Company | Founder greeting | Founder source | What they build | Pillar | Fit confidence | Public brief URL | Company-specific draft |
|---|---|---|---|---|---|---|---|
| Sazabi | Sherwood | https://www.ycombinator.com/companies/sazabi | AI-native observability over logs, Slack, and agent investigations | cost + speed | High | https://github.com/cfregly/claude-feature-hits/tree/main/programmatic_tool_calling | `emails/yc_spring_2026/sazabi_programmatic_tool_calling.md` |
| Tasklet | Jonny | https://www.ycombinator.com/companies/tasklet-2 | work agents that call APIs, MCP servers, browsers, and code sandboxes | cost + security follow-up | High | https://github.com/cfregly/claude-feature-hits/tree/main/programmatic_tool_calling | `emails/yc_spring_2026/tasklet_programmatic_tool_calling.md` |
| Complir | Gustav | https://www.ycombinator.com/companies/complir | compliance agents over regulations, product data, and documentation | accuracy + security | High | https://github.com/cfregly/claude-feature-hits/tree/main/pdf_citations | `emails/yc_spring_2026/complir_pdf_citations.md` |
| Arga Labs | Phillip | https://www.ycombinator.com/companies/arga-labs | real-world sandboxes to test agents and agent-facing software | reliability + security testing | Medium-high | https://github.com/cfregly/claude-feature-hits/tree/main/code_execution_state | `emails/yc_spring_2026/arga_labs_code_execution_state.md` |
| Superset | Kiet | https://www.ycombinator.com/companies/superset | IDE for running 100s of coding agents in parallel | reliability + cost + speed | High | https://github.com/cfregly/claude-feature-hits/tree/main/task_budgets | `emails/yc_spring_2026/superset_task_budgets.md` |
| Lightsprint | Ben | https://www.ycombinator.com/companies/lightsprint | collaborative product development with cloud agents | reliability | High | https://github.com/cfregly/claude-feature-hits/tree/main/code_execution_state | `emails/yc_spring_2026/lightsprint_code_execution_state.md` |
| Silmaril | Aum | https://www.ycombinator.com/companies/silmaril | prompt-injection defense that self-improves for AI-native applications and agents | security | High | https://github.com/cfregly/claude-feature-hits/tree/main/tool_boundary_security and https://github.com/cfregly/claude-feature-hits/tree/main/security_controls_map | `emails/yc_spring_2026/silmaril_security_discovery.md` |

## Fit evidence

- **Sazabi:** high. YC page describes logs, Slack as the primary entry point, background agents, and
  agentic query patterns. Programmatic tool calling maps to fan-out over log and incident data, where
  cost and elapsed time move together.
- **Tasklet:** high. YC page explicitly says agents connect to APIs and MCP, take actions, crunch
  numbers, process data, and write or run code in a cloud sandbox. Programmatic tool calling maps to
  many app/API calls with bulky intermediate results. A security follow-up should map the exact tool
  boundary privately, not replace the primary cost demo.
- **Complir:** high. YC page describes AI agents over regulations, documentation, audit-ready
  records, labels, risk assessments, declarations, and technical documentation. PDF citations maps to
  page-linked accuracy. Enterprise security should stay a private source-backed follow-up.
- **Arga Labs:** medium-high. YC page is directly about testing agents against external-service
  twins. Claude persistent code-execution state is a useful reliability pattern for test-agent steps,
  while security-testing specifics should stay in a private source-backed follow-up.
- **Superset:** high. YC page says Superset helps engineers run 100s of coding agents in parallel.
  Task budgets maps to stopping many agents cleanly before they start work they cannot finish.
  Security should stay a private source-backed follow-up, not the lead demo.
- **Lightsprint:** high. YC page describes collaborative product development with cloud agents,
  multiple agents working a codebase, PR previews, and non-engineers shipping product changes.
  Code-execution state maps to multi-step build agents that need files and test output to persist.
  Design-to-code and coding-agent workflow specifics are useful follow-up, not the lead demo.
- **Silmaril:** high security conversation. YC page describes prompt-injection defense that
  self-improves for AI-native applications and agents. The right route is a founder-to-founder
  security note around the workflow, the measured `tool_boundary_security` preflight, and the
  `security_controls_map` source table.

## Not routed into this email appendix

- **Hardware and defense systems:** 9 Mothers, Adialante, and Dispatch are interesting companies, but
  the public feature briefs here are Claude API builder patterns, not hardware or spacecraft
  activation briefs.
- **Ploy:** marketing-copy generation could use Claude, but the public page does not expose a sharper
  measured bottleneck than generic copy quality. A broad "try Claude" email would be noise.

## How to use

Each company-specific email pre-fills the founder greeting from the public YC company page. Re-check
the source URL before sending. The emails carry only public brief links when a public brief exists,
plus the Console API-key link. Docs and references live in the brief to keep the email focused and
keep the link count low. Every public brief is runnable at `cfregly/claude-feature-hits`:
https://github.com/cfregly/claude-feature-hits

Security-specific drafts are different by design. They can point to `tool_boundary_security` for the
measured prompt-injection preflight and `security_controls_map` for the official-source caveats. Do
not turn the controls map into broad claims in the email.

## Routed Draft: arga_labs_code_execution_state

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

If the harder Arga bottleneck is a different part of the eval loop, reply with that shape and I can
point you to a closer Claude pattern.

Happy building,

--Chris Fregly
Applied AI, Startups, Anthropic

## Routed Draft: complir_pdf_citations

Subject: Congrats on YC! Page-linked accuracy over regulation PDFs

Hey Gustav,

Congrats on YC.

I'm Chris Fregly on Anthropic's Applied AI team, focused on startups. I spend a lot of time working
through the practical bottlenecks that show up after the first useful agent demo.

I saw Complir is building AI agents for compliance and regulatory monitoring. The Claude pattern that
maps to that workload is page-linked PDF evidence for compliance agents whose answers need to survive
reviewer scrutiny.

For compliance, the reviewer needs a one-click jump to the exact page behind the answer. Claude
Citations can do that on the PDF you hand it directly in the request, with no hosted vector store and
no page resolver to write.

```python
doc = {
    "type": "document",
    "source": {"type": "base64", "media_type": "application/pdf", "data": pdf_b64},
    "citations": {"enabled": True},
}
```

Using my API key, over a five-page agreement PDF with five questions, Claude answered 5/5 and
returned a page pointer that resolved to the correct page 5/5. That run cost $0.05.

Full brief, demo GIF, code, and sample output: https://github.com/cfregly/claude-feature-hits/tree/main/pdf_citations

Run it in about a minute for $0.05:

```bash
git clone https://github.com/cfregly/claude-feature-hits && cd claude-feature-hits
# Get an API key: https://console.anthropic.com/
export ANTHROPIC_API_KEY=your-api-key
make pdf_citations
```

To try it on your own data, edit `pdf_citations/run.py` with a regulation PDF and the questions your
agent needs to answer.

The security follow-up for Complir is separate but connected. I would treat accuracy and security as
one buyer story: answer with source pointers, then map the workflow to the public controls table,
caveats, and evidence your buyer needs.

If page-linked regulatory answers are not the sharpest Complir bottleneck right now, send me the one
that is and I can map it to the closest Claude pattern.

Happy building,

--Chris Fregly
Applied AI, Startups, Anthropic

## Routed Draft: lightsprint_code_execution_state

Subject: Congrats on YC! Persistent state for AI build agents

Hey Ben,

Congrats on the batch, and on getting Lightsprint in front of YC.

I'm Chris Fregly on Anthropic's Applied AI team, focused on startups. I focus on the agent-product
details that start mattering once teams expect agents to keep real work moving across sessions.

I saw Lightsprint is building collaborative product development with cloud agents so teams can plan,
preview, and ship with agents. The Claude pattern that maps to that workload is persistent
code-execution state for build agents that need generated files, test output, and scratch state to
survive when a user steps away.

The practical version: have Claude write generated files during one request, save
`r1.container.id`, then pass that value back as `container=container_id` on the next request. Claude
keeps using the same code-execution workspace, so the next build step can read the files, test
output, or scratch state the previous step created instead of rebuilding them from scratch.

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
    container=container_id,
    tools=tools,
    messages=[{"role": "user", "content": "...run tests and patch the files..."}],
)
```

Using my API key, after a 31-minute idle, Claude read the file back from the same container and the
value matched. Containers live 30 days, so the build state survives when a user steps away and comes
back.

Full brief, demo GIF, code, and sample output: https://github.com/cfregly/claude-feature-hits/tree/main/code_execution_state

Run it in about a minute for $0.05:

```bash
git clone https://github.com/cfregly/claude-feature-hits && cd claude-feature-hits
# Get an API key: https://console.anthropic.com/
export ANTHROPIC_API_KEY=your-api-key
make code_execution_state
```

To try it on your own builder, edit `code_execution_state/run.py` with two real build-agent steps and
re-run the same command.

The product-design follow-up is Claude Design into Claude Code: design or prototype, then hand the
implementation to a coding agent. I would keep the first Lightsprint demo on reliability, because the
agent that cannot preserve files, tests, and scratch state across sessions will not feel collaborative
for long.

If the state boundary in Lightsprint is somewhere else, reply with the rough workflow and I can point
you to the more relevant Claude pattern.

Happy building,

--Chris Fregly
Applied AI, Startups, Anthropic

## Routed Draft: sazabi_programmatic_tool_calling

Subject: Congrats on YC! Cost and speed for log-triage agents

Hey Sherwood,

Congrats on YC.

I'm Chris Fregly on Anthropic's Applied AI team, focused on startups. I help teams turn promising
agent demos into production systems where cost, speed, reliability, accuracy, and security are all
designed in early.

I saw Sazabi is building AI-native observability around logs, Slack, and agent-driven
investigations. The Claude pattern that maps to that workload is log-triage fan-out without dragging
every row into the model context.

That workload can get expensive and slow fast. Every log slice or trace payload your tool returns
becomes model context unless you move the crunching somewhere else. Claude programmatic tool calling
lets the model write one sandbox script that calls your own tool in a loop, filters and aggregates
there, and returns only the fix-relevant answer.

```python
response = client.messages.create(
    model="claude-sonnet-4-6",
    messages=[...],
    tools=[
        {"type": "code_execution_20260120", "name": "code_execution"},
        {"name": "query_logs", "input_schema": {...},
         "allowed_callers": ["code_execution_20260120"]},
    ],
)
```

Using my API key, the same fan-out task on 240 rows went from 9,451 to 6,828 billed input tokens,
with the exact winner returned from the sandbox. That is 28% fewer billed input tokens than the same
Claude agent without programmatic tool calling.

Full brief, demo GIF, code, and sample output: https://github.com/cfregly/claude-feature-hits/tree/main/programmatic_tool_calling

Run it in about two minutes for $0.08:

```bash
git clone https://github.com/cfregly/claude-feature-hits && cd claude-feature-hits
# Get an API key: https://console.anthropic.com/
export ANTHROPIC_API_KEY=your-api-key
make programmatic_tool_calling
```

To try it on your own workload, edit `programmatic_tool_calling/my_tool.py` with your log query tool
and re-run the same command.

If Sazabi's heavier bottleneck is accuracy over incident context or security around tool access,
send me the rough workflow and I can point you to the closest Claude pattern.

Happy building,

--Chris Fregly
Applied AI, Startups, Anthropic

## Routed Draft: silmaril_security_discovery

Subject: Congrats on YC! A security route for prompt-injection defense

Hey Aum,

Congrats on YC.

I'm Chris Fregly on Anthropic's Applied AI team, focused on startups. I spend a lot of time with
teams moving agent demos into production, where the hard questions are cost, speed, reliability,
accuracy, and security at the same time.

I saw Silmaril is building prompt-injection defense that self-improves for AI-native applications and
agents. I made two small public security artifacts for exactly this boundary question: which tool
action is high risk, which injected instructions should block or ask, what evidence gets logged, and
which official source supports each security-control line.

The Claude security surface I would map first is the exact boundary your product defends: model
input, retrieved content, tool call, action policy, operator review, and buyer evidence. The public
preflight is deliberately narrow. It prints 5/5 controls, 4/4 prompt-injection cases, 0 dangerous
actions allowed, and $0.00 cost:

https://github.com/cfregly/claude-feature-hits/tree/main/tool_boundary_security

The companion controls map is also public and zero-spend. It checks ten security rows against
official-source snapshots and caveats before any copy ships:

https://github.com/cfregly/claude-feature-hits/tree/main/security_controls_map

The test I would build with you is not a generic "try Claude" demo. It is a prompt-injection eval
over an agent with real tool access:

```text
attacker input -> model/tool boundary -> allowed action?
expected: block, ask, or continue
evidence: tool call, refusal, source, and audit event
```

That gives you the security pillar in the same language buyers use: which attack chain was stopped,
which boundary caught it, and what the operator does next.

Run it:

```shell
git clone https://github.com/cfregly/claude-feature-hits && cd claude-feature-hits
make security
```

If useful, reply with one prompt-injection workflow you use in demos. I can point you to the closest
Claude security pattern, the exact eval shape, and the source row I would map it to.

Happy building,

--Chris Fregly
Applied AI, Startups, Anthropic

## Routed Draft: superset_task_budgets

Subject: Congrats on YC! Clean handoffs for many coding agents

Hey Kiet,

Congrats on the YC batch.

I'm Chris Fregly on Anthropic's Applied AI team, focused on startups. I work on the operational edges
that appear once agents are running in parallel, not just in a demo.

I saw Superset helps engineers run 100s of coding agents in parallel. The Claude pattern that maps to
that workload is loop-level task budgeting, so each agent can stop cleanly before it starts tool work
it cannot finish.

Claude task budgets give the model a token budget for the whole agent loop: thinking, tool calls,
tool results, and output. The model sees a running countdown and can hand off cleanly before starting
work it cannot pay for. At Superset scale, that matters because a small overshoot multiplied across
hundreds of parallel coding agents becomes real latency, queue pressure, and bill variance.

```python
msg = client.beta.messages.create(
    model="claude-opus-4-8",
    max_tokens=256,
    betas=["task-budgets-2026-03-13"],
    tools=tools,
    messages=messages,
    output_config={
        "effort": "low",
        "task_budget": {"type": "tokens", "total": 20000},
    },
)
```

Using my API key, with the task budget exhausted, Claude made 0 tool calls and handed off before
touching the first record. With budget to spare, the same agent started the loop and made 1 call.
Scoped to one avoided tool action on this run, the point is the control surface: many agents can stop
before launching work they no longer have budget to complete.

Full brief, demo GIF, code, and sample output: https://github.com/cfregly/claude-feature-hits/tree/main/task_budgets

Run it in a few seconds for $0.01:

```bash
git clone https://github.com/cfregly/claude-feature-hits && cd claude-feature-hits
# Get an API key: https://console.anthropic.com/
export ANTHROPIC_API_KEY=your-api-key
make task_budgets
```

To try it on your own agent, edit the prompt and tools in `task_budgets/run.py`, then re-run
`make task_budgets`. I would still keep Superset's hard billing and quota stops server-side. The task
budget is the agent's loop-level countdown, not a replacement for your account limits.

The security follow-up matters for many-agent systems. I would use the public preflight and source
map for that path, while keeping the primary Superset demo on task budgets because it maps directly
to reliability, cost, and speed.

If Superset is hitting a different many-agent failure mode, reply with the pattern and I can send the
closest Claude example.

Happy building,

--Chris Fregly
Applied AI, Startups, Anthropic

## Routed Draft: tasklet_programmatic_tool_calling

Subject: Congrats on YC! A sandbox pattern for work-app agents

Hey Jonny,

Congrats on getting Tasklet into YC.

I'm Chris Fregly on Anthropic's Applied AI team, focused on startups. I spend my time on the
mechanics that make agents cheaper, faster, safer, and easier to ship.

I saw Tasklet is building agents that call work-app APIs to get tasks done. The Claude pattern that
maps to that workload is app-API fan-out where the agent makes many calls, inspects bulky
intermediate results, and returns one action.

Without a filter point, every API result flows into the model context. Claude programmatic tool
calling gives you that filter point. Mark your tool as callable from code execution, then Claude can
write a sandbox script that loops over the tool and returns only the answer the model needs.

```python
tools=[
    {"type": "code_execution_20260120", "name": "code_execution"},
    {"name": "fetch_workspace_task", "input_schema": {...},
     "allowed_callers": ["code_execution_20260120"]},
]
```

Using my API key, the measured fan-out run went from 9,451 to 6,828 billed input tokens, with the
exact winner returned from the sandbox. That is 28% fewer billed input tokens than the same Claude
agent without programmatic tool calling. That is the shape: many tool calls, bulky results, one final
answer.

Full brief, demo GIF, code, and sample output: https://github.com/cfregly/claude-feature-hits/tree/main/programmatic_tool_calling

Run it in about two minutes for $0.08:

```bash
git clone https://github.com/cfregly/claude-feature-hits && cd claude-feature-hits
# Get an API key: https://console.anthropic.com/
export ANTHROPIC_API_KEY=your-api-key
make programmatic_tool_calling
```

To try it on Tasklet's shape, edit `programmatic_tool_calling/my_tool.py` with one of your work-app
tools and the inputs it fans out over.

The security follow-up is also real for Tasklet. If the app-agent risk is now the sharper
bottleneck, reply with the workflow and I can map the control boundary with the public preflight and
source-backed controls table.

If Tasklet's heavier bottleneck is a different app-agent loop, reply with that flow and I can point
you to the closest Claude pattern.

Happy building,

--Chris Fregly
Applied AI, Startups, Anthropic
