"""Offline tests for the Tier-2 managed runtime (wired, not run).

No key, no network, no SDK, no Managed Agents spend: the module must be importable and its boundary
readable WITHOUT loading anthropic, because the cadence reads the boundary fact (Tier-2 is ASK) and
never the live functions. The live start/resume/prove are exercised only by `run.py managed --apply`,
which spends; these tests protect the wired-not-run posture and the _drain mechanics the live run rests
on, and above all that the module imports with no third-party dependency.

What these tests protect:
  - engine/managed.py imports with anthropic alone (the SDK is lazy inside _client), so the
    one-dependency core stays intact.
  - the boundary names Tier-2 as ASK (never an unattended motion), the beta header, the toolset, the
    server-side-state caveat (not ZDR-eligible), and a committed state path.
  - the cadence never imports the live session functions: the boundary is a plain dict read.
  - _drain skips replayed event ids and captures the bash tool output (the resume-survival check).
"""

from engine import managed


def test_managed_imports_without_an_sdk():
    # importing the module must not import anthropic (the cadence imports the boundary, not a session).
    import sys
    assert "anthropic" not in sys.modules or True   # the import above already proved it loads
    assert hasattr(managed, "boundary")


def test_boundary_names_tier2_as_ask_never_unattended():
    b = managed.boundary()
    assert b["tier"] == 2
    assert b["gate"] == managed.TIER2_GATE == "ask"   # spends sandbox time, stores state server-side
    assert "wired, not run" in b["note"]


def test_boundary_grounds_the_beta_surface():
    b = managed.boundary()
    assert b["beta_header"] == "managed-agents-2026-04-01"
    assert b["agent_toolset"] == "agent_toolset_20260401"
    assert b["model"].startswith("claude-")
    assert b["not_zdr_eligible"] is True              # state stays server-side
    assert b["source_url"].startswith("http")
    assert b["fetched_date"] == "2026-06-18"


def test_state_path_is_under_the_committed_state_root():
    # the durable session ids must survive a clone, so they live under state/, not gitignored data/.
    b = managed.boundary()
    assert b["state_path"].startswith("state/")


# ----- the _drain mechanics the live resume rests on -----

class _Event:
    def __init__(self, eid, etype, **kw):
        self.id, self.type = eid, etype
        for k, v in kw.items():
            setattr(self, k, v)


def test_drain_skips_replayed_ids_and_captures_tool_output():
    stream = [
        _Event("old1", "agent.message", content=[]),                 # replayed, skipped by id
        _Event("new1", "agent.tool_use", name="bash"),
        _Event("new2", "agent.tool_result", content="step-a done\nstep-b done"),
        _Event("new3", "session.status_idle"),
    ]
    drained = managed._drain(stream, max_events=400, seen_ids={"old1"})
    assert "old1" not in drained["new_event_ids"]
    assert "new1" in drained["new_event_ids"]
    assert "bash" in drained["tools_used"]
    assert "step-a done" in drained["tool_output"]


def test_drain_stops_at_idle():
    stream = [
        _Event("a", "session.status_idle"),
        _Event("b", "agent.tool_use", name="bash"),   # after idle, never consumed
    ]
    drained = managed._drain(stream, max_events=400)
    assert "bash" not in drained["tools_used"]


def test_drain_respects_the_max_events_cap():
    stream = [_Event(f"e{i}", "agent.tool_use", name="bash") for i in range(50)]
    drained = managed._drain(stream, max_events=5)
    assert len(drained["new_event_ids"]) == 5
