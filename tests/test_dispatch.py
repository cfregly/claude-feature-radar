"""Offline tests for the demoKind seam and the Demonstrator dispatch.

No key, no network, no model call: every test drives the deterministic taxonomy, the registry, and the
dispatcher with synthetic edges. Importing the demonstrators registers them without an SDK call (their
run_*_arm pulls the SDK lazily), so the registry is exercised exactly as the sweep exercises it.

The things these tests protect:
  - demoKind resolves from the seed table, then a best-effort axis guess, then "other", never crashes.
  - dispatch routes a built edge to its demonstrator with a surfaced estimate (no spend before a
    human sees the number), and files a build-a-demonstrator ASK stub for an unmapped kind.
  - the Receipt honesty contract: a claude-ahead verdict is downgraded to never-evaluated when a
    competitor arm did not run and the lead is not an all-fetched absence-of-evidence.
  - the estimate-surfaced gate check in engine.gate.audit().
"""
from engine import demokinds
from engine.demonstrators import base
from engine.demonstrators.base import Arm, CostEstimate, Verdict, reconcile_verdict
from engine.demonstrators.registry import REGISTRY, dispatch, register, register_all


# ----- the taxonomy resolves every key, and never crashes -----

def test_seed_table_maps_the_built_edges():
    assert demokinds.demokind_for("ptc") == "token_accounting"
    assert demokinds.demokind_for("citations") == "grounding_resolution"
    assert demokinds.demokind_for("context_editing") == "long_horizon_survival"
    assert demokinds.demokind_for("managed_agents") == "retention_resume"
    assert demokinds.demokind_for("pricing") == "cost"


def test_seed_table_resolves_dashed_and_undashed_forms():
    # The built-edge folder form and the slug form both resolve to the same demoKind.
    assert demokinds.demokind_for("programmatic-tool-calling") == "token_accounting"
    assert demokinds.demokind_for("context-editing") == "long_horizon_survival"
    assert demokinds.demokind_for("cost_and_effort") == demokinds.demokind_for("cost-and-effort")


def test_unknown_key_falls_back_to_axis_guess_then_other():
    # A key not in the seed table guesses from the axis, and an unknown axis lands on "other". Never a
    # crash, so a brand-new edge always routes.
    assert demokinds.demokind_for("never_seen", axis="grounding") == "grounding_resolution"
    assert demokinds.demokind_for("never_seen", axis="retention") == "retention_resume"
    assert demokinds.demokind_for("never_seen", axis="totally-unknown") == "other"
    assert demokinds.demokind_for("never_seen") == "other"


def test_is_seeded_separates_table_keys_from_guesses():
    assert demokinds.is_seeded("ptc") is True
    assert demokinds.is_seeded("never_seen_edge") is False


def test_every_seed_demokind_is_canonical():
    for kind in demokinds.KEY_TO_DEMOKIND.values():
        assert demokinds.is_known_kind(kind), f"{kind} is not in the canonical DEMO_KINDS list"


# ----- the three built demonstrators register -----

def test_built_demonstrators_register():
    register_all()
    assert REGISTRY.get("token_accounting") is not None
    assert REGISTRY.get("grounding_resolution") is not None
    assert REGISTRY.get("long_horizon_survival") is not None


def test_a_registered_demonstrator_declares_its_kind():
    register_all()
    for kind, demo in REGISTRY.items():
        assert demo.demo_kind == kind


# ----- dispatch routes by demoKind, surfaces the estimate, never crashes -----

def test_dispatch_routes_a_built_edge_with_a_surfaced_estimate():
    register_all()
    edge = {"key": "ptc", "axis": "cost"}
    r = dispatch(edge)
    assert r.covered is True
    assert r.demo_kind == "token_accounting"
    assert r.estimate is not None and r.estimate.usd > 0  # PTC spends a credit
    assert r.gate == "ask"                                  # so it waits for approval
    assert r.estimate.command == "make ptc"


def test_dispatch_files_a_build_stub_for_an_off_taxonomy_kind():
    # A kind not in the canonical taxonomy has no registered demonstrator, so dispatch returns an ASK
    # stub naming what to build, not a crash.
    edge = {"key": "brand_new", "axis": "observability", "demoKind": "not_a_real_kind"}
    r = dispatch(edge)
    assert r.demonstrator is None
    assert r.gate == "ask"
    assert "build a demonstrator" in (r.ask_stub or "")


def test_dispatch_holds_an_unchecked_other_candidate_with_a_precondition_stub():
    # The "other" kind now HAS a demonstrator (the parity-gated one), so an unchecked candidate is
    # DECLINED pending its parity check: an ASK stub that holds the edge, never pitched, never a crash.
    register_all()
    edge = {"key": "fallback_credit", "axis": "correctness", "demoKind": "other"}
    r = dispatch(edge)
    assert r.demonstrator is None            # declined: held until the parity check passes
    assert r.gate == "ask"
    assert "precondition is unmet" in (r.ask_stub or "")


def test_dispatch_stamps_the_resolved_kind_onto_an_unstamped_edge():
    register_all()
    edge = {"key": "citations", "axis": "grounding"}  # no demoKind field
    r = dispatch(edge)
    assert edge["demoKind"] == "grounding_resolution"  # stamped so applicable() can read it
    assert r.covered is True


def test_dispatch_respects_a_per_edge_demokind_override():
    # An explicit demoKind on the edge always wins over the seed-table guess.
    register_all()
    edge = {"key": "ptc", "axis": "cost", "demoKind": "long_horizon_survival"}
    r = dispatch(edge)
    assert r.demo_kind == "long_horizon_survival"
    assert isinstance(r.demonstrator, type(REGISTRY["long_horizon_survival"]))


# ----- the Receipt honesty contract -----

def _claude_arm():
    return Arm(provider="claude", model="claude-x", ran=True)


def test_claude_ahead_holds_when_a_competitor_arm_did_not_run():
    # A claude-ahead verdict with an unrun competitor arm and no all-fetched absence basis is
    # downgraded to never-evaluated, never shipped as an unproven lead. This is the core rule.
    competitors = [Arm(provider="openai", model="gpt", ran=False, note="key absent")]
    verdict, note = reconcile_verdict("claude-ahead", _claude_arm(), competitors, "within-claude-only")
    assert verdict == "never-evaluated"
    assert "held" in note


def test_claude_ahead_stands_on_an_all_fetched_absence_of_evidence():
    # When the lead rests on a documented absence and every source fetched, the verdict stands even
    # with no competitor arm to run (the PTC case: no named equivalent exists to run an arm against).
    verdict, note = reconcile_verdict("claude-ahead", _claude_arm(), [], "absence-of-evidence")
    assert verdict == "claude-ahead"


def test_claude_ahead_stands_when_every_competitor_arm_ran():
    competitors = [Arm(provider="openai", model="gpt", ran=True),
                   Arm(provider="gemini", model="gem", ran=True)]
    verdict, _ = reconcile_verdict("claude-ahead", _claude_arm(), competitors, "head-to-head")
    assert verdict == "claude-ahead"


def test_non_claude_ahead_verdicts_pass_through_untouched():
    for v in ("parity", "claude-behind", "never-evaluated", "within-claude-only"):
        out, _ = reconcile_verdict(v, _claude_arm(), [], "within-claude-only")
        assert out == v


def test_build_receipt_applies_the_contract():
    # The base build_receipt helper must run reconcile_verdict, so a demonstrator cannot forget it.
    class _D(base.BaseDemonstrator):
        demo_kind = "token_accounting"

    edge = {"key": "ptc", "axis": "cost", "demoKind": "token_accounting",
            "fair_comparison": {"lead_basis": "within-claude-only"}, "claim": "x"}
    claude = _claude_arm()
    competitors = [Arm(provider="openai", model="gpt", ran=False)]
    v = Verdict(verdict="claude-ahead", passed=True, metric={"pct": 28})
    receipt = _D().build_receipt(edge, claude, competitors, v, {"estimate": {}},
                                 workload={}, grounding=[])
    assert receipt.verdict == "never-evaluated"  # downgraded by the contract
    assert receipt.passed is True                 # the gate still records what it measured


# ----- the estimate-surfaced gate check -----

def test_audit_flags_a_spend_proposed_without_a_surfaced_estimate():
    from engine import gate
    routing = [{"key": "ptc", "gate": gate.ASK, "demonstrator": "PTCDemonstrator",
                "estimate_surfaced": False}]
    violations = gate.audit([], routing)
    assert violations and any("surfaced estimate" in v for v in violations)


def test_audit_passes_a_spend_with_a_surfaced_estimate():
    from engine import gate
    routing = [{"key": "ptc", "gate": gate.ASK, "demonstrator": "PTCDemonstrator",
                "estimate_surfaced": True}]
    assert gate.audit([], routing) == []


def test_audit_ignores_routing_for_a_zero_cost_always_demonstrator():
    from engine import gate
    routing = [{"key": "edges", "gate": gate.ALWAYS, "demonstrator": "DiscoveryDemonstrator",
                "estimate_surfaced": False}]
    assert gate.audit([], routing) == []  # a $0 always demonstrator needs no estimate


# ----- the grounded landscape correction (managedAgentsCorrection) -----

def test_grounding_correction_demotes_retention_to_parity():
    from engine import scan
    # managed_agents and memory_tool must never carry an absence-of-evidence Claude-only lead. The
    # correction re-grades them to doc-grounded parity, zeroing the lead so they are never pitched.
    for key in ("managed_agents", "memory_tool"):
        edge = {"key": key, "axis": "retention", "verdict": "claude-ahead", "lead_score": 2,
                "score": 6, "fair_comparison": {"lead_basis": "absence-of-evidence"}}
        out = scan.apply_grounding_correction(edge)
        assert out["verdict"] == "parity"
        assert out["lead_score"] == 0 and out["score"] == 0
        assert out["fair_comparison"]["lead_basis"] == "doc-grounded-parity"


def test_grounding_correction_demotes_context_editing_to_parity():
    from engine import scan
    # context editing vs server-side compaction is parity, so the long-horizon LEADERSHIP claim
    # anchors on METR, not context editing.
    edge = {"key": "context_editing", "axis": "long-horizon", "verdict": "claude-ahead",
            "lead_score": 2, "score": 6, "fair_comparison": {"lead_basis": "absence-of-evidence"}}
    out = scan.apply_grounding_correction(edge)
    assert out["verdict"] == "parity" and out["lead_score"] == 0


def test_grounding_correction_leaves_other_edges_untouched():
    from engine import scan
    edge = {"key": "ptc", "axis": "cost", "verdict": "claude-ahead", "lead_score": 2, "score": 6,
            "fair_comparison": {"lead_basis": "absence-of-evidence"}}
    out = scan.apply_grounding_correction(edge)
    assert out["verdict"] == "claude-ahead" and out["lead_score"] == 2  # PTC is a genuine lead, untouched
