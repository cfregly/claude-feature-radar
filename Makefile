# The competitive-gap engine. Each target runs in one command.
.PHONY: setup demo demo-quick demo-full longhorizon longhorizon-smoke compare alert scan verify draft deslop gif clean

PY := .venv/bin/python

setup: ## create the venv and install the one dependency
	python3 -m venv .venv
	$(PY) -m pip install --quiet --upgrade pip
	$(PY) -m pip install --quiet -r requirements.txt
	@echo "Setup done. Now: cp .env.example .env and paste your ANTHROPIC_API_KEY."

demo: ## the main event: a long agent, with and without the managed features (about $0.90)
	$(PY) run.py demo

demo-quick: ## a 10-document version that just shows the curve bend (about $0.10)
	$(PY) run.py demo --quick

demo-full: ## a 45-document version with a more dramatic curve
	$(PY) run.py demo --full

longhorizon: ## the regime where context editing pays off: unbounded crashes at the window, edited finishes (about $1 to $2)
	$(PY) run.py longhorizon

longhorizon-smoke: ## a cheap run that exercises the harness without reaching the window (cents)
	$(PY) run.py longhorizon --smoke

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

deslop: ## check the prose for em-dashes, en-dashes, and semicolons
	$(PY) scripts/deslop_check.py

gif: ## regenerate docs/demo.gif from demo.tape (needs vhs, ffmpeg, ttyd)
	vhs demo.tape

clean:
	rm -rf .venv data memories __pycache__ */__pycache__
