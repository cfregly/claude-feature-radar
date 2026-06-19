# Edge: cost, two conditional pricing edges with both regimes shown

Part of [claude-competitive-engine](../../README.md). The question this answers for a founder watching
the bill: are there traffic shapes where Claude's pricing structure is genuinely cheaper, and where does
that stop being true. The honest read is that there are two, both narrow and both conditional, and this
bundle is built to show the regime where Claude loses next to the regime where it wins, so a founder can
see exactly which side of the crossover their own workload sits on.

This is the one demonstrator that calls no model and spends nothing. It computes the total dollar cost of
a realistic traffic pattern on each vendor's live, dated prices. `make cost` needs no key and no network.
Full output in [`sample.txt`](sample.txt).

## The honesty rule that makes this credible

A cost edge that only ever shows the window where Claude wins is a cherry-pick. The gate in
[`cost_model.py`](../../engine/demonstrators/cost_model.py) (`both_regimes_shown`) refuses to pass unless
BOTH a win regime AND a lose regime resolve and the crossover is named. The verdict is therefore never an
unconditional "Claude is cheaper." It is regime-bounded by construction, and the bundle ships the lose
cases in the same table as the win cases.

## Edge 1: one-hour cache TTL with no per-hour storage fee

For a large prefix reused on a sparse, bursty cadence (a read every several minutes with gaps), Claude
charges a flat one-time write plus reads at a tenth of base input, with no separate per-hour storage fee.

| regime | shape | Claude | competitor | who wins |
|---|---|---|---|---|
| WIN | a 50k-token prefix reused 12 times over 8h, reads ~40 min apart | $0.48 | Gemini $2.02 (per-hour storage meter) | Claude beats the storage meter |
| LOSE (high QPS) | the same prefix reused 2000 times, reads seconds apart | $30.00 read-line | Gemini $20.00, OpenAI $25.00 | Claude loses on base price |
| LOSE (long hold) | a prefix held warm 3h between reads (past Claude's 1h max TTL) | $0.60 (cache expired) | OpenAI 24h extended $0.16 | Claude loses to longer retention |

In the win regime, Claude's flat cache beats Gemini's per-hour storage meter, which charges for the cached
token count over the whole TTL window whether or not it is read. In that same window OpenAI's best-effort
cache happens to hold the prefix and reads cheaper than Claude, so the win is specifically against the
storage-meter model, not a clean sweep. The receipt prints that openly. The lose regimes are real: at high
QPS the tenth-of-base read multiplier is identical on every vendor, so the bill collapses toward base input
price where Claude is highest, and a hold longer than one hour loses to OpenAI's 24h extended retention.

## Edge 2: no long-context premium

For a per-call context above the competitor's 200k surcharge threshold, on a Claude tier whose flat rate
is below the surcharged competitor rate, the flat 1M-window band is cheaper.

| regime | shape | Claude (Sonnet, flat $3/MTok) | Gemini 3.1 Pro | who wins |
|---|---|---|---|---|
| WIN | a ~300k-token context (above the 200k band) | $0.90 | $1.20 ($4/MTok above 200k) | Claude's flat band |
| LOSE | the same prompt at ~50k tokens (below the band) | $0.15 | $0.10 ($2/MTok below 200k) | Gemini's lower raw price |

Sonnet is the honest default here. Its flat $3/MTok beats Gemini 3.1 Pro's surcharged $4/MTok above 200k.
Opus at a flat $5/MTok would not win this band even at the competitor's doubled rate, so the demonstrator
states which tier it used and computes the win flag rather than assuming it. Below the 200k threshold there
is no surcharge edge, and on raw per-token input price the competitor is cheaper, so Claude loses the
small-context call.

## Where every number comes from

All prices fetched 2026-06-18. The Claude figures are read from [`common/models.py`](../../common/models.py),
the verified registry, so they cannot drift from the rest of the engine. The competitor figures (Gemini's
per-hour storage meter and above-200k surcharge band, OpenAI's best-effort and 24h-extended caching) are
dated constants in [`cost_model.py`](../../engine/demonstrators/cost_model.py), each carrying its source
url and date:

- Claude pricing: [platform.claude.com/docs/en/about-claude/pricing](https://platform.claude.com/docs/en/about-claude/pricing)
- Gemini caching: [ai.google.dev/gemini-api/docs/caching](https://ai.google.dev/gemini-api/docs/caching)
- Gemini pricing: [ai.google.dev/gemini-api/docs/pricing](https://ai.google.dev/gemini-api/docs/pricing)
- OpenAI caching: [developers.openai.com/api/docs/guides/prompt-caching](https://developers.openai.com/api/docs/guides/prompt-caching)

## Run it yourself

```bash
git clone https://github.com/cfregly/claude-competitive-engine && cd claude-competitive-engine
make cost          # the $0 pricing-model edge, both regimes, crossover named (no key, no spend)
```

`run.py` is not the entry point here. The demonstrator runs directly. `make cost` needs nothing installed
and spends nothing. Override the tiers with `--cache-model` and `--lc-model` to price your own model
choice. A founder's real numbers (prefix size, reuse density, hold time, context size) move the crossover,
so the bundle states the assumptions and lets you re-run on your own shape. Prices move, so re-fetch the
four sources before quoting.

See [`PRODUCT_EMAIL.md`](PRODUCT_EMAIL.md) for the internal read: which side of the crossover a
workload sits on, and where the price advantage flips.
