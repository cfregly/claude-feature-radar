# Master edge landscape: Claude Developer Platform vs OpenAI and Google

Date: 2026-06-18. Reconciles the four committed briefs (platform-edge, sharpest-edge,
agentic-landscape, verified-picture, all 2026-06-17), the 2026-06-18 live-doc delta recheck, and
the never-evaluated surface sweep (2026-06-18). One ranked landscape, the top-set call, honorable
mentions, exclusions, and the genuine changes since 2026-06-17.

All competitor-absence findings below are doc-sourced absence-of-evidence (strong, not a lab-proven
absence). Anthropic's own numbers (38%, 11%/24%, 76%) are doc-sourced, not reproduced on our key.
Reproduce before any outbound quote. The surface ships monthly, so re-verify every dated detail
before the next pitch.

## The top-set call

Yes. The three built edges stay the top set. Programmatic tool calling, Citations, and context
editing are the right three to anchor the work, and nothing in the 2026-06-18 recheck or the
never-evaluated sweep is compelling enough to displace them.

- Programmatic tool calling (PTC) is the sharpest pick and ranks #1. It is GA (the live curl on
  2026-06-18 still carries no anthropic-beta header), it has a mechanism no competitor doc matches
  (allowed_callers keeps developer-tool outputs out of context), and it has a built two-run token
  receipt in the repo.
- Citations ranks #2. It is the cleaner Claude-only binary (per-character source pointer, free
  quote, guaranteed-valid pointers), GA, ZDR-eligible, and still unmatched after the live recheck
  (Gemini File Search still tops out at chunk, page, and media_id, no character offset).
- Context editing is built as the long-horizon reliability receipt and stays in the top three as
  the user named it, but with an honest framing: its head-to-head verdict is contested, not a clean
  lead. It is still beta, and OpenAI ships a GA-style server-side compaction endpoint. One
  correction folded in below: Claude now also ships its own compaction API (beta), so the earlier
  "OpenAI is arguably ahead on compaction" line is now a parity statement, not a Claude deficit.
  Context editing therefore anchors a single-vendor reliability demonstration, not a head-to-head
  win. The head-to-head referee that Claude actually leads is the METR long-horizon anchor.

One nuance the user should carry: if the email needs a head-to-head leadership claim from an
independent referee, the METR 50% task time-horizon is the only one Claude wins with a real margin
(about 1.9x) and a citable data file. The runnable receipt is the context-editing long-horizon
isolation. So the honest hierarchy is PTC and Citations as the platform-feature edges, METR as the
long-horizon head-to-head anchor, and context editing as the within-Claude reliability receipt.

## Master ranked landscape (every evaluated capability)

Verdict legend: claude-ahead, parity, claude-behind, retired, never-evaluated.

| Rank | Capability | Verdict | Built |
|------|------------|---------|-------|
| 1 | Programmatic tool calling (PTC, allowed_callers keeps tool outputs out of context) | claude-ahead | yes |
| 2 | Citations (per-character source pointers, free verbatim quote, guaranteed-valid) | claude-ahead | yes |
| 3 | METR 50% task time-horizon (long-horizon autonomy, the head-to-head anchor) | claude-ahead | yes |
| 4 | Context editing (server-side auto-prune of tool results and thinking blocks) | claude-behind (contested head-to-head, single-vendor reliability win) | yes |
| 5 | Advisor tool (managed executor-plus-advisor cost and quality blend) | claude-ahead (candidate, never head-to-head) | no |
| 6 | Search results content blocks (source-attributed citations over your own RAG results) | claude-ahead (candidate, extends the Citations thesis to live RAG) | no |
| 7 | One-hour cache TTL with no per-hour storage fee | claude-ahead (narrow, conditional on bursty-recurring traffic) | no |
| 8 | No long-context premium (flat 1M-window billing) | claude-ahead (conditional on a long-context-per-call workload) | no |
| 9 | SWE-bench Pro (vendor self-report) | claude-ahead (lower weight, memorization footnote) | no |
| 10 | MCP Atlas (tool-use benchmark, vendor self-report) | claude-ahead (lower weight) | no |
| 11 | Fallback credit plus server-side fallback (single-call cross-model refusal recovery) | claude-ahead (candidate, narrow, Fable and Mythos only) | no |
| 12 | Cache diagnostics (per-request cache_miss_reason explainer) | claude-ahead (candidate, narrow observability) | no |
| 13 | Mid-conversation system messages (mutate instructions without busting the cache) | claude-ahead (candidate, narrow DX and cost) | no |
| 14 | Claude Code as a programmable build surface (Actions, plugins, headless CI) | parity (split across briefs, demoted to supporting) | no |
| 15 | Agent SDK as a build surface | parity (lowest glue-code floor, supporting only) | no |
| 16 | Effort plus adaptive thinking (reasoning-effort dial) | parity (supporting cost story only) | no |
| 17 | Memory tool (model-driven file memory on the founder's own storage) | parity (client-side, hand-rollable) | no |
| 18 | Compaction (Claude-native summarizing compaction API) | parity (both vendors ship it, corrects a stale brief claim) | no |
| 19 | Managed Agents runtime bundle (multi-agent, Outcomes-native, agent Memory, vault creds, scheduling) | parity (richer than the aggregate verdict, needs a fresh per-feature pass) | no |
| 20 | OSWorld-Verified (computer-use benchmark) | parity (narrow, contested, vendor-self-reported) | no |
| 21 | Computer use (the capability) | parity (all three beta or preview) | no |
| 23 | 1M-token context window (raw size) | parity (Gemini matches or exceeds the number) | no |
| 24 | Tool search (defers tool definitions, the discovery layer) | parity (OpenAI matches on gpt-5.4-plus) | no |
| 25 | Agent Skills (SKILL.md) | parity (open standard rivals adopted, cuts against a moat) | no |
| 26 | MCP (Model Context Protocol) | parity (Anthropic gave it to the Linux Foundation, anti-lock-in credibility) | no |
| 27 | Web search and web fetch (built-in tools) | parity (matched across all three) | no |
| 28 | Code execution tool (the sandbox itself, separate from PTC) | parity (all three ship it) | no |
| 29 | Extended, adaptive, interleaved thinking | parity (all three ship a reasoning mode) | no |
| 30 | PDF and vision input | parity (matched) | no |
| 31 | Files API | parity (matched on the competitive axis) | no |
| 32 | Scheduled deployments for Managed Agents (cron) | parity (a founder can cron their own job) | no |
| 33 | Data residency (per-request inference_geo) | parity (differentiated on mechanism, thin) | no |
| 34 | Task budgets (per-request spend and token cap) | parity (budget caps are common) | no |
| 35 | Governance APIs (Admin, Usage and Cost, Compliance, Rate Limits, Code Analytics) | parity (all majors ship admin and usage APIs) | no |
| 36 | Models API capabilities discovery (capabilities object) | parity (infra, internal tooling, not a pitch) | no |
| 37 | output_tokens_details.thinking_tokens billing breakdown plus display omitted | parity (observability, measurement-correctness) | no |
| 38 | ant CLI, 300k batch output, automatic prompt caching | parity (convenience and ergonomics) | no |
| 39 | 50% Batch API discount | parity (matched) | no |
| 40 | 90%-off cached reads (0.1x multiplier) | parity (identical multiplier across all three) | no |
| 41 | Fast mode (speed parameter, premium-priced, preview) | claude-behind (Claude is not the fastest, paid latency knob) | no |
| 44 | Structured Outputs | claude-behind (OpenAI shipped it first, incompatible with Citations) | no |
| 45 | Raw cost per token | claude-behind (most expensive tier, hard cut) | no |
| 46 | Raw speed and latency | claude-behind (proven not fastest, hard cut) | no |
| 47 | Prompt caching TCO (total-cost regime) | retired (0.1x parity collapses to base price, 1h TTL is a liability vs 24h) | no |
| 48 | tau-bench and tau2-bench on Opus 4.8 | never-evaluated (absent from the system card, do not attribute a number) | no |

Single-vendor or color-only items kept out of the ranked table because they are not a head-to-head
comparison: the repo's own context-editing long-horizon receipt (the reliability story behind row
4), and vendor "ran for N hours" endurance demos (Sonnet 4.5 over 30 hours, GPT-5.3-Codex about 25
hours, single-run anecdotes, no shared protocol, color only behind the METR number).

## Honorable mentions (evaluated, not built)

- Claude Code as a programmable build surface (row 14). The strongest "not built" candidate. A
  genuine product-level lead as one bundle (the at-claude GitHub Action opens working PRs following
  CLAUDE.md, plugins package skills, agents, hooks, MCP, and monitors as one marketplace unit), but
  every headline primitive now has a shipping OpenAI or Google equivalent, so it demoted to a
  build-velocity supporting point. Hard to prove with one clean number.
- Computer use (row 21). Claude Opus 4.8 leads OSWorld-Verified on the newest models (83.4% vs GPT
  78.7% vs Gemini 76.2% on Anthropic's card), but the lead is narrow, vendor-self-reported, and an
  effective tie at the older generation on OpenAI's own page. Not built, not an anchor.
- Advisor tool (row 5). The sharpest never-evaluated candidate: the only one of the three vendors
  to expose a managed cost-and-quality blend as one server-side tool. Worth a token-receipt demo if
  a second platform edge is wanted on the cost axis. Run the parity check first (a two-model router
  is conceptually replicable).
- Search results content blocks (row 6). Extends the Citations edge from static documents to live
  RAG and tool pipelines, the shape founders actually ship. A natural fold into the Citations work
  or a demo of its own.
- SWE-bench Pro and MCP Atlas (rows 9 and 10). Claude leads both, but they are vendor self-reports
  (SWE-bench Pro carries an OpenAI memorization footnote), so they are corroboration, not the
  anchor.

## Exclusions (do not pitch as a Claude lead), one line each

- Raw cost per token: Claude is the most expensive tier on a fair benchmark. Hard cut.
- Raw speed and latency: Claude is proven not the fastest. Hard cut.
- Prompt caching TCO: the 0.1x read multiplier is identical across all three, so at high QPS the
  bill is base price where Claude is highest. Retired.
- 90%-off cached reads: identical 0.1x multiplier on all three.
- 50% Batch API discount: matched by all three.
- 1M-token window size: Gemini matches or exceeds the raw number.
- MCP: Anthropic gave it to the Linux Foundation, so it is anti-lock-in credibility, not exclusivity.
- Agent Skills (SKILL.md): an open standard rivals adopted, which cuts against a moat narrative.
- Structured Outputs: OpenAI shipped it first, and it is incompatible with Citations on the same
  document (400).
- Tool search: OpenAI matches on gpt-5.4-plus, Google has an open parity request.
- Web search and web fetch, code execution sandbox, extended thinking, PDF and vision, Files API:
  all matched across vendors.
- Memory tool: client-side, so a competitor can hand-roll the same loop.
- Fast mode: a premium-priced preview latency knob, not an edge. Keep the speed-loss narrative
  honest.
- Effort dial, Agent SDK, Claude Code build surface: parity as headlines, kept as supporting
  points only.
- Compaction, Managed Agents runtime bundle, scheduled deployments, data residency, task budgets,
  governance APIs, capabilities discovery, thinking-token billing breakdown, ant CLI, automatic
  caching: parity or infra, useful as internal tooling or supporting color, not a differentiator.
- Aggregator SWE-bench numbers of 95.5% or 95%: fabricated, never quote.
- The claude_mythos_preview_early 1044.8 min METR entry and the about 14.5 hr live estimate: do not
  cite. Quote only the 718.8 min (about 12.0 hr) data-file figure with its is_sota flag.

## Anything that genuinely changed since 2026-06-17

Real, dated changes from the 2026-06-18 recheck and the never-evaluated sweep. None inverts the
ranked top set.

- Fable 5 and Mythos 5 launched 2026-06-09 with a new tokenizer that produces about 30% more
  tokens than pre-Opus-4.7 models. Material for any token-count or cost receipt, so re-run before
  quoting numbers. Both are 1M context default, 128k max output, always-on adaptive thinking
  (disabling thinking returns 400).
- Sonnet 4 (claude-sonnet-4-20250514) and Opus 4 (claude-opus-4-20250514) retired 2026-06-15, so
  requests now error. Scrub any lingering model ids.
- Context editing gained a clear_thinking_20251015 strategy (thinking-block clearing) on top of
  clear_tool_uses, but is still beta under context-management-2025-06-27.
- Correction to a stale brief claim: Claude ships its own server-side compaction API (beta), so the
  verified-picture brief's "OpenAI's compaction is arguably ahead" is now a parity statement, not a
  Claude deficit. Claude has both in-place context editing and summarizing compaction.
- The PTC doc page added a BrowseComp and DeepSearchQA framing (+11% performance with 24% fewer
  input tokens) and a hardened warning that allowed_callers is not a hard API-level block and must
  not be relied on as a security boundary.
- The Citations doc now states ZDR-eligible explicitly (consistent with the platform-edge brief).
- OpenAI Assistants API shuts down 2026-08-26 (parity folded into the Responses API). Housekeeping
  on OpenAI's agent surface, not a PTC rival.
- Gemini File Search became multimodal on 2026-05-07 (before the cutoff, so not new since the
  brief): image embeddings via gemini-embedding-2, grounding metadata gained media_id and
  page_numbers. Still no character-level offset, so Claude's per-character Citations lead is
  unchanged.

No-change-found on the load-bearing items: Citations GA status and mechanics, PTC GA status and the
38% number, all pricing on the anchor surfaces, Gemini character-level (still absent), and any
beta-to-GA flip on the three Claude anchors. The Claude one-hour max cache TTL vs OpenAI 24-hour
retention nuance is unchanged (no new caching duration knob shipped).

Two items the next sweep should fold in beyond the compaction correction: the Managed Agents bundle
(multi-agent, Outcomes-native, agent Memory, vault env creds, 100k auto-spill, scheduled
deployments) is richer than the aggregate "parity" verdict and deserves a fresh per-feature parity
pass, and several never-evaluated candidates (advisor tool, search results content blocks, fallback
credit, cache diagnostics) need a parity check before any claim.

## Sources

Briefs reconciled:
/briefs/2026-06-17-platform-edge.md,
/briefs/2026-06-17-agentic-landscape.md, /briefs/2026-06-17-sharpest-edge.md,
/briefs/2026-06-17-verified-picture.md.

Live docs (fetched 2026-06-18): platform.claude.com/docs/en/build-with-claude/citations,
/agents-and-tools/tool-use/programmatic-tool-calling, /build-with-claude/context-editing,
/build-with-claude/overview, /release-notes/overview. Google:
ai.google.dev/gemini-api/docs/file-search and /changelog. OpenAI: developers.openai.com Code Interpreter,
function-calling, and Responses-API guides.

Built edges verified in the repo: edges/citations/demo.py with data/last_citations.json (make
citations), the PTC two-run receipt in engine/ with data/last_ptc.json (make ptc), and the
context-editing long-horizon receipt engine/longhorizon_compare.py with data/last_longhorizon.json
(make longhorizon), which is also the runnable receipt behind the METR long-horizon brief.
