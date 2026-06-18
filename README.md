# claude-competitive-engine

A repeatable engine that finds where the Claude Developer Platform genuinely beats OpenAI and Google,
proves each edge with a fair cross-vendor benchmark you reproduce on your own keys, refuses to
overclaim, and drafts the founder email. Do not trust the pitch, re-run it.

## The mechanism: a $0 weekly live-docs sweep that finds the edge and drafts the email

The platforms ship every month, so a winner you found last quarter is parity this quarter. This engine
does not cache a winner. Every week it re-runs the whole search:

```bash
make edges
```

`make edges` fetches every doc in `engine/sources_registry.py` (Claude, OpenAI, and Gemini) with a
stdlib conditional GET, diffs each page against the last run in `landscape/landscape.json`, ranks the
genuine differentiators by value to a founder times how clearly Claude still leads, and writes the
refreshed `landscape/landscape.json`, a dated changelog, and a dated brief in `briefs/`. No API call,
no benchmark, no spend. It is $0.

Two honesty rules are wired into the code, not the prose. A blocked or unreadable fetch is recorded as
status `unknown`, never as competitor-absence, so the loop cannot manufacture a Claude lead from a
failed download. And a Claude-ahead ranking stands only when every relevant competitor source actually
fetched this run. When the sweep surfaces a fresh edge, `make draft` turns the measured receipt into a
founder email. That whole chain (fetch, diff, rank, draft) is measurement and drafting, so it runs
unattended on a weekly cadence. The boundary is fixed in `engine/gate.py`: nothing in the cadence
sends mail, spends past a cap, or pushes anywhere.

This is the headline. What follows is what the sweep currently ranks at the top, each one proven.

## The featured edges, with the one command that reproduces each

### Programmatic tool calling: about 28% fewer billed input tokens on a fan-out agent (`make ptc`)

If your agent calls a tool many times over data it then crunches (expense checks across a team,
rollups across regions or accounts, log or trace triage), every tool result flows into the model's
context and you pay input tokens for all of it, even the rows the model only sums and throws away.
Claude has a GA feature for this. Add `allowed_callers: ["code_execution_20260120"]` to a tool and
Claude writes one sandbox script that calls your tool in a loop, filters there, and returns only the
answer. The bulky outputs go to the sandbox, not the model.

Measured on the same fan-out task two ways, same model (Sonnet 4.6), same answer required: across 4
regions of 60 sales rows each (240 rows), find the highest-revenue region.

| mode | billed input tokens | answer |
|---|--:|:--:|
| plain tool use | 9,451 | wrong (the model summed 240 rows in its head) |
| programmatic | 6,828 | east (the sandbox computed it) |

A 28% input-token cut, and the code answered correctly where the in-context model did not. The win is
fan-out shaped: on a sequential single-call task the live doc reports it is flat to about 8% more
expensive, so this is for tool-heavy agents. No competitor keeps your own custom-tool outputs out of
context the way `allowed_callers` does. `make ptc`, about six cents on Sonnet.

### Citations: a guaranteed char-level pointer into your user's own document (`make citations`)

For a product built over a user's own documents (contracts, clinical notes, financial filings, support
docs), the trust layer is the click-through to the exact sentence a claim came from. Turn on
`citations: {"enabled": true}` per document and Claude returns each claim with a character range plus
the verbatim quote, extracted and guaranteed to resolve by the API, free of output tokens, with zero
resolver code on your side. Only Claude returns a per-character document pointer. The honest baseline
without it is to ask the model for the quote and resolve it yourself with `str.find`, which returns -1
the moment the model paraphrases, and you own and pay for that code. `make citations`, about six cents.

## Run it on your own tool: watch your own bill drop

You do not have to trust the receipt. The programmatic-tool-calling edge ships as a forkable app, so
you reproduce the bill-cut on your own tool. Edit ONE file, [`app/yourtool.py`](app/yourtool.py): paste
your Messages-API tool dict and the Python that runs it. Then:

```bash
make app
```

runs the same fan-out task twice over your tool, plain tool use vs programmatic, and prints your own
before/after billed-input table, the dollar delta at the model's input price, and an upfront cost line
before it spends anything. Out of the box it ships the worked region_sales example, so `make app-check`
gives you a real number before you change a line and asserts the invariant (programmatic mode bills
fewer input tokens AND answers correctly).

On the shipped example on Sonnet 4.6, measured live: plain tool use billed 9,451 input tokens,
programmatic billed 6,828, a 28% reduction, both correct, for about six cents. Keep your task fan-out
shaped when you swap your tool in. The app and the `make ptc` receipt share one audited token counter
([`engine/demonstrators/token_core.py`](engine/demonstrators/token_core.py)), so the app's number and
the edge's number come from the same code.

## Fork and run

```bash
git clone <this-repo> && cd claude-competitive-engine   # the public URL lands on publish; <this-repo> is the placeholder until then
make setup                        # the venv and the one dependency (anthropic)
cp .env.example .env              # paste your ANTHROPIC_API_KEY
make edges                        # the $0 weekly sweep: find the edges, no key needed
make ptc                          # the sharpest edge, about six cents (needs ANTHROPIC_API_KEY)
make app-check                    # the forkable app on the shipped example, then edit app/yourtool.py
```

For the citations edge and the full cross-vendor credibility benchmark, add the optional OpenAI and
Gemini SDKs and keys: `make compare-deps`, then paste `OPENAI_API_KEY` and `GEMINI_API_KEY` into
`.env`, then `make citations`.

## Beneath the headline

The credibility under the two featured wins, kept honest and below the fold:

- **The full ranking and the parity edges.** The sweep also tracks edges where a competitor matches
  Claude (context editing against OpenAI compaction, for one). They stay in the ranking as parity, not
  pitched as wins. Each is isolated in `edges/<edge>/` with its own demo, committed receipt, and notes.
  The sourced reasoning is in [`briefs/`](briefs/).
- **The cost honesty layer.** No edge here is raw price or speed, because a fair best-to-best benchmark
  (`make compare`) showed Claude is not the cheapest or fastest on a plain tool agent. The engine
  reports that plainly rather than hiding it, which is what makes the two wins above trustworthy. The
  losing and parity cells stay in the brief.
- **Every number is a receipt.** Prices live once in [`common/models.py`](common/models.py), verified
  in [`docs/VERIFIED_FACTS.md`](docs/VERIFIED_FACTS.md). Costs come from the API `usage` object. Beta
  features are labeled beta. Competitor claims trace to the competitor's own dated docs. A cost-claim
  gate (`make check-claims`) fails if a quoted figure drifts from its committed receipt, and `make
  cite` grounds every shipped price through Claude's own Citations API into
  [`docs/CITED_FACTS.md`](docs/CITED_FACTS.md).

## The full command surface

```
make edges               # the $0 weekly sweep: fetch the live docs, diff, rank, write the landscape, changelog, and brief (no API call)
make ptc                 # the programmatic-tool-calling edge benchmark (about six cents)
make citations           # the citations edge benchmark (needs all three keys, about six cents)
make app                 # the forkable bill-cut app on your own tool (app/yourtool.py)
make app-check           # the app self-test on the shipped example
make draft               # the founder email, from the verified anchor
make compare             # the cross-vendor credibility table, all three arms (needs all three keys)
make scan                # the committed seed and fallback edges, no API call
make verify              # the skeptic pass that refutes the overstated ones
make cite                # ground every shipped price and fact through Claude's own Citations API
make check-claims        # the cost-claim gate
make ci                  # the full offline gate chain, the same one CI runs ($0)
```

It is packaged as a skill ([`SKILL.md`](SKILL.md)) so a founder can re-run the same analysis any week.
The canonical founder email is at [`FOUNDER_EMAIL_SUBMISSION.md`](FOUNDER_EMAIL_SUBMISSION.md).

## Layout

```
app/            the forkable bill-cut app: yourtool.py (the one edit surface) + billcut.py
edges/<edge>/   demo.py, sample.txt, README.md, one per edge
engine/         the cross-vendor arms, compare, sweep_edges, scan, verify, drafters, the audited token counter
common/         the verified model + price registry, the cost math, the client
landscape/      the committed diff baseline (landscape.json) and the dated changelog the sweep writes
briefs/         the dated, sourced competitive sweeps
docs/           VERIFIED_FACTS.md, CITED_FACTS.md, FINDINGS.md
scripts/        the deslop, cost-claim, and docs-vs-code gates
```

MIT licensed. Re-run it any week. The edge moves, and so does this.
