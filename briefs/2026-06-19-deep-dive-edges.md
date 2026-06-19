# Deep-dive edges, 2026-06-19

A deeper grind into the response-field, citation-object, and billing-field layer, run as the `/loop`
mandate to keep finding edges. Internal both-directions record. Three deep clusters were mined: web
grounding fidelity, the MCP connector and agentic loop, and fine-grained economics/observability.

## Shipped this iteration (verified, all arms ran)

### web-citations (demoKind web_grounding) -> claude-ahead

The grounding-fidelity thesis (already shipped for user docs, PDFs, and RAG chunks) extended to LIVE
WEB sources. Claude's web_search returns each claim with a `web_search_result_location` carrying the
verbatim `cited_text` (up to 150 chars of the source), free of tokens. The competitors cite a URL but
their offsets index the model's own answer, with no source quote.

| arm | answered | web citations | with a verbatim source quote |
|---|:---:|:---:|:---:|
| Claude Sonnet 4.6, web_search | 3/3 | 9 | 9 |
| OpenAI GPT-5.5, web_search | 3/3 | 3 | 0 |
| Gemini 3.1 Pro, Google Search | 3/3 | 6 | 0 |

All three cited URLs, only Claude returned the verbatim source quote, on every citation. Edge bundle:
`edges/web-citations/`. Live receipt: `make web-citations` ($0.30). A subfeature note worth keeping:
the dynamic-filtering web tags route web content through code execution, which trades the citation for
pre-context token filtering, so this edge uses the basic web_search tag where the citation is returned
directly. Two axes of the same tool, two different wins (fidelity here, cost-filtering held separately).

## Mined and settled (not promotable, recorded for honesty)

### MCP connector + agentic loop -> PARITY

OpenAI's Responses MCP matches every Claude MCP-connector subfeature (server-side client, OAuth,
`allowed_tools` filtering, `defer_loading`) and LEADS on two (granular `require_approval` approvals, a
managed connector catalog, documented non-storage of the auth token). The one composition that could
have been Claude-only, keeping a bulky MCP tool result out of context via PTC, is explicitly killed by
the docs: MCP-connector tools cannot be called programmatically. Gemini has no server-side remote MCP
("coming soon"), but that is parity per best-to-best because OpenAI ships it. Do not pitch MCP.

### usage.iterations[] mixed-rate cost attribution + cache_creation TTL-write split -> real-candidate (observability), held

Claude's usage object resolves spend the competitors blend: `usage.iterations[]` reports per
sub-inference tokens at each model's own billing rate inside one server-side response (the advisor and
server tools), and `cache_creation` splits cache-write tokens into `ephemeral_5m_input_tokens` vs
`ephemeral_1h_input_tokens`. OpenAI and Gemini report aggregate-only usage inside one response. This is
genuine but narrow (it only bites with Claude's server-side fan-out, like the advisor, which is itself
held) and overlaps the shipped cache-diagnostics observability edge. Held as a candidate, not pitched.

### token-counting endpoint -> PARITY

OpenAI now ships `POST /v1/responses/input_tokens` (server-side, counts tools and files), matching
Claude's `count_tokens` and Gemini's `countTokens`. The only unmatched sliver (free + separate
rate-limit pool) is documented for Claude but unknown for OpenAI, so it cannot be claimed. Not an edge.

### prompt caching (mixed-TTL multi-breakpoint) -> needs-live-check, leans parity

Claude's developer-controlled 4 breakpoints + mixed 5m/1h TTL lead OpenAI's automatic-only caching but
roughly tie Gemini's explicit cache objects, and caching was already ruled parity. Would need a
measured layered-prompt dollar win to reopen. Not pursued this round.

## What stands after this iteration

New edge shipped: web-citations (claude-ahead). The verified Claude-ahead edge set is now
programmatic-tool-calling, citations, pdf-citations, search-results, grounding-stack, web-citations,
exact-list-ledger, cache-diagnostics, task-budgets, bulk-extended-output. Held with reason:
advisor_tool, the token/cost stack (response_inclusion SDK-ahead), the usage-iterations observability
candidate. Settled parity this round: MCP connector, token counting.

## Sources (fetched 2026-06-19)

- Claude web search tool: https://platform.claude.com/docs/en/agents-and-tools/tool-use/web-search-tool
- Claude MCP connector: https://platform.claude.com/docs/en/agents-and-tools/mcp-connector
- Claude advisor tool (usage.iterations): https://platform.claude.com/docs/en/agents-and-tools/tool-use/advisor-tool
- Claude prompt caching: https://platform.claude.com/docs/en/build-with-claude/prompt-caching
- Claude token counting: https://platform.claude.com/docs/en/build-with-claude/token-counting
- OpenAI web search: https://developers.openai.com/api/docs/guides/tools-web-search
- OpenAI MCP connectors: https://developers.openai.com/api/docs/guides/tools-connectors-mcp
- OpenAI token counting: https://developers.openai.com/api/docs/guides/token-counting
- Gemini Google Search: https://ai.google.dev/gemini-api/docs/google-search
- Gemini file search: https://ai.google.dev/gemini-api/docs/file-search
