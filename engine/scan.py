"""scan: the verified competitive picture, the seed and fallback layer of the engine.

Holds what the 2026-06-17 audit found after a skeptic refuted every claim and a live competitor
parity check dropped anything OpenAI or Google already matches: what is genuinely Claude-ahead, what
is parity or refuted, and where Claude is behind. Competitors are named here because it is sourced,
dated evidence. Founder-facing text anonymizes them.

These constants are now the committed SEED and FALLBACK, not the live source of truth. The live
fetch-diff-rank loop in engine/sweep_edges.py (run with `make edges`) overwrites
landscape/landscape.json every run, and current_edges() below reads that landscape when it is
present, falling back to these constants on a fresh checkout that has not swept yet. The surface
moves monthly, so re-run the sweep, do not cache a winner.

Sources: the 2026-06-17 whole-platform capability sweep and the agentic and long-horizon
leaderboards, kept in the internal both-directions analysis.
"""

from __future__ import annotations

import json
import pathlib

from engine.demokinds import demokind_for, is_seeded

# Survived the skeptic AND the competitor-parity check as genuinely Claude-ahead, ranked by
# value to a founder times how clearly Claude leads.
#
# Each seed carries a demoKind (which Demonstrator proves it) and a fair_comparison (the honest spec
# that demonstrator consumes), so a fresh checkout routes through the typed dispatcher exactly the way
# a swept landscape does. The sweep's normalize() stamps the same two fields onto every live edge.
DIFFERENTIATORS = [
    {
        "key": "programmatic-tool-calling", "axis": "cost", "rank": 1,
        "demoKind": "token_accounting",
        "claim": "The model writes one sandbox script that calls the developer's own tools in a loop "
                 "and keeps the bulky tool outputs out of the model context.",
        "why": "No named OpenAI or Google equivalent keeps a developer's own custom-tool OUTPUTS out "
               "of context (allowed_callers). OpenAI ships a code interpreter and tool search but not "
               "this, an absence-of-evidence lead. GA, no beta header (2026-06-18). Measured (make "
               "programmatic-tool-calling): on a 240-row fan-out task billed input fell from 9,451 to 6,828 tokens, about "
               "28% (Anthropic's own doc reports about 24%), and the sandbox code answered correctly "
               "where the in-context model failed. Fan-out-shaped (sequential tasks flat to +8%), it "
               "adds round-trips, and it is not on Bedrock or Vertex and not ZDR-eligible.",
        "fair_comparison": {
            "task_shape": "fan-out, 4 regions x ~60 rows",
            "claude_config": {"feature": "allowed_callers", "beta_on": True, "model": "sonnet"},
            "competitor_arms": [{"vendor": "openai", "surface": "code_interpreter", "best_config": True},
                                {"vendor": "gemini", "surface": "code_execution", "best_config": True}],
            "isolate": "only programmatic-tool-calling toggled; memory and prompt held constant",
            "score_gate": "answers_match AND mode_b_input < mode_a_input",
            "lead_basis": "absence-of-evidence",
            "maturity": {"claude": "ga", "beta_header": None, "fetched_date": "2026-06-18"},
            "repro": {"command": "make programmatic-tool-calling", "est_cost_usd": 0.08, "est_time_s": 90},
        },
    },
    {
        "key": "citations", "axis": "grounding", "rank": 2,
        "demoKind": "grounding_resolution",
        "claim": "Native, in-request source citations with no hosted vector store: one call cites a "
                 "directly-supplied PDF (page span) plus developer-supplied RAG chunks plus inline text, "
                 "the verbatim cited_text free of output tokens, zero persisted objects. OpenAI "
                 "(file_citation) and Gemini (File Search) cite only through a persisted, pre-indexed "
                 "store and cannot cite a directly-supplied inline PDF.",
        "why": "The wedge is convenience and the no-store bundle, NOT a correctness guarantee over a "
               "competent do-it-yourself path. Two parts were refuted, measured both ways. char-level "
               "granularity holds only for plain text (PDFs are page-level, the same coarseness as "
               "Gemini File Search). And the resolve GUARANTEE is PARITY: the paraphrase-resolution arm "
               "tested it across three regimes (frontier gpt-5.5/gemini-3.1-pro, the cheapest tiers, and "
               "30-document scale), and a steel-manned DIY, where the model paraphrases the answer but "
               "copies a verbatim supporting quote and you resolve it with a normalized str.find, "
               "resolves as well as Claude on every tier. The paraphrase-DROP only appears against weaker "
               "competitor models that paraphrase their own quote, so it is not best-to-best. What "
               "survives best-to-best: (1) cited_text is free of output tokens and of input tokens on "
               "replay, which no competitor documents; (2) the one-request, no-hosted-store, mixed-source "
               "bundle, while OpenAI and Gemini both require a hosted vector store with upload and index, "
               "neither cites a directly-supplied inline PDF, and Gemini File Search cannot be combined "
               "with another tool in one call; (3) zero resolver code, a DX convenience. Where Claude "
               "loses: Citations and Structured Outputs return a 400 together. GA, no beta header. See "
               "docs/FINDINGS.md #8.",
        "fair_comparison": {
            "task_shape": "8 questions over 3 plain-text user documents",
            "claude_config": {"feature": "citations.enabled", "beta_on": False, "model": "haiku"},
            "competitor_arms": [{"vendor": "claude", "surface": "DIY str.find", "best_config": True},
                                {"vendor": "openai", "surface": "DIY str.find", "best_config": True},
                                {"vendor": "gemini", "surface": "DIY str.find", "best_config": True}],
            "isolate": "same documents and questions on every arm; only the resolve mechanism differs",
            "score_gate": "source[start:end]==cited_text (Citations) AND source.find(quote)!=-1 (DIY)",
            "lead_basis": "within-claude-only",
            "maturity": {"claude": "ga", "beta_header": None, "fetched_date": "2026-06-18"},
            "repro": {"command": "make citations", "est_cost_usd": 0.06, "est_time_s": 120},
        },
    },
    {
        "key": "long-horizon-autonomy", "axis": "long-horizon", "rank": 3,
        "demoKind": "long_horizon_survival",
        "claim": "Longest autonomous task horizon of any released model on the independent referee.",
        "why": "METR's 50% task time-horizon (neutral, not a vendor): the top released Claude model "
               "is the only one flagged top, about 1.9x the best non-Claude before reliability falls "
               "to 50% (Claude about 12 hr, Gemini 3.1 Pro about 6.4 hr, GPT-5.2 about 5.9 hr). This "
               "is the dimension where 'finishes long jobs' survives a skeptic on neutral data. The "
               "runnable receipt (make longhorizon) is a within-Claude context-editing reliability "
               "isolation; the LEADERSHIP anchor is METR, not context editing, which is parity with "
               "OpenAI compaction.",
        "fair_comparison": {
            "task_shape": "a chain of 8 incident reports, each about 40,000 tokens",
            "claude_config": {"feature": "context_management/clear_tool_uses", "beta_on": True, "model": "haiku"},
            "competitor_arms": [{"vendor": "claude", "surface": "editing OFF (within-Claude baseline)", "best_config": True}],
            "isolate": "only context editing toggled; memory tool and prompt identical in both arms",
            "score_gate": "editing_on finished AND correct; editing_off reached the window and failed",
            "lead_basis": "within-claude-only",
            "maturity": {"claude": "beta", "beta_header": "context-management-2025-06-27", "fetched_date": "2026-06-18"},
            "repro": {"command": "make longhorizon", "est_cost_usd": 2.0, "est_time_s": 150},
        },
    },
    {
        "key": "code-execution-state", "axis": "reliability", "rank": 4,
        "demoKind": "retention_resume",
        "claim": "The code-execution sandbox keeps its container and files across separate requests and "
                 "for 30 days, so a multi-step agent's state survives between turns and across a long idle.",
        "why": "Claude returns a reusable container id (response.container.id); pass it as container=<id> "
               "on the next call and a file written in one request is readable in the next. Measured "
               "(make code-execution-state then make code-execution-state-verify): a nonce written to /tmp/state.txt "
               "read back from the SAME container after a 31.1-minute idle. No named OpenAI or Google "
               "equivalent keeps a developer's sandbox files across a long idle: OpenAI's code_interpreter "
               "container is discarded after 20 minutes idle (documented, unrecoverable) and Gemini exposes "
               "no reusable container handle, an absence-of-evidence lead. Warm reuse is parity; the edge is "
               "durability and cross-request persistence. Code execution is beta and not ZDR-eligible.",
        "fair_comparison": {
            "task_shape": "write a nonce to /tmp/state.txt, reuse the container, re-read after a 31-min idle",
            "claude_config": {"feature": "container reuse (container.id)", "beta_on": True, "model": "sonnet"},
            "competitor_arms": [
                {"vendor": "openai", "surface": "code_interpreter", "best_config": True},
                {"vendor": "gemini", "surface": "code_execution", "best_config": True},
            ],
            "isolate": "same write-then-reread workload on each arm; only container lifetime differs",
            "score_gate": "claude reads the nonce back from the reused container after the documented idle",
            "lead_basis": "absence-of-evidence",
            "maturity": {"claude": "beta", "beta_header": "code-execution-2025-08-25", "fetched_date": "2026-06-19"},
            "repro": {"command": "make code-execution-state", "est_cost_usd": 0.05, "est_time_s": 60},
        },
    },
    {
        "key": "pdf-citations", "axis": "grounding", "rank": 5,
        "demoKind": "pdf_grounding",
        "claim": 'For a PDF supplied directly in the request (base64 document block), Claude Citations returns a verifiable page_location pointer (start/end page, 1-indexed) plus the cited_text quote, free of output tokens and with no beta header. On a 5-page agreement PDF with 5 questions, Claude answered 5/5 and the page pointer resolved to the correct page 5/5.',
        "why": 'Head-to-head receipt (edges/pdf-citations/receipt.json, 2026-06-19, total $0.084408): claude:haiku answered 5/5, cited 5/5, page_correct 5/5 at $0.0458. openai:gpt-5.4 (Responses input_file, direct PDF) answered 5/5 but cited 0/5 (file citations require the hosted file_search vector store, a different persisted path). gemini:gemini-3.5-flash (inline PDF) answered 5/5 but cited 0/5 (page citations require file_search_store). So on the direct-PDF path Claude is the only one of the three returning a verifiable per-page pointer with the quote; competitor citation is absent, not merely weaker. Conflict to note: Citations + Structured Outputs return a 400 together (live doc warning).',
        "fair_comparison": {'task_shape': '5 questions over a 5-page synthetic SaaS Pro Plan agreement PDF supplied directly in the request (not uploaded to a hosted vector store); the gate is a verifiable per-page pointer into that PDF, checked against the known answer page; same PDF, same questions, same one-sentence-and-cite instruction on every arm.', 'claude_config': {'feature': 'Citations on an inline base64 PDF document block (page_location)', 'beta_on': False, 'model': 'claude-haiku-4-5-20251001'}, 'competitor_arms': ['openai:gpt-5.4 (Responses input_file, directly-supplied PDF, no vector store)', 'gemini:gemini-3.5-flash (inline PDF part, no file_search_store)'], 'isolate': 'only the platform differs; identical PDF, questions, and instruction across arms; competitors scored on whether the DIRECT-PDF path returns any pointer, since a hosted vector store is a separate persisted flow named in the sources', 'score_gate': 'Claude answered all and every pointer resolved to the exact expected page; no competitor returned any pointer into the directly-supplied PDF; every arm ran cleanly', 'lead_basis': 'head-to-head', 'maturity': {'claude': 'GA', 'beta_header': None, 'fetched_date': '2026-06-19'}, 'repro': {'command': 'make pdf-citations', 'est_cost_usd': 0.084408, 'est_time_s': 40}},
    },
    {
        "key": "search-results", "axis": "grounding", "rank": 6,
        "demoKind": "byo_rag_grounding",
        "claim": 'For developer-supplied RAG chunks passed inline as search_result blocks, Claude returns a search_result_location block-span pointer with zero hosted objects, while OpenAI and Gemini require a hosted file-search store and return a coarser file-level or chunk-level pointer for their closest citation path.',
        "why": "Verified live 2026-06-19 (receipt total $0.052453, edges/search-results/receipt.json). All three vendors cited the correct source chunk 5/5, so this is not an absence-of-evidence lead. Claude's lead is the citation mechanism plus the absence of a persisted store: claude:haiku cited inline with a block-span pointer and 0 hosted objects for $0.0067; openai:gpt-mid needed 11 hosted setup calls and 6 persisted objects, returning a file-level pointer ($0.0301); gemini:gem-flash needed 6 setup calls and 6 persisted objects, returning a chunk-level pointer ($0.0156). The competitor arms create and delete real vector stores, so the comparison is best-to-best on the cite-your-own-chunks subfeature. No beta header required (doc cURL uses only anthropic-version: 2023-06-01).",
        "fair_comparison": {'task_shape': '5 questions over 5 developer-supplied RAG chunks; the gate is a citation that resolves to the correct source chunk and the count of hosted-store setup calls and persisted objects required to get it', 'claude_config': {'feature': 'search_result content blocks with citations enabled (search_result_location)', 'beta_on': False, 'model': 'claude-haiku-4-5-20251001'}, 'competitor_arms': ['openai:gpt-5.4 file_search over a real hosted vector_store', 'gemini:gemini-3.5-flash file_search over a real hosted file_search_store'], 'isolate': 'same chunks, same questions, same cite instruction on every arm; only the platform and its citation mechanism differ', 'score_gate': 'Claude answered 5/5 and cited 5/5 inline with block-span and 0 hosted objects; every competitor needed a hosted store (setup_calls>0, persisted_objects>0) and returned a coarser pointer', 'lead_basis': 'head-to-head', 'maturity': {'claude': 'GA', 'beta_header': 'none', 'fetched_date': '2026-06-19'}, 'repro': {'command': 'make search-results', 'est_cost_usd': 0.06, 'est_time_s': 120}},
    },
    {
        "key": "grounding-stack", "axis": "grounding", "rank": 7,
        "demoKind": "grounding_stack",
        "claim": 'In one client.messages.create request, Claude cites a plain-text document (char_location), a directly-supplied base64 PDF (page_location), and a developer-supplied search_result chunk (search_result_location), returning the correct typed pointer for each source with zero hosted vector-store objects. Measured 2026-06-19 on Claude Haiku 4.5: 3/3 sources cited in one request, $0.0101.',
        "why": 'Receipt edges/grounding-stack/receipt.json (total_cost $0.021635) shows claude:haiku 3/3 source types cited in one request (char_location+page_location+search_result_location), 0 persisted objects, $0.010121. OpenAI gpt-5.4 and Gemini 3.5-flash both answered 3/3 but returned 0/3 inline pointers on the same one-request mixed-source path: their only citation path is a hosted file-search vector store (persisted, pre-indexed), measured separately in the search-results edge. The combination of three single-source citation wins (char/page/search_result) stacked into one request is the wedge; competitors cannot assemble the equivalent grounded answer inline in one call. Live smoke 2026-06-19 reproduced 3/3 answered + all three pointer kinds for $0.003246.',
        "fair_comparison": {'task_shape': 'one request carrying three mixed inline sources (a plain-text document, a directly-supplied base64 PDF, and a developer-supplied search_result chunk) plus a three-part question, one fact unique to each source; gate counts how many sources return a citation that resolves to that exact source and how many hosted-store objects were required', 'claude_config': {'feature': 'Citations (char_location + page_location + search_result_location in one response)', 'beta_on': False, 'model': 'claude-haiku-4-5-20251001'}, 'competitor_arms': ['openai:gpt-5.4 (Responses API, input_file PDF + input_text inline, no vector store)', 'gemini:gemini-3.5-flash (inline PDF part + inline text, no file_search_store)'], 'isolate': 'same three inline sources, same question, one request on every arm; only the platform citation mechanism differs, so the per-source pointer count is attributable', 'score_gate': 'claude answered==3 AND sources_cited==3 AND pointer_kinds=={char_location,page_location,search_result_location} AND persisted_objects==0; competitors answered==3 AND sources_cited==0', 'lead_basis': 'head-to-head', 'maturity': {'claude': 'GA', 'beta_header': 'none required (Citations and search_result blocks are GA, verified 2026-06-19)', 'fetched_date': '2026-06-19'}, 'repro': {'command': 'make grounding_stack', 'est_cost_usd': 0.0101, 'est_time_s': 40}},
    },
    {
        "key": "web-citations", "axis": "grounding", "rank": 8,
        "demoKind": "web_grounding",
        "claim": "Claude's web_search returns each web-grounded claim as a web_search_result_location citation carrying the verbatim cited_text (up to 150 chars of the source page), free of input/output tokens; the nearest competitor web-grounding objects cite a URL plus an offset into the model's own answer, with no source quote.",
        "why": "Verified live 2026-06-19 (receipt edges/web-citations/receipt.json, total $0.303544). claude:sonnet-4-6 returned 9/9 web citations with a verbatim source quote; openai:gpt-5.5 web_search returned 3 url_citation objects (start/end index into the model's OWN output, 0 with a source quote); gemini:gemini-3.1-pro-preview Google Search grounding returned 6 grounding chunks (uri+title, output-offset segments, 0 with a source quote). All three answered all 3 questions and cited URLs, so the win is citation FIDELITY (self-verifying source quote), not citation presence. Uses the basic web_search_20250305 tag where the citation object is returned directly; the dynamic-filtering tags route web content through code execution and trade the citation linkage for pre-context filtering.",
        "fair_comparison": {'task_shape': "3 web-research questions, each forced to search the live web on every vendor; the gate is how many returned citations carry a verbatim quote FROM the source page vs a bare URL plus an offset into the model's own answer", 'claude_config': {'feature': 'web_search with web_search_result_location citations (cited_text)', 'beta_on': False, 'model': 'claude-sonnet-4-6'}, 'competitor_arms': ['openai:gpt-5.5 web_search (url_citation)', 'gemini:gemini-3.1-pro-preview Google Search grounding (grounding_chunks)'], 'isolate': "the same web-research questions on every arm; only the platform's web citation mechanism differs, so the source-quote count is attributable", 'score_gate': 'claude returns web citations carrying a verbatim source quote AND every competitor cites URLs but returns zero citations with a source quote', 'lead_basis': 'head-to-head', 'maturity': {'claude': 'GA', 'beta_header': 'none', 'fetched_date': '2026-06-19'}, 'repro': {'command': 'make web_citations', 'est_cost_usd': 0.12, 'est_time_s': 60}},
    },
    {
        "key": "bulk-extended-output", "axis": "cost", "rank": 9,
        "demoKind": "extended_output",
        "claim": 'Claude emits one un-truncated deliverable above 128k output tokens in a single request via the Message Batches API with the output-300k-2026-03-24 beta header (cap 300,000), exceeding the documented single-request output ceilings of the strongest competitor frontier models.',
        "why": "Receipt edges/bulk-extended-output/receipt.json (2026-06-19): Claude Sonnet 4.6 batch+beta emitted 230,607 output tokens un-truncated (end_turn) in one request, vs GPT-5.5 documented 128,000 cap and Gemini 3.5 Flash 65,536 cap. The head-to-head live arms stopped early behaviorally (764 and 32,263 tokens), so the gate is Claude > every competitor's DOCUMENTED single-request ceiling AND > every measured output, both true. Per-token cost is parity at the 50% batch discount, so the edge is the single un-truncated turn above 128k, not the dollar figure. Beta, batch-only, not on Bedrock/Vertex/Foundry, async (minutes to over an hour).",
        "fair_comparison": {'task_shape': 'one request asking for a 3,000-entry enumerated document with a strict no-abbreviation instruction; the gate is output tokens produced in ONE request and whether it truncated', 'claude_config': {'feature': 'Message Batches API + extended output (300k max_tokens)', 'beta_on': 'output-300k-2026-03-24', 'model': 'claude-sonnet-4-6'}, 'competitor_arms': ['openai:gpt-5.5 (documented 128k output cap)', 'gemini:gemini-3.5-flash (documented 65,536 output cap)'], 'isolate': 'same prompt and same above-cap max-output setting on every arm; only the platform single-request output ceiling differs', 'score_gate': 'claude finished un-truncated AND claude output tokens > every competitor documented cap AND > every competitor measured output AND both competitor arms ran', 'lead_basis': 'head-to-head', 'maturity': {'claude': 'beta', 'beta_header': 'output-300k-2026-03-24', 'fetched_date': '2026-06-19'}, 'repro': {'command': 'make bulk_output', 'est_cost_usd': 0.2, 'est_time_s': 200}},
    },
    {
        "key": "exact-list-ledger", "axis": "cost", "rank": 10,
        "demoKind": "token_accounting",
        "claim": 'On a long-stream exact-list workload (30-report chain, each report about 20,000 tokens, the agent must report the exact sorted list of every URGENT id held in its own reasoning with no memory tool), Claude Haiku 4.5 with context editing (clear_tool_uses_20250919, keep=1, beta header context-management-2025-06-27) returns the exact list while holding peak carried context to 35,186 tokens, for $0.6700 and 60.7s.',
        "why": 'All three frontier arms returned the exact list on the headline run (receipt edges/exact-list-ledger/receipt.json, 2026-06-19), so the edge is NOT exclusivity. The win is cost and wall-clock time at equal correctness: Claude $0.6700/60.7s vs OpenAI gpt-5.5 compaction $1.8425/164.3s (about 64% cheaper, 63% faster) vs Gemini 3.1 Pro full context $2.5690/201.0s (about 74% cheaper, 70% faster). A 5-run repeat confirmed 5/5 exact on both server-side-managed arms (Claude and OpenAI), so correctness is not a fluke. The cost margin is config-sensitive: about 65% cheaper at keep=1, about 8% at keep=3. promotable_edge=true in the receipt.',
        "fair_comparison": {'task_shape': 'Long-stream chain agent: 30 incident reports, each about 20,000 tokens, read one at a time through a read_document tool (each report names the next, shuffled order so no batching), agent must output the exact sorted list of every URGENT id held in its own running notes, no memory tool, max_turns 44.', 'claude_config': {'feature': 'context editing (clear_tool_uses_20250919, trigger input_tokens 45000, keep tool_uses 1)', 'beta_on': True, 'model': 'claude-haiku-4-5-20251001'}, 'competitor_arms': ['OpenAI gpt-5.5 with Responses compaction (compact_threshold 45000)', 'Gemini gemini-3.1-pro-preview with full context window'], 'isolate': "Same deterministic seeded corpus (CHAIN_SEED 42), same exact-list prompt, same agent strategy on every arm; only each platform's context-management mechanism differs, so the cost and time delta is attributable to it. Prompt caching on for the Claude arm; OpenAI caching automatic; Gemini implicit caching, none disabled.", 'score_gate': 'Promote only when Claude is exact AND every competitor that ran is exact AND Claude beats every exact competitor on cost AND wall-clock time (engine/ledger_compare.py verdict()).', 'lead_basis': 'head-to-head', 'maturity': {'claude': 'beta', 'beta_header': 'context-management-2025-06-27', 'fetched_date': '2026-06-19'}, 'repro': {'command': 'make ledger', 'est_cost_usd': 5, 'est_time_s': 426}},
    },
    {
        "key": "cache-diagnostics", "axis": "cost", "rank": 11,
        "demoKind": "cache_diagnostics",
        "claim": 'Claude cache diagnostics returns a typed cache_miss_reason (model/system/tools/messages) plus a cache_missed_input_tokens estimate for a silent prompt-cache prefix change, while the closest OpenAI prompt-caching and Gemini context-caching surfaces expose cache token counters but no per-request miss-reason field.',
        "why": 'Receipt edges/cache-diagnostics/receipt.json (2026-06-19): Claude matched all 4 documented variants (system_changed/tools_changed/messages_changed/model_changed); OpenAI gpt-5.5 and Gemini gemini-3.1-pro-preview both ran with cache_signal_present=true but root_cause_known=false and zero diagnostic_fields. docs_absence_check found no equivalent in OpenAI prompt-caching or Gemini caching/token-counting docs. Lead is absence-of-evidence: competitors expose counters, not a typed miss reason. Honest scope: this is an observability edge, not cheaper inference on the two-call probe.',
        "fair_comparison": {'task_shape': 'Two consecutive long cached-prefix requests where the second silently changes one prefix surface; read the per-request cache-miss diagnostic.', 'claude_config': {'feature': 'cache diagnostics (diagnostics.previous_message_id + diagnostics.cache_miss_reason)', 'beta_on': True, 'model': 'claude-haiku-4-5-20251001'}, 'competitor_arms': ['openai gpt-5.5 Responses API prompt_cache_key + prompt_cache_retention', 'gemini gemini-3.1-pro-preview context caching counters'], 'isolate': 'Only the changed prefix surface varies between the two calls; the diagnostic field is the measured output.', 'score_gate': 'promotable_edge:true requires Claude root_cause_known and all competitor cache arms ran and exposed no miss-reason field and no competitor doc shows an exact equivalent.', 'lead_basis': 'absence-of-evidence', 'maturity': {'claude': 'beta', 'beta_header': 'cache-diagnosis-2026-04-07', 'fetched_date': '2026-06-19'}, 'repro': {'command': 'make cache-diagnostics', 'est_cost_usd': 0.14, 'est_time_s': 20}},
    },
    {
        "key": "task-budgets", "axis": "reliability", "rank": 12,
        "demoKind": "task_budget",
        "claim": 'Claude task_budget gives supported models a provider-side remaining-budget countdown for the full agentic loop (thinking, tool calls, tool results, output), so the model hands off gracefully before starting a tool action it cannot finish. On a budget-sensitive 12-record audit, near-exhausted budget produced 0 tool calls and a clean handoff while the high-budget control started the loop.',
        "why": 'Verified live 2026-06-19 on claude-opus-4-8 with beta header task-budgets-2026-03-13. Receipt edges/task-budgets/receipt.json shows promotable_edge: true and a measured tool-loop workload win (claude_low_budget_tool_calls=0, claude_control_tool_calls=1). Closest competitor controls are output (max_output_tokens), reasoning (OpenAI reasoning_effort), or thinking (Gemini thinking_budget) budgets; the fetched OpenAI reasoning and Gemini thinking docs (2026-06-19) showed no full-loop provider-side remaining-budget marker (docs_absence_check equivalent_found=false on both), and both competitors started the tool loop on the same workload (openai 1, gemini 1). Lead is absence-of-evidence, not head-to-head parity-broken: competitors lack the exact full-loop countdown subfeature, they are not slower at the same thing.',
        "fair_comparison": {'task_shape': 'Single-turn agentic-loop decision with one fetch_record tool: start a 12-record audit by calling fetch_record(1) unless a hidden near-exhausted task budget says to hand off first. Same prompt across all arms; only the remaining-budget signal differs.', 'claude_config': {'feature': 'task_budget (output_config.task_budget {type:tokens,total:20000,remaining:N})', 'beta_on': 'task-budgets-2026-03-13', 'model': 'claude-opus-4-8'}, 'competitor_arms': [{'provider': 'openai', 'model': 'gpt-5.5', 'closest_control': 'reasoning_effort=low + max_output_tokens=256, Responses API'}, {'provider': 'gemini', 'model': 'gemini-3.1-pro-preview', 'closest_control': 'thinking_budget=128 + max_output_tokens=256'}], 'isolate': 'Only the remaining task budget is toggled between the Claude low-budget arm (remaining=50) and the Claude high-budget control (remaining=5000); prompt, model, tool, and effort are held constant, so the behavior change is attributable to the budget alone.', 'score_gate': 'promotable_edge requires the measured tool-loop workload win: Claude low-budget stops before the first tool call (tool_calls=0, graceful handoff), the Claude high-budget control starts the loop (tool_calls=1), and every closest competitor control also starts the loop with no full-loop marker exposed.', 'lead_basis': 'absence-of-evidence', 'maturity': {'claude': 'beta', 'beta_header': 'task-budgets-2026-03-13', 'fetched_date': '2026-06-19'}, 'repro': {'command': 'make task_budgets', 'est_cost_usd': 0.01, 'est_time_s': 8}},
    },
]

# Refuted, parity, or behind after the live check. Do NOT pitch these as a Claude lead.
PARITY = [
    {"note": "Context editing vs server-side compaction: parity. Both vendors ship GA server-side "
             "context management (Claude additionally ships beta in-place context editing), so the "
             "make-longhorizon receipt is a within-Claude reliability isolation, not a head-to-head "
             "lead. The long-horizon LEADERSHIP claim anchors on the independent METR time-horizon."},
    {"note": "Managed Agents resumability: doc-grounded parity on the capability. OpenAI ships GA "
             "durable state (Responses Conversations, Agents SDK file-backed sessions survive a "
             "process restart) and Gemini Live resumes within a 2-hour handle window, so a "
             "kill-and-resume is table stakes. The genuine win is the bundle (Anthropic-hosted or "
             "self-hosted sandbox plus agent loop plus persistent filesystem plus history plus "
             "compaction in one product, beta header managed-agents-2026-04-01) and the time axis "
             "(no 30-day TTL, no 2-hour cap). State must stay server-side, so it is not ZDR- or "
             "HIPAA-BAA-eligible. NEVER pitched as a Claude-only capability."},
    {"note": "Prompt caching, Batch, Files API, Structured Outputs, Skills, MCP: all matched."},
    {"note": "1M-token window: matched or exceeded by Gemini on raw size."},
    {"note": "Computer use, extended thinking, PDF and vision: all beta or matched."},
]

# Where Claude is behind. Feeds the product-team email.
GAPS = [
    {"note": "OpenAI is cheaper per token on the fair cost/speed benchmark (and faster)."},
    {"note": "Cache retention: Gemini arbitrary TTL, OpenAI 24h, vs Claude fixed 5m or 1h."},
    {"note": "Citations cannot be combined with Structured Outputs (the API returns a 400)."},
]

CHOSEN = (
    "The sharpest edge is programmatic tool calling: add allowed_callers to a tool and Claude writes "
    "one sandbox script that calls it in a loop and keeps the bulky outputs out of the model context. "
    "GA, no named competitor equivalent. Measured (make programmatic-tool-calling): billed input fell about 28% on a 240-row "
    "fan-out task (Anthropic's doc reports about 24%), and the code answered correctly where the "
    "in-context model failed. Fan-out-shaped, it adds round-trips, and it is not on Bedrock or Vertex "
    "or ZDR. The cleanest near-binary edge is Citations: the only GA API with a per-character source "
    "pointer into the user's own document, the verbatim quote extracted and free of output tokens "
    "(Gemini File Search is page-level and still preview, OpenAI cites its own output). The third is "
    "long-horizon autonomy: the longest task horizon on METR's independent referee, about 1.9x the next "
    "best, though our own cross-vendor long run is a tie at affordable scale. Each edge has its own "
    "folder under edges/ with its demo, receipt, and emails. Re-run the sweep, do not cache a winner."
)


# The grounded landscape correction (framework managedAgentsCorrection, live vendor docs 2026-06-18).
# These keys must NEVER carry an absence-of-evidence Claude-only lead off the sweep's deterministic
# normalizer, because the normalizer only sees that no competitor source in the registry shares the
# key, which on a stateful or context-management feature is a registry gap, not a real capability
# absence. The grounded read is parity:
#   - managed_agents / memory_tool (retention_resume): durable kill-and-resume is table stakes (OpenAI
#     Responses Conversations and Agents SDK file-backed sessions are GA, Gemini Live resumes within a
#     2-hour handle). The genuine win is the managed-harness BUNDLE and the time axis (no 30-day TTL,
#     no 2-hour cap), labeled beta (managed-agents-2026-04-01), not ZDR-eligible. Parity on capability.
#   - context_editing (long_horizon_survival): both vendors ship GA server-side compaction, so the
#     editing receipt is a within-Claude reliability isolation, and the long-horizon LEADERSHIP claim
#     anchors on the independent METR time-horizon, not context editing. Parity head-to-head.
# The sweep re-grades these keys to parity (lead 0) with the corrected lead_basis, so a manufactured
# Claude-only lead can never reach the landscape or the brief.
GROUNDING_CORRECTION = {
    "managed_agents": {"verdict": "parity", "lead_basis": "doc-grounded-parity",
                       "note": "doc-grounded parity on capability; the win is the managed bundle and "
                               "the time axis (beta managed-agents-2026-04-01), not a Claude-only "
                               "kill-and-resume. State stays server-side, so not ZDR-eligible."},
    "memory_tool": {"verdict": "parity", "lead_basis": "doc-grounded-parity",
                    "note": "client-side and hand-rollable (Codex Memories GA, Vertex Memory Bank), a "
                            "better-shaped convention, not a moat. Parity."},
    "context_editing": {"verdict": "parity", "lead_basis": "doc-grounded-parity",
                        "note": "both vendors ship GA server-side compaction; the make-longhorizon "
                                "receipt is a within-Claude reliability isolation, and long-horizon "
                                "LEADERSHIP anchors on the independent METR time-horizon, not context "
                                "editing."},
}


def apply_grounding_correction(edge: dict) -> dict:
    """Re-grade a swept edge to the grounded verdict when its key is in GROUNDING_CORRECTION. Sets the
    verdict to parity, zeroes the lead so it is never pitched, and writes the corrected lead_basis and
    note onto the edge's fair_comparison. Idempotent. The sweep calls this on every ranked edge after
    stamping, so the managedAgentsCorrection holds on the live landscape, not only in the seed prose."""
    corr = GROUNDING_CORRECTION.get(edge.get("key"))
    if not corr:
        return edge
    edge["verdict"] = corr["verdict"]
    edge["lead_score"] = 0
    edge["score"] = 0
    fc = edge.setdefault("fair_comparison", {})
    fc["lead_basis"] = corr["lead_basis"]
    fc["grounding_note"] = corr["note"]
    return edge


def _landscape_path() -> pathlib.Path:
    return pathlib.Path(__file__).resolve().parent.parent / "landscape" / "landscape.json"


# The live sweep keys a source by its short doc slug (programmatic_tool_calling, context_editing), while the seed
# DIFFERENTIATORS key by the built-edge folder name (programmatic-tool-calling, long-horizon-autonomy).
# This alias map resolves a live key to its seed so a built edge carries the vetted, measured claim
# and why, not a bare placeholder line.
_SEED_KEY_ALIAS = {
    "programmatic_tool_calling": "programmatic-tool-calling",
    "citations": "citations",
    "context_editing": "long-horizon-autonomy",
}


def _seed_for(live_key: str) -> dict | None:
    by_key = {d["key"]: d for d in DIFFERENTIATORS}
    for cand in (live_key, _SEED_KEY_ALIAS.get(live_key), live_key.replace("_", "-")):
        if cand and cand in by_key:
            return by_key[cand]
    return None


def seed_for_key(live_key: str) -> dict | None:
    """Public wrapper for the live sweep. A source is pitchable only when it maps to a vetted seed
    comparison here; broad docs, blogs, and changelogs stay discovery inputs until a receipt is built."""
    return _seed_for(live_key)


def current_edges() -> list[dict]:
    """The live ranked edges when a sweep has run, the committed seed constants otherwise.

    Reads landscape/landscape.json (written by engine/sweep_edges.py) and returns its genuine-lead
    edges (lead_score > 0) sorted high to low, mapped to the {key, axis, claim, why, rank} shape the
    rest of the engine consumes. On a fresh checkout with no sweep yet, or an unreadable landscape, it
    falls back to the committed DIFFERENTIATORS seed so verify and draft never break. Parity and
    behind cells (lead_score 0) are excluded from this leads list, the same honesty cut the sweep
    makes: they stay in the landscape but are never pitched."""
    f = _landscape_path()
    if not f.exists():
        return list(DIFFERENTIATORS)
    try:
        land = json.loads(f.read_text())
    except (json.JSONDecodeError, OSError):
        return list(DIFFERENTIATORS)
    leads = [e for e in land.get("edges", []) if e.get("lead_score", 0) > 0]
    if not leads:
        return list(DIFFERENTIATORS)
    out = []
    for i, e in enumerate(leads, 1):
        # Map the live edge to the consumer shape. Reuse the rich seed claim/why when the key matches
        # a built edge (the live extractor's evidence_quote is a heuristic line, the seed prose is the
        # vetted claim), otherwise build a plain claim/why from the live evidence so a brand-new edge
        # still flows through. The evidence_quote always carries the live grounding.
        seed = _seed_for(e["key"])
        out.append({
            "key": e["key"], "axis": e.get("axis", "unknown"), "rank": i,
            "demoKind": e.get("demoKind") or (seed.get("demoKind") if seed else None)
                        or demokind_for(e["key"], e.get("axis")),
            "fair_comparison": e.get("fair_comparison") or (seed.get("fair_comparison") if seed else None) or {},
            "claim": seed["claim"] if seed else f"{e['key']} ({e.get('verdict','claude-ahead')}).",
            "why": seed["why"] if seed else (e.get("evidence_quote") or ""),
            "verdict": e.get("verdict", "claude-ahead"), "score": e.get("score"),
            "evidence_quote": e.get("evidence_quote", ""), "source_url": e.get("source_url"),
        })
    return out


def stamp_demokind(edge: dict) -> dict:
    """Stamp demoKind + fair_comparison onto a live edge record (the sweep normalizer calls this).

    A built edge inherits the vetted seed demoKind and the seed fair_comparison spec. An unknown key
    gets a best-effort axis->demoKind guess (engine/demokinds) and a minimal fair_comparison whose
    lead_basis is held: a guessed kind is never-evaluated until a demonstrator and a parity check
    exist, the same absence-of-evidence discipline the sweep already enforces on an unverified lead. A
    per-edge demoKind already on the record always wins, so a hand-tuned value is never clobbered."""
    key, axis = edge.get("key", ""), edge.get("axis", "unknown")
    seed = _seed_for(key)
    if not edge.get("demoKind"):
        edge["demoKind"] = (seed.get("demoKind") if seed else None) or demokind_for(key, axis)
    if not edge.get("fair_comparison"):
        if seed and seed.get("fair_comparison"):
            edge["fair_comparison"] = dict(seed["fair_comparison"])
        else:
            # A genuinely new key: a minimal, honest spec. lead_basis is held until a demonstrator and
            # a parity check exist, so the edge is never pitched off a guessed demoKind.
            edge["fair_comparison"] = {
                "task_shape": "unknown until a demonstrator is built",
                "claude_config": {}, "competitor_arms": [], "isolate": "",
                "score_gate": "machine-checkable gate to be defined by the demonstrator",
                "lead_basis": "absence-of-evidence" if is_seeded(key) else "within-claude-only",
                "maturity": {"claude": edge.get("status", "unverified"),
                             "beta_header": edge.get("beta_header"),
                             "fetched_date": edge.get("fetched_date")},
                "repro": {"command": "", "est_cost_usd": 0.0, "est_time_s": 0.0},
            }
    return edge


def current_anchor() -> str:
    """The anchor text for the founder email: the CHOSEN seed paragraph when the live top edge is one
    of the three built edges (the vetted, measured prose), else a plain pointer to the live top edge.
    Keeps the drafter grounded in a measured receipt and never invents a number for a new edge."""
    edges = current_edges()
    if not edges:
        return CHOSEN
    top = edges[0]
    if _seed_for(top["key"]) is not None:
        return CHOSEN
    return (f"The newest ranked edge this run is {top['key']} on the {top['axis']} axis "
            f"({top.get('verdict','claude-ahead')}). No measured receipt is built for it yet, so this "
            f"anchor carries the live doc evidence only: {top.get('why','')}".strip())


def main():
    print("\n  Verified competitive picture, 2026-06-17 (skeptic-refuted + live parity check)\n")
    print("  Claude-ahead (survived the skeptic and the parity check), ranked:")
    for d in DIFFERENTIATORS:
        print(f"    {d['rank']}. [{d['axis']}] {d['claim']}")
        print(f"        {d['why']}")
    print("\n  Parity or refuted (do not pitch as a lead):")
    for p in PARITY:
        print(f"    = {p['note']}")
    print("\n  Where Claude is behind (the product email):")
    for g in GAPS:
        print(f"    - {g['note']}")
    print(f"\n  Anchor for the founder email:\n    {CHOSEN}")
    print("\n  Sources: the internal 2026-06-17 platform sweep and agentic-landscape analysis\n")


if __name__ == "__main__":
    main()
