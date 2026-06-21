# YC Spring 2026 standouts, routed to a specific brief

Source list: TechCrunch, "The 11 standout startups from YC's Demo Day, according to VCs," published
2026-06-18: https://techcrunch.com/2026/06/18/the-11-standout-startups-from-ycs-demo-day-according-to-vcs/

Company pages and founder greetings last reviewed from public YC pages on 2026-06-20.

The batch-level email is `emails/YC_BATCH_FOUNDER_EMAIL.md`. In the submitted founder-email Google
Doc, put the batch email first, then include this routing table and the six routed drafts below as an
appendix. Each routed company draft names the workload in the opener and points to the exact public
brief README, demo GIF, code, and sample output. Reused numbers are intentional: each routed draft
points to the same reproducible public run for that Claude pattern, measured once using my API key, so a
founder can rerun the brief before swapping in their own workload. The five hardware, defense, and
security companies do not map to a Claude builder edge, so they are not contacted: targeting, not
spraying.

## Routed (6)

Founder names come from the public YC company page. Use the first listed active founder unless the
page clearly marks a CEO founder. Re-check the page before sending because founder pages can change.

| Company | Founder greeting | Founder source | What they build | Segment | Fit confidence | Public brief URL | Company-specific draft |
|---|---|---|---|---|---|---|---|
| Sazabi | Sherwood | https://www.ycombinator.com/companies/sazabi | AI-native observability over logs, Slack, and agent investigations | cost | High | https://github.com/cfregly/claude-feature-hits/tree/main/programmatic_tool_calling | `emails/yc_spring_2026/sazabi_programmatic_tool_calling.md` |
| Tasklet | Jonny | https://www.ycombinator.com/companies/tasklet-2 | work agents that call APIs, MCP servers, browsers, and code sandboxes | cost | High | https://github.com/cfregly/claude-feature-hits/tree/main/programmatic_tool_calling | `emails/yc_spring_2026/tasklet_programmatic_tool_calling.md` |
| Complir | Gustav | https://www.ycombinator.com/companies/complir | compliance agents over regulations, product data, and documentation | trust | High | https://github.com/cfregly/claude-feature-hits/tree/main/pdf_citations | `emails/yc_spring_2026/complir_pdf_citations.md` |
| Arga Labs | Phillip | https://www.ycombinator.com/companies/arga-labs | real-world sandboxes to test agents and agent-facing software | agent | Medium-high | https://github.com/cfregly/claude-feature-hits/tree/main/code_execution_state | `emails/yc_spring_2026/arga_labs_code_execution_state.md` |
| Superset | Kiet | https://www.ycombinator.com/companies/superset | IDE for running 100s of coding agents in parallel | agent | High | https://github.com/cfregly/claude-feature-hits/tree/main/task_budgets | `emails/yc_spring_2026/superset_task_budgets.md` |
| Lightsprint | Ben | https://www.ycombinator.com/companies/lightsprint | collaborative product development with cloud agents | agent | High | https://github.com/cfregly/claude-feature-hits/tree/main/code_execution_state | `emails/yc_spring_2026/lightsprint_code_execution_state.md` |

## Fit evidence

- **Sazabi:** high. YC page describes logs, Slack as the primary entry point, background agents, and agentic query patterns. Programmatic tool calling maps to fan-out over log and incident data.
- **Tasklet:** high. YC page explicitly says agents connect to APIs and MCP, take actions, crunch numbers, process data, and write/run code in a cloud sandbox. Programmatic tool calling maps to many app/API calls with bulky intermediate results.
- **Complir:** high. YC page describes AI agents over regulations, documentation, audit-ready records, labels, risk assessments, declarations, and technical documentation. PDF citations maps to page-linked evidence.
- **Arga Labs:** medium-high. YC page is directly about testing agents against external-service twins, so the agent-testing fit is real. The uncertainty is implementation: Claude persistent code-execution state is a useful pattern for test-agent steps, but Arga may already own the sandbox layer.
- **Superset:** high. YC page says Superset helps engineers run 100s of coding agents in parallel. Task budgets maps to stopping many agents cleanly before they start work they cannot finish.
- **Lightsprint:** high. YC page describes collaborative product development with cloud agents, multiple agents working a codebase, PR previews, and non-engineers shipping product changes. Code-execution state maps to multi-step build agents that need files and test output to persist.

## Not contacted (5, no edge fit)

9 Mothers (counter-drone hardware), Adialante (MRI hardware), Dispatch (spacecraft), Ploy
(marketing-copy generation), Silmaril (agent security infrastructure). None maps to a measured Claude
builder edge, so a cold email would be noise.

## How to use

Each company-specific email pre-fills the founder greeting from the public YC company page. Re-check
the source URL before sending. The email already carries the public brief link, the demo GIF, the code
change, the measured result, the starter-credit CTA, the one-command reproduce path, and a narrow
reply path: send the real bottleneck and Chris can point to the closest Claude pattern. The emails
intentionally include only the public brief/repo links plus the starter-credit link. Docs and
references live in the brief to keep the email focused and keep the link count low. Every brief is
public and runnable at `cfregly/claude-feature-hits`:
https://github.com/cfregly/claude-feature-hits
