# claude-competitive-engine

A forkable repo that repeatedly finds live Claude platform feature edges, and turns them into
runnable code for builders to reproduce in their own environment.

The Claude Developer Platform ships every month, so the sharpest edge moves. This repo re-checks the
live docs, ranks the genuine differentiators by what a founder building a product actually prices
(cost, speed, reliability, correctness), and ships each as a one-command benchmark that reads its
numbers off a real API call. Do not trust the writeup, re-run it.

![demo](docs/demo.gif)

Each edge below is proven on a real task, with the receipt committed in `edges/<edge>/sample.txt`.
The distilled, founder-facing versions, the ones a founder clones and reproduces in a single
command, live in the companion repo [`claude-feature-briefs`](https://github.com/cfregly/claude-feature-briefs).

## Lead edge: programmatic tool calling, about 28% fewer billed input tokens (`make ptc`)

If your agent calls a tool many times over data it then crunches (usage rollups across cohorts,
plan-limit checks across accounts, log or trace triage), every tool result flows into the model's
context and you pay input tokens for all of it, even the rows the model only sums and throws away.

Claude has a GA feature for this. Add `allowed_callers: ["code_execution_20260120"]` to a tool and
include the code execution tool, and Claude writes one sandbox script that calls your tool in a loop,
filters and aggregates there, and returns only the answer. The bulky outputs go to the sandbox, not
the model.

Measured on the same fan-out task two ways, same model (Sonnet 4.6), same answer required: across 4
regions of 60 sales rows each (240 rows), find the highest-revenue region.

| mode | billed input tokens | answer |
|---|--:|:--:|
| plain tool use | 9,451 | the model summed 240 rows in its head |
| programmatic | 6,828 | east (the sandbox computed it) |

A 28% input-token cut, and the sandbox returns the exact winner. This pays off when your agent calls
a tool many times over data it then crunches (the fan-out shape). The full receipt is [`edges/programmatic-tool-calling/sample.txt`](edges/programmatic-tool-calling/sample.txt).

```bash
make ptc          # about $0.06 on Sonnet, needs ANTHROPIC_API_KEY
```

Reproduce it on your own tool: edit ONE file, [`app/yourtool.py`](app/yourtool.py), paste your
Messages-API tool dict and the Python that runs it, then `make app` runs the same fan-out task twice
over your tool and prints your own before/after billed-input table and the dollar delta. `make
app-check` runs the shipped example and asserts the invariant first, so you get a real number before
you change a line.

Feature references, fetched 2026-06-18:
- Programmatic tool calling docs: https://platform.claude.com/docs/en/agents-and-tools/tool-use/programmatic-tool-calling
- The 24% fewer input tokens / 11% accuracy gain on agentic search: https://claude.com/blog/improved-web-search-with-dynamic-filtering
- The PTC cookbook (runnable): https://platform.claude.com/cookbook/tool-use-programmatic-tool-calling-ptc

## Supporting edge: Citations, a verifiable per-character source pointer (`make citations`)

For a product built over your users' own documents (contracts, clinical notes, financial filings,
support docs), the trust layer is the click-through to the exact sentence a claim came from. Turn on
`citations: {"enabled": true}` per document and Claude returns each claim with a character range plus
the verbatim quote, extracted and guaranteed by the API to resolve, free of output tokens, with zero
resolver code on your side.

Measured over 8 questions on 3 plain-text documents, each citation graded against the real source:

| approach | resolves | who resolves it | quote free of output tokens | output tokens | cost |
|---|:--:|:--:|:--:|--:|--:|
| Claude Haiku 4.5 + Citations | 8/8 (guaranteed by the API) | the API | yes | 308 | $0.011 |
| DIY: ask the model for the quote, resolve with `str.find` | 8/8 | your code | no | 563 | $0.006 |

The DIY baseline resolves on clean text too, so the edge is not that nobody else can do it. The edge
is that Claude does it for you, guaranteed, free of output tokens, with no resolver code, and only
Claude returns a per-character document pointer. The full receipt is
[`edges/citations/sample.txt`](edges/citations/sample.txt).

```bash
make citations    # about $0.06, needs ANTHROPIC_API_KEY
```

Feature references, fetched 2026-06-18:
- Citations docs: https://platform.claude.com/docs/en/build-with-claude/citations
- Citations cookbook (runnable): https://platform.claude.com/cookbook/misc-using-citations

## Fork and run

```bash
git clone <this-repo> && cd claude-competitive-engine   # the public URL lands on publish
make setup                        # the venv and the one dependency (anthropic)
cp .env.example .env              # paste your ANTHROPIC_API_KEY
make ptc                          # the lead edge, about $0.06 (needs ANTHROPIC_API_KEY)
make app-check                    # the forkable app on the shipped example, then edit app/yourtool.py
```

Cost expectations: every benchmark reads its numbers off a real API call. `make ptc` and `make
citations` each cost about $0.06 on the shipped task. There is no hidden spend, and each target
prints its cost before it commits anything.

The citations edge runs on the Anthropic key alone. To add the cross-vendor table that backs the
per-character claim (the DIY `str.find` baseline on OpenAI and Gemini), install the optional SDKs and
keys: `make compare-deps`, then paste `OPENAI_API_KEY` and `GEMINI_API_KEY` into `.env`.

## Layout

```
app/            the forkable bill-cut app: yourtool.py (the one edit surface) + billcut.py
edges/<edge>/   demo.py, sample.txt, README.md, one per edge
common/         the verified model and price registry, the cost math, the client
docs/           VERIFIED_FACTS.md, CITED_FACTS.md, the demo recording
```

It is packaged as a skill ([`SKILL.md`](SKILL.md)) so you can re-run the same analysis any week.

MIT licensed.
