# Edge vetting, 2026-06-19

This is the human vetting pass over the widened 2026-06-19 source sweep and the first live
subfeature receipts. It promotes the exact-list ledger edge, the cache diagnostics edge, the task
budgets edge, the PDF citations edge, the search results edge, and the grounding-stack edge, because
all six receipts cleared their best-to-best gates. The other candidates stay held with the parity risk
and exact proof needed to move from held to measured.

Update: the exact-list ledger workload below did clear the promotable gate. A new edge bundle now
lives at `edges/exact-list-ledger/`.

Update: the cache diagnostics workload also cleared the promotable gate. A new edge bundle now lives
at `edges/cache-diagnostics/`.

Update: the task budgets tool-loop workload cleared the promotable gate. A new edge bundle now lives
at `edges/task-budgets/`.

Update: the direct-PDF citations workload cleared the promotable gate. A new edge bundle now lives at
`edges/pdf-citations/`.

Update: the BYO RAG search-results workload cleared the promotable gate. A new edge bundle now lives
at `edges/search-results/`.

Update: the mixed-source grounding-stack workload cleared the promotable gate. A new edge bundle now
lives at `edges/grounding-stack/`.

## Promoted edge: exact-list ledger

The new workload tests a long stream where the agent must preserve a precise accumulated list while
large tool results become disposable after each step. It uses the same deterministic 30-report chain
for Claude, OpenAI, and Gemini. Each report is about 20,000 tokens. The expected answer is computed in
code: `[0, 3, 6, 9, 12, 15, 18, 21, 24, 27]`.

Live receipt: `make ledger` wrote `data/last_ledger_compare.json`, and the committed edge receipt is
`edges/exact-list-ledger/receipt.json`. Claude Haiku 4.5 with context editing, OpenAI GPT-5.5 with
Responses compaction, and Gemini 3.1 Pro Preview with full context all returned the exact list. Claude
won on the measured value axes: $0.6700 and 60.7s, compared with OpenAI at $1.8425 and 164.3s, and
Gemini at $2.5690 and 201.0s. Verdict: `positive_signal: true`, `promotable_edge: true`.

Why this can ship: it is a best-to-best head-to-head on a real long-stream exact-state workload, every
competitor arm ran, every answer was exact, and Claude still won on cost and time. The claim is scoped:
Claude is not the only platform that solved it. Claude is the cheaper and faster exact run on this
workload.

Primary sources:
- Claude context editing: https://platform.claude.com/docs/en/build-with-claude/context-editing
- OpenAI compaction: https://developers.openai.com/api/docs/guides/compaction
- Gemini long context: https://ai.google.dev/gemini-api/docs/long-context

## Promoted edge: cache diagnostics

The new workload tests a silent prompt-cache break. It sends two long cached-prefix requests and
changes only the system prefix on the second request, the same bug shape as timestamps in system
prompts, routing metadata, or non-deterministic schema serialization. The expected root cause is
`system_changed`.

Live receipt: `make cache-diagnostics` wrote `data/last_cache_diagnostics.json`, and the committed
edge receipt is `edges/cache-diagnostics/receipt.json`. Claude Haiku 4.5 with cache diagnostics
identified 4/4 documented cache-miss reason variants: `system_changed`, `tools_changed`,
`messages_changed`, and `model_changed`. In the primary changed-system case it returned
`diagnostics.cache_miss_reason.type: system_changed` and estimated 6,827 missed input tokens. OpenAI
GPT-5.5 prompt caching ran its closest cache surface and exposed cache token counters, but no
miss-reason field. Gemini 3.1 Pro Preview also ran its closest cache counter surface and exposed no
miss-reason field. Claude cost $0.0694 and took 12.7s, OpenAI cost $0.0515 and took 2.7s, and Gemini
cost $0.0242 and took 3.5s. Verdict: `positive_signal: true`, `promotable_edge: true`.

Why this can ship: it is a best-to-best observability comparison on a real cache debugging workload.
The claim is scoped: Claude is not the only platform with prompt or context caching. Claude is the one
that named the cache-break root cause on this workload, covering all four documented root-cause types
and reducing the manual suspect list from four prompt-prefix surfaces to one.

Primary sources:
- Claude cache diagnostics: https://platform.claude.com/docs/en/build-with-claude/cache-diagnostics
- OpenAI prompt caching: https://developers.openai.com/api/docs/guides/prompt-caching
- Gemini context caching: https://ai.google.dev/gemini-api/docs/caching

## Promoted edge: PDF citations

The new workload tests the direct-upload PDF path. A five-page synthetic agreement PDF is supplied
directly in the request. The model answers five questions, one fact per page, and the gate checks
whether the response returns a citation pointer into the supplied PDF that resolves to the expected
page.

Live receipt: `make pdf-citations` wrote `data/last_pdf_citations.json`, and the committed edge
receipt is `edges/pdf-citations/receipt.json`. Claude Haiku 4.5 with Citations answered 5/5,
returned a direct-PDF citation pointer for 5/5, and resolved to the correct page for 5/5. OpenAI
GPT-5.4 with direct `input_file` answered 5/5 but returned 0/5 direct-PDF pointers. Gemini 3.5 Flash
with inline PDF also answered 5/5 but returned 0/5 direct-PDF pointers. Claude cost $0.0458 and took
6.2s, OpenAI cost $0.0064 and took 15.9s, and Gemini cost $0.0322 and took 14.1s. Verdict:
`positive_signal: true`, `promotable_edge: true`.

Why this can ship: it is a best-to-best grounding comparison on the same directly supplied PDF. The
claim is scoped: Claude is not the only platform that can answer questions over PDFs, and OpenAI and
Gemini both have hosted file-search or vector-store paths. Claude is the one that returned a
correct-page citation pointer on the direct-PDF path in this workload.

Primary sources:
- Claude citations: https://platform.claude.com/docs/en/build-with-claude/citations
- Claude PDF support: https://platform.claude.com/docs/en/build-with-claude/pdf-support
- OpenAI file inputs: https://developers.openai.com/api/docs/guides/file-inputs
- OpenAI file search: https://developers.openai.com/api/docs/guides/tools-file-search
- Gemini document processing: https://ai.google.dev/gemini-api/docs/document-processing
- Gemini file search: https://ai.google.dev/gemini-api/docs/file-search

## Promoted edge: search results

The new workload tests the bring-your-own-RAG path. Five developer-supplied chunks are passed
directly in the request as `search_result` content blocks. The model answers five questions, one fact
per chunk, and the gate checks whether the response returns a citation pointer that resolves to the
correct source chunk without creating a hosted search store.

Live receipt: `make search-results` wrote `data/last_search_results.json`, and the committed edge
receipt is `edges/search-results/receipt.json`. Claude Haiku 4.5 with Search Results answered 5/5,
returned 5/5 correct source citations, used a `block-span` pointer, and created 0 hosted objects.
OpenAI GPT-5.4 with hosted file search answered 5/5 and cited 5/5, but used a file-level pointer and
created 6 persisted objects. Gemini 3.5 Flash with hosted file search answered 5/5 and cited 5/5, but
used a chunk-level pointer and created 6 persisted objects. Claude cost $0.0067 and took 4.5s,
OpenAI cost $0.0301 and took 19.8s, and Gemini cost $0.0156 and took 26.5s. Verdict:
`positive_signal: true`, `promotable_edge: true`.

Why this can ship: it is a best-to-best grounding comparison for citing chunks the developer already
retrieved. The claim is scoped: Claude is not the only platform that can cite the correct source.
Claude is the one that returned an inline block-span citation into developer-supplied chunks with no
hosted store, upload, indexing step, or persisted third-party copy on this workload.

Primary sources:
- Claude search results: https://platform.claude.com/docs/en/build-with-claude/search-results
- Claude citations: https://platform.claude.com/docs/en/build-with-claude/citations
- OpenAI file search: https://developers.openai.com/api/docs/guides/tools-file-search
- Gemini file search: https://ai.google.dev/gemini-api/docs/file-search

## Promoted edge: grounding stack

The new workload tests a combination, not a single feature label. One request carries three inline
source types: a plain-text document, a directly supplied PDF, and a developer-supplied `search_result`
chunk. The question asks for one fact unique to each source. The gate checks whether the response
returns typed pointers into all three supplied sources in the same request.

Live receipt: `make grounding-stack` wrote `data/last_grounding_stack.json`, and the committed edge
receipt is `edges/grounding-stack/receipt.json`. Claude Haiku 4.5 answered 3/3, returned 3/3 inline
source-type pointers in one response, and created 0 hosted objects. The pointer kinds were
`char_location`, `page_location`, and `search_result_location`. OpenAI GPT-5.4 and Gemini 3.5 Flash
both answered 3/3 on the same inline inputs but returned 0/3 inline-source pointers. Claude cost
$0.0101 and took 2.3s, OpenAI cost $0.0028 and took 4.4s, and Gemini cost $0.0087 and took 3.9s.
Verdict: `positive_signal: true`, `promotable_edge: true`.

Why this can ship: it is a best-to-best one-request inline mixed-source grounding comparison. The
claim is scoped: Claude is not the only platform that can answer over mixed content, and hosted
file-search paths are measured separately. Claude is the one that returned typed pointers into the
plain text, direct PDF, and developer-supplied RAG chunk in one response without a hosted store.

Primary sources:
- Claude citations: https://platform.claude.com/docs/en/build-with-claude/citations
- Claude search results: https://platform.claude.com/docs/en/build-with-claude/search-results
- Claude PDF support: https://platform.claude.com/docs/en/build-with-claude/pdf-support
- OpenAI file search: https://developers.openai.com/api/docs/guides/tools-file-search
- Gemini file search: https://ai.google.dev/gemini-api/docs/file-search

## Best new candidate: dynamic web filtering

Claude web search and web fetch now expose a sharper subfeature than the mechanical key-level scan can
see. The current Claude docs say `web_search_20260318` and `web_fetch_20260318` can use code execution
to filter search or fetched page content before that content reaches the context window. The same pages
also describe `response_inclusion: "excluded"` for result blocks that were already consumed by a
completed code execution call.

Why this may be an edge: OpenAI documents web search controls such as filters, sources, live-access
control, and `return_token_budget`. Gemini documents Google Search and URL context. In the fetched docs,
neither competitor page states the same pre-context code-filtering mechanism plus consumed-result
exclusion. That is not proof yet. It is enough to make this the first candidate to test.

Proof to build: a multi-entity research task with many irrelevant hits or long pages. Run Claude dynamic
filtering, Claude basic search or fetch, OpenAI Responses web search, and Gemini Google Search or URL
context. Score answer correctness, citation fidelity, search or fetch result tokens carried forward,
and output tokens returned to the client.

Live receipt: `make dynamic-web` wrote `data/last_dynamic_web_filtering.json`. Claude Sonnet 4.6
exercised dynamic filtering with `web_search_20260209` called from code execution, answered correctly,
and grounded the answer in official Anthropic docs. The latest run used 17,267 Claude tokens in 17.7s.
OpenAI GPT-5.5 also answered correctly with grounding through its closest web-search control, using
15,069 tokens in 9.8s. Gemini 3.1 Pro Preview ran but did not produce a grounded correct answer,
using 629 tokens in 7.7s. Verdict: `positive_signal: true`, `promotable_edge: false`.

Discrepancy resolved for the current key/runtime: PyPI shows `anthropic 0.111.0` as the latest public
Python SDK, and the project `.venv` is on that version. The generated SDK schema still has
`web_search_20260209` and `web_fetch_20260309`, but no `web_search_20260318`,
`web_fetch_20260318`, or `response_inclusion`. Raw HTTP directly against `/v1/messages` also rejects
the docs-new tags, so this is not just SDK-side validation. Plausible beta-header names tested so far
were rejected as unexpected. Treat the state as docs ahead of the current public SDK/server surface
for this key, not as a Claude win.

Why held: the newer `web_search_20260318` and `response_inclusion` shape is documented but not live for
the API/key used here. Dynamic filtering is live through `web_search_20260209` and `web_fetch_20260309`,
but response inclusion must not be pitched until a live receipt shows SDK schema support and raw API
acceptance. Also, Claude did not beat every grounded correct competitor on total tokens because OpenAI
was grounded and correct on the lookup. Do not generate a public edge yet.

Primary sources:
- Claude web search: https://platform.claude.com/docs/en/agents-and-tools/tool-use/web-search-tool
- Claude web fetch: https://platform.claude.com/docs/en/agents-and-tools/tool-use/web-fetch-tool
- OpenAI web search: https://developers.openai.com/api/docs/guides/tools-web-search
- Gemini tools: https://ai.google.dev/gemini-api/docs/tools

## Promoted edge: task budgets

Claude `task_budget` is scoped to the full agentic loop, including thinking, tool calls, tool
results, and output. The docs position it as a way for Claude to self-regulate long agentic tasks
and finish gracefully near a budget.

Parity risk checked: OpenAI has `max_output_tokens` and reasoning effort. Gemini has thinking levels
and thinking budgets. Those are adjacent controls, but the fetched docs did not show an exact
provider-side full-loop remaining-budget marker covering thinking, tool calls, tool results, and
output.

The promoted workload tests a fixed tool loop at the first dangerous moment: a 12-record audit is
about to begin by calling `fetch_record(1)`. The low-budget run should hand off before making that
external tool call. The high-budget Claude control, OpenAI closest controls, and Gemini closest
controls should start the tool loop.

Live receipt: `make task-budget` wrote `data/last_task_budgets.json`. Claude Opus 4.8 accepted
`task_budget` with the `task-budgets-2026-03-13` beta header and, with `remaining: 50`, returned a
clean handoff at `stop_reason=end_turn`. On the tool-loop workload, Claude with low remaining budget
made 0 tool calls and handed off in 1.6s. The high-budget Claude control made 1 tool call in 3.0s.
OpenAI GPT-5.5 with low reasoning effort and `max_output_tokens` made 1 tool call in 2.1s. Gemini
3.1 Pro Preview with `thinking_budget: 128` made 1 tool call in 3.3s. Verdict:
`positive_signal: true`, `promotable_edge: true`.

Why this can ship: it is a best-to-best control comparison on an agent handoff workload. The claim is
scoped: Claude is not the only platform with budget-like controls. Claude is the one that exposed a
hidden full-loop low-budget marker to the model and stopped before an external tool action that the
closest competitor controls started.

Primary sources:
- Claude task budgets: https://platform.claude.com/docs/en/build-with-claude/task-budgets
- OpenAI reasoning controls: https://developers.openai.com/api/docs/guides/reasoning
- Gemini thinking budgets: https://ai.google.dev/gemini-api/docs/thinking

## Held or likely parity

`fallback_credit` remains interesting, but it depends on a refused Fable or Mythos request. The live
access probe in `briefs/2026-06-19-access-gate-probes.json` checked both `claude-fable-5` and
`claude-mythos-5` with the fallback-credit beta header. Both returned `NotFoundError` and pointed to
the Anthropic Fable/Mythos access-suspension source. Treat it as blocked until Fable or Mythos access
is restored.

`fast_mode` is a speed candidate, not a clean product edge yet. `make fast-mode` wrote
`data/last_fast_mode.json`: standard Opus 4.8 ran, but the documented fast-mode request with
`speed: "fast"` and `fast-mode-2026-02-01` returned `RateLimitError` because this org currently has 0
fast-mode input tokens per minute. Treat it as blocked until the key has fast-mode capacity, then
compare price, quality, and wall clock against OpenAI priority processing and Gemini priority
inference. OpenAI and Gemini both document adjacent priority paths, so same-model Claude speedup is
not enough by itself to promote a public edge.

`advisor_tool` now has a live full-run receipt and remains held. `make advisor` wrote
`data/last_advisor.json` with every arm run on the same 8-task execution-graded coding slice. The
Sonnet 4.6 executor plus Opus 4.8 advisor arm used the advisor once per problem and scored 8/8
overall, 4/4 held-out, but cost $0.3237 total and $0.0405 per solved task. Opus 4.8 solo also scored
8/8 and cost $0.0572 total. OpenAI GPT-5.5, Gemini 3.1 Pro, OpenAI GPT-5.4 mini, and Gemini 3.5 Flash
also scored 8/8, with cost per solved task of $0.0129, $0.0266, $0.0008, and $0.0180 respectively.
Verdict: `positive_signal: false`, `promotable_edge: false`. The next advisor workload must be harder
and must show a quality lift that beats Opus solo and every same-quality competitor arm on cost per
solved task before any public edge bundle is generated.

`effort` and `adaptive_thinking` are likely parity. OpenAI and Gemini both document reasoning or
thinking controls.

`token_counting` is parity. OpenAI and Gemini both document token counting.

`batch_processing`, `tool_search`, `MCP connector`, `files`, `structured_outputs`, and `computer_use`
remain parity or behind in the current landscape. Do not pitch them as Claude-ahead without a new
subfeature-level claim.

## Action

Build the next demonstrators around the subfeatures, not the high-level feature names:

- For `web_search_tool` and `web_fetch_tool`, test pre-context code filtering and consumed-result
  exclusion on noisy research pages, then measure answer quality, citation fidelity, and carried or
  returned tokens.

Until those value proofs exist, the remaining candidates stay in the held/parity-gated state and out
of any founder email or public edge bundle.
