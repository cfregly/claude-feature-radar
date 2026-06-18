"""Offline tests for the eval_quality demonstrator.

No key, no network, no model call: every test drives the deterministic pieces (the BYO-JSONL loader,
the built-in slice's split discipline, the sandbox grader on a known program, the Cell tally and the
held-out-split overfit guard, the recommendation) and the demonstrator interface against a synthetic
in-memory GridRun, so the score gate and the honesty contract are proven without a model call. The
live grid (the real model calls) is exercised by `make eval`, which spends; these tests protect the
logic that run depends on.

What these tests protect:
  - the demonstrator registers under eval_quality and dispatch routes cost-and-effort and the
    model-tier keys to it.
  - the built-in slice carries a real dev/test split (the held-out number is not a re-run of dev).
  - the sandbox grader passes a correct program and fails a wrong one (the SAME machine-check gate).
  - the BYO-JSONL loader reads a stranger's tasks and defaults their split to held-out test.
  - score() reads the HELD-OUT test pass rate and emits claude-ahead only when Claude's best cell
    strictly out-passes every competitor arm that RAN.
  - the honesty contract downgrades claude-ahead to never-evaluated when a competitor arm did not run.
  - parity on a tie, claude-behind when a competitor wins (the product-team direction).
  - the overfit guard surfaces a cell that wins on dev but drops on the held-out test split.
"""

import json

from engine.demonstrators import eval_quality as eq
from engine.demonstrators.base import Arm
from engine.demonstrators.registry import REGISTRY, dispatch, register_all


# ----- registration + dispatch -----

def test_eval_quality_registers():
    register_all()
    demo = REGISTRY.get("eval_quality")
    assert demo is not None
    assert demo.demo_kind == "eval_quality"


def test_dispatch_routes_cost_and_effort_to_eval_quality():
    register_all()
    r = dispatch({"key": "cost-and-effort", "axis": "cost"})
    assert r.covered is True
    assert r.demo_kind == "eval_quality"
    assert r.estimate is not None and r.estimate.usd > 0   # it spends, so it is an ASK
    assert r.gate == "ask"
    assert r.estimate.command == "make eval"


def test_dispatch_routes_model_tier_migration_to_eval_quality():
    register_all()
    for key in ("model_tier_migration", "tier", "effort"):
        r = dispatch({"key": key, "axis": "cost"})
        assert r.demo_kind == "eval_quality", key
        assert r.covered is True


# ----- the labeled slice carries a real held-out split -----

def test_builtin_slice_has_disjoint_dev_and_test_splits():
    probs = eq.load_problems()
    dev = {p.qid for p in probs if p.split == "dev"}
    test = {p.qid for p in probs if p.split == "test"}
    assert dev and test
    assert not (dev & test)   # disjoint, so the held-out number is a real generalization check


def test_builtin_slice_spans_both_difficulty_tiers():
    probs = eq.load_problems()
    diffs = {p.difficulty for p in probs}
    assert "medium" in diffs and "hard" in diffs


# ----- the sandbox grader is the same machine-check on every arm -----

def test_grader_passes_a_correct_program_and_fails_a_wrong_one():
    # sum_to_n is in the dev slice; grade a correct and a wrong program against its hidden tests.
    sum_task = next(p for p in eq.load_problems() if p.qid == "sum_to_n")
    correct = "n=int(input())\nprint(n*(n+1)//2)"
    wrong = "n=int(input())\nprint(n)"
    ok, _ = eq.grade(correct, sum_task.tests, timeout=8)
    bad, _ = eq.grade(wrong, sum_task.tests, timeout=8)
    assert ok is True
    assert bad is False


def test_extract_code_pulls_the_last_python_block():
    text = "thinking...\n```python\nprint(1)\n```\nand the final answer:\n```python\nprint(2)\n```"
    assert eq.extract_code(text) == "print(2)"


# ----- the BYO-JSONL loader -----

def test_byo_loader_reads_tasks_and_defaults_split_to_test(tmp_path):
    f = tmp_path / "my.jsonl"
    f.write_text(json.dumps({
        "name": "echo", "prompt": "Read a line and print it.",
        "tests": [["hi\n", "hi"]], "difficulty": "medium"}) + "\n")
    probs = eq._load_byo(str(f))
    assert len(probs) == 1
    assert probs[0].qid == "echo"
    assert probs[0].split == "test"          # a stranger's own cases are the held-out set
    assert probs[0].tests == [("hi\n", "hi")]


def test_byo_loader_rejects_a_task_with_no_tests(tmp_path):
    f = tmp_path / "bad.jsonl"
    f.write_text(json.dumps({"prompt": "x", "tests": []}) + "\n")
    try:
        eq._load_byo(str(f))
        assert False, "expected a ValueError on an empty tests list"
    except ValueError:
        pass


# ----- a synthetic GridRun the score/receipt path reads -----

def _cell(model, effort, *, dev, test, cost, judge_agree=None, n_dev=4, n_test=4):
    """Build a Cell with controlled dev/test pass counts, so the score and the overfit guard are
    exercised without a model call."""
    c = eq.Cell(model, effort)
    c.timed_tasks = n_dev + n_test
    c.total_cost = cost
    c.input_tokens = 100
    c.output_tokens = 50
    c.by_split["dev"].graded = n_dev
    c.by_split["dev"].correct = round(dev * n_dev)
    c.by_split["test"].graded = n_test
    c.by_split["test"].correct = round(test * n_test)
    c.overall.graded = n_dev + n_test
    c.overall.correct = c.by_split["dev"].correct + c.by_split["test"].correct
    if judge_agree is not None:
        c.judged = n_test
        c.judge_agree = round(judge_agree * n_test)
    return c


def _grid(cells, judge=False):
    return eq.GridRun(cells=cells, n_problems=8, n_dev=4, n_test=4, total_cost=sum(c.total_cost for c in cells),
                      efforts=("low", "high"), judge=judge, skipped=[])


def test_score_claude_ahead_when_best_cell_out_passes_every_competitor():
    d = eq.EvalQualityDemonstrator()
    cells = [
        _cell("haiku", "low", dev=1.0, test=1.0, cost=0.01),     # cheap Claude tier wins held-out
        _cell("opus", "high", dev=1.0, test=1.0, cost=0.20),     # frontier Claude tier ran too
        _cell("gpt-top", "high", dev=1.0, test=0.75, cost=0.10),
        _cell("gem-pro", "high", dev=1.0, test=0.50, cost=0.08),
    ]
    spec = {"_run": _grid(cells)}
    claude = d.run_claude_arm({}, spec)
    comps = d.run_competitor_arms({}, spec)
    v = d.score(claude, comps, spec)
    assert v.verdict == "claude-ahead"
    assert v.passed is True


def test_score_parity_on_a_held_out_tie():
    d = eq.EvalQualityDemonstrator()
    cells = [
        _cell("sonnet", "high", dev=1.0, test=0.75, cost=0.05),
        _cell("gpt-top", "high", dev=1.0, test=0.75, cost=0.10),
    ]
    spec = {"_run": _grid(cells)}
    v = d.score(d.run_claude_arm({}, spec), d.run_competitor_arms({}, spec), spec)
    assert v.verdict == "parity"
    assert v.passed is False


def test_score_claude_behind_when_a_competitor_wins_the_held_out():
    d = eq.EvalQualityDemonstrator()
    cells = [
        _cell("sonnet", "high", dev=1.0, test=0.50, cost=0.05),
        _cell("gpt-top", "high", dev=1.0, test=1.0, cost=0.10),
    ]
    spec = {"_run": _grid(cells)}
    v = d.score(d.run_claude_arm({}, spec), d.run_competitor_arms({}, spec), spec)
    assert v.verdict == "claude-behind"


def test_receipt_downgrades_claude_ahead_when_a_competitor_arm_did_not_run():
    # Claude out-passes the arm that ran, but the Gemini key was absent (no gem cell in the grid).
    d = eq.EvalQualityDemonstrator()
    cells = [
        _cell("sonnet", "high", dev=1.0, test=1.0, cost=0.05),
        _cell("gpt-top", "high", dev=1.0, test=0.50, cost=0.10),
    ]
    spec = {"_run": _grid(cells)}
    claude = d.run_claude_arm({}, spec)
    # competitor arms include gem-pro, which has no cell -> ran=False
    comps = d.run_competitor_arms({}, spec)
    assert any(not c.ran for c in comps)   # gem-pro did not run
    v = d.score(claude, comps, spec)
    assert v.verdict == "claude-ahead"     # the gate sees only the arms that ran
    edge = {"key": "cost-and-effort", "axis": "cost", "demoKind": "eval_quality",
            "fair_comparison": {"lead_basis": "head-to-head"}, "claim": "x"}
    receipt = d.receipt(edge, claude, comps, v, spec)
    assert receipt.verdict == "never-evaluated"   # downgraded by the honesty contract


def test_receipt_claude_ahead_stands_when_every_competitor_arm_ran():
    d = eq.EvalQualityDemonstrator()
    cells = [
        _cell("haiku", "low", dev=1.0, test=1.0, cost=0.01),
        _cell("opus", "high", dev=1.0, test=1.0, cost=0.20),
        _cell("gpt-mid", "high", dev=1.0, test=0.75, cost=0.08),
        _cell("gpt-top", "high", dev=1.0, test=0.75, cost=0.10),
        _cell("gem-flash", "high", dev=1.0, test=0.50, cost=0.06),
        _cell("gem-pro", "high", dev=1.0, test=0.50, cost=0.08),
    ]
    spec = {"_run": _grid(cells)}
    claude = d.run_claude_arm({}, spec)
    comps = d.run_competitor_arms({}, spec)
    assert all(c.ran for c in comps)
    v = d.score(claude, comps, spec)
    edge = {"key": "cost-and-effort", "axis": "cost", "demoKind": "eval_quality",
            "fair_comparison": {"lead_basis": "head-to-head"}, "claim": "x"}
    receipt = d.receipt(edge, claude, comps, v, spec)
    assert receipt.verdict == "claude-ahead"
    assert receipt.demo_kind == "eval_quality"
    assert "task_shape" in receipt.workload
    assert receipt.metric.get("per_arm")


# ----- the overfit guard -----

def test_recommend_flags_a_cell_that_overfits_dev():
    # A cell at 100% dev but 25% held-out test must be flagged by the overfit guard.
    cell = _cell("sonnet", "high", dev=1.0, test=0.25, cost=0.05)
    lines = eq.recommend(_grid([cell]))
    assert any("Overfit guard" in ln for ln in lines)


def test_recommend_headline_uses_the_held_out_number():
    cell = _cell("haiku", "low", dev=1.0, test=1.0, cost=0.01)
    lines = eq.recommend(_grid([cell]))
    assert any("HELD-OUT" in ln for ln in lines)


def test_recommend_judge_note_appears_when_judge_on_and_panel_disagrees():
    cell = _cell("sonnet", "high", dev=1.0, test=1.0, cost=0.05, judge_agree=0.5)
    lines = eq.recommend(_grid([cell], judge=True))
    assert any("Judge cross-check" in ln for ln in lines)
