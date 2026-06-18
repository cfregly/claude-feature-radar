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

1. **Compare best to best, latest to latest.** Use each platform's newest API and all of its best
   features, including alpha and beta, on both sides. Never disable a competitor's caching,
   compaction, or parallelism, and never use an older API, to make Claude look better. Never
   handicap Claude either. If our best loses to their best, that is the finding.
2. **Always use the live docs.** Every capability claim and every price traces to the vendor's own
   current doc page, fetched at run time, dated. Memory tells you what to verify, never what to
   assert.
3. **Verify before you trust. Try the variants.** A benchmark has many knobs (model tier, trim
   threshold, caching on or off, prompt wording). Sweep them and explain every number before you
   believe it. A single run is a guess. (See the prompt-confound and cache-invalidation findings in
   `docs/FINDINGS.md` for why this is not optional.)
4. **Honesty runs both directions.** When Claude wins, write the founder email. When a competitor
   wins or has something Claude lacks, write the product-team email. Same rigor either way.
5. **Scrutinize every outbound word.** The founder email and the product email are the highest-stakes
   surfaces. Every claim sourced and not overstated, the reproduction one command with clear key
   placement and an upfront cost, the prose deslop-clean. When in doubt, weaken the claim.

## The steps

### 1. Audit the live docs (what is genuinely Claude-only, and what Claude lacks)
For each candidate Claude capability, fetch the current Claude doc, the current OpenAI doc, and the
current Gemini doc, and classify it: claude-only, claude-ahead, parity, or behind. Run a skeptic
pass that tries to refute every claude-only claim by finding the competitor's equivalent. Keep only
what survives. This produces two lists: Claude's genuine differentiators and Claude's genuine gaps.
Map each to the founder priority stack: cost, speed, then reduced maintenance and heavy lifting.

### 2. Benchmark best to best
Run the same long-horizon agent on each platform at full strength and measure the outcomes a
founder pays for: total cost, wall-clock time, and correctness.

```
make compare    # OpenAI (Responses + compaction + caching) vs Claude (context editing + memory + caching)
make sweep      # the same, across the knobs that matter, so the result is trusted not assumed
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

### 5. Ship the reproducible bundle
A self-contained, dated bundle with both platforms' code, the receipts (cost, time, answers), clear
key placement, the exact cost and time to reproduce, and the constraints, so a founder can swap in
their own prompt and know what changes. The founder email links it.

## What a founder runs

```bash
git clone <this-repo> && cd claude-competitive-engine
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
engine/openai_arm.py          the OpenAI arm (Responses API, compaction + caching, latest)
engine/compare.py             OpenAI vs Claude, best to best, outcomes a founder pays for
engine/sweep.py               the variant sweep that makes the result trustworthy
engine/draft_email.py         the founder email, from the verified anchor
engine/product_alert.py       the product-team email, both-direction honesty
common/                       verified model + price registry, cost math, client
docs/VERIFIED_FACTS.md        the cited source of truth for every number
```

MIT licensed. Re-run it any week. The gap moves, and so does this.
