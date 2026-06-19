---
name: claude-competitive-engine
description: >-
  Run a fair, live-docs competitive analysis of the Claude platform against OpenAI and Google
  Gemini, then emit the assets: a founder email anchored on a genuinely Claude-only capability, a
  product-team email on what competitors have that Claude does not, and a reproducible benchmark
  bundle a founder can run themselves. Use when someone wants to find what Claude has that others
  lack, run a best-to-best cost / speed / correctness benchmark, generate live-evangelism assets, or
  keep competitive intelligence current as the platforms ship every month. Triggers on "competitive
  engine", "what does Claude have that OpenAI or Gemini do not", "fair Claude vs competitor
  benchmark", "live evangelism", "founder email", "competitive gap", or "what do competitors have
  that Claude lacks".
---

# claude-competitive-engine

A repeatable engine that, every time it runs, re-checks the live docs, runs a fair benchmark, and
produces three things:

1. a **founder email** anchored on a capability that is genuinely Claude-only or clearly
   Claude-ahead this week,
2. a **product-team email** listing what OpenAI or Gemini has that Claude does not, and
3. a **reproducible bundle** (both our code and the competitor's code) so anyone can re-run it.

The platforms ship monthly, so a hard-coded claim rots fast. This re-verifies and tells the truth
in both directions, including when Claude loses.

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
   model before a quality claim. When a number cannot be made comparable, drop it. Credibility is the
   whole asset.
8. **A mechanism is not a value, a feature is measured where it bites, and one variable moves at a
   time.** Naming what a feature does (held context at 3k instead of 36k) is a mechanism, not a value.
   The value is a measured change in cost, speed, correctness, or reliability, shown in the regime
   where the feature pays off, with everything else held constant so the win is attributable. A
   feature that only helps at scale is measured at scale: `edges/context-editing/demo.py` holds the memory
   tool and the prompt constant in both arms and toggles ONLY context editing, so the result (editing
   off crashes at the window, editing on finishes) is attributable to context editing alone. The
   earlier version moved four variables at once and wrongly credited context editing for a correct
   answer the memory tool produced. State the measured value, isolate the variable, or do not claim it.
9. **Find the global edge, not a local minimum.** The anchor can be any capability across the whole
   Claude Developer Platform: an API primitive (prompt caching, the Batch API, the memory tool, code
   execution, citations, extended thinking, the 1M-token window), the Agent SDK, Agent Skills, MCP,
   Claude Code, or an economics lever. Do not lock onto the first measurable Claude-only feature, that
   is a local minimum. Survey the entire surface, rank every genuine differentiator by value to a
   founder times how clearly Claude leads after the competitor-parity check, and anchor on the global
   maximum. Then pick the task that EXERCISES that edge: a toy task collapses every model to a
   cost-and-speed race Claude may lose, so the benchmark must be a real job where the edge decides the
   outcome. Re-run the whole search every time, the platform ships monthly and the edge moves. Search
   and rank BEFORE you build, never anchor on the first measurable thing. Any genuine value-add is a
   valid anchor even if narrow, provided it is measured on an axis a founder pays for (cost, speed,
   reliability, long-running, correctness) AGAINST the competitor at its best, not just against Claude
   without the feature. A feature-on-versus-off result is a within-Claude value-add until the
   cross-vendor arm is run, so label it as exactly that.
10. **Understand the mechanism, then find the workload where the edge appears.** Before claiming or
    dismissing a feature, learn how it and the competitor's nearest equivalent actually work and where
    each breaks (Claude's context editing clears in place, OpenAI's compaction summarizes and can drop
    a detail, Gemini carries the full window and pays for it). A toy task shows parity because it never
    stresses the mechanism. Use the mechanism to design a REAL workload that exercises it (a long
    tool-heavy agent, large per-call payloads, a many-document answer), state the workload and the
    founder situation it maps to plainly, and measure. Reliability under load, long-horizon completion,
    correctness under load, and cost at scale are real-world edges, so surface them rather than
    dismissing a feature on a naive test. This vets the feature and finds its genuine win condition, it
    never manufactures a rigged one.

11. **Name the founder use case and the Claude features on every outbound surface.** Every founder
    email and the README hero is written for one reader, a founder building over their users' own work
    (contracts, charts, tickets, research, support docs, a long-running agent). Name that use case and
    the workload behind it first, then name the Claude Developer Platform and Claude Agent SDK features
    that serve it: Citations for the verifiable per-character pointer, the memory tool and context
    editing for the long-horizon job, prompt caching, the model tiers, and the verified differentiator
    the search surfaced this run. Name the feature, then show what the founder gets on that workload,
    measured against the competitor at its best. A feature name is not a value.

12. **The public surface shows only wins, in the founder's language.** Rules 4 and 6 (both-directions
    honesty, lead with the worth) govern the internal analysis and the reviewer. The founder-facing
    surface, meaning the emails, the briefs, and the landing README, shows only verified Claude wins and
    never exposes a Claude negative. No "Claude got it wrong" baseline, no "where Claude loses". Reframe
    any benefit with an unflattering flip side in the positive (exact totals because the math runs in
    code). Speak the founder's language: explain every term (fan out, tool use, rollups, allowed_callers,
    rows to code), lead with the value a founder prices (cost, speed, reliability, accuracy), write cost
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
    as the real sender (name, team, company), with the signature in the email only and never inside the
    public briefs repo. Do not editorialize about feature maturity in a founder email, so mention beta or
    a required header only when the founder must set it, and for a GA feature do not say "it is GA" at all. The
    subject line must clear spam filters, so use no money-and-urgency trigger words (cut, save, free, cheap,
    discount, guarantee, a dollar sign) and keep it warm, personal, and specific to the feature, a genuine note
    to the reader, for example "Congrats on YC! A cool Claude feature to help you build". Write in the
    first person as the sender who represents Anthropic ("we measured", not "Anthropic measures"), and
    open with a concrete line, not vague filler. Use a startup-native example for a startup audience
    (plan limits, usage, churn, signups, logs, MRR), not a generic enterprise one, and carry that single
    example through the problem, the code, the table, and the tool name.
    Every word fights for its place, so cut anything that does not earn its spot, the same every-word-earns-its-place standard.

## The steps

### 1. Audit the live docs (sweep the whole platform surface for the global edge)
Sweep the ENTIRE Claude Developer Platform, not a fixed feature list: the Messages API primitives
(prompt caching, the Batch API, the memory tool, code execution, citations, extended thinking, the
1M-token window), the Agent SDK, Agent Skills, MCP, Claude Code, and the economics levers. For each
candidate, fetch the current Claude doc, the current OpenAI doc, and the current Gemini doc, and
classify it: claude-only, claude-ahead, parity, or behind. Run a skeptic pass that tries to refute
every claude-only claim by finding the competitor's equivalent, and drop anything a competitor
already matches. Then RANK what survives by value to a founder times how clearly Claude leads, and
carry the global maximum forward as the anchor, not the first thing that was easy to measure. This
produces two lists: Claude's genuine differentiators, ranked, and Claude's genuine gaps. Map each to
the founder priority stack: cost, speed, then reduced maintenance and heavy lifting.

### 2. Benchmark best to best
Run the same long-horizon agent on each platform at full strength and measure the outcomes a
founder pays for: total cost, wall-clock time, and correctness.

```
make compare    # OpenAI (Responses + compaction + caching) vs Claude (context editing + memory + caching)
make sweep      # the same, across the knobs that matter, so the result is trusted not assumed
make longhorizon # the regime where managed context pays off: unmanaged degrades or crashes, managed finishes
```

### 3. Synthesize the honest picture
Combine the audit and the benchmark. State plainly where Claude wins, where it ties, and where it
loses. The anchor for the founder email is the sharpest item that is genuinely Claude-only or
clearly Claude-ahead and survived the skeptic, not whatever sounds best.

### 4. Draft the two emails
```
make draft      # the founder email, anchored on the verified differentiator
make alert      # the product-team email, when a competitor is ahead or has something we lack
```

Each email leads with what the reader gets, names the workload (the agent shape and the model ids on
each side), and states the cost and time to reproduce up front. It passes the reader-point-of-view
review, read cold as a busy founder, before it is allowed out.

### 4b. Publish a verified edge to the public briefs repo

```
make publish-brief EDGE=programmatic-tool-calling   # generate a self-contained public brief, offline, $0
```

`make publish-brief EDGE=<key>` (`engine/publish_brief.py`) is the one-source-of-truth fix for the drift
between this engine and the public claude-feature-briefs repo: instead of hand-maintaining a second copy
of a brief, it generates the public brief FROM the engine's own committed truth. It is fail-closed. The
verdict gate refuses to publish unless the edge reads as a clean Claude win in the engine's own records:
the landscape edge must be verdict `claude-ahead` with `lead_score > 0` (falling back to the
`scan.DIFFERENTIATORS` seed leads on a fresh checkout), any present `data/last_<edge>.json` receipt must
agree, and the `fair_comparison.lead_basis` must be a non-regime-bounded basis (head-to-head,
absence-of-evidence, or within-claude-only), so a cost-model or doc-grounded-parity edge is refused. On
refusal it prints the verdict it read and the source, exits non-zero, and writes nothing. On success it
vendors the engine modules the brief needs (rewriting imports by a deterministic prefix swap, refusing
any dangling import), writes a wins-only README and a PROVENANCE stamp, makes idempotent appends to the
briefs-root Makefile and README, and writes the founder email to the engine's own `emails/`. It makes no
model call, never spends, never pushes, and never sends. The default `--briefs-root` is
`../claude-feature-briefs`.

### 5. Ship the reproducible bundle
A self-contained, dated bundle with both platforms' code, the receipts (cost, time, answers), clear
key placement, the exact cost and time to reproduce, and the constraints, so a founder can swap in
their own prompt and know what changes. The founder email links it.

## What a founder runs

```bash
git clone https://github.com/cfregly/claude-competitive-engine && cd claude-competitive-engine
make setup                              # venv + anthropic
pip install -r requirements-compare.txt # openai, only for the comparison
cp .env.example .env                    # paste ANTHROPIC_API_KEY and OPENAI_API_KEY
make compare                            # the fair head-to-head on your own keys
```

Cost to reproduce is printed before you start and is about a dollar on the default size. Point it at
your own task by editing the chain builder and the prompt in `engine/demo.py`.

## The bundled tools

```
engine/scan.py / verify.py    candidate gaps and the skeptic pass
engine/demo.py                the Claude arm (chain agent, context editing + memory + caching)
edges/context-editing/demo.py the long-horizon proof: unmanaged degrades or crashes, managed finishes
engine/openai_arm.py          the OpenAI arm (Responses API, compaction + caching, latest)
engine/compare.py             OpenAI vs Claude, best to best, outcomes a founder pays for
engine/sweep.py               the variant sweep that makes the result trustworthy
engine/draft_email.py         the founder email, from the verified anchor
engine/product_alert.py       the product-team email, both-direction honesty
common/                       verified model + price registry, cost math, client
docs/VERIFIED_FACTS.md        the cited source of truth for every number
```

MIT licensed. Re-run it any week. The gap moves, and so does this.
