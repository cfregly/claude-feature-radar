#!/usr/bin/env bash
# Full cross-vendor re-run, sequential (avoids rate-limit fan-out collisions and the
# data/last_eval.json clobber between the two eval runs). Logs everything to LOG.
set -u
cd "$(dirname "$0")/.."
PY=.venv/bin/python
LOG=/tmp/rerun_logs
mkdir -p "$LOG"

# Load the worktree .env (now carrying the new credit-bearing ANTHROPIC key) into the env.
set -a; . ./.env; set +a

run() {  # run <name> <env-prefix-or-empty> <cmd...>
  local name="$1"; shift
  echo "===== START $name $(date -u +%H:%M:%S) ====="
  /usr/bin/env bash -c "$*" >"$LOG/$name.log" 2>&1
  local rc=$?
  echo "===== END   $name rc=$rc $(date -u +%H:%M:%S) ====="
  return 0
}

# $0 deterministic demonstrators (no API) — fast, capture fresh stdout for the sample.txt refresh
run retention      "$PY engine/demonstrators/retention_resume.py"
run cost           "$PY engine/demonstrators/cost_model.py"
run parity_gated   "$PY run.py other"

# Citations grounding (Anthropic-only, confirmed funded) — the 'CITATIONS for EVERYTHING' pass
run cite           "$PY -m engine.cite_facts"
[ -f docs/CITED_FACTS.md ] && cp docs/CITED_FACTS.md "$LOG/CITED_FACTS.md"
[ -f data/last_cite.json ] && cp data/last_cite.json "$LOG/last_cite.json"

# eval Run 1: built-in labeled slice, judge panel on, full cross-vendor
run eval_run1      "$PY engine/demonstrators/eval_quality.py --judge"
[ -f data/last_eval.json ] && cp data/last_eval.json "$LOG/eval_run1.json"

# eval Run 2: LiveCodeBench hard slice, judge panel on, full cross-vendor
run eval_run2_lcb  "EVAL_LCB=1 $PY engine/demonstrators/eval_quality.py --judge"
[ -f data/last_eval.json ] && cp data/last_eval.json "$LOG/eval_run2_lcb.json"

# agentic head-to-head: 4 instances x 6 models, symmetric loop, no-Docker grader (longest, ~10 min)
run agentic        "$PY engine/demonstrators/agentic_grading.py"
[ -f data/last_agentic.json ] && cp data/last_agentic.json "$LOG/last_agentic.json"

echo "ALL DONE $(date -u +%H:%M:%S)"
