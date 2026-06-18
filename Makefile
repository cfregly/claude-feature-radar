# The competitive-gap engine. Each target runs in one command.
.PHONY: setup compare-deps ptc citations citations-quick demo demo-quick demo-full longhorizon longhorizon-smoke longhorizon-compare compare alert scan verify draft check-claims deslop gif clean

PY := .venv/bin/python

setup: ## create the venv and install the one dependency
	python3 -m venv .venv
	$(PY) -m pip install --quiet --upgrade pip
	$(PY) -m pip install --quiet -r requirements.txt
	@echo "Setup done. Now: cp .env.example .env and paste your ANTHROPIC_API_KEY."

compare-deps: ## install the OpenAI + Gemini SDKs into the SAME venv, for compare/sweep
	$(PY) -m pip install --quiet -r requirements-compare.txt
	@echo "Compare deps installed into .venv. Now paste OPENAI_API_KEY and GEMINI_API_KEY into .env."

ptc: ## EDGE: programmatic tool calling, the input-token receipt on a fan-out task (needs ANTHROPIC_API_KEY, about $0.06)
	$(PY) edges/programmatic-tool-calling/demo.py

citations: ## EDGE: verifiable citations vs the DIY str.find baseline, all three vendors (needs compare-deps + 3 keys, about $0.06)
	$(PY) edges/citations/demo.py

citations-quick: ## a 3-question, cents-scale smoke of the citations edge
	$(PY) edges/citations/demo.py --quick

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

compare: ## OpenAI vs Claude on the same long agent, both best config (needs openai + OPENAI_API_KEY)
	$(PY) run.py compare

alert: ## if a competitor won the last compare, draft the internal product-team note
	$(PY) run.py alert

sweep: ## trust-the-result variant sweep (caching on/off x managed/baseline, vs OpenAI)
	$(PY) run.py sweep

scan: ## print the candidate gaps, grounded in both sides' docs (no API call)
	$(PY) run.py scan

verify: ## the skeptic pass: ask Claude to break each candidate, keep what survives
	$(PY) run.py verify

draft: ## draft the founder email from the measured receipt
	$(PY) run.py draft

check-claims: ## verify the citations reproduction cost still matches the summed receipt
	$(PY) scripts/cost_claim_check.py

deslop: check-claims ## prose gate (em-dashes, en-dashes, semicolons) plus the citations cost-claim gate
	$(PY) scripts/deslop_check.py

gif: ## regenerate docs/demo.gif from demo.tape (needs vhs, ffmpeg, ttyd)
	vhs demo.tape

clean:
	rm -rf .venv data memories __pycache__ */__pycache__
