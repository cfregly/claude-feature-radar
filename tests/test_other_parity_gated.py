"""Offline tests for the thin parity-gated demonstrators (the long tail).

No key, no network, no model call: every test drives the deterministic parity-check ledger and the
demonstrator interface with synthetic edges. The whole point of this kind is the parity-check
precondition, so the tests above all protect that an unchecked candidate is HELD never-evaluated and is
never pitched, and that flipping its recorded parity check to "survives" is what unblocks it.

What these tests protect:
  - the demonstrator registers under the "other" demoKind and dispatch routes every recorded
    candidate to it.
  - applicable() returns False for an unchecked or killed candidate, so dispatch files a
    precondition-unmet ASK stub and the edge is held, never pitched.
  - the score verdict for a held candidate is never-evaluated; flipping the parity check to "survives"
    moves it to within-claude-only (the opt-in thin proof would then run), never claude-ahead.
  - no competitor arm runs on the held path, so the honesty contract can never read claude-ahead.
"""

import pytest

from engine.demonstrators import other_parity_gated as opg
from engine.demonstrators.registry import REGISTRY, dispatch, register_all


# ----- registration + dispatch -----

def test_other_demonstrator_registers():
    register_all()
    demo = REGISTRY.get("other")
    assert demo is not None
    assert demo.demo_kind == "other"


@pytest.mark.parametrize("key", sorted(opg.PARITY_CHECKS))
def test_dispatch_routes_each_candidate_to_other_and_respects_parity_state(key):
    register_all()
    r = dispatch({"key": key, "axis": opg.PARITY_CHECKS[key]["axis"]})
    assert r.demo_kind == "other"
    if opg.parity_check_passed(key):
        assert r.demonstrator is not None
        assert r.gate == "ask"
    else:
        assert r.demonstrator is None        # declined: held, never pitched
        assert r.gate == "ask"
        assert "precondition" in (r.ask_stub or "") or "declined" in (r.ask_stub or "")


# ----- the parity-check precondition -----

def test_unpromoted_candidates_start_unchecked_and_held():
    for key, entry in opg.PARITY_CHECKS.items():
        if key in {"cache_diagnostics", "task_budgets"}:
            continue
        assert entry["parity_verdict"] == "unchecked"
        assert opg.parity_check_passed(key) is False


@pytest.mark.parametrize("key", ["cache_diagnostics", "task_budgets"])
def test_promoted_parity_checks_survived(key):
    assert opg.PARITY_CHECKS[key]["parity_verdict"] == "survives"
    assert opg.parity_check_passed(key) is True


def test_parity_check_passed_only_on_survives():
    assert opg.parity_check_passed("unknown_key") is False
    # a "killed" verdict stays held, only "survives" unblocks.
    saved = opg.PARITY_CHECKS["fallback_credit"]["parity_verdict"]
    try:
        opg.PARITY_CHECKS["fallback_credit"]["parity_verdict"] = "killed"
        assert opg.parity_check_passed("fallback_credit") is False
        opg.PARITY_CHECKS["fallback_credit"]["parity_verdict"] = "survives"
        assert opg.parity_check_passed("fallback_credit") is True
    finally:
        opg.PARITY_CHECKS["fallback_credit"]["parity_verdict"] = saved


def test_applicable_is_false_until_the_parity_check_passes():
    d = opg.OtherParityGatedDemonstrator()
    edge = {"key": "fallback_credit", "demoKind": "other"}
    assert d.applicable(edge) is False               # unchecked: held
    saved = opg.PARITY_CHECKS["fallback_credit"]["parity_verdict"]
    try:
        opg.PARITY_CHECKS["fallback_credit"]["parity_verdict"] = "survives"
        assert d.applicable(edge) is True            # survives: unblocked
    finally:
        opg.PARITY_CHECKS["fallback_credit"]["parity_verdict"] = saved


# ----- the held verdict is never-evaluated, never claude-ahead -----

def test_held_candidate_scores_never_evaluated():
    d = opg.OtherParityGatedDemonstrator()
    edge = {"key": "web_search_tool", "demoKind": "other"}
    claude = d.run_claude_arm(edge, {})
    comps = d.run_competitor_arms(edge, {})
    v = d.score(claude, comps, {})
    assert v.verdict == "never-evaluated"
    assert v.passed is False
    assert claude.ran is False                       # no model run on the held path


def test_no_competitor_arm_runs_on_the_held_path():
    d = opg.OtherParityGatedDemonstrator()
    assert d.run_competitor_arms({"key": "fallback_credit", "demoKind": "other"}, {}) == []


def test_passing_the_parity_check_moves_the_verdict_to_within_claude_only():
    d = opg.OtherParityGatedDemonstrator()
    edge = {"key": "fallback_credit", "demoKind": "other"}
    saved = opg.PARITY_CHECKS["fallback_credit"]["parity_verdict"]
    try:
        opg.PARITY_CHECKS["fallback_credit"]["parity_verdict"] = "survives"
        claude = d.run_claude_arm(edge, {})
        v = d.score(claude, d.run_competitor_arms(edge, {}), {})
        assert v.verdict == "within-claude-only"     # the opt-in thin proof would then run, ASK on spend
        assert v.verdict != "claude-ahead"           # never a head-to-head lead off the parity gate
    finally:
        opg.PARITY_CHECKS["fallback_credit"]["parity_verdict"] = saved


def test_receipt_of_a_held_candidate_carries_the_parity_check_state():
    d = opg.OtherParityGatedDemonstrator()
    edge = {"key": "web_search_tool", "demoKind": "other",
            "fair_comparison": {"lead_basis": "within-claude-only"}, "axis": "observability"}
    claude = d.run_claude_arm(edge, {})
    v = d.score(claude, [], {})
    receipt = d.receipt(edge, claude, [], v, {"estimate": {}})
    assert receipt.verdict == "never-evaluated"
    assert receipt.demo_kind == "other"
    assert len(receipt.grounding) == 1 and receipt.grounding[0]["date"] == "2026-06-19"
    assert "never-evaluated" in receipt.workload.get("assumptions", "").lower()


def test_estimates_are_bounded_under_the_per_demo_cap():
    d = opg.OtherParityGatedDemonstrator()
    for key in opg.PARITY_CHECKS:
        est = d.estimate({"key": key}, {})
        assert 0 < est.usd <= 6.0                    # a bounded thin proof, well under the per-demo cap


def test_promoted_estimates_use_public_make_targets():
    d = opg.OtherParityGatedDemonstrator()
    assert d.estimate({"key": "cache_diagnostics"}, {}).command == "make cache_diagnostics"
    assert d.estimate({"key": "task_budgets"}, {}).command == "make task_budgets"
