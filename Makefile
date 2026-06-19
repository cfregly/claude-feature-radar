# The competitive-gap engine. Each target runs in one command.
.PHONY: setup compare-deps app app-check ptc citations citations-quick cite demo demo-quick demo-full longhorizon longhorizon-smoke longhorizon-compare compare alert edges cadence coverage managed parity-gated scan verify verify-live eval eval-smoke eval-judge retention retention-live cost draft publish-brief check-claims check-docs core-imports check-surface check-receipts test ci deslop gif clean

PY := .venv/bin/python

setup: ## create the venv and install the one dependency
	python3 -m venv .venv
	$(PY) -m pip install --quiet --upgrade pip
	$(PY) -m pip install --quiet -r requirements.txt
	@echo "Setup done. Now: cp .env.example .env and paste your ANTHROPIC_API_KEY."

compare-deps: ## install the OpenAI + Gemini SDKs into the SAME venv, for compare/sweep
	$(PY) -m pip install --quiet -r requirements-compare.txt
	@echo "Compare deps installed into .venv. Now paste OPENAI_API_KEY and GEMINI_API_KEY into .env."

app: ## FORKABLE APP: run the fan-out task over your own tool (app/my_tool.py), print your before-and-after token bill (needs ANTHROPIC_API_KEY, about $0.08)
	$(PY) -m app.run_tokens

app-check: ## the app self-test: run the shipped example and assert the PTC invariant (Mode B bills fewer input tokens AND answers correctly) before you trust it on your own tool (about $0.08)
	$(PY) -m app.run_tokens --check

ptc: ## EDGE: programmatic tool calling, the input-token receipt on a fan-out task (needs ANTHROPIC_API_KEY, about $0.08)
	$(PY) edges/programmatic-tool-calling/demo.py

citations: ## EDGE: verifiable citations vs the DIY str.find baseline, all three vendors (needs compare-deps + 3 keys, $0.06)
	$(PY) edges/citations/demo.py

citations-quick: ## a 3-question, cents-scale smoke of the citations edge
	$(PY) edges/citations/demo.py --quick

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

compare: ## the credibility table: OpenAI vs Gemini vs Claude on the same long agent, all best config (needs compare-deps + ANTHROPIC + OPENAI + GEMINI keys; the Gemini row degrades gracefully if its key or quota is missing)
	$(PY) run.py compare

alert: ## if a competitor won the last compare, draft the internal product-team note
	$(PY) run.py alert

sweep: ## trust-the-result variant sweep (caching on/off x managed/baseline, vs OpenAI)
	$(PY) run.py sweep

edges: ## the cheap discovery loop: sweep the live docs, diff against the last run, rank, write the landscape + changelog + brief (NO API call, NO benchmark spend, $0)
	$(PY) run.py edges

cadence: ## the unattended engine: sweep, rank, dispatch by demoKind, draft the newest uncovered lead to the inert outbox, update coverage, write the run manifest, audit the boundary (NO benchmark spend, NO send, $0)
	$(PY) run.py cadence --dry-run

coverage: ## per-demoKind coverage: what is built vs adapt vs build, and the gaps the engine surfaces about itself (NO API call, $0)
	$(PY) run.py coverage

managed: ## the Tier-2 monthly resumable Managed Agents runtime, wired but not run (prints the boundary, $0; --apply runs a live session and spends a small bounded amount)
	$(PY) run.py managed

parity-gated: ## the long-tail parity-gated candidates (fallback credit, cache_miss_reason, Claude Code build velocity), each HELD until its parity check survives (NO API call, $0)
	$(PY) run.py other

scan: ## print the candidate gaps, grounded in both sides' docs (no API call)
	$(PY) run.py scan

verify: ## the skeptic pass: ask Claude to break each candidate, keep what survives
	$(PY) run.py verify

verify-live: ## live-claim re-prover: re-check the model access, knobs, and prices against real calls (spends cents)
	$(PY) scripts/verify_live.py

eval: ## EDGE eval_quality: the cost x effort grid on a labeled slice, held-out test split, all providers (needs compare-deps + keys, about $3-4)
	$(PY) engine/demonstrators/eval_quality.py

eval-smoke: ## a cents-scale Claude-only smoke of the eval grid (Haiku + Sonnet, low effort)
	$(PY) engine/demonstrators/eval_quality.py --models haiku,sonnet --efforts low

eval-judge: ## the eval grid with the cross-model judge panel on (the too-trusting-grader cross-check)
	$(PY) engine/demonstrators/eval_quality.py --judge

retention: ## EDGE retention_resume: the doc-grounded retention/bundle parity receipt across 3 vendors (NO key, NO Managed Agents spend, $0)
	$(PY) engine/demonstrators/retention_resume.py

retention-live: ## OPT-IN: the live Managed Agents kill-and-resume (start, resume, negative control, steer; beta, needs ANTHROPIC_API_KEY, spends a small bounded amount)
	$(PY) engine/demonstrators/retention_resume.py --live

cost: ## EDGE cost: the pure pricing-model edge over swept dated prices, both win and lose regimes with the crossover named (NO API call, NO key, $0)
	$(PY) engine/demonstrators/cost_model.py

draft: ## draft the founder email from the measured receipt
	$(PY) run.py draft

publish-brief: ## generate a self-contained public brief for a VERIFIED Claude-win edge into ../claude-feature-briefs (offline, $0, writes files only, never pushes/sends)
	$(PY) -m engine.publish_brief --edge=$(EDGE)

check-claims: ## verify the citations reproduction cost still matches the summed receipt
	$(PY) scripts/cost_claim_check.py

check-docs: ## docs-vs-code gate: no make/run.py/model-id/beta-header drift in the docs (offline, $0)
	$(PY) scripts/check_docs.py

core-imports: ## one-dependency gate: the core imports with anthropic alone, the optional SDKs blocked (offline, $0)
	$(PY) scripts/check_core_imports.py

check-surface: ## surface gate: no internal/private-repo leakage in source, no Claude negative on a founder email (offline, $0)
	$(PY) scripts/check_surface.py

check-receipts: ## receipt-drift gate: every measured number in the prose traces to a committed receipt (offline, $0)
	$(PY) scripts/check_receipts.py

test: ## the offline test suite (the gate boundary, the dispatch seam, the shared infra; no key, no network)
	$(PY) -m pytest -q

deslop: check-claims ## prose gate (em-dashes, en-dashes, semicolons) plus the citations cost-claim gate
	$(PY) scripts/deslop_check.py

ci: deslop check-docs core-imports check-surface check-receipts test ## the full offline gate chain, the same one CI runs ($0)
	@echo "ci: all offline gates passed."

gif: ## regenerate docs/demo.gif from demo.tape (needs vhs, ffmpeg, ttyd)
	vhs demo.tape

clean:
	rm -rf .venv data memories __pycache__ */__pycache__
