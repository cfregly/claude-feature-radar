# claude-competitive-engine

A repeatable engine that finds where the Claude Developer Platform genuinely beats OpenAI and Google,
proves it with fair cross-vendor benchmarks you can reproduce on your own keys, refuses to overclaim,
and emits a founder email per edge. The platforms ship every month, so it re-runs the whole search
each time rather than caching a winner. It reports honestly, including where Claude loses.

## How it works

1. **Sweep** the whole platform and the competitor docs, live, and write a dated brief (`briefs/`).
2. **Rank** every genuine differentiator by value to a founder times how clearly Claude leads, after a
   competitor-parity check that drops anything a rival already matches.
3. **Benchmark** the top edges fairly, cross-vendor, with every number read off the real API.
4. **Scrutinize** every outbound claim with an adversarial panel. It has caught its own overclaims
   (a context-editing local minimum, a citations strawman, a "no competitor ships it" absolute).
5. **Emit** a founder email and a product-team email, per edge.

## The edges

Each edge is isolated in `edges/<edge>/` with its own `demo.py`, committed receipt (`sample.txt`),
`FOUNDER_EMAIL.md`, `PRODUCT_EMAIL.md`, and `README.md`, so we can compare them and pick a winner.

| edge | what it is | status | the measured finding |
|---|---|---|---|
| [programmatic-tool-calling](edges/programmatic-tool-calling/) | Claude writes one sandbox script that calls your tools in a loop and filters results before they reach context | GA | ~28% fewer billed input tokens on a 240-row fan-out task, and the code answers correctly where the in-context model fails (`make ptc`) |
| [citations](edges/citations/) | a per-character verifiable source pointer into the user's own document, free of output tokens | GA | the pointer resolves in-API, guaranteed, with zero resolver code (`make citations`) |
| [context-editing](edges/context-editing/) | in-place clearing that keeps a long agent under the context window | beta | editing off fails 3/3 on a heavy chain, editing on finishes 3/3 (`make longhorizon`) |

Honest ranking: programmatic tool calling is the sharpest (a cost cut a founder feels, no named
competitor equivalent), citations is the cleanest near-binary (only Claude returns a char-level
document pointer, though Gemini File Search now does page-level), and context-editing is the thinnest
(OpenAI ships comparable compaction, and it is beta). The full sourced reasoning is in `briefs/`.

## The credibility layer: Claude is not the cheapest, and we prove it

No edge is cost or speed, because a fair benchmark showed Claude does not win them. The same 32-step
tool agent, all three at full strength:

| platform | cost | time | correct |
|---|--:|--:|:--:|
| OpenAI gpt-5.4-mini | **$0.046** | **42.5s** | no (9 vs 11) |
| Gemini gemini-3.5-flash | $0.374 | 42.6s | yes (11) |
| Claude Haiku 4.5 (context editing on) | $0.124 | 58.4s | no (10 vs 11) |
| Claude Haiku 4.5 (off) | $0.120 | 50.1s | yes (11) |

OpenAI is cheapest and fastest. We report it exactly as it ran (`make compare`), which is the point:
this is the credibility layer, not the pitch. There is also an independent second signal, METR's task
time-horizon, where the top released Claude model runs the longest autonomous jobs of any model (about
1.9x the next best), though our own cross-vendor long run is a tie at affordable scale (`make
longhorizon-compare`). Sourced in [`briefs/2026-06-17-agentic-landscape.md`](briefs/2026-06-17-agentic-landscape.md).

## Where Claude loses (the honest other direction)

Raw price and speed, the coding-agent leaderboards (GPT-5.5 leads Terminal-Bench and BrowseComp),
cache retention (Gemini arbitrary TTL, OpenAI 24h, vs Claude 5m/1h), and the per-edge gaps in each
`edges/<edge>/PRODUCT_EMAIL.md`. Honesty runs both ways.

## Run it

```bash
git clone <this-repo> && cd claude-competitive-engine
make setup && make compare-deps   # core deps, then the OpenAI + Gemini SDKs, into the same venv
cp .env.example .env              # paste your Anthropic, OpenAI, and Gemini keys
make ptc                          # the sharpest edge, on your own keys
make citations                    # the cleanest edge, about six cents
make longhorizon                  # the context-editing edge
make compare                      # the fair cost/speed/correctness benchmark (credibility layer)
```

## This is an engine, not a one-off

```
make scan                # the ranked, verified edges from the live-docs sweep
make verify              # a skeptic pass that refutes the overstated ones
make ptc                 # the programmatic-tool-calling edge benchmark
make citations           # the citations edge benchmark
make longhorizon         # the context-editing edge benchmark
make compare             # the fair cost/speed benchmark (the credibility layer)
make sweep               # the variant sweep that makes the compare result trustworthy
make longhorizon-compare # the cross-vendor long task (a tie at affordable scale, honestly)
make draft               # the founder email, from the verified anchor
make alert               # the product-team email, when a competitor is ahead
make cite                # ground every shipped price and fact through Claude's own Citations API
```

Re-run it any week. It is packaged as a skill ([`SKILL.md`](SKILL.md)) so a founder can run the same
analysis themselves: do not trust the pitch, reproduce it.

## Every number is a receipt

Prices live once in [`common/models.py`](common/models.py), verified in
[`docs/VERIFIED_FACTS.md`](docs/VERIFIED_FACTS.md). Costs come from the API `usage` object. Beta
features are labeled beta. Competitor claims trace to the competitor's own docs, dated, in the briefs.
Nothing is quoted from memory. A cost-claim gate (`make check-claims`) fails if a quoted figure drifts
from its committed receipt. And we eat our own dog food: `make cite` grounds every shipped price and
platform fact through Claude's own Citations API into [`docs/CITED_FACTS.md`](docs/CITED_FACTS.md),
each backed by a guaranteed-valid verbatim quote located by the very feature this repo pitches.

## Layout

```
edges/<edge>/   demo.py, sample.txt, FOUNDER_EMAIL.md, PRODUCT_EMAIL.md, README.md, one per edge
engine/         shared: the cross-vendor arms (openai/gemini), compare, sweep, scan, verify, drafters
common/         shared: the verified model + price registry, the cost math, the client
briefs/         the dated, sourced competitive sweeps
docs/           VERIFIED_FACTS.md and FINDINGS.md
scripts/        the deslop and cost-claim gates
```

MIT licensed. Re-run it any week. The edge moves, and so does this.
