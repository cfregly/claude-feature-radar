"""Offline tests for the retention_resume demonstrator.

No key, no network, no SDK, no Managed Agents spend: every test drives the deterministic pieces (the
_drain event consumer with a fake stream, the continuity gate, the doc-grounded receipt) and the
demonstrator interface against synthetic in-memory results, so the parity verdict, the within-Claude
live verdict, and the honesty contract are proven without a live call. The live kill-and-resume (the
real Managed Agents session) is exercised only by `make retention-live`, which spends; these tests
protect the logic that run depends on and, above all, that the verdict is NEVER claude-ahead.

What these tests protect:
  - the demonstrator registers under retention_resume and dispatch routes managed_agents + memory_tool
    to it; the DEFAULT path is a $0 always-gated demonstrator (no Managed Agents spend).
  - the default verdict is doc-grounded PARITY, never claude-ahead (the managedAgentsCorrection):
    durable kill-and-resume is table stakes, so the win is the bundle + time axis, labeled beta.
  - run_competitor_arms returns no arm (a parity capability has no head-to-head arm to run), and the
    receipt can therefore never read a claude-ahead verdict.
  - the live opt-in folds in a kill-resume continuity proof whose verdict is within-claude-only, and
    the continuity gate (events replayed, sandbox files present, negative control recovered nothing)
    decides pass/fail; a negative control that recovers something fails the gate.
  - the doc-grounded retention table names all three vendors with dated sources and the beta header.
  - _drain skips the replayed events (by id) and captures the bash tool output on resume.
"""

from engine.demonstrators import retention_resume as rr
from engine.demonstrators.base import Arm
from engine.demonstrators.registry import REGISTRY, dispatch, register_all


# ----- registration + dispatch -----

def test_retention_resume_registers():
    register_all()
    demo = REGISTRY.get("retention_resume")
    assert demo is not None
    assert demo.demo_kind == "retention_resume"


def test_dispatch_routes_managed_agents_to_retention_resume_as_a_zero_cost_always():
    register_all()
    r = dispatch({"key": "managed_agents", "axis": "reliability"})
    assert r.covered is True
    assert r.demo_kind == "retention_resume"
    # the DEFAULT path spends nothing (the live kill-resume is the opt-in), so it is an ALWAYS, not ASK.
    assert r.estimate is not None and r.estimate.usd == 0.0
    assert r.gate == "always"
    assert r.estimate.command == "make retention"


def test_dispatch_routes_memory_tool_to_retention_resume():
    register_all()
    r = dispatch({"key": "memory_tool", "axis": "reliability"})
    assert r.demo_kind == "retention_resume"
    assert r.covered is True


# ----- the default verdict is doc-grounded parity, NEVER claude-ahead -----

def test_default_verdict_is_doc_grounded_parity_never_claude_ahead():
    d = rr.RetentionResumeDemonstrator()
    claude = d.run_claude_arm({}, {})
    comps = d.run_competitor_arms({}, {})
    v = d.score(claude, comps, {})
    assert v.verdict == "parity"            # never claude-ahead: kill-and-resume is table stakes
    assert v.passed is True                 # the doc-grounded comparison is complete (table present)
    assert "doc-grounded-parity" in v.metric.get("verdict_basis", "")


def test_no_competitor_arm_runs_for_a_parity_capability():
    # A parity capability has no head-to-head arm to run (it would only re-show parity), so the arm list
    # is empty by design, which is also what keeps the receipt from ever reading claude-ahead.
    d = rr.RetentionResumeDemonstrator()
    assert d.run_competitor_arms({}, {}) == []


def test_receipt_default_is_parity_with_three_dated_grounding_rows():
    d = rr.RetentionResumeDemonstrator()
    claude = d.run_claude_arm({}, {})
    v = d.score(claude, [], {})
    edge = {"key": "managed_agents", "axis": "reliability", "demoKind": "retention_resume",
            "fair_comparison": {"lead_basis": "doc-grounded-parity"}, "claim": "durable resume"}
    receipt = d.receipt(edge, claude, [], v, {"estimate": {"usd": 0.0, "command": "make retention"}})
    assert receipt.verdict == "parity"
    assert receipt.demo_kind == "retention_resume"
    assert len(receipt.grounding) == 3                      # Claude, OpenAI, Gemini, each dated
    assert all(g.get("date") == "2026-06-18" for g in receipt.grounding)
    assert "NOT eval quality" in receipt.workload.get("scope", "")


def test_receipt_never_claims_claude_ahead_even_with_a_claude_ahead_proposal():
    # Belt and suspenders: even if a buggy caller hands score() a claude-ahead Verdict, the demonstrator
    # never runs a competitor arm, so the base honesty contract holds the verdict (it cannot be
    # claude-ahead with zero competitor arms run). This is the managedAgentsCorrection, enforced.
    from engine.demonstrators.base import Verdict
    d = rr.RetentionResumeDemonstrator()
    claude = d.run_claude_arm({}, {})
    rogue = Verdict(verdict="claude-ahead", passed=True, metric={})
    edge = {"key": "managed_agents", "axis": "reliability", "demoKind": "retention_resume",
            "fair_comparison": {"lead_basis": "doc-grounded-parity"}, "claim": "x"}
    receipt = d.receipt(edge, claude, [], rogue, {"estimate": {}})
    assert receipt.verdict == "never-evaluated"            # downgraded: no competitor arm ran


# ----- the doc-grounded retention table -----

def test_retention_table_names_all_three_vendors_with_sources():
    receipt = rr.grounded_receipt()
    vendors = {row["vendor"] for row in receipt["retention_table"]}
    assert vendors == {"Claude", "OpenAI", "Gemini"}
    for row in receipt["retention_table"]:
        assert row["source_url"].startswith("http")
        assert row["date"] == "2026-06-18"
    assert receipt["beta_header"] == "managed-agents-2026-04-01"
    assert receipt["not_zdr_eligible"] is True


def test_grounded_receipt_has_no_live_run_by_default():
    # the default $0 path runs nothing live.
    assert rr.grounded_receipt()["live_run"] is None


# ----- the live opt-in: within-claude-only, gated by the continuity check -----

def _live(*, replayed=4, files=True, neg_recovered=False, recovered=True, steer=2):
    return {
        "started": {"new_event_ids": [f"e{i}" for i in range(replayed)]},
        "resumed": {"recovered": recovered, "events_replayed_on_resume": replayed,
                    "sandbox_files_present": files, "resume_wall_clock_gap_s": 12.3},
        "negative_control": {"recovered": neg_recovered},
        "steered": {"tools_used": ["bash"] * steer},
    }


def test_continuity_gate_passes_a_clean_kill_resume():
    passed, checks = rr.continuity_passed(_live())
    assert passed is True
    assert checks["events_replayed"] == 4
    assert checks["sandbox_files_present"] is True
    assert checks["negative_control_recovered"] is False


def test_continuity_gate_fails_when_the_negative_control_recovers_something():
    # if a wrong session id recovered state, the clean resume is not attributable to server-side
    # persistence, so the receipt must not pass.
    passed, _ = rr.continuity_passed(_live(neg_recovered=True))
    assert passed is False


def test_continuity_gate_fails_when_the_sandbox_files_did_not_survive():
    passed, _ = rr.continuity_passed(_live(files=False))
    assert passed is False


def test_continuity_gate_fails_when_no_events_replayed():
    passed, _ = rr.continuity_passed(_live(replayed=0))
    assert passed is False


def test_live_verdict_is_within_claude_only_never_claude_ahead():
    d = rr.RetentionResumeDemonstrator()
    spec = {"live": _live()}
    claude = d.run_claude_arm({}, spec)
    v = d.score(claude, d.run_competitor_arms({}, spec), spec)
    assert v.verdict == "within-claude-only"   # a continuity + bundle proof, never a head-to-head lead
    assert v.passed is True
    edge = {"key": "managed_agents", "axis": "reliability", "demoKind": "retention_resume",
            "fair_comparison": {"lead_basis": "doc-grounded-parity"}, "claim": "x"}
    receipt = d.receipt(edge, claude, [], v, {"estimate": {"usd": 1.5, "command": "make retention-live"}})
    assert receipt.verdict == "within-claude-only"
    # the receipt carries the per-check continuity numbers (events replayed, files present, neg control)
    assert receipt.metric.get("live_continuity", {}).get("events_replayed") == 4
    assert receipt.metric.get("live_continuity", {}).get("negative_control_recovered") is False
    # the Claude arm carries the rolled-up pass flag.
    assert claude.metric.get("live_continuity_passed") is True


def test_live_estimate_is_the_opt_in_spend():
    d = rr.RetentionResumeDemonstrator()
    est = d.estimate({}, {"live": _live()})
    assert est.usd > 0                      # the live run spends a small bounded amount
    assert est.usd <= 6.0                   # well under the per-demonstrator cap
    assert est.command == "make retention-live"


# ----- _drain skips replayed events and captures bash output (the port's mechanics) -----

class _Event:
    def __init__(self, eid, etype, **kw):
        self.id, self.type = eid, etype
        for k, v in kw.items():
            setattr(self, k, v)


def test_drain_skips_replayed_event_ids_and_captures_tool_output():
    # a fake stream: one replayed event (must be skipped), one new tool_result with the ledger line,
    # then idle. _drain must skip the seen id and surface the bash output so the files-present check works.
    stream = [
        _Event("old1", "agent.message", content=[]),                       # replayed, skipped by id
        _Event("new1", "agent.tool_use", name="bash"),
        _Event("new2", "agent.tool_result", content="step-a done\nstep-b done"),
        _Event("new3", "session.status_idle"),
    ]
    drained = rr._drain(stream, max_events=400, seen_ids={"old1"})
    assert "old1" not in drained["new_event_ids"]
    assert "new1" in drained["new_event_ids"]
    assert "bash" in drained["tools_used"]
    assert "step-a done" in drained["tool_output"]
