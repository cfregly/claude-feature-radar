# The competitive-gap engine. Each target runs in one command.
DEEP_BUDGET_USD ?= 2.00
DEEP_BUDGET_LABEL ?= grind-deep
DEEP_EFFORT ?= xhigh
VERIFY_JUDGES ?= claude,openai
.PHONY: setup compare-deps mcp-deps mcp app app-check programmatic-tool-calling ptc-cache-context citations citations-quick citations-paraphrase cite demo demo-quick demo-full longhorizon longhorizon-smoke longhorizon-compare ledger ledger-smoke compare alert edges cadence grind grind-deep combine coverage managed parity-gated dynamic-web task-budget cache-diagnostics fast-mode pdf-citations search-results grounding-stack web-citations bulk-output advisor code-execution-state code-execution-state-verify scan verify verify-live eval eval-smoke eval-judge retention retention-live cost security-posture security draft publish-brief publish-misses check-claims check-docs core-imports check-surface check-split check-receipts test ci deslop gif clean

PY := .venv/bin/python

setup: ## create the venv and install the one dependency
	python3 -m venv .venv
	$(PY) -m pip install --quiet --upgrade pip
	$(PY) -m pip install --quiet -r requirements.txt
	@echo "Setup done. Now: cp .env.example .env and paste your ANTHROPIC_API_KEY."

compare-deps: ## install the OpenAI + Gemini SDKs into the SAME venv, for compare/sweep
	$(PY) -m pip install --quiet -r requirements-compare.txt
	@echo "Compare deps installed into .venv. Now paste OPENAI_API_KEY and GEMINI_API_KEY into .env."

mcp-deps: ## install the optional MCP Python SDK into the SAME venv, for the chat-window server (make mcp)
	$(PY) -m pip install --quiet -r requirements-mcp.txt
	@echo "MCP SDK installed into .venv. Now: make mcp (or register the server in Claude Code/Desktop, see the README)."

mcp: ## MCP SERVER (stdio): drive the engine from a chat window. Read tools + the $0 discovery loop run free; publish and benchmark are ASK and refuse without confirm. Needs make mcp-deps once.
	$(PY) -m engine.mcp_server

app: ## FORKABLE APP: run the fan-out task over your own tool (app/my_tool.py), print your before-and-after token bill (needs ANTHROPIC_API_KEY, about $0.08)
	$(PY) -m app.run_tokens

app-check: ## the app self-test: run the shipped example and assert the PTC invariant (Mode B bills fewer input tokens AND answers correctly) before you trust it on your own tool (about $0.08)
	$(PY) -m app.run_tokens --check

programmatic-tool-calling: ## EDGE: programmatic tool calling, the input-token receipt on a fan-out task (needs ANTHROPIC_API_KEY, about $0.08)
	$(PY) edges/programmatic-tool-calling/demo.py

ptc-cache-context: ## EDGE MODEL: PTC + cache + 1M-context cost cliff over verified prices (NO API call, $0)
	$(PY) run.py ptc-cache-context

citations: ## EDGE: Claude Citations, a verifiable per-character source pointer into your user's own documents, one Claude arm (needs ANTHROPIC_API_KEY, $0.01)
	$(PY) edges/citations/demo.py

citations-quick: ## a 3-question, cents-scale smoke of the citations edge
	$(PY) edges/citations/demo.py --quick

citations-paraphrase: ## EDGE: Claude inline citations vs OpenAI file_search vs Gemini File Search over a user's own documents, feature vs feature (needs 3 keys, about $0.15)
	$(PY) run.py citations-paraphrase --emit-edge

pdf-citations: ## EDGE: page citations into a directly supplied PDF, Claude vs direct PDF/file inputs (needs 3 keys, cents)
	$(PY) run.py pdf-citations --emit-edge

search-results: ## EDGE: cite the developer's own RAG chunks inline, vs OpenAI/Gemini hosted file_search (needs 3 keys, cents)
	$(PY) run.py search-results --emit-edge

grounding-stack: ## EDGE (combination): cite text + PDF + RAG chunk each with its own pointer in ONE request, vs OpenAI/Gemini inline (needs 3 keys, cents)
	$(PY) run.py grounding-stack --emit-edge

web-citations: ## EDGE: a verifiable quote FROM the web source vs OpenAI/Gemini url-only web citations (needs 3 keys, cents)
	$(PY) run.py web-citations --emit-edge

bulk-output: ## EDGE: largest deliverable in ONE request, Claude 300k batch beta vs OpenAI/Gemini output caps (needs 3 keys, a few dollars, the Claude batch is slow)
	$(PY) run.py bulk-output --emit-edge

advisor: ## advisor tool: cheap executor + frontier advisor in ONE request, cost-at-quality vs the competitor frontier solo (needs 3 keys, a few dollars)
	$(PY) run.py advisor --emit-edge

code-execution-state: ## EDGE write phase: write a nonce to each vendor's code sandbox, warm read-back, save container ids (needs 3 keys, cents)
	$(PY) run.py code-execution-state

code-execution-state-verify: ## EDGE verify phase: re-read the SAME containers after a >20-min idle, Claude survives vs OpenAI expired (needs 3 keys, cents)
	$(PY) run.py code-execution-state --verify --emit-edge

cite: ## ground every shipped price and fact through Claude's own Citations API (writes docs/CITED_FACTS.md, cents)
	$(PY) -m engine.cite_facts

demo: ## the main event: a long agent, with and without the managed features (about $0.90)
	$(PY) run.py demo

demo-quick: ## a 10-document version that just shows the curve bend (about $0.10)
	$(PY) run.py demo --quick

demo-full: ## a 45-document version with a more dramatic curve
	$(PY) run.py demo --full

longhorizon: ## EDGE: context editing isolated, 3 runs: unbounded fails 3/3 (crash or wrong answer), edited finishes 3/3 (about $2)
	$(PY) edges/context-editing/demo.py --repeat 3

longhorizon-smoke: ## a cheap run that exercises the context-editing harness without reaching the window (cents)
	$(PY) edges/context-editing/demo.py --smoke

longhorizon-compare: ## cross-vendor head-to-head on the long task: Claude editing+memory vs OpenAI compaction vs Gemini (needs compare-deps + 3 keys, about $3)
	$(PY) run.py longhorizon-compare --repeat 3

ledger: ## EDGE: exact-list long stream, Claude context editing vs OpenAI compaction vs Gemini full context (needs 3 keys, about $5)
	$(PY) run.py ledger --full

ledger-smoke: ## cents-scale exact-list smoke, useful for checking the harness shape
	$(PY) run.py ledger --docs 8 --doc-tokens 3000 --no-gemini

compare: ## the credibility table: OpenAI vs Gemini vs Claude on the same long agent, all best config (needs compare-deps + ANTHROPIC + OPENAI + GEMINI keys, and the Gemini row degrades gracefully if its key or quota is missing)
	$(PY) run.py compare

alert: ## if a competitor won the last compare, draft the internal product-team note
	$(PY) run.py alert

sweep: ## trust-the-result variant sweep (caching on/off x managed/baseline, vs OpenAI)
	$(PY) run.py sweep

edges: ## the cheap discovery loop: sweep the live docs, diff against the last run, rank, write the landscape + changelog + brief (NO API call, NO benchmark spend, $0)
	$(PY) run.py edges

cadence: ## the unattended engine: sweep, rank, dispatch by demoKind, draft the newest uncovered lead to the inert outbox, update coverage, write the run manifest, audit the boundary (NO benchmark spend, NO send, $0)
	$(PY) run.py cadence --dry-run

grind: cadence coverage ci ## LOOP (tier 1, $0, fire-and-forget): the recurring edge loop, coverage view, and full offline gate, and paid proofs stay explicit per-edge targets

grind-deep: grind ## LOOP (tier 2, budgeted): the $0 loop, then the skeptic and combinatorial generator under DEEP_BUDGET_USD
	$(MAKE) verify DEEP_BUDGET_USD=$(DEEP_BUDGET_USD) DEEP_BUDGET_LABEL=$(DEEP_BUDGET_LABEL) DEEP_EFFORT=$(DEEP_EFFORT) VERIFY_JUDGES=$(VERIFY_JUDGES)
	$(MAKE) combine DEEP_BUDGET_USD=$(DEEP_BUDGET_USD) DEEP_BUDGET_LABEL=$(DEEP_BUDGET_LABEL) DEEP_EFFORT=$(DEEP_EFFORT)

coverage: ## per-demoKind coverage: what is built vs adapt vs build, and the gaps the engine surfaces about itself (NO API call, $0)
	$(PY) run.py coverage

managed: ## the Tier-2 monthly resumable Managed Agents runtime, wired but not run (prints the boundary, $0, and --apply runs a live session and spends a small bounded amount)
	$(PY) run.py managed

parity-gated: ## the long-tail parity-gated candidates, each HELD until its parity check survives (NO API call, $0)
	$(PY) run.py other

dynamic-web: ## live subfeature validation for web search/fetch dynamic filtering (needs 3 keys + compare-deps, spends a bounded amount)
	$(PY) run.py dynamic-web

task-budget: ## live subfeature validation for task_budget full-loop budget markers (needs 3 keys + compare-deps, spends a bounded amount)
	$(PY) run.py task-budget --emit-edge

cache-diagnostics: ## EDGE: cache-miss root-cause observability, Claude vs OpenAI/Gemini cache counters (needs 3 keys, cents)
	$(PY) run.py cache-diagnostics --emit-edge

fast-mode: ## live validation for fast mode access and same-model speedup (needs ANTHROPIC_API_KEY, held if org has 0 fast-mode ITPM)
	$(PY) run.py fast-mode

scan: ## print the candidate gaps, grounded in both sides' docs (no API call)
	$(PY) run.py scan

verify: ## budgeted skeptic pass. Set VERIFY_JUDGES=claude,openai for GPT-5.5 xhigh as a second critic
	RADAR_BUDGET_USD=$(DEEP_BUDGET_USD) RADAR_BUDGET_LABEL=$(DEEP_BUDGET_LABEL) RADAR_CLAUDE_EFFORT=$(DEEP_EFFORT) $(PY) run.py verify --judges "$(VERIFY_JUDGES)"

verify-live: ## live-claim re-prover: re-check the model access, knobs, and prices against real calls (spends cents)
	$(PY) scripts/verify_live.py

combine: ## the budgeted combinatorial generator: Opus + adaptive thinking proposes and skeptic-tests feature stacks
	RADAR_BUDGET_USD=$(DEEP_BUDGET_USD) RADAR_BUDGET_LABEL=$(DEEP_BUDGET_LABEL) RADAR_CLAUDE_EFFORT=$(DEEP_EFFORT) $(PY) run.py combine

eval: ## EDGE eval_quality: the cost x effort grid on a labeled slice, held-out test split, all providers (needs compare-deps + keys, about $3-4)
	$(PY) engine/demonstrators/eval_quality.py

eval-smoke: ## a cents-scale Claude-only smoke of the eval grid (Haiku + Sonnet, low effort)
	$(PY) engine/demonstrators/eval_quality.py --models haiku,sonnet --efforts low

eval-judge: ## the eval grid with the cross-model judge panel on (the too-trusting-grader cross-check)
	$(PY) engine/demonstrators/eval_quality.py --judge

retention: ## EDGE retention_resume: the doc-grounded retention/bundle parity receipt across 3 vendors (NO key, NO Managed Agents spend, $0)
	$(PY) engine/demonstrators/retention_resume.py

retention-live: ## OPT-IN: the live Managed Agents kill-and-resume (start, resume, negative control, steer, beta, needs ANTHROPIC_API_KEY, spends a small bounded amount)
	$(PY) engine/demonstrators/retention_resume.py --live

cost: ## EDGE cost: the pure pricing-model edge over swept dated prices, both win and lose regimes with the crossover named (NO API call, NO key, $0)
	$(PY) engine/demonstrators/cost_model.py

security-posture: ## PRIVATE security_posture: official-source security/admin posture receipt (NO API call, NO key, $0)
	$(PY) run.py security-posture --json

security: security-posture

draft: ## draft the founder email from the measured receipt
	$(PY) run.py draft

publish-brief: ## generate a self-contained public brief for a VERIFIED Claude-win edge into ../claude-feature-hits (the comparison gate defaults OFF, offline, $0, writes files only, never pushes/sends)
	$(PY) -m engine.publish_brief --edge=$(EDGE)

publish-misses: ## republish the 7 head-to-head briefs into MISSES_ROOT with the comparison gate defaulted ON (the always-full both-directions mirror). Set MISSES_ROOT to the private both-directions checkout, offline, $0
	@test -n "$(MISSES_ROOT)" || { echo "set MISSES_ROOT=<path to the private both-directions head_to_head dir>"; exit 1; }
	@for e in pdf-citations search-results grounding-stack web-citations bulk-extended-output exact-list-ledger code-execution-state; do \
		echo "publishing $$e (compare default ON) ..."; \
		$(PY) -m engine.publish_brief --edge=$$e --briefs-root=$(MISSES_ROOT) --compare-default on || exit 1; \
	done

check-claims: ## verify the citations reproduction cost still matches the summed receipt
	$(PY) scripts/cost_claim_check.py

check-docs: ## docs-vs-code gate: no make/run.py/model-id/beta-header drift in the docs (offline, $0)
	$(PY) scripts/check_docs.py

core-imports: ## one-dependency gate: the core imports with anthropic alone, the optional SDKs blocked (offline, $0)
	$(PY) scripts/check_core_imports.py

check-surface: ## surface gate: no internal/private-repo leakage in source, no Claude negative on a founder email (offline, $0)
	$(PY) scripts/check_surface.py

check-split: ## split gate: public wins stay in hits, private misses stay in the private sibling checkout (offline, $0)
	$(PY) scripts/check_split.py

check-receipts: ## receipt-drift gate: every measured number in the prose traces to a committed receipt (offline, $0)
	$(PY) scripts/check_receipts.py

test: ## the offline test suite (the gate boundary, the dispatch seam, the shared infra, no key, no network)
	$(PY) -m pytest -q

deslop: check-claims ## prose gate (em-dashes, en-dashes, semicolons) plus the citations cost-claim gate
	$(PY) scripts/deslop_check.py

ci: deslop check-docs core-imports check-surface check-split check-receipts test ## the full offline gate chain, the same one CI runs ($0)
	@echo "ci: all offline gates passed."

gif: ## regenerate docs/demo.gif from demo.tape (needs vhs, ffmpeg, ttyd)
	@if grep -lIE 'sk-ant-|sk-proj-|AIza[0-9A-Za-z_-]{8}|xox[baprs]-|ghp_' demo.tape edges/programmatic-tool-calling/sample.txt 2>/dev/null; then \
		echo "ABORT: key material found in a gif input above. Scrub it before recording."; exit 1; \
	fi
	vhs demo.tape

clean:
	rm -rf .venv data memories __pycache__ */__pycache__
