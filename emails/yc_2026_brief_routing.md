# YC Spring 2026 standouts, routed to a specific brief

Source list: TechCrunch, the 11 standout startups from YC Demo Day, 2026-06-18. Each routed company
gets the one brief whose value prop matches its bottleneck, and the matching founder email is the
draft to send. The five hardware, defense, and security companies do not map to a Claude builder edge,
so they are not contacted: targeting, not spraying.

## Routed (6)

| Company | What they build | Segment | Brief to send | Email draft |
|---|---|---|---|---|
| Sazabi | finds prod problems via log analysis, fixes via Slack | cost | Programmatic tool calling (fan out over logs, keep the bulky rows out of context) | `emails/ptc_FOUNDER_EMAIL.md` |
| Tasklet | an agent that calls work-app APIs to do tasks | cost | Programmatic tool calling (many tool calls, only the answer returns) | `emails/ptc_FOUNDER_EMAIL.md` |
| Complir | AI agents for compliance and regulatory monitoring | trust | PDF citations (a page pointer into the regulation PDF, verifiable) | `emails/pdf_citations_FOUNDER_EMAIL.md` |
| Arga Labs | digital-twin sandboxes for agents to test code | agent | Code-execution state (the sandbox keeps its files across turns) | `emails/code_exec_state_FOUNDER_EMAIL.md` |
| Superset | run 100+ coding agents in isolated workspaces | agent | Task budgets (cap each agent loop so it stops clean, not mid-action) | `emails/task_budgets_FOUNDER_EMAIL.md` |
| Lightsprint | non-engineers build and ship app features via AI | agent | Code-execution state (a build agent that keeps state between steps) | `emails/code_exec_state_FOUNDER_EMAIL.md` |

## Not contacted (5, no edge fit)

9 Mothers (counter-drone hardware), Adialante (MRI hardware), Dispatch (spacecraft), Ploy
(marketing-copy generation), Silmaril (agent security infrastructure). None maps to a measured Claude
builder edge, so a cold email would be noise.

## How to use

Each email has `{first_name}` and `{your_name}` placeholders. Fill the founder's first name, set your
own sign-off, and the email already carries the brief link, the one-line code change, the measured
receipt, and the one-command reproduce path. Every brief is public and runnable at
`cfregly/claude-feature-briefs`.
