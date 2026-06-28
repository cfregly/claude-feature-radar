# claude-feature-hits: public promoted artifacts only.

VENV    := .venv
PY      := $(VENV)/bin/python
PIP     := $(VENV)/bin/pip

ARTIFACTS := $(shell python3 scripts/artifact_manifest.py active)

.PHONY: programmatic_tool_calling programmatic_tool_calling_cache_context check ci gif clean help

help:
	@echo "make programmatic_tool_calling  promoted live cost artifact: run the programmatic tool calling token-bill comparison (\$$0.08)"
	@echo "make programmatic_tool_calling_cache_context         checked model-token artifact: programmatic tool calling + cache + 1M context (\$$0)"
	@echo "make check                     run all promoted artifact checks; programmatic_tool_calling spends API tokens"
	@echo "make ci                        repo hygiene gate, no API spend"
	@echo "make gif                       rebuild demo.gif for artifact directories that have demo.tape"
	@echo "make clean                     remove the venv and caches"

$(VENV)/.installed: requirements.txt
	python3 -m venv $(VENV)
	$(PIP) install --quiet --upgrade pip
	$(PIP) install --quiet -r requirements.txt
	@touch $(VENV)/.installed

programmatic_tool_calling: $(VENV)/.installed
	$(PY) -m programmatic_tool_calling.compare_direct_vs_programmatic

programmatic_tool_calling_cache_context: $(VENV)/.installed
	$(PY) -m programmatic_tool_calling_cache_context.compare_cache_context_programmatic

check: $(VENV)/.installed
	@python3 scripts/artifact_manifest.py check | while read cmd; do echo "$$cmd"; $$cmd; done

ci: $(VENV)/.installed
	$(PY) scripts/check_reducer_contract.py
	$(PY) scripts/check_trace_contract.py
	$(PY) scripts/deslop_check.py
	$(PY) scripts/check_public_receipts.py
	$(PY) scripts/reconciliation_check.py
	$(PY) scripts/secret_check.py
	$(PY) scripts/public_surface_check.py
	$(PY) -m compileall -q $(ARTIFACTS) scripts
	$(PY) scripts/import_check.py

gif:
	@for b in $(ARTIFACTS); do \
		if grep -lIE 'sk-ant-|sk-proj-|AIza[0-9A-Za-z_-]{8}|xox[baprs]-|ghp_' $$b/demo.tape $$b/sample.txt 2>/dev/null; then \
			echo "ABORT: key material found in a gif input for $$b. Scrub it before recording."; exit 1; \
		fi; \
	done
	@for b in $(ARTIFACTS); do echo "vhs $$b/demo.tape"; vhs $$b/demo.tape; done

clean:
	rm -rf $(VENV) __pycache__ */__pycache__ */*/__pycache__
