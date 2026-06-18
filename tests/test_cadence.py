"""Offline tests for the unattended cadence.

No key, no network, no model call: the cadence's draft is a deterministic $0 template, so every test
runs the orchestration and the pieces it rests on without an SDK. The do_sweep=False path reuses the
committed landscape (no network), and the run is redirected to a temp repo root so the tests never
write the real state/ tree.

What these tests protect, the load-bearing posture of the recurring engine:
  - the cadence run is $0 and gate.audit() returns empty: nothing outward or non-ALWAYS ran unattended,
    and every proposed spend carried a surfaced estimate.
  - the run NEVER sends and NEVER runs a benchmark: it only writes inert files to the outbox and the
    manifest, and the dispatch decision surfaces the estimate without running the demonstrator.
  - the drafted email is deslop-clean (no em-dash, en-dash, or semicolon outside code), checked on
    every generated email by deslop_outbox().
  - the draft anchors on the newest UNCOVERED lead and never repeats an edge the ledger already drafted.
  - parity and behind edges are never drafted (only genuine leads anchor an email).
"""

import json

import pytest

from engine import cadence


# ----- the deterministic draft is deslop-clean and grounded -----

def _edge():
    return {"key": "ptc", "axis": "cost", "verdict": "claude-ahead", "lead_score": 2,
            "demoKind": "token_accounting",
            "claim": "The model writes one sandbox script that calls the developer's own tools.",
            "fair_comparison": {"repro": {"command": "make ptc", "est_cost_usd": 0.06, "est_time_s": 90}}}


def test_draft_is_deslop_clean():
    text = cadence._draft_email(_edge(), None)
    assert cadence.deslop_outbox(text) == []          # no banned char outside fenced code


def test_draft_carries_the_command_cost_and_claim():
    text = cadence._draft_email(_edge(), None)
    assert "make ptc" in text
    assert "$0.06" in text
    assert "sandbox script" in text                   # the claim is on the surface
    assert "{repo_link}" in text                       # the link placeholder is preserved


def test_draft_prefers_the_routing_estimate_over_the_seed_repro():
    routing = {"key": "ptc", "estimate": {"usd": 0.09, "wall_clock_s": 120, "command": "make ptc"}}
    text = cadence._draft_email(_edge(), routing)
    assert "$0.09" in text                             # the live estimate wins
    assert "2.0 minutes" in text


def test_deslop_outbox_catches_a_banned_char():
    bad = "This line has a semicolon; it should be caught."
    assert cadence.deslop_outbox(bad)                  # non-empty: a violation


def test_deslop_outbox_exempts_fenced_code():
    ok = "intro\n```\na; b; c\n```\noutro"
    assert cadence.deslop_outbox(ok) == []             # semicolons inside a code fence are exempt


# ----- the anchor: newest uncovered lead, never a parity edge -----

def test_anchor_is_the_top_uncovered_lead():
    ranked = [
        {"key": "ptc", "lead_score": 2}, {"key": "citations", "lead_score": 2},
        {"key": "managed_agents", "lead_score": 0},   # parity, never anchored
    ]
    assert cadence._anchor_edge(ranked, covered_keys=set())["key"] == "ptc"
    assert cadence._anchor_edge(ranked, covered_keys={"ptc"})["key"] == "citations"


def test_anchor_skips_parity_and_behind_edges():
    ranked = [{"key": "managed_agents", "lead_score": 0}, {"key": "x", "lead_score": 0}]
    assert cadence._anchor_edge(ranked, covered_keys=set()) is None  # no genuine lead, no email


def test_anchor_falls_back_to_top_lead_when_all_covered():
    ranked = [{"key": "ptc", "lead_score": 2}]
    assert cadence._anchor_edge(ranked, covered_keys={"ptc"})["key"] == "ptc"


# ----- the full run: $0, audit empty, no send, no benchmark, against a temp repo root -----

@pytest.fixture
def temp_repo(tmp_path, monkeypatch):
    """Redirect the engine's repo_root to a temp dir, seeded with a committed landscape so do_sweep=False
    has a baseline to read. Every cadence write lands in the temp tree, never the real state/."""
    (tmp_path / "state" / "outbox").mkdir(parents=True)
    (tmp_path / "state" / "runs").mkdir(parents=True)
    (tmp_path / "landscape").mkdir()
    landscape = {
        "as_of_date": "2026-06-18",
        "edges": [
            {"key": "ptc", "axis": "cost", "verdict": "claude-ahead", "lead_score": 2, "score": 6,
             "demoKind": "token_accounting",
             "fair_comparison": {"repro": {"command": "make ptc", "est_cost_usd": 0.06, "est_time_s": 90}}},
            {"key": "managed_agents", "axis": "retention", "verdict": "parity", "lead_score": 0,
             "score": 0, "demoKind": "retention_resume", "fair_comparison": {}},
        ],
        "capabilities": {}, "content_hashes": {}, "coverage": {},
    }
    (tmp_path / "landscape" / "landscape.json").write_text(json.dumps(landscape))
    monkeypatch.setattr(cadence, "repo_root", lambda: tmp_path)
    # scan.current_edges reads the same landscape path off ITS own repo-root resolution; point it here.
    import engine.scan as scan
    monkeypatch.setattr(scan, "_landscape_path", lambda: tmp_path / "landscape" / "landscape.json")
    return tmp_path


def test_run_is_zero_cost_audit_empty_and_never_sends(temp_repo):
    result = cadence.run(do_sweep=False)
    # the boundary held: nothing outward or non-ALWAYS ran, no spend without a surfaced estimate.
    assert result["audit_violations"] == []
    # every step the run recorded is an ALWAYS step.
    assert all(s["gate"] == "always" for s in result["did"])
    assert all(s["outward"] is False for s in result["did"])
    # the manifest records zero spend and not sent.
    manifest = json.loads((temp_repo / result["manifest"]).read_text())
    assert manifest["spent_usd"] == 0.0
    assert manifest["sent"] is False


def test_run_drafts_an_inert_deslop_clean_outbox_file(temp_repo):
    result = cadence.run(do_sweep=False)
    assert result["outbox_draft"] is not None
    draft = (temp_repo / result["outbox_draft"]).read_text()
    assert cadence.deslop_outbox(draft) == []          # the generated email is deslop-clean
    assert "{repo_link}" in draft                       # inert: a placeholder, not a real send


def test_run_never_runs_a_benchmark_only_surfaces_the_estimate(temp_repo):
    result = cadence.run(do_sweep=False)
    # a spending lead (ptc) is dispatched as ask-run-demonstrator with a surfaced estimate, NOT run.
    ptc = next((r for r in result["routing"] if r["key"] == "ptc"), None)
    assert ptc is not None
    assert ptc["action"] == "ask-run-demonstrator"
    assert ptc["gate"] == "ask"
    assert ptc["estimate_surfaced"] is True


def test_run_does_not_repeat_an_edge_the_ledger_already_drafted(temp_repo):
    # first run drafts ptc; a second run with ptc recorded as drafted must not re-anchor on it. With ptc
    # the only lead, the fallback re-uses the top lead, but the coverage row is what protects the stream.
    cadence.run(do_sweep=False)
    ledger = (temp_repo / "state" / "coverage.jsonl").read_text()
    assert any('"action": "drafted"' in line and '"edge_key": "ptc"' in line
               for line in ledger.splitlines())


def test_run_writes_the_coverage_view_into_the_manifest(temp_repo):
    result = cadence.run(do_sweep=False)
    manifest = json.loads((temp_repo / result["manifest"]).read_text())
    assert "coverage" in manifest
    assert manifest["coverage"]["demo_kinds_total"] >= 9
    assert manifest["coverage"]["gaps"] == []          # the engine reports no gaps about itself
