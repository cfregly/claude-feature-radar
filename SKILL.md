---
name: claude-feature-radar
description: >-
  Run a fair, live-docs competitive analysis of the Claude platform against OpenAI and Google
  Gemini, then emit the assets: a founder email anchored on a genuinely Claude-only capability, a
  product-team email on what competitors have that Claude does not, and a reproducible benchmark
  bundle a founder can run themselves. Use when someone wants to find what Claude has that others
  lack, run a best-to-best cost / speed / reliability / accuracy / security benchmark, generate live-evangelism assets, or
  keep competitive intelligence current as the platforms ship every month. Triggers on "competitive
  engine", "what does Claude have that OpenAI or Gemini do not", "fair Claude vs competitor
  benchmark", "live evangelism", "founder email", "competitive gap", or "what do competitors have
  that Claude lacks".
---

# claude-feature-radar

A repeatable engine that, every time it runs, re-checks the live docs, runs a fair benchmark, and
produces three things:

1. a **founder email** anchored on a capability that is genuinely Claude-only or clearly
   Claude-ahead this week,
2. a **product-team email** listing what OpenAI or Gemini has that Claude does not, and
3. a **reproducible bundle** (both our code and the competitor's code) so anyone can re-run it.

The platforms ship monthly, so a hard-coded claim rots fast. This re-verifies and tells the truth
in both directions, including when Claude loses.

The promotion bar is adversarially-confirmed to add value. A candidate stays internal or held until
the skeptic pass, exact sources, and receipts prove a founder-valued outcome survived.

## The rules, non-negotiable

These are why the output is trusted. Break one and the trust is gone.

0. **Use Chris Fregly's voice.** Before drafting or editing any founder email, product email, brief,
   README CTA, or outbox draft, read `CHRIS_FREGLY_VOICE.md`. Write builder-to-builder: warm,
   direct, concrete, measured, first-person, and code-backed. Keep the public talk cadence, but strip
   transcript filler. Start with the workload, then the mechanism, receipt, and next step.

1. **Compare best to best, latest to latest.** Use each platform's newest API and all of its best
   features, including alpha and beta, on both sides. Never disable a competitor's caching,
   compaction, or parallelism, and never use an older API, to make Claude look better. Never
   handicap Claude either. If our best loses to their best, that is the finding. Beta and alpha are
   not merely allowed, they are often where the Claude edge lives, so anchor on a beta or alpha
   feature when it is the sharpest verified differentiator and label it beta with the doc, the date,
   and any beta header it needs (Claude Managed Agents needs `managed-agents-2026-04-01`, for example).
   When docs advertise a newer tool version, model, parameter, response field, or beta header, verify
   latest SDK version, installed SDK schema, raw API acceptance, and header requirements before
   treating it as live.
   Fast mode has a separate org-level rate-limit pool. A `0 fast mode input tokens per minute` error
   cannot be fixed in this repo or by changing the Messages request. Request fast-mode access or a
   fast-mode rate-limit increase through the Anthropic account path, confirm it on the Claude Console
   Limits page or with the Rate Limits API, then run `make fast-mode` for the receipt.
2. **Always use the live docs.** Every capability claim and every price traces to the vendor's own
   current doc page, fetched at run time, dated. Memory tells you what to verify, never what to
   assert.
3. **Verify before you trust. Try the variants.** A benchmark has many knobs (model tier, trim
   threshold, caching on or off, prompt wording). Sweep them and explain every number before you
   believe it. A single run is a guess. (See the prompt-confound and cache-invalidation findings in
   `docs/FINDINGS.md` for why this is not optional.)
4. **Honesty runs both directions.** When Claude wins, write the founder email. When a competitor
   wins or has something Claude lacks, write the product-team email. Same rigor either way.
5. **Scrutinize every outbound word, with a mandatory adversarial panel.** The founder email and the
   product email are the highest-stakes surfaces. Neither ships without a final outbound-scrutiny
   pass: an adversarial review panel that hunts for one overclaim, checks every claim against the
   brief and the benchmark, confirms the email opens with a measurable, true, Claude-favorable hook,
   confirms the reproduction is one command with clear key placement and an upfront cost, and
   confirms the prose is deslop-clean. If any reviewer flags an overclaim, weaken it. This pass is
   mandatory on every run. An overstated outbound message is worse than no message.
6. **Lead with the worth to the reader, and keep it transparent.** Every output (the two emails, the
   README, the result tables) says what the reader gets before how it was made, and carries the
   workload (the task, the agent shape, the model ids on each side, the features on), the run's cost
   and time, and the cost and time for the reader to reproduce it, up front. Every review of an
   outbound surface is done from the receiver's point of view, cold, as a busy founder: what is this,
   what do I get, what does it cost me to check, why believe you, what next.
7. **Apples to apples, or the number does not ship.** Every cross-vendor number counts the same thing
   on every side, verified. Claude's `input_tokens` excludes cached tokens (cache_read is separate),
   while OpenAI's `input_tokens` and Gemini's `prompt_token_count` include them, so carried context is
   input plus cache_read plus cache_creation on Claude (all three input buckets) and the total field on
   the others. Pull every price live, report the caching config, and run the competitor's stronger
   model before an Accuracy/correctness claim. When a number cannot be made comparable, drop it. Credibility is the
   whole asset.
8. **A mechanism is not a value, a feature is measured where it bites, and one variable moves at a
   time.** Naming what a feature does (held context at 3k instead of 36k) is a mechanism, not a value.
   The value is a measured change in one of the five feature-hit pillars, shown in the regime where
   the feature pays off, with everything else held constant so the win is attributable. A
   feature that only helps at scale is measured at scale: `edges/context-editing/demo.py` holds the memory
   tool and the prompt constant in both arms and toggles ONLY context editing, so the result (editing
   off crashes at the window, editing on finishes) is attributable to context editing alone. The
   earlier version moved four variables at once and wrongly credited context editing for a correct
   answer the memory tool produced. State the measured value, isolate the variable, or do not claim it.
9. **Find the global edge, not a local minimum.** The anchor can be any capability across the whole
   Claude Developer Platform: an API primitive (prompt caching, the Batch API, the memory tool, code
   execution, citations, extended thinking, the 1M-token window), the Agent SDK, Agent Skills, MCP,
   Claude Code, or an economics lever. Do not lock onto the first measurable Claude-only feature, that
   is a local minimum. Survey the entire surface, then dive below the feature label. Break every
   candidate into subfeatures: parameters, modes, beta headers, response fields, billing behavior,
   lifecycle rules, failure modes, and where it sits inside an agent loop. Do not stop at "web
   search", "files", "tools", "agents", "caching", or "code execution" and call it parity. The wedge
   often lives one layer down, as with web search where the generic feature is parity but pre-context
   dynamic filtering plus result-block exclusion can still be a real candidate. Rank every genuine
   differentiator by value to a founder times how clearly Claude leads after the competitor-parity
   check, and anchor on the global maximum. Then pick the task that EXERCISES that edge: a toy task
   collapses every model to a cost-and-speed race Claude may lose, so the benchmark must be a real job
   where the edge decides the outcome. Re-run the whole search every time, the platform ships monthly
   and the edge moves. Search and rank BEFORE you build, never anchor on the first measurable thing.
   Any genuine value-add is a valid anchor even if narrow, provided it is measured on a pillar a founder
   pays for (cost, speed, reliability, accuracy, or security) AGAINST the competitor at its best,
   not just against Claude without the feature. A feature-on-versus-off result is a within-Claude
   value-add until the cross-vendor arm is run, so label it as exactly that.
10. **Understand the mechanism, then find the workload where the edge appears.** Before claiming or
    dismissing a feature, learn how it and the competitor's nearest equivalent actually work and where
    each breaks (Claude's context editing clears in place, OpenAI's compaction summarizes and can drop
    a detail, Gemini carries the full window and pays for it). A toy task shows parity because it never
    stresses the mechanism. Use the mechanism to design a REAL workload that exercises it (a long
    tool-heavy agent, large per-call payloads, a many-document answer), state the workload and the
    founder situation it maps to plainly, and measure. Reliability under load, long-horizon completion,
    accuracy under load, cost at scale, speed under load, and security boundaries are real-world edges, so surface them rather than
    dismissing a feature on a naive test. This vets the feature and finds its genuine win condition, it
    never manufactures a rigged one.

11. **Compare at subfeature depth, then explain it plainly.** The comparison unit is the smallest
    meaningful mechanism that changes builder value, not the broad marketing feature. For every
    candidate, write the subfeature claim first: what changes in the API call, what the model sees,
    what the client receives, and which cost, speed, reliability, accuracy, or security number should move.
    Compare the competitor's closest subfeature, not only its headline feature. If the competitor has
    the umbrella capability but lacks the exact mode, field, lifecycle behavior, or token-accounting
    behavior, record the candidate as parity-gated and test it. If it survives, explain that
    subfeature in public-reader language with public docs and a receipt. If docs, SDK, and runtime
    disagree at this level, resolve and record that discrepancy first: accepted tags, rejected tags,
    SDK schema support, raw HTTP result, beta-header attempts, and whether the candidate is held.

12. **Name the founder use case and the Claude features on every outbound surface.** Every founder
    email and the README hero is written for one reader, a founder building over their users' own work
    (contracts, charts, tickets, research, support docs, a long-running agent). Name that use case and
    the workload behind it first, then name the Claude Developer Platform and Claude Agent SDK features
    that serve it: Citations for the verifiable per-character pointer, the memory tool and context
    editing for the long-horizon job, prompt caching, the model tiers, and the verified differentiator
    the search surfaced this run. Name the feature, then show what the founder gets on that workload,
    measured against the competitor at its best. A feature name is not a value.

13. **The public surface shows only wins, in the founder's language.** Rules 4 and 6 (both-directions
    honesty, lead with the worth) govern the internal analysis and the reviewer. The founder-facing
    surface, meaning the emails, the briefs, and the landing README, shows only verified Claude wins and
    never exposes a Claude negative. No "Claude got it wrong" baseline, no "where Claude loses". Reframe
    any benefit with an unflattering flip side in the positive (exact totals because the math runs in
    code). Speak the founder's language: explain every term (fan out, tool use, rollups, allowed_callers,
    rows to code), lead with the value a founder prices (cost, speed, reliability, accuracy, or security), write cost
    as a dollar figure like $0.06, label every table column plainly with the key number where a quick
    scan expects it, keep it warm, and review it cold as a founder with five seconds. The founder-facing
    checklist, read cold as a busy YC founder with five seconds: open with a warm personal note to the YC
    founder then get to the point, state the problem in their terms (dollars, latency, maintenance) before
    the feature as the solution, show the real minimal code in Python with the changed lines marked,
    include the current official doc link verified live, label table columns as with-the-feature versus
    without-it with each cell explained, abbreviate the value ("28% cheaper"), never imply a Claude
    negative even softly, keep the voice that of a friend and fellow builder not a salesperson, and give
    one reproduce path of one or two commands with the cost as a dollar figure. Keep it crisp (cut every
    word that does not earn its place, warm but never awkward, proper grammar), make the
    run-it-on-your-own-data path explicit (the one file to edit and the one command to re-run), and sign
    neutrally as a sender placeholder plus "Building with Claude" unless the user provides an approved
    real sender. Keep the signature in the email only and never inside the public hits repo. Do not
    editorialize about feature maturity in a founder email, so mention beta or
    a required header only when the founder must set it, and for a GA feature do not say "it is GA" at all. The
    subject line must clear spam filters, so use no money-and-urgency trigger words (cut, save, free, cheap,
    discount, guarantee, a dollar sign) and keep it warm, personal, and specific to the feature, a genuine note
    to the reader, for example "Congrats on YC! A cool Claude feature to help you build". Write in the
    first person as a builder sharing the run ("I measured", "using my API key"). Generic engine
    drafts never claim to speak for Anthropic. The curated take-home email packet may use the
    assigned Anthropic role because the prompt explicitly asks for it. Open with a concrete line,
    not vague filler. Use a startup-native example for a startup audience
    (plan limits, usage, churn, signups, logs, MRR), not a generic enterprise one, and carry that single
    example through the problem, the code, the table, and the tool name.
    Every word fights for its place, so cut anything that does not earn its spot, the same every-word-earns-its-place standard.

14. **Public readers have only public context.** Any generated public brief, README, founder email, or
    forkable bundle must stand alone with files that ship in that repo and public URLs. Do not rely on
    the parent workspace, local receipts, local plans, or any unlinked repository. If a
    claim, instruction, source, or reproduction step is needed to understand the edge, include it in
    the public artifact or link to a public source.

15. **Fan out only on a wide, independent search space.** The engine is not a parallel pipeline by
    default. The discovery loop is one deterministic stdlib pass for $0, and the skeptic pass is one
    model call over all candidates, not a fleet. Fan out (a multi-lane sweep, a review panel) only
    when the search space is wide and independent (many subfeatures or competitor surfaces at once,
    each lane blind to the others), when a thorough audit needs coverage over cost, or when a finding
    wants diverse skeptic lenses. Stay inline and sequential to ground a single claim (one fetch) or
    to verify one edge against its primary source, where the rigor is reading one source carefully,
    not skimming ten. Managed Agents is a capability this engine may anchor an edge on, never the
    machinery that runs it. Parallel processing is earned by the search space, not taken by default.

16. **Model tier tracks stakes, not cost.** Pick the tier by stakes times reasoning difficulty times
    volume, never "default to cheap". The judgment seats decide what is true and what ships, so they
    run on the top tier (Opus) with adaptive thinking on: the skeptic pass (`engine/verify.py`), the
    founder email, and the product-team note. Extraction and mid-tier work that an API already
    guarantees runs on Sonnet, like the Citations grounding loop (`engine/cite_facts.py`), where
    thinking adds latency over many calls for no judgment gain. The deterministic discovery loop stays
    a $0 pass with no model call at all. Almost nothing here runs on Haiku, and the one place it would
    is a benchmark arm that deliberately races Claude's cheap tier against the competitor's equivalent
    cheap tier (GPT and Gemini), tier-matched on purpose, never a judgment call. Haiku cannot take the
    effort knob or adaptive thinking, which is exactly why it is wrong for any seat whose job is to
    think. When in doubt, go up a tier: the judgment calls are low-volume, so the cost of the top tier
    is pennies and the cost of a lenient skeptic is the whole asset.

## The steps

### 1. Audit the live docs (sweep the whole platform surface for the global edge)
Sweep the ENTIRE Claude Developer Platform, not a fixed feature list: the Messages API primitives
(prompt caching, the Batch API, the memory tool, code execution, citations, extended thinking, the
1M-token window), the Agent SDK, Agent Skills, MCP, Claude Code, and the economics levers. For each
candidate, fetch the current Claude doc, the current OpenAI doc, and the current Gemini doc. Then
break the candidate into subfeatures before classifying it: modes, headers, parameters, response
fields, billing behavior, lifecycle behavior, tool-loop behavior, and failure modes. Classify the
subfeature, not only the high-level feature, as claude-only, claude-ahead, parity, or behind. Run a
skeptic pass that tries to refute every claude-only claim by finding the competitor's exact equivalent,
and drop anything a competitor already matches. For docs-new subfeatures, test the latest SDK and
raw API surface before ranking. A documented field that is not accepted by the current API/key is a
held discrepancy, not a public edge. Then RANK what survives by value to a founder times
how clearly Claude leads, and carry the global maximum forward as the anchor, not the first thing that
    was easy to measure. This produces two lists: Claude's genuine differentiators, ranked, and Claude's
    genuine gaps. Map each to the five feature-hit pillars: cost, speed, reliability, accuracy, and
    security. These are feature outcomes, not the radar architecture or activation funnel. A feature can
    carry multiple pillars only when each pillar has its own receipt.

### 2. Benchmark best to best
Run the same long-horizon agent on each platform at full strength and measure the feature-hit
outcomes a founder pays for: cost, speed, reliability, accuracy, and security where applicable.

```
make compare    # OpenAI (Responses + compaction + caching) vs Claude (context editing + memory + caching)
make sweep      # the same, across the knobs that matter, so the result is trusted not assumed
make longhorizon # the regime where managed context pays off: unmanaged degrades or crashes, managed finishes
make ledger     # exact-list long stream, Claude vs OpenAI vs Gemini, data-backed edge when promotable
make pdf-citations # direct-PDF page citations, data-backed edge when promotable
make search-results # BYO RAG chunk citations, data-backed edge when promotable
make grounding-stack # text + PDF + RAG chunk citations in one request, data-backed edge when promotable
make web-citations # live-web citations with a verbatim source quote, data-backed edge when promotable
make citations-paraphrase # Claude inline citations vs OpenAI file_search vs Gemini File Search over a user's own documents, feature vs feature, data-backed edge when promotable
make bulk-output # largest single-request deliverable, data-backed edge when promotable
make cache-diagnostics # cache-miss root-cause observability, data-backed edge when promotable
make task-budget # full-loop budget marker, stop-before-tool-call edge when promotable
make fast-mode  # fast-mode access and speed validation, held if org has 0 fast-mode ITPM
make advisor    # advisor routing cost-at-quality candidate, held unless promotable
```

For the recurring loop, use:

```
make grind        # tier 1, $0: doc sweep, rank, coverage, full offline CI
make grind-deep   # tier 2, budgeted: the $0 loop, then the Opus skeptic and combinatorial generator
make check-freshness  # fail when watched source hashes drift from the pinned landscape
make freshness-report # write the inert receipt-update report for a human PR
```

`make grind` is the default no-credit loop: live doc sweep, rank, dispatch estimates, inert outbox
draft, coverage view, and the full offline CI gate. It never runs a paid proof. `make grind-deep` adds
the Opus skeptic pass and the combinatorial edge generator on top. A daily scheduler may use
`make grind-deep DEEP_BUDGET_USD=10.00 DEEP_BUDGET_WARN_USD=2.00`: `$2` is the normal daily baseline,
`$10` is the hard burst ceiling, and the budget ledger must warn loudly before crossing the baseline.
When the loop surfaces a candidate, run the specific live target named in the estimate, promote only
when the receipt says `promotable_edge: true`, then run `make grind` again so the landscape, coverage,
and gates catch up.

Freshness is a gate, not a publisher. `make check-freshness` compares live source hashes against
`landscape/landscape.json`. `make freshness-report` writes stale sources, rerun commands, blank
results, and blank promote, hold, or miss decisions under `state/outbox/freshness/`. A release does
not update the claim. A rerun updates the claim.

### 3. Synthesize the honest picture
Combine the audit and the benchmark. State plainly where Claude wins, where it ties, and where it
loses. The anchor for the founder email is the sharpest item that is genuinely Claude-only or
clearly Claude-ahead and survived the skeptic, not whatever sounds best.

For held candidates, run the narrow validators before writing any public claim:

```
make dynamic-web   # live receipt for web search/fetch dynamic filtering, held unless promotable
make fast-mode     # access-gated until the org has nonzero fast-mode ITPM
make advisor       # held unless a harder workload shows cost-at-quality value
```

These commands can produce positive signal. None creates a public edge unless its receipt shows
`promotable_edge: true`. Keep comparing subfeatures and combinations, not headline features: response
fields, lifecycle behavior, billing fields, beta headers, conflicts, and how the feature behaves
inside an agent loop are the search space.

### 4. Draft the two emails
```
make draft      # the founder email, anchored on the verified differentiator
make alert      # the product-team email, when a competitor is ahead or has something we lack
```

Each email leads with what the reader gets, names the workload (the agent shape and the model ids on
each side), and states the cost and time to reproduce up front. It passes the reader-point-of-view
review, read cold as a busy founder, before it is allowed out.

### 4b. Publish a verified edge to the public hits repo

```
make publish-brief EDGE=programmatic-tool-calling   # generate a self-contained public brief, offline, $0
```

`make publish-brief EDGE=<key>` (`engine/publish_brief.py`) exports to the optional public
`claude-feature-hits` companion repo. The engine itself is still self-contained: a normal clone does
not need that sibling checkout unless the user is publishing a brief. Instead of hand-maintaining a
second copy of a brief, it generates the public brief FROM the engine's own committed truth. It is
fail-closed. The verdict gate refuses to publish unless the edge reads as a clean Claude win in the engine's own records:
the landscape edge must be verdict `claude-ahead` with `lead_score > 0` (falling back to the
`scan.DIFFERENTIATORS` seed leads on a fresh checkout), any present `data/last_<edge>.json` receipt must
agree, and the `fair_comparison.lead_basis` must be a non-regime-bounded basis (head-to-head,
absence-of-evidence, or within-claude-only), so a cost-model or doc-grounded-parity edge is refused. On
refusal it prints the verdict it read and the source, exits non-zero, and writes nothing. On success it
vendors the engine modules the brief needs (rewriting imports by a deterministic prefix swap, refusing
any dangling import), writes a wins-only README and a PROVENANCE stamp, makes idempotent appends to the
briefs-root Makefile and README, and writes the founder email to the engine's own `emails/`. It makes no
model call, never spends, never pushes, and never sends. Pass `--briefs-root=<path>` when the companion
repo is not checked out at the default `../claude-feature-hits` location.

### 5. Ship the reproducible bundle
A self-contained, dated bundle with both platforms' code, the receipts (cost, time, answers), clear
key placement, the exact cost and time to reproduce, and the constraints, so a founder can swap in
their own prompt and know what changes. The founder email links it.

## What a founder runs

```bash
git clone https://github.com/cfregly/claude-feature-radar && cd claude-feature-radar
make setup                              # venv + anthropic
pip install -r requirements-compare.txt # openai, only for the comparison
cp .env.example .env                    # paste ANTHROPIC_API_KEY and OPENAI_API_KEY
make compare                            # the fair head-to-head using your own API keys
```

Cost to reproduce is printed before you start and is about a dollar on the default size. Point it at
your own task by editing the chain builder and the prompt in `engine/demo.py`.

## Operate it from a chat window (MCP server)

The engine runs conversationally through an MCP server over stdio, so you can drive it from Claude
Code or Claude Desktop. The read tools (`list_edges`, `show_landscape`, `show_coverage`,
`show_boundary`) and the `$0` discovery loop (`run_discovery`) run unattended for free. The two
outward tools are ASK and refuse until you pass `confirm=true`: `publish_brief` writes a public brief
(fail-closed verdict gate, never pushes) and `run_benchmark` runs a paid proof (estimate surfaced,
cost-capped). The actions that send, post, or push have no tool, so a chat client cannot trigger them.
The boundary mirrors `engine/gate.py`, and `show_boundary` prints it for inspection.

```bash
make mcp-deps                                  # install the optional MCP SDK into the same .venv (once)
claude mcp add claude-feature-radar -- "$(pwd)/.venv/bin/python" "$(pwd)/engine/mcp_server.py"
```

Then ask in plain language: "show the ranked Claude edges", "run the discovery loop and tell me what
changed", "what can the engine prove today", "what is this server allowed to do on its own", "publish
the brief for programmatic tool calling", or "benchmark the citations edge". The README "Drive the
engine from a chat window" section has the full tool table, the Claude Desktop steps, and the grounding
citation. Grounded against the live MCP and Claude Code docs on 2026-06-20.

## The bundled tools

```
engine/mcp_server.py          the stdio MCP server, the chat-window entrypoint (the one optional SDK)
engine/mcp_tools.py           the SDK-free tool logic and the gate boundary the server exposes
engine/scan.py / verify.py    candidate gaps and the skeptic pass
engine/demo.py                the Claude arm (chain agent, context editing + memory + caching)
edges/context-editing/demo.py the long-horizon proof: unmanaged degrades or crashes, managed finishes
engine/openai_arm.py          the OpenAI arm (Responses API, compaction + caching, latest)
engine/compare.py             OpenAI vs Claude, best to best, outcomes a founder pays for
engine/sweep.py               the variant sweep that makes the result trustworthy
engine/ledger_compare.py      the exact-list long-stream edge, best-to-best across 3 vendors
engine/demonstrators/dynamic_web_filtering.py  the held dynamic web filtering validator
engine/demonstrators/task_budgets.py           the task_budget full-loop edge validator
engine/demonstrators/web_citations.py          the live-web source-quote citation edge validator
engine/demonstrators/bulk_extended_output.py   the large single-request deliverable edge validator
engine/draft_email.py         the founder email, from the verified anchor
engine/product_alert.py       the product-team email, both-direction honesty
common/                       verified model + price registry, cost math, client
docs/VERIFIED_FACTS.md        the cited source of truth for every number
```

MIT licensed. Re-run it any week. The gap moves, and so does this.
