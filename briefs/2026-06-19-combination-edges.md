# Combination edges, 2026-06-19

A hunt for edges that only appear when Claude features or subfeatures are STACKED, run as the `/loop`
mandate to find every promotable edge across features, subfeatures, and combinations. Internal
both-directions record. CLAUDE.md (root and engine) now mandates checking combinations, not just
single features and subfeatures.

## Method

Fanned out three combination-cluster analysts (grounding stack, token and cost stack, bulk-economics
stack), each comparing Claude's best stack against the competitor's BEST achievable stack on one
workload, same request count, same guarantees. Then took the top candidate to a live three-vendor
head-to-head.

## Shipped this iteration (verified, all arms ran)

### grounding-stack (demoKind grounding_stack) -> claude-ahead

The combination of three single-source grounding wins (citations, pdf-citations, search-results) in ONE
request over mixed inline sources. Workload: one request carrying a plain-text document, a
directly-supplied PDF, and a developer-supplied search_result chunk, plus a three-part question with one
fact unique to each source.

| arm | answered | source types cited in one request | hosted objects |
|---|:---:|:---:|:---:|
| Claude Haiku 4.5 | 3/3 | 3/3 (char + page + search_result) | 0 |
| OpenAI GPT-5.4 inline | 3/3 | 0/3 | 0 |
| Gemini 3.5 Flash inline | 3/3 | 0/3 | 0 |

All three answered correctly. Only Claude returned a pointer into the supplied content, all three
location types in one response. The competitors' hosted file-search path is measured in the
search-results edge (file or chunk-level, six persisted objects, cannot cite a directly-supplied PDF),
and Gemini file search cannot combine with another tool in one call. Receipt:
`edges/grounding-stack/receipt.json`. Conflict recorded: citations plus structured outputs return a 400,
so the grounded answer is free text.

## Remaining candidates, HELD with a concrete blocker (probed, not cheaply promotable)

### bulk-economics stack (Batch + 1h cache + 300k extended output) -> HELD, needs an expensive proof

Documented capability-cap gap: a single batch turn emits up to 300k output tokens on Claude (beta
`output-300k-2026-03-24`, batch-only) vs 128k on GPT-5.5 and 65,536 on Gemini 3.5 Flash / 3.1 Pro. All
three give a 50% batch discount and compose caching plus structured outputs into batch, so per-token
cost is parity. The edge is one un-truncated deliverable per request, no chunk-and-stitch, above 128k
output. Probed live 2026-06-19, and the cheap proof FAILED to settle it: the Claude batch accepts
`max_tokens=300000` at create time even without the beta header (validation is per-item at processing,
not at create), and BOTH OpenAI (`max_output_tokens=200000`) and Gemini (`max_output_tokens=200000`)
ACCEPT an above-cap value at request validation and return `ok` on a tiny prompt. So no vendor rejects
the parameter cheaply. The cap only binds when output actually reaches it, so the only honest proof is
an expensive run that generates past 128k tokens (a few dollars of output per side, and a Claude batch
can take up to an hour). HELD: promotable only behind an explicit go for that heavyweight generation
receipt. Risk even then: beta header, value only above 128k output, Gemini Flash is cheaper per token.

### token/cost stack (PTC + code execution + web_search dynamic filtering) -> HELD, SDK-ahead + PTC already ships the input half

Real mechanism gap: neither OpenAI nor Gemini can keep a CUSTOM tool's bulky output out of the model's
billed context the way `allowed_callers` does. But the clean INCREMENTAL value over the shipped PTC
edge is the OUTPUT-token half (`response_inclusion: "excluded"`), and that plus `web_search_20260318`
remain docs-ahead of the public SDK 0.111.0 (confirmed again this pass). The INPUT-token half is
already captured by the shipped programmatic-tool-calling edge, and the web-filtering increment needs a
nondeterministic live-web fan-out whose net win can be erased by code-execution overhead. HELD:
re-evaluate when the SDK ships `response_inclusion`, then measure the output-token increment over
PTC-alone. Not a clean new promotable edge today.

## What stands after this round

New combination edge shipped this round: grounding-stack (claude-ahead, verified live, all arms ran).
The two remaining combination candidates are HELD with concrete blockers above: bulk-economics needs a
heavyweight generation receipt behind an explicit go, and the token/cost stack is SDK-ahead on its only
increment over the already-shipped PTC edge. The cheaply-verifiable combination space is dry for this
round: every other stack examined (citations + structured outputs, prompt caching + context editing,
tool search + MCP) is a conflict or parity. The loop converges here until the SDK ships
`response_inclusion` or a go authorizes the bulk-economics generation run.

## Sources (fetched 2026-06-19)

- Citations: https://platform.claude.com/docs/en/build-with-claude/citations
- Search results: https://platform.claude.com/docs/en/build-with-claude/search-results
- PDF support: https://platform.claude.com/docs/en/build-with-claude/pdf-support
- Batch processing: https://platform.claude.com/docs/en/build-with-claude/batch-processing
- Programmatic tool calling: https://platform.claude.com/docs/en/agents-and-tools/tool-use/programmatic-tool-calling
- Web search tool: https://platform.claude.com/docs/en/agents-and-tools/tool-use/web-search-tool
- OpenAI file search: https://developers.openai.com/api/docs/guides/tools-file-search
- OpenAI batch: https://developers.openai.com/api/docs/guides/batch
- Gemini file search: https://ai.google.dev/gemini-api/docs/file-search
- Gemini batch: https://ai.google.dev/gemini-api/docs/batch-api
