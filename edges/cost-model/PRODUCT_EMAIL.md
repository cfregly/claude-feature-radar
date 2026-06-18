# Product-team email: cost, where Claude's pricing wins and where it loses (the lose regimes are the flag)

This edge is a conditional cost win with real lose regimes, so this internal note carries the same rigor
as a founder email and flags the exact shapes where a competitor's pricing structure beats ours. Honesty
runs in both directions: when the engine finds a regime where Claude is the more expensive bill, that
ships to the product team, not buried.

---

**Subject:** Cost edge is real on two narrow traffic shapes, and we lose three named regimes worth flagging

To the Claude platform team,

I built the cost edge into the competitive engine as a pure pricing-model computation (no API call, $0)
over the live, dated prices, fetched 2026-06-18. The Claude figures reconcile against `common/models.py`,
the competitor figures trace to each vendor's own pricing and caching docs. The engine gate refuses to
pass a cost edge unless both a win regime and a lose regime resolve, so this note carries both.

Where the structure genuinely wins:

- The 1h cache TTL with no per-hour storage fee. On sparse, bursty reuse (a 50k-token prefix read a dozen
  times across 8 hours), Claude's flat write plus 0.1x reads with no storage is about $0.48, where
  Gemini's explicit cache is about $2.02 because it meters per-hour storage on the cached tokens for the
  whole TTL window. Source: ai.google.dev/gemini-api/docs/caching.
- The flat 1M-window input band with no above-200k surcharge. On Sonnet (flat $3/MTok), a 300k-token call
  is about $0.90, where Gemini 3.1 Pro charges $4/MTok above 200k for about $1.20. Source:
  ai.google.dev/gemini-api/docs/pricing. The Claude flat-band fact: platform.claude.com/docs/en/about-claude/pricing.

Where we lose, and these are the flags:

- High-QPS continuous reuse. The 0.1x cache-read multiplier is identical on every vendor, so the bill
  collapses toward base input price, and Claude's base input is the highest tier-for-tier. At 2000 reads
  the Claude read-line is $30 vs Gemini $20 vs OpenAI $25. The no-storage-fee edge does not help here.
- Holds longer than one hour. Claude's cache TTL maxes at 1h. OpenAI's best-effort caching reaches 24h
  extended retention on newer models, so a prefix read 3 hours apart hits on OpenAI ($0.16 in the model)
  and expires-and-reprocesses on Claude ($0.60). Source:
  developers.openai.com/api/docs/guides/prompt-caching.
- Below the 200k surcharge threshold, and on the top Claude tier. The long-context win is tier-specific:
  Sonnet's flat $3/MTok beats the surcharged $4, but Opus at a flat $5/MTok does not, and below 200k there
  is no surcharge to dodge so the competitor's raw input price wins the small call.

What I recommend we take from this. The two wins are real and worth a founder slide, but only when scoped
to the exact traffic shape (sparse bursty reuse held under an hour, and a long-context call above 200k on
a mid tier). We should not let either become a "Claude is cheaper" headline, because the high-QPS and
long-hold regimes flip it. The two structural gaps a founder on a cost-sensitive high-throughput workload
will feel are the 1-hour cache TTL cap (vs a 24h option elsewhere) and the base input price at the top
tier. Those are the product levers if we want the cost story to hold at scale, not just on the bursty edge.

Reproduce: `make cost` in the repo, no key, $0. Every price is dated and re-fetchable from the four source
links above. Prices move monthly, so re-ground before the next outbound use.

Built honestly in both directions,

The competitive engine

---

### Why it is built this way (not part of the email)

- **The lose regimes are the point of the note.** The engine writes the product-team email when a fair run
  surfaces a regime where a competitor is cheaper, so the high-QPS, long-hold, and below-threshold losses
  lead the second half, not a footnote.
- **The win is scoped, never inflated.** Both wins are stated with their exact traffic shape and the
  crossover, so nobody downstream turns a conditional edge into a total-cost-of-ownership claim.
- **It names the product levers.** The 1-hour cache TTL cap and the top-tier base input price are called
  out as the two things that would have to change for the cost story to hold at high throughput, which is
  the actionable signal for the platform team.
- **Every number is a dated receipt.** All prices trace to the vendor docs in `edges/cost-model/sample.txt`,
  fetched 2026-06-18, and the Claude prices reconcile against `common/models.py`.
