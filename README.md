# claude-feature-radar

A private engine that repeatedly finds live Claude platform feature edges, proves them on real
workloads, and publishes only verified Claude wins into public runnable briefs.

Package role: this is the private method repo. Show it live when useful, but do not send a public
link. The public founder-facing output is `claude-feature-hits`. The Product feedback output stays
private.

## Promotion Boundary

The radar is not a static "claims repo." It is a recurring discovery and promotion system. New
Anthropic or competitor releases enter as candidates, not public claims. The radar sweeps docs and
changelogs, stores source hashes and dated snapshots, diffs against the prior landscape, ranks
candidate edges, then only promotes a result if a runnable workload, baseline, eval, receipt, and
skeptic gate survive. If the claim weakens, it moves to misses or stays held instead of being
pitched.

Search broad, prove narrow, republish only with receipts. `feature-radar` watches the surface.
`feature-hits` only contains reproducible wins. `feature-misses` keeps parity, caveats, losses, and
stale findings so stale claims do not disappear. Founder-kit pins companion commits or tags, so
recipes are reproducible even if a companion repo changes later.

A release does not update the claim. A rerun updates the claim.

Freshness hardening lives in two read-only targets:

```bash
make check-freshness     # fail when watched source hashes drift from landscape/landscape.json
make freshness-report    # write an inert receipt-update report under state/outbox/freshness/
```

The freshness report is PR-ready evidence for a human. It does not publish, push, send, or update a
claim.

The Claude Developer Platform ships every month, so the sharpest edge moves. This repo re-checks the
live docs, ranks the genuine differentiators by what a founder building a product actually prices:
cost, speed, reliability, accuracy, and security. It ships only the winning public pattern, with
numbers read from a real API call. Do not trust the writeup, re-run it.

![demo](docs/demo.gif)

Each edge below is proven on a real task, with saved output committed in `edges/<edge>/sample.txt`.
The distilled, founder-facing versions, the ones a founder clones and reproduces in a single
command, live in the companion repo [`claude-feature-hits`](https://github.com/cfregly/claude-feature-hits).

Every edge here is measured before it ships, and measurement is not enough. `make verify` writes
`landscape/adversarial.json`, and publish, MCP lead lists, cadence drafts, and the paid founder-email
drafter only expose edges that are adversarially-confirmed to add value. A `KILLED` row by any current
judge holds the edge until the framing is narrowed and re-tested.

## Current confirmed public lead: programmatic tool calling, about 28% fewer billed input tokens than the same Claude agent without the feature (`make programmatic-tool-calling`)

Current adversarial status, 2026-06-24: confirmed. Claude Opus 4.8 xhigh and GPT-5.5 xhigh both let
the measured fan-out framing survive: the task shows a real token-cost and correctness win, and the
competitor stack has no native equivalent for model-written code looping over developer tools while
keeping bulky intermediate outputs out of model context without building a custom sandbox layer.

If your agent calls a tool many times over data it then crunches (usage rollups across cohorts,
plan-limit checks across accounts, log or trace triage), every tool output flows into the model's
context and you pay input tokens for all of it, even the outputs the model only sums and throws away.

Claude has a feature for this, no beta header. Add `allowed_callers: ["code_execution_20260120"]` to a tool and
include the code execution tool, and Claude writes one sandbox script that calls your tool in a loop,
filters and aggregates there, and returns only the answer. The bulky outputs go to the sandbox, not
the model.

Measured on the same fan-out task two ways, same model (Sonnet 4.6), same answer required: across 4
regions of 60 sales outputs each (240 outputs), find the highest-revenue region.

| mode | billed input tokens | what happens to the 240 outputs |
|---|--:|:--|
| plain tool use | 9,451 | all 240 outputs flow through the model's context |
| programmatic | 6,828 | the sandbox aggregates, only the answer (east) reaches the model |

A 28% input-token cut against the same Claude agent without programmatic tool calling, and the sandbox
returns the exact winner. This proves the mechanism on a fan-out shape and is the current public
feature hit. Cost scope: this is token/API cost, not all-in production COGS. Code execution runtime can
bill separately after the monthly free allowance. The full saved output is
[`edges/programmatic-tool-calling/sample.txt`](edges/programmatic-tool-calling/sample.txt).

The expanded PTC + prompt-cache + 1M-context proof is deterministic arithmetic over dated prices plus
that live PTC receipt. On a 700,000-token stable-prefix session with 100 turns and 200,000 raw
tool-output tokens per turn, Claude cache+PTC is `$43.40` vs `$142.40` for Claude cache without PTC
and `$135.55` for best-case GPT-5.5 1M+cache without PTC. The cliff is the PTC leg: cache and 1M
context do not remove fresh tool-output tokens if the raw outputs keep returning to model context.
Those are model-token estimates and exclude any separate code-execution runtime charge.
The receipt is [`edges/programmatic-tool-calling/ptc-cache-context.json`](edges/programmatic-tool-calling/ptc-cache-context.json),
regenerated by `make ptc-cache-context`.

```bash
make programmatic-tool-calling          # estimated $0.08 token/API cost on Sonnet, needs ANTHROPIC_API_KEY
make ptc-cache-context                  # deterministic PTC + cache + 1M cost model, $0
```

Reproduce it on your own tool: edit ONE file, [`app/my_tool.py`](app/my_tool.py), paste your
Messages-API tool dict and the Python that runs it, then `make app` runs the same fan-out task twice
over your tool and prints your own before-and-after billed-input table and the dollar delta. `make
app-check` runs the shipped example and asserts the invariant first, so you get a real number before
you change a line.

Feature references, fetched 2026-06-18:
- Programmatic tool calling docs: https://platform.claude.com/docs/en/agents-and-tools/tool-use/programmatic-tool-calling
- The 24% fewer input tokens / 11% accuracy gain on agentic search: https://claude.com/blog/improved-web-search-with-dynamic-filtering
- The PTC cookbook (runnable): https://platform.claude.com/cookbook/tool-use-programmatic-tool-calling-programmatic_tool_calling

## Measured but currently held: Citations, a verifiable per-character source pointer (`make citations`)

For a product built over your users' own documents (contracts, clinical notes, financial filings,
support docs), the accuracy layer is the click-through to the exact sentence a claim came from. Turn on
`citations: {"enabled": true}` per document and Claude returns each claim with a character range plus
the verbatim quote, extracted and guaranteed by the API to resolve, free of output tokens, with zero
resolver code on your side.

Measured over 8 questions on 3 plain-text documents, each citation graded against the real source:

| what you get with Claude Haiku 4.5 + Citations | result |
|---|:--|
| every claim resolves to a real source range | 8/8, guaranteed by the API |
| who writes the resolver | the API, zero resolver code on your side |
| the verbatim quote | returned free of output tokens |
| pointer granularity | per character, into the user's own document |

Claude returns a per-character pointer into your user's own document, guaranteed to resolve, with the
verbatim quote free of output tokens and no resolver code to maintain. Current adversarial status,
2026-06-24: held. The live GPT-5.5 xhigh skeptic killed the broad no-store framing because a
competitor stack can combine inline files or extracted chunks, structured output, and a deterministic
quote resolver. Keep the measured receipts, but do not pitch this as a public feature hit until a
narrower claim survives the adversarial value gate. The full saved output is
[`edges/citations/sample.txt`](edges/citations/sample.txt).

```bash
make citations    # estimated $0.01, needs ANTHROPIC_API_KEY
```

Feature references, fetched 2026-06-18:
- Citations docs: https://platform.claude.com/docs/en/build-with-claude/citations
- Citations cookbook (runnable): https://platform.claude.com/cookbook/misc-using-citations

## Supporting edge: PDF citations, page pointers for directly supplied PDFs (`make pdf-citations`)

When a user uploads a PDF and asks a question immediately, the accuracy layer is the page a human can
check. Claude Citations can return a `page_location` citation for a PDF supplied directly in the
request, with the page number and quoted source text. The app does not need to persist the document in
a hosted search store or write its own page resolver.

Measured over 5 questions on a 5-page synthetic agreement PDF, each answer graded against the known
source page:

| arm | answered | direct-PDF pointer | right page | cost | wall time |
|---|:---:|:---:|:---:|---:|---:|
| Claude Haiku 4.5 + PDF Citations | 5/5 | 5/5 | 5/5 | $0.05 | 6.2s |
| OpenAI GPT-5.4 direct `input_file` | 5/5 | 0/5 | 0/5 | $0.01 | 15.9s |
| Gemini 3.5 Flash inline PDF | 5/5 | 0/5 | 0/5 | $0.03 | 14.1s |

Claude answered every question and returned a correct-page citation for every answer. OpenAI and
Gemini answered the same direct-PDF questions but returned no pointer into the supplied PDF on this
direct-file path. Current adversarial status, 2026-06-24: held. GPT-5.5 xhigh killed the public
framing because a competitor stack can combine file search or deterministic page extraction with
structured citations, and the receipt does not compare total cost, latency, or security against that
stack. The edge is direct-PDF grounding evidence, not a current public feature hit. The
full saved output is [`edges/pdf-citations/sample.txt`](edges/pdf-citations/sample.txt), with machine data
in [`edges/pdf-citations/receipt.json`](edges/pdf-citations/receipt.json).

```bash
make pdf-citations # cents-scale direct-PDF citation run, needs all three keys
```

Feature references, fetched 2026-06-19:
- Claude citations docs: https://platform.claude.com/docs/en/build-with-claude/citations
- Claude PDF support docs: https://platform.claude.com/docs/en/build-with-claude/pdf-support
- OpenAI file inputs docs: https://developers.openai.com/api/docs/guides/file-inputs
- OpenAI file search docs: https://developers.openai.com/api/docs/guides/tools-file-search
- Gemini document processing docs: https://ai.google.dev/gemini-api/docs/document-processing
- Gemini file search docs: https://ai.google.dev/gemini-api/docs/file-search

## Measured but currently held: Search results, citations into your own RAG chunks (`make search-results`)

If you run your own retriever (pgvector, a custom reranker, multi-tenant isolation), the accuracy layer
is a deep link from each answer to the exact chunk it came from. Pass your retrieved passages as
`search_result` content blocks with `citations: {"enabled": true}` and Claude returns each claim with a
`search_result_location`: the chunk index, the block span inside it, and the verbatim quote, free of
output tokens. No hosted vector store to stand up, no persisted copy of the user's data, no resolver
code.

Measured over 5 questions on 5 developer-supplied chunks, each citation graded against the chunk that
holds the answer:

| arm | correct cite | pointer | hosted objects | cost |
|---|:---:|:---:|:---:|---:|
| Claude Haiku 4.5 + search results | 5/5 | block-span | 0 | $0.01 |
| OpenAI GPT-5.4 hosted file search | 5/5 | file-level | 6 | $0.03 |
| Gemini 3.5 Flash hosted file search | 5/5 | chunk-level | 6 | $0.02 |

All three cited the correct source. Claude did it inline, resolver-free, with a block-level pointer and
zero persisted objects, where the others each stood up a hosted store of six objects and returned a
coarser pointer. Current adversarial status, 2026-06-24: held. The live GPT-5.5 xhigh skeptic killed
the broad framing because a competitor stack can pass stable chunk IDs inline and require structured
chunk/span output through a small resolver. The full saved output is
[`edges/search-results/sample.txt`](edges/search-results/sample.txt), with machine data in
[`edges/search-results/receipt.json`](edges/search-results/receipt.json).

```bash
make search-results # cents-scale, needs all three keys
```

Feature references, fetched 2026-06-19:
- Claude search results docs: https://platform.claude.com/docs/en/build-with-claude/search-results
- OpenAI file search docs: https://developers.openai.com/api/docs/guides/tools-file-search
- Gemini file search docs: https://ai.google.dev/gemini-api/docs/file-search

## Supporting edge: Grounding stack, three mixed sources cited in one request (`make grounding-stack`)

Real doc-QA products often answer over mixed sources at once: a plain-text note, a PDF the user just
uploaded, and a chunk your own retriever returned. Claude Citations can cite all three in one request:
`char_location` for the text document, `page_location` for the PDF, and `search_result_location` for
the RAG chunk.

Measured over one mixed-source request with three facts, one unique fact per source:

| arm | answered | inline source types cited | hosted objects | cost |
|---|:---:|:---:|:---:|---:|
| Claude Haiku 4.5 | 3/3 | 3/3 | 0 | $0.01 |
| OpenAI GPT-5.4 inline sources | 3/3 | 0/3 | 0 | $0.01 |
| Gemini 3.5 Flash inline sources | 3/3 | 0/3 | 0 | $0.01 |

All three answered correctly. Only Claude returned pointers into the supplied content, and it returned
all three location types in the same response. Current adversarial status, 2026-06-24: held. GPT-5.5
xhigh killed the public framing because a competitor stack can serialize all sources into a unified
source map and use structured citations plus quote-offset validation, making this mostly one-call
packaging. The edge is the one-request inline mixed-source path evidence, not a current public feature
hit. The full saved output is
[`edges/grounding-stack/sample.txt`](edges/grounding-stack/sample.txt), with machine data in
[`edges/grounding-stack/receipt.json`](edges/grounding-stack/receipt.json).

```bash
make grounding-stack # cents-scale, needs all three keys
```

Feature references, fetched 2026-06-19:
- Claude citations docs: https://platform.claude.com/docs/en/build-with-claude/citations
- Claude search results docs: https://platform.claude.com/docs/en/build-with-claude/search-results
- Claude PDF support docs: https://platform.claude.com/docs/en/build-with-claude/pdf-support
- OpenAI file search docs: https://developers.openai.com/api/docs/guides/tools-file-search
- Gemini file search docs: https://ai.google.dev/gemini-api/docs/file-search

## Supporting edge: Web citations, a verifiable quote from the source (`make web-citations`)

For a research, monitoring, or compliance agent over live web sources, every flagged claim should
deep-link to the exact sentence so a human verifies it in seconds. Claude's web_search returns each
claim with a `web_search_result_location`: the URL, the title, and the verbatim `cited_text` (up to 150
characters of the actual source passage), free of input and output tokens. The claim arrives
self-verifying.

Measured over 3 web-research questions, each forced to search the live web, 2026-06-19:

| arm | answered | web citations | with a verbatim source quote |
|---|:---:|:---:|:---:|
| Claude Sonnet 4.6, web_search | 3/3 | 9 | 9 |
| OpenAI GPT-5.5, web_search | 3/3 | 3 | 0 |
| Gemini 3.1 Pro, Google Search | 3/3 | 6 | 0 |

All three cited web URLs, but only Claude returned the verbatim source quote on every citation.
OpenAI's `url_citation` and Gemini's grounding segments index the model's own answer text and carry
only a URL and title, so a claim is not checkable without re-fetching the page. Current adversarial
status, 2026-06-24: held. GPT-5.5 xhigh killed the public framing because competitors can pair URL
citations with page fetch and deterministic quote matching, while the receipt shows equal answer and
URL-citation success with no measured user-value delta beyond native packaging. The full saved output is
[`edges/web-citations/sample.txt`](edges/web-citations/sample.txt), with machine data in
[`edges/web-citations/receipt.json`](edges/web-citations/receipt.json).

```bash
make web-citations # cents-scale, needs all three keys
```

Feature references, fetched 2026-06-19:
- Claude web search docs: https://platform.claude.com/docs/en/agents-and-tools/tool-use/web-search-tool
- OpenAI web search docs: https://developers.openai.com/api/docs/guides/tools-web-search
- Gemini Google Search docs: https://ai.google.dev/gemini-api/docs/google-search

## Supporting edge: Code-execution state that survives (`make code-execution-state`)

A multi-step data agent over a user's files wants to build up state, intermediate tables, a fitted
model, charts, across a conversation without re-uploading or re-running setup. Claude's code execution
sandbox persists its container and files across separate requests (reuse `response.container.id`), and
the container lives 30 days, so the state is there even after the user steps away.

Measured 2026-06-19 by writing a nonce to each vendor's sandbox, reading it back from the reused
container, then re-reading the same container after a 31-minute idle:

| vendor | persists across requests | survives a 31-min idle |
|---|:---:|:---:|
| Claude Sonnet 4.6 | yes | yes, read the file back |
| OpenAI GPT-5.5 | yes, while warm | no, `400 Container is expired` |
| Gemini 3.5 Flash | no reusable container | not applicable |

While warm, Claude and OpenAI both reuse a container. After the idle, Claude read its file back while
OpenAI's container had been discarded (the documented 20-minute idle expiry, measured as a real `400`),
and Gemini has no reusable container to begin with. Current adversarial status, 2026-06-24: held.
GPT-5.5 xhigh killed the public framing because competitors can preserve long-idle workspace state
with files or object storage and rehydrate it, and the receipt proves a 31-minute nonce rather than a
30-day reliability outcome. The evidence remains useful, but it is not a current public feature hit.
The full saved output is [`edges/code-execution-state/sample.txt`](edges/code-execution-state/sample.txt), with machine
data in [`edges/code-execution-state/receipt.json`](edges/code-execution-state/receipt.json).

```bash
make code-execution-state        # write phase, then wait > 20 minutes
make code-execution-state-verify # re-read: Claude survives, OpenAI expired
```

Feature references, fetched 2026-06-19:
- Claude code execution docs: https://platform.claude.com/docs/en/agents-and-tools/tool-use/code-execution-tool
- OpenAI code interpreter docs: https://developers.openai.com/api/docs/guides/tools-code-interpreter
- Gemini code execution docs: https://ai.google.dev/gemini-api/docs/code-execution

## Supporting edge: Bulk extended output, the largest deliverable in one request (`make bulk-output`)

A nightly job that turns each backlog row into one long deliverable (a full report, a large
extraction, a long scaffold) wants it whole, not chunked. On the Message Batches API with the beta
header `output-300k-2026-03-24`, Claude raises the single-request output ceiling to 300,000 tokens. The
competitors' best models cap a single request lower, so a deliverable above their cap forces a
chunk-and-stitch loop.

Measured over one request per arm asking for a long enumerated document, 2026-06-19:

| arm | output tokens in one request | finished | documented cap |
|---|--:|:---:|--:|
| Claude Sonnet 4.6, batch + 300k beta | 230,607 | yes (`end_turn`) | 300,000 |
| OpenAI GPT-5.5 | 764 | stopped early | 128,000 |
| Gemini 3.5 Flash | 32,263 | stopped early | 65,536 |

Claude emitted 230,607 output tokens in one request and finished the deliverable un-truncated, about
1.8x GPT-5.5's documented ceiling and 3.5x Gemini's. Current adversarial status, 2026-06-24: held.
GPT-5.5 xhigh killed the public framing because competitors can chunk, continue, and stitch the same
artifact at similar token cost, while Claude is async and the receipt shows no quality or speed win.
The evidence remains useful, but it is not a current public feature hit. The full
saved output is [`edges/bulk-extended-output/sample.txt`](edges/bulk-extended-output/sample.txt), with
machine data in [`edges/bulk-extended-output/receipt.json`](edges/bulk-extended-output/receipt.json).

```bash
make bulk-output # a few dollars, and the Claude batch can take many minutes, needs all three keys
```

Feature references, fetched 2026-06-19:
- Claude batch processing docs: https://platform.claude.com/docs/en/build-with-claude/batch-processing
- OpenAI GPT-5.5 model card: https://developers.openai.com/api/docs/models/gpt-5.5
- Gemini 3.5 Flash model card: https://ai.google.dev/gemini-api/docs/models/gemini-3.5-flash

## Supporting edge: Exact-list ledger, less cost and time on a long stream (`make ledger`)

Some agent tasks do not need every old tool output in context. They need a precise running state: the
exact set of flagged transaction ids, incident ids, support escalations, or compliance findings.

The ledger edge tests that shape directly. The agent reads 30 large reports, about 20,000 tokens each,
through a tool. It must keep the exact sorted list of every URGENT report id and print the full list
at the end. The corpus is deterministic and the ground truth is computed in code.

| arm | exact list | cost | wall time | peak context |
|---|:---:|---:|---:|---:|
| Claude Haiku 4.5 with context editing | yes | $0.67 | 60.7s | 35,186 |
| OpenAI GPT-5.5 with Responses compaction | yes | $1.84 | 164.3s | 41,548 |
| Gemini 3.1 Pro Preview with full context | yes | $2.57 | 201.0s | 434,629 |

All three arms got the exact list. Claude won on cost and time: about 64% cheaper and 63% faster than
the exact OpenAI run, and about 74% cheaper and 70% faster than the exact Gemini run. Current
adversarial status, 2026-06-24: held. OpenAI survived the claim, but Claude Opus 4.8 xhigh killed it
because the cost and speed delta is confounded by model-tier mismatch and is config-fragile, so the
any-kill rule holds it. The full saved output
is [`edges/exact-list-ledger/sample.txt`](edges/exact-list-ledger/sample.txt), with machine data in
[`edges/exact-list-ledger/receipt.json`](edges/exact-list-ledger/receipt.json).

```bash
make ledger       # estimated $5 on the 2026-06-19 full run, needs all three keys
```

Feature references, fetched 2026-06-19:
- Claude context editing docs: https://platform.claude.com/docs/en/build-with-claude/context-editing
- OpenAI compaction docs: https://developers.openai.com/api/docs/guides/compaction
- Gemini long context docs: https://ai.google.dev/gemini-api/docs/long-context

## Measured but currently held: Cache diagnostics, root cause for silent cache misses (`make cache-diagnostics`)

Prompt caching saves money only when the cached prefix stays stable. A timestamp in the system prompt,
a reordered tool schema, or a changed message history can silently turn a cache hit into a miss. The
usual counter tells you that cache reads dropped. It does not tell you why.

The cache diagnostics edge tests that production debugging shape. The workload sends long
cached-prefix requests across all four documented miss-reason variants.

| arm | root cause known | miss reason exposed |
|---|:---:|---|
| Claude Haiku 4.5 cache diagnostics | yes | `system_changed`, typed and per request |
| OpenAI GPT-5.5 prompt caching | no | none |
| Gemini 3.1 Pro cache counters | no | none |

Claude identified 4/4 documented cache-miss reason variants and reduced the manual cache-miss suspect
list from four prompt-prefix surfaces to one for each miss. The edge is observability: a typed,
per-request reason for every silent cache miss. Current adversarial status, 2026-06-24: held. The live
GPT-5.5 xhigh skeptic killed the broad framing because cache counters plus request hashing and section
diffs can give a practical root-cause diagnosis. The full saved output is
[`edges/cache-diagnostics/sample.txt`](edges/cache-diagnostics/sample.txt), with machine data in
[`edges/cache-diagnostics/receipt.json`](edges/cache-diagnostics/receipt.json).

```bash
make cache-diagnostics # cents-scale, needs all three keys
```

Feature references, fetched 2026-06-19:
- Claude cache diagnostics docs: https://platform.claude.com/docs/en/build-with-claude/cache-diagnostics
- OpenAI prompt caching docs: https://developers.openai.com/api/docs/guides/prompt-caching
- Gemini context caching docs: https://ai.google.dev/gemini-api/docs/caching

## Measured but currently held: Task budgets, stop before a budget-exhausted tool loop (`make task-budget`)

Long-running agents need a clean handoff before they start work that cannot fit the remaining budget.
Output caps and reasoning budgets can limit pieces of a call, but they do not give the model a
provider-side remaining-budget marker for the full loop of thinking, tool calls, tool outputs, and
output.

The task-budget edge tests the first dangerous moment: the agent is about to begin a 12-record audit
by calling `fetch_record(1)`. If the hidden task budget is near exhausted, the correct behavior is to
hand off before making that external tool call.

| arm | hidden low-budget stop | first tool calls | wall time |
|---|:---:|---:|---:|
| Claude Opus 4.8 low budget | yes | 0 | 1.6s |
| Claude Opus 4.8 high-budget control | n/a | 1 | 3.0s |
| OpenAI GPT-5.5 closest controls | no | 1 | 2.1s |
| Gemini 3.1 Pro Preview closest controls | no | 1 | 3.3s |

Claude saw the low remaining `task_budget` and handed off before the first tool call. The high-budget
Claude control, OpenAI closest controls, and Gemini closest controls all started the tool loop. The
edge is budget-control reliability, not a universal cost claim. Current adversarial status, 2026-06-24:
held. The live GPT-5.5 xhigh skeptic killed the broad framing because a competitor agent runner can
combine usage accounting, output/reasoning caps, and preflight tool gates on the same workload. The
full saved output is
[`edges/task-budgets/sample.txt`](edges/task-budgets/sample.txt), with machine data in
[`edges/task-budgets/receipt.json`](edges/task-budgets/receipt.json).

```bash
make task-budget # bounded live measured run, needs all three keys
```

Feature references, fetched 2026-06-19:
- Claude task budgets docs: https://platform.claude.com/docs/en/build-with-claude/task-budgets
- OpenAI reasoning controls docs: https://developers.openai.com/api/docs/guides/reasoning
- Gemini thinking budgets docs: https://ai.google.dev/gemini-api/docs/thinking

## Fork and run

```bash
git clone https://github.com/cfregly/claude-feature-radar && cd claude-feature-radar
make setup                        # the venv and the one dependency (anthropic)
cp .env.example .env              # paste your ANTHROPIC_API_KEY
make programmatic-tool-calling      # confirmed public lead, estimated $0.08 (needs ANTHROPIC_API_KEY)
make app-check                    # the forkable app on the shipped example, then edit app/my_tool.py
```

Cost expectations: every benchmark reads its numbers off a real API call. `make programmatic-tool-calling` is estimated $0.08,
`make citations` estimated $0.06, `make pdf-citations` estimated $0.09, `make search-results` estimated $0.06,
`make grounding-stack` estimated $0.03, `make cache-diagnostics` is cents-scale, `make task-budget` is a
bounded live measured run, and `make ledger` estimated $5 on the shipped full task. There is no hidden spend,
and each target prints its saved output before it commits anything.

Daily deep discovery is budgeted separately from individual proofs. `make grind-deep` defaults to a
$2 hard cap for the skeptic plus combination generator. A scheduler may run
`make grind-deep DEEP_BUDGET_USD=10.00 DEEP_BUDGET_WARN_USD=2.00` when the goal is to find new edges
and combos more aggressively: `$2` stays the normal daily baseline, `$10` is the hard burst ceiling,
and the budget ledger prints `LOUD BUDGET WARNING` when a preflight crosses the baseline.

The citations edge runs on the Anthropic key alone and proves Claude's structured source-pointer
saved output. Cross-vendor grounding comparisons live in the sibling edges, each with its own stated task
shape and optional SDK/key requirements.

## Drive the engine from a chat window (MCP server)

The engine ships an MCP (Model Context Protocol) server, so you can run it conversationally from
Claude Code or Claude Desktop instead of the terminal. It speaks stdio, the transport both clients
use. The server is a thin wrapper in [`engine/mcp_server.py`](engine/mcp_server.py): all the logic and
the safety boundary live in [`engine/mcp_tools.py`](engine/mcp_tools.py), which adds no dependency. The
MCP Python SDK is the one optional package the server needs, kept off the core one-dependency path.

Grounded against the live docs on 2026-06-20: FastMCP exposes a tool with the `@mcp.tool()` decorator
(parameter type hints become the input schema, the docstring becomes the description), stdio is the
default transport, and `claude mcp add` registers a local server. Sources: the
[MCP Python SDK README](https://github.com/modelcontextprotocol/python-sdk) and the
[Claude Code MCP docs](https://code.claude.com/docs/en/mcp).

```bash
make mcp-deps                     # install the optional MCP SDK into the same .venv (once)
make mcp                          # run the server in the foreground (Ctrl-C to stop)
```

### The tools, and the lane each one runs in

The server mirrors the engine's own gate ([`engine/gate.py`](engine/gate.py)). The read tools and the
discovery loop run unattended for free. Anything that writes a repo or spends credits is ASK: it
refuses until you pass `confirm=true`. The actions that send, post, or push are not exposed as tools
at all, so a chat client can never trigger them.

| Tool | What it does | Lane | Spend |
|------|--------------|------|-------|
| `list_edges` | The ranked edge set (verdict, lead basis and score, value, axis) | Safe, unattended | $0 |
| `show_landscape` | A summary: counts by verdict, the top leads, coverage gaps | Safe, unattended | $0 |
| `show_coverage` | Per-demoKind coverage plus the recent coverage ledger | Safe, unattended | $0 |
| `show_boundary` | The gate lanes, the per-tool tier, and the audit (which must be empty) | Safe, unattended | $0 |
| `run_discovery` | The discovery loop: sweep live docs, diff, rank, draft to the inert outbox, coverage | Safe, unattended | $0 |
| `publish_brief` | Generate a public brief for a verified-win edge into the hits repo | ASK, needs `confirm=true` | $0, writes files |
| `run_benchmark` | A paid proof against real API calls, with the estimate surfaced and a cost cap | ASK, needs `confirm=true` | spends credits |

`publish_brief` runs a fail-closed verdict gate first, so it refuses any edge that is not a clean,
ranked, non-regime-bounded Claude win, and it never pushes a remote. `run_benchmark` shows the dollar
estimate before it spends and refuses any estimate over the cap, with a hard ceiling it will not cross
from a tool call. Call either one with `confirm=false` first to preview the action for free.

### Register it in Claude Code

From the engine repo root, after `make mcp-deps`:

```bash
claude mcp add claude-feature-radar -- "$(pwd)/.venv/bin/python" "$(pwd)/engine/mcp_server.py"
claude mcp list                   # verify it is registered and reachable
```

`$(pwd)` records the absolute path at registration time, so the server launches from any working
directory. Use `--scope user` to make it available in every project, or `--scope project` to write a
shared `.mcp.json` into the repo. The project-scoped JSON looks like this:

```json
{
  "mcpServers": {
    "claude-feature-radar": {
      "type": "stdio",
      "command": "/ABSOLUTE/PATH/TO/claude-feature-radar/.venv/bin/python",
      "args": ["/ABSOLUTE/PATH/TO/claude-feature-radar/engine/mcp_server.py"]
    }
  }
}
```

### Register it in Claude Desktop

Open Settings, then Developer, then Edit Config, and add the same `mcpServers` block as above into
`claude_desktop_config.json` (the Edit Config button opens the file for you). Use the absolute path to
the `.venv` Python and to `engine/mcp_server.py`. Restart Claude Desktop, and the tools appear under
the server name.

### Trigger phrases

Once registered, ask in plain language and the client routes to a tool:

- "Show me the ranked Claude edges" or "what are the current leads" runs `list_edges` or `show_landscape`.
- "Run the discovery loop" or "sweep the docs and tell me what changed" runs `run_discovery`.
- "What can the engine prove today" or "show the coverage" runs `show_coverage`.
- "What is this server allowed to do on its own" runs `show_boundary`.
- "Publish the brief for programmatic tool calling" runs `publish_brief` and waits for your confirm.
- "Benchmark the citations edge" runs `run_benchmark`, shows the cost estimate, and waits for your confirm.

## Layout

```
app/            the forkable token-bill app: my_tool.py (the one edit surface) + run_tokens.py + example_tool.py
edges/<edge>/   demo.py, sample.txt, README.md, one per edge
common/         the verified model and price registry, the cost math, the client
engine/         the discovery loop, the demonstrators, the gate, and the MCP server (mcp_server.py + mcp_tools.py)
docs/           VERIFIED_FACTS.md, CITED_FACTS.md, the demo recording
```

It is packaged as a skill ([`SKILL.md`](SKILL.md)) so you can re-run the same analysis any week.

MIT licensed.
