"""Offline tests for the publish_brief verdict gate, the load-bearing safety property of the
one-source-of-truth fix. No key, no network, no spend: every test drives the deterministic gate and the
deterministic vendoring against the committed engine truth (or a synthetic edge record).

The thing these tests protect is the fail-closed posture: a brief is published ONLY for a clean,
ranked, non-regime-bounded claude-ahead win whose receipt (if present) agrees, and a refusal writes
NOTHING (no partial brief dir). They mirror the offline, no-network shape of the other engine tests.
"""

import json

import pytest

from engine import publish_brief as pb


# --------------------------------------------------------------------------- the gate, on real edges


def test_clean_win_passes_the_gate():
    """programmatic-tool-calling is the engine's anchor: claude-ahead, ranked, absence-of-evidence. The
    gate must pass it (reading the committed landscape or the seed fallback)."""
    gate = pb.verdict_gate("programmatic-tool-calling")
    assert gate.ok, gate.reason
    assert gate.verdict == "claude-ahead"
    assert gate.lead_basis in pb.PUBLISHABLE_LEAD_BASES


def test_slug_and_folder_key_both_resolve():
    """Both the live sweep slug (programmatic_tool_calling) and the built-edge folder name resolve to the same passing edge."""
    assert pb.verdict_gate("programmatic_tool_calling").ok
    assert pb.verdict_gate("programmatic-tool-calling").ok


@pytest.mark.parametrize("edge_key", [
    "eval-quality",        # within-claude grid, not a published cross-vendor lead
    "retention-resume",    # doc-grounded parity (managed bundle is the win, not a Claude-only resume)
    "cost-model",          # regime-bounded: the lead flips on the next price change
    "parity-gated",        # held behind a parity check, never pitched
])
def test_non_win_edges_are_refused(edge_key):
    """Each non-win edge must be refused by the gate (ok False), with a reason. These are exactly the
    keys the spec says must REFUSE."""
    gate = pb.verdict_gate(edge_key)
    assert not gate.ok, f"{edge_key} unexpectedly passed the gate: {gate.reason}"
    assert gate.reason


def test_unknown_edge_is_refused_not_crashed():
    gate = pb.verdict_gate("not-a-real-edge")
    assert not gate.ok
    assert "no edge record" in gate.reason


# --------------------------------------------------------------------------- the gate, on synthetic edges
# These pin the individual rules in isolation, so a future change to the seed table cannot silently
# loosen the gate.


def _synthetic_edge(monkeypatch, *, verdict, lead_score, lead_basis, key="programmatic-tool-calling"):
    edge = {
        "key": key, "axis": "cost", "verdict": verdict, "lead_score": lead_score,
        "fair_comparison": {"lead_basis": lead_basis},
    }
    monkeypatch.setattr(pb, "_find_edge", lambda k: (dict(edge), "synthetic"))
    # No receipt veto in the synthetic-edge rule tests: keep the receipt out of the way.
    monkeypatch.setattr(pb, "_receipt_path", lambda k: None)
    return edge


def test_behind_verdict_refused(monkeypatch):
    _synthetic_edge(monkeypatch, verdict="claude-behind", lead_score=5, lead_basis="head-to-head")
    assert not pb.verdict_gate("programmatic-tool-calling").ok


def test_parity_verdict_refused(monkeypatch):
    _synthetic_edge(monkeypatch, verdict="parity", lead_score=0, lead_basis="doc-grounded-parity")
    assert not pb.verdict_gate("programmatic-tool-calling").ok


def test_zero_lead_score_refused_even_if_claude_ahead(monkeypatch):
    _synthetic_edge(monkeypatch, verdict="claude-ahead", lead_score=0, lead_basis="absence-of-evidence")
    g = pb.verdict_gate("programmatic-tool-calling")
    assert not g.ok and "lead_score" in g.reason


def test_regime_bounded_lead_basis_refused(monkeypatch):
    """A claude-ahead, ranked edge with a non-publishable (regime-bounded or held) lead_basis is refused."""
    _synthetic_edge(monkeypatch, verdict="claude-ahead", lead_score=5, lead_basis="doc-grounded-parity")
    g = pb.verdict_gate("programmatic-tool-calling")
    assert not g.ok and "lead_basis" in g.reason


def test_cost_model_key_refused_even_if_mislabeled(monkeypatch):
    """The cost-model key is refused outright even if a record mislabels its lead_basis as publishable."""
    edge = {"key": "cost-model", "axis": "cost", "verdict": "claude-ahead", "lead_score": 9,
            "fair_comparison": {"lead_basis": "head-to-head"}}
    monkeypatch.setattr(pb, "_find_edge", lambda k: (dict(edge), "synthetic"))
    monkeypatch.setattr(pb, "_receipt_path", lambda k: None)
    g = pb.verdict_gate("cost-model")
    assert not g.ok and "regime-bounded" in g.reason


def test_private_only_demokind_refused_even_if_mislabeled_as_win(monkeypatch):
    edge = {
        "key": "cmek", "axis": "security", "demoKind": "security_posture",
        "verdict": "claude-ahead", "lead_score": 9,
        "fair_comparison": {"lead_basis": "head-to-head"},
    }
    monkeypatch.setattr(pb, "_find_edge", lambda k: (dict(edge), "synthetic"))
    monkeypatch.setattr(pb, "_receipt_path", lambda k: None)
    g = pb.verdict_gate("cmek")
    assert not g.ok
    assert "private-only" in g.reason


# --------------------------------------------------------------------------- the receipt veto


def test_disagreeing_receipt_vetoes(monkeypatch, tmp_path):
    """A present receipt that does NOT indicate a Claude win vetoes a green-landscape publish."""
    _synthetic_edge(monkeypatch, verdict="claude-ahead", lead_score=5, lead_basis="absence-of-evidence")
    bad = tmp_path / "last_programmatic_tool_calling.json"
    bad.write_text(json.dumps({"mode_b_correct": False, "verdict": "never-evaluated"}))
    monkeypatch.setattr(pb, "_receipt_path", lambda k: bad)
    g = pb.verdict_gate("programmatic-tool-calling")
    assert not g.ok and "veto" in g.reason.lower()


def test_agreeing_receipt_passes(monkeypatch, tmp_path):
    _synthetic_edge(monkeypatch, verdict="claude-ahead", lead_score=5, lead_basis="absence-of-evidence")
    good = tmp_path / "last_programmatic_tool_calling.json"
    good.write_text(json.dumps({"mode_b_correct": True, "pct_input_reduction": 28.0,
                                "mode_a": {"billed_input": 9451}, "mode_b": {"billed_input": 6828}}))
    monkeypatch.setattr(pb, "_receipt_path", lambda k: good)
    assert pb.verdict_gate("programmatic-tool-calling").ok


# --------------------------------------------------------------------------- shipped numbers come from the
# committed receipt-of-record, not the transient scratch json (the one-source-of-truth durable fix)


def test_committed_receipt_matches_the_gated_sample():
    """_committed_receipt parses edges/<folder>/sample.txt, the SAME committed file scripts/check_receipts.py
    checks, so a published brief quotes the receipt-of-record. The numbers and the honest correctness flags
    come straight off it: Mode A answered None (wrong), Mode B answered the true winner."""
    r = pb._committed_receipt(pb.PLANS["programmatic-tool-calling"])
    assert r is not None, "the committed edges/programmatic-tool-calling/sample.txt must parse"
    assert r["mode_a"]["billed_input"] == 9451
    assert r["mode_b"]["billed_input"] == 6828
    assert round(r["pct_input_reduction"]) == 28
    assert r["mode_a_correct"] is False, "the public table must never claim Mode A was correct"
    assert r["mode_b_correct"] is True


def test_committed_receipt_ignores_the_transient_json(monkeypatch):
    """The decoupling that fixes the drift: _committed_receipt never consults the transient receipt path,
    so a drifted or missing data/last_<edge>.json cannot move a published brief's numbers."""
    def boom(_k):
        raise AssertionError("_committed_receipt must not read the transient receipt path")
    monkeypatch.setattr(pb, "_receipt_path", boom)
    r = pb._committed_receipt(pb.PLANS["programmatic-tool-calling"])
    assert r["mode_a"]["billed_input"] == 9451 and r["mode_b"]["billed_input"] == 6828
    # and the generated receipt snapshot the gif replays carries those committed numbers, not a scratch run
    sample = pb._sample_source(pb.PLANS["programmatic-tool-calling"], r)
    assert "9,451" in sample and "6,828" in sample and "correct" not in sample


# --------------------------------------------------------------------------- write-nothing on refusal


def test_refusal_writes_nothing(tmp_path):
    """A refused publish leaves the briefs root untouched: no brief dir, no Makefile/README created."""
    # Seed a minimal root so the root-exists check passes and we are testing the gate refusal path.
    (tmp_path / "Makefile").write_text(".PHONY: help\n")
    (tmp_path / "README.md").write_text("# briefs\n")
    before = sorted(p.name for p in tmp_path.iterdir())
    rc = pb.publish("cost-model", tmp_path, "make publish-brief EDGE=cost-model")
    assert rc != 0
    after = sorted(p.name for p in tmp_path.iterdir())
    assert before == after, "a refused publish must not create or modify any file in the briefs root"
    assert not (tmp_path / "cost").exists() and not (tmp_path / "cost-model").exists()


def test_missing_briefs_root_writes_nothing(tmp_path):
    """A non-existent briefs root is an error that writes nothing."""
    missing = tmp_path / "does-not-exist"
    rc = pb.publish("programmatic-tool-calling", missing, "cmd")
    assert rc == 2
    assert not missing.exists()


# --------------------------------------------------------------------------- vendoring: no dangling imports


def test_import_swap_rewrites_engine_and_common_prefixes():
    src = ("from engine.demonstrators.token_core import run_mode\n"
           "from common.models import get\n"
           "from common.pricing import cost_usd\n")
    out = pb._swap_imports(src)
    assert "from .token_core import run_mode" in out
    assert "from .common.models import get" in out
    assert "from .common.pricing import cost_usd" in out
    pb._assert_no_dangling(out, "synthetic")  # must not raise


def test_dangling_engine_import_is_refused():
    with pytest.raises(pb.PublishRefused):
        pb._assert_no_dangling("from engine.providers import openai_arm\n", "synthetic")


def test_dangling_common_import_is_refused():
    with pytest.raises(pb.PublishRefused):
        pb._assert_no_dangling("from common.runner import call\n", "synthetic")


def test_vendored_engine_files_are_closure_clean():
    """Every file the PTC plan vendors imports only from its declared closure after the prefix swap, so a
    shipped brief never carries a dangling import. This is the static guarantee, checked without writing."""
    plan = pb.PLANS["programmatic-tool-calling"]
    for vf in plan.files:
        text = (pb.ROOT / vf.src).read_text()
        pb._assert_no_dangling(pb._swap_imports(text), vf.dst)  # must not raise
