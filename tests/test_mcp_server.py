"""Offline boundary tests for the MCP tool surface, the twin of tests/test_gate.py.

They run with no key, no network, and no MCP SDK installed: every test drives engine/mcp_tools.py (the
SDK-free logic layer), never engine/mcp_server.py (the thin FastMCP wrapper that needs the optional
package). The one thing they protect is the load-bearing safety property the cadence already holds, now
carried onto the chat surface: an unattended caller can never send, post, push, or spend, because the
ASK tools refuse until a human passes confirm=True and the send, post, and push actions are not exposed
as tools at all.

A second, structural guard runs through every benchmark test: subprocess.run is replaced with a raiser
by an autouse fixture, so no test in this file can ever actually spend, even by mistake.
"""

import json

import pytest

from engine import gate
from engine import mcp_tools as mt
from engine.publish_brief import GateResult


# A subprocess that explodes, wired in everywhere by default: no test may ever run a real benchmark.
@pytest.fixture(autouse=True)
def _no_real_spend(monkeypatch):
    def boom(*a, **k):
        raise AssertionError("a boundary test tried to actually run a benchmark (subprocess.run)")
    monkeypatch.setattr(mt.subprocess, "run", boom)


# --------------------------------------------------------------------------- the tier registry


def test_every_tool_is_always_or_ask_never_a_never():
    """Every exposed tool sits in the ALWAYS or ASK lane. The NEVER lane has no tool, by design."""
    for t in mt.TOOLS:
        assert t.tier in (gate.ALWAYS, gate.ASK), f"{t.name} has an unexpected tier {t.tier!r}"


def test_always_tools_are_internal_free_and_need_no_confirmation():
    for t in mt.TOOLS:
        if t.tier == gate.ALWAYS:
            assert t.outward is False, f"{t.name} is ALWAYS but outward"
            assert t.spends is False, f"{t.name} is ALWAYS but spends"
            assert t.confirm_required is False, f"{t.name} is ALWAYS but needs confirmation"


def test_ask_tools_require_confirmation_and_are_outward_or_spend():
    for t in mt.TOOLS:
        if t.tier == gate.ASK:
            assert t.confirm_required is True, f"{t.name} is ASK but runs without confirmation"
            assert t.outward or t.spends, f"{t.name} is ASK but neither outward nor spends"


def test_no_tool_maps_to_a_never_action():
    """The send, post, push, and overspend actions are refused by design and have no tool. Assert no
    tool name collides with a NEVER action id, the absence-of-capability boundary made mechanical."""
    never_ids = {a.id for a in gate.NEVER_ACTIONS}
    tool_names = {t.name for t in mt.TOOLS}
    assert never_ids.isdisjoint(tool_names), f"a NEVER action is exposed as a tool: {never_ids & tool_names}"


# --------------------------------------------------------------------------- the audit (the boundary)


def test_unattended_surface_passes_the_audit():
    """The MCP-surface twin of test_gate.test_every_always_action_passes_unattended: the set of actions
    an unattended caller can take with no human token is all ALWAYS and nothing outward, so audit() is
    empty."""
    assert mt.audit_unattended() == []
    assert gate.audit(mt.unattended_did()) == []


def test_show_boundary_reports_the_boundary_held():
    b = mt.show_boundary()
    assert b["boundary_held"] is True
    assert b["unattended_audit_violations"] == []
    assert set(b["gate"]) == {"always", "ask", "never"}
    # the send/post/push actions are named in the boundary but are not tools
    assert "send_mail" in b["never_actions_have_no_tool"]


def test_every_confirm_gated_action_is_caught_if_run_unattended():
    """The other direction, the twin of test_gate.test_every_ask_and_never_action_is_caught: if a
    confirm-gated tool were ever (wrongly) treated as unattended, the audit must flag it. This proves
    the gate would catch a regression that made an ASK tool auto-runnable."""
    flagged = gate.audit(mt.confirm_gated_did())
    names = {t.name for t in mt.TOOLS if t.confirm_required}
    assert names, "there must be confirm-gated tools to protect"
    for n in names:
        assert any(n in v for v in flagged), f"{n} would not be caught if it ran unattended"


# --------------------------------------------------------------------------- publish_brief (ASK)


def test_publish_brief_without_confirm_refuses_a_held_edge():
    """Task budgets has a receipt, but the current adversarial report holds the framing."""
    r = mt.publish_brief("task-budgets", confirm=False)
    assert r["gate_ok"] is False
    assert r["published"] is False
    assert r["refused"] is True
    assert r["spent_usd"] == 0.0
    assert r["pushed"] is False and r["sent"] is False


def test_publish_brief_preview_writes_nothing_when_gate_is_clean(monkeypatch):
    monkeypatch.setattr(mt, "verdict_gate", lambda edge: GateResult(
        True, edge, "claude-ahead", "head-to-head", "synthetic", "ok"))
    r = mt.publish_brief("programmatic-tool-calling", confirm=False)
    assert r["gate_ok"] is True
    assert r["published"] is False
    assert r["requires_confirmation"] is True


def test_publish_brief_refuses_a_regime_bounded_edge_even_with_confirm():
    """cost-model is regime-bounded: the gate refuses it, and a refusal writes nothing, confirm or not."""
    r = mt.publish_brief("cost-model", confirm=True)
    assert r["gate_ok"] is False
    assert r["published"] is False
    assert r["refused"] is True


def test_publish_brief_with_confirm_routes_to_the_writer_only_on_a_clean_gate(monkeypatch, tmp_path):
    """confirm=True flips behavior: it calls the publisher. We stub the writer (so the real hits repo
    is untouched) and point the target at a temp dir, and assert the tool reports what the writer did.
    The point is that confirm is what unlocks the write, never an unattended call."""
    calls = {}

    def fake_publish(edge, briefs_root, command):
        calls["edge"] = edge
        (briefs_root / "programmatic_tool_calling").mkdir(parents=True, exist_ok=True)
        (briefs_root / "programmatic_tool_calling" / "README.md").write_text("# brief\n")
        return 0

    monkeypatch.setattr(mt, "verdict_gate", lambda edge: GateResult(
        True, edge, "claude-ahead", "head-to-head", "synthetic", "ok"))
    monkeypatch.setattr(mt, "publish", fake_publish)
    monkeypatch.setattr(mt, "_briefs_root", lambda: tmp_path)
    r = mt.publish_brief("programmatic-tool-calling", confirm=True)
    assert calls["edge"] == "programmatic-tool-calling"
    assert r["published"] is True
    assert r["pushed"] is False and r["sent"] is False
    assert any("README.md" in w for w in r["wrote"])


# --------------------------------------------------------------------------- run_benchmark (ASK, spends)


def test_run_benchmark_without_confirm_returns_an_estimate_and_spends_nothing():
    r = mt.run_benchmark("programmatic-tool-calling", confirm=False)
    assert r["ran"] is False
    assert r["spent_usd"] == 0.0
    assert r["requires_confirmation"] is True
    assert r["estimate"]["est_cost_usd"] > 0
    assert r["pushed"] is False and r["sent"] is False


def test_run_benchmark_over_the_cap_is_refused_and_does_not_spend():
    """An estimate over max_usd is refused with an ask-to-raise, before any key check or subprocess."""
    r = mt.run_benchmark("programmatic-tool-calling", confirm=True, max_usd=0.01)
    assert r["ran"] is False and r["spent_usd"] == 0.0
    assert r["refused"] is True
    assert "cap" in r["message"].lower()


def test_run_benchmark_negative_cap_is_refused_cleanly():
    """A negative max_usd is invalid input and is refused with a clear message, never a confusing
    over-the-cap refusal, and it never spends."""
    r = mt.run_benchmark("programmatic-tool-calling", confirm=True, max_usd=-1.0)
    assert r["ran"] is False and r["spent_usd"] == 0.0
    assert r["refused"] is True
    assert "non-negative" in r["message"].lower()


def test_run_benchmark_over_the_hard_ceiling_is_refused_outright(monkeypatch):
    """An estimate over the hard ceiling is refused no matter how high max_usd is, the overspend lane."""
    monkeypatch.setattr(mt, "_benchmark_plan", lambda e: {
        "command": "make demo", "est_cost_usd": 9.99, "est_time_s": 600, "verdict": "x", "axis": "y"})
    r = mt.run_benchmark("anything", confirm=True, max_usd=1000.0)
    assert r["ran"] is False and r["spent_usd"] == 0.0
    assert r["refused"] is True
    assert "hard ceiling" in r["message"].lower()


def test_run_benchmark_with_confirm_but_no_key_refuses_before_spending(monkeypatch):
    """confirm + an in-cap estimate but no key: refuse before the subprocess, never spend. load_env is
    stubbed so the engine .env cannot quietly supply a key during the test."""
    monkeypatch.setattr(mt, "load_env", lambda: None)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    r = mt.run_benchmark("programmatic-tool-calling", confirm=True, max_usd=1.0)
    assert r["ran"] is False and r["spent_usd"] == 0.0
    assert r["refused"] is True
    assert "anthropic_api_key" in r["message"].lower()


def test_run_benchmark_run_path_uses_a_make_argv_and_never_a_shell(monkeypatch):
    """The only place a spend can happen: confirm, in-cap, key present. We stub the subprocess to prove
    the wiring (a make argv, no shell) without spending a cent."""
    monkeypatch.setattr(mt, "_benchmark_plan", lambda e: {
        "command": "make eval-smoke", "est_cost_usd": 0.02, "est_time_s": 30, "verdict": "x", "axis": "y"})
    monkeypatch.setattr(mt, "load_env", lambda: None)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-not-real")
    seen = {}

    class _Done:
        returncode = 0
        stdout = "ran ok\n"
        stderr = ""

    def fake_run(argv, **kwargs):
        seen["argv"] = argv
        seen["shell"] = kwargs.get("shell", False)
        return _Done()

    monkeypatch.setattr(mt.subprocess, "run", fake_run)
    r = mt.run_benchmark("eval-quality", confirm=True, max_usd=1.0)
    assert r["ran"] is True
    assert r["exit_code"] == 0
    assert r["spent_usd"] == 0.02  # the run path reports the spend, like every other path reports $0
    assert seen["argv"] == ["make", "eval-smoke"]
    assert seen["shell"] is False


def test_benchmark_argv_rejects_an_unknown_command():
    """A repro command that is not a make target or a run.py subcommand is never turned into an argv,
    so a stray command string can never become an arbitrary shell call."""
    assert mt._benchmark_argv("rm -rf /") is None
    assert mt._benchmark_argv("curl http://evil") is None
    assert mt._benchmark_argv("make citations") == ["make", "citations"]


# --------------------------------------------------------------------------- read tools are safe and shaped


def test_list_edges_is_read_only_and_returns_rows():
    r = mt.list_edges(leads_only=True)
    assert "edges" in r and isinstance(r["edges"], list)
    for row in r["edges"]:
        assert row.get("lead_score", 0) > 0


def test_list_edges_caps_the_row_count_and_treats_negatives_as_all():
    capped = mt.list_edges(limit=3)
    assert len(capped["edges"]) <= 3
    full = mt.list_edges(limit=0)
    neg = mt.list_edges(limit=-5)
    assert len(neg["edges"]) == len(full["edges"])  # a negative limit means all, never a silent miscap


def test_list_edges_unknown_verdict_is_a_clear_error_not_a_silent_empty():
    r = mt.list_edges(verdict="not-a-verdict")
    assert r["count"] == 0 and r["edges"] == []
    assert "error" in r and "valid_verdicts" in r
    # a real verdict still filters normally
    ok = mt.list_edges(verdict="claude-ahead")
    assert "error" not in ok


def test_show_landscape_and_coverage_are_read_only_shapes():
    land = mt.show_landscape()
    assert "by_verdict" in land and "top_leads" in land
    cov = mt.show_coverage(ledger_tail=3)
    assert "rows" in cov and "ledger_tail" in cov
    assert len(cov["ledger_tail"]) <= 3


# --------------------------------------------------------------------------- run_discovery is $0 and audited


@pytest.fixture
def temp_repo(tmp_path, monkeypatch):
    """Redirect the cadence's repo_root to a temp dir seeded with a committed landscape, so run_discovery
    runs the real loop offline (sweep=False) and writes only into the temp tree. Mirrors the fixture in
    tests/test_cadence.py."""
    from engine import cadence
    import engine.scan as scan

    (tmp_path / "state" / "outbox").mkdir(parents=True)
    (tmp_path / "state" / "runs").mkdir(parents=True)
    (tmp_path / "landscape").mkdir()
    landscape = {
        "as_of_date": "2026-06-18",
        "edges": [
            {"key": "programmatic_tool_calling", "axis": "cost", "verdict": "claude-ahead",
             "lead_score": 2, "score": 6, "demoKind": "token_accounting",
             "fair_comparison": {"lead_basis": "head-to-head", "task_shape": "fan-out",
                                 "score_gate": "tokens lower",
                                 "repro": {"command": "make programmatic-tool-calling",
                                           "est_cost_usd": 0.08, "est_time_s": 90}}},
            {"key": "managed_agents", "axis": "reliability", "verdict": "parity", "lead_score": 0,
             "score": 0, "demoKind": "retention_resume", "fair_comparison": {}},
        ],
        "capabilities": {}, "content_hashes": {}, "coverage": {},
    }
    (tmp_path / "landscape" / "landscape.json").write_text(json.dumps(landscape))
    (tmp_path / "landscape" / "adversarial.json").write_text(json.dumps({
        "reports": [{
            "judge": "openai",
            "verdicts": [{"key": "programmatic_tool_calling", "verdict": "SURVIVES", "why": "ok"}],
        }]
    }))
    monkeypatch.setattr(cadence, "repo_root", lambda: tmp_path)
    monkeypatch.setattr(scan, "_landscape_path", lambda: tmp_path / "landscape" / "landscape.json")
    return tmp_path


def test_run_discovery_is_zero_cost_audited_and_never_outward(temp_repo):
    r = mt.run_discovery(sweep=False)
    assert r["ok"] is True
    assert r["audit_violations"] == []
    assert r["spent_usd"] == 0.0
    assert r["sent"] is False and r["pushed"] is False
    # it drafted to the inert outbox, never sent
    assert r["outbox_draft"] is not None
