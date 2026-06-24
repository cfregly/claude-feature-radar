# YC Spring 2026 standouts, routed to a specific production blocker

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
| Sazabi | Sherwood | https://www.ycombinator.com/companies/sazabi | AI-native observability over logs, Slack, and agent investigations | cost | High | https://github.com/cfregly/claude-feature-hits/tree/main/programmatic_tool_calling | `emails/yc_spring_2026/sazabi_programmatic_tool_calling.md` |
| Tasklet | Jonny | https://www.ycombinator.com/companies/tasklet-2 | work agents that call APIs, MCP servers, browsers, and code sandboxes | cost + security follow-up | High | https://github.com/cfregly/claude-feature-hits/tree/main/programmatic_tool_calling | `emails/yc_spring_2026/tasklet_programmatic_tool_calling.md` |
| Complir | Gustav | https://www.ycombinator.com/companies/complir | compliance agents over regulations, product data, and documentation | accuracy + security follow-up | High | https://github.com/cfregly/claude-feature-hits/tree/main/pdf_citations | `emails/yc_spring_2026/complir_pdf_citations.md` |
| Arga Labs | Phillip | https://www.ycombinator.com/companies/arga-labs | real-world sandboxes to test agents and agent-facing software | reliability + security-testing follow-up | Medium-high | https://github.com/cfregly/claude-feature-hits/tree/main/code_execution_state | `emails/yc_spring_2026/arga_labs_code_execution_state.md` |
| Superset | Kiet | https://www.ycombinator.com/companies/superset | IDE for running 100s of coding agents in parallel | reliability | High | https://github.com/cfregly/claude-feature-hits/tree/main/task_budgets | `emails/yc_spring_2026/superset_task_budgets.md` |
| Lightsprint | Ben | https://www.ycombinator.com/companies/lightsprint | collaborative product development with cloud agents | reliability | High | https://github.com/cfregly/claude-feature-hits/tree/main/code_execution_state | `emails/yc_spring_2026/lightsprint_code_execution_state.md` |
| Silmaril | Aum | https://www.ycombinator.com/companies/silmaril | prompt-injection defense that self-improves for AI-native applications and agents | security | High | https://github.com/cfregly/claude-feature-hits/tree/main/tool_boundary_security and https://github.com/cfregly/claude-feature-hits/tree/main/security_claims_guard | `emails/yc_spring_2026/silmaril_security_discovery.md` |

## Fit evidence

- **Sazabi:** high. YC page describes logs, Slack as the primary entry point, background agents, and
  agentic query patterns. Programmatic tool calling maps to fan-out over log and incident data, where
  billed input tokens move.
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
  `security_claims_guard` source table.

## Not routed into this email appendix

- **Hardware and defense systems:** 9 Mothers, Adialante, and Dispatch are interesting companies, but
  the public feature briefs here are Claude API builder patterns, not hardware or spacecraft
  activation briefs.
- **Ploy:** marketing-copy generation could use Claude, but the public page does not expose a sharper
  measured production blocker than generic copy quality. A broad platform email would be noise.

## How to use

Each company-specific email pre-fills the founder greeting from the public YC company page. Re-check
the source URL before sending. The emails carry only public brief links when a public brief exists,
plus the Console API-key link. Docs and references live in the brief to keep the email focused and
keep the link count low. Every public brief is runnable at `cfregly/claude-feature-hits`:
https://github.com/cfregly/claude-feature-hits

Security-specific drafts are different by design. They can point to `tool_boundary_security` for the
measured prompt-injection preflight and `security_claims_guard` for the official-source caveats. Do
not turn the controls map into broad claims in the email.
