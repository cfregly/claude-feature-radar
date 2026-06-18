# Founder email: cost (the two traffic shapes where Claude's pricing is cheaper, and where it is not)

This edge is a conditional, regime-bounded cost win, not a total-cost-of-ownership claim. The email
leads with the founder workload (a reused prefix and a long-context call), names the two pricing shapes
where Claude is genuinely cheaper, and shows the crossover where it stops being true in the same breath,
so the founder can place their own numbers. The hero stays competitor-neutral per the repo convention,
and the dated competitor prices appear as evidence, not a swipe.

---

**Subject:** Two traffic shapes where Claude is the cheaper bill, and the line where that flips

Hey {first_name},

If you are picking a model provider on price, the headline per-token rates will mislead you, because the
bill depends on the shape of your traffic, not the sticker. I ran the numbers on two shapes founders
actually ship, on every vendor's live, dated pricing, and there are two specific cases where Claude wins
the bill and a clear line where it loses. I would rather you see both than the half I could cherry-pick.

The first shape is a big reused prefix on bursty, recurring traffic: a system prompt plus a large
reference document that you cache and read every few minutes, with gaps. Claude charges a flat one-time
cache write plus reads at a tenth of base input, and no per-hour storage fee. Model a 50k-token
prefix read a dozen times across an eight-hour window and Claude's bill is about $0.48. The same prefix on
Gemini's explicit cache is about $2.02, because Gemini meters per-hour storage on the cached tokens for
the whole window whether you read them or not. The line where this flips: at high QPS the tenth-of-base
read rate is the same on every vendor, so the bill collapses toward the base input price, and there Claude
is the most expensive. And Claude's cache tops out at a one-hour TTL, so if you hold a prefix warm longer
than an hour between reads, a provider with 24-hour cache retention beats it. This is a win for sparse
bursty reuse held under an hour, not a win at scale.

The second shape is a single long-context call: one request with a few hundred thousand tokens of context
(a whole codebase, a long transcript, a big document set). Claude bills the full 1M-token window flat at
standard input pricing, with no surcharge band above 200k. A 900k-token request costs the same per token
as a 9k-token one. On Sonnet at a flat $3 per million tokens, a 300k-token call is about $0.90, where a
competitor that doubles its rate above 200k charges about $1.20 for the same call. The line where this
flips: below 200k there is no surcharge to dodge, and on raw per-token price the competitor can be cheaper,
so the small-context call goes the other way. And this win is tier-specific. It holds on Sonnet, not on the
top Claude tier, whose flat rate sits above the competitor's surcharged rate, so the receipt names the tier
it used.

{repo_link}

Run it yourself: `make cost` is a $0 pricing-model computation. No key, no network, no spend. It prints
both shapes, both the win and the lose regime for each, and the named crossover, so you can drop in your
own prefix size, reuse cadence, and context size and see which side of the line you sit on. Every price is
dated 2026-06-18 and traces to the vendor's own pricing page, and the Claude figures reconcile against the
model registry in the repo, so you can check them instead of trusting me. Prices move, so re-fetch before
you commit a number to a board deck.

The reason I am handing you the lose regimes next to the win regimes is the reason to trust the win: this
is what your bill will actually do, not the half that flatters one vendor.

Go build,

{your_name}
Building with Claude

---

### Why it is built this way (not part of the email)

- **It is a conditional win, framed as one.** The email names the exact traffic shape for each edge (a
  sparse bursty reused prefix held under an hour, and a long-context call above 200k on a mid tier) and
  the crossover where the win flips, so the founder is never sold a total-cost win the numbers do not
  support.
- **The lose regimes ship in the body, not a footnote.** High-QPS base-price loss, the one-hour TTL loss
  to 24h retention, and the below-200k loss are all stated, because a founder picking on price needs the
  line, not just the favorable point.
- **The win is tier-honest.** Edge 2 holds on Sonnet, not the top tier, so the email says so and the
  demonstrator computes the win flag rather than assuming it. An Opus flat band would not beat the
  competitor's surcharged rate, and pretending it does would be the exact overclaim this repo exists to
  catch.
- **Every price is a dated receipt.** The flat 1h cache with no storage fee, the flat 1M band, the
  competitor storage meter and surcharge band all trace to the vendor docs in
  `edges/cost-model/sample.txt`, fetched 2026-06-18, and the Claude prices reconcile against
  `common/models.py`, not quoted from memory.
