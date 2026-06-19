"""Offline tests for the engine's always, ask, never boundary. They run with no key and
no network, and they assert the one thing the gated-outbound posture rests on: audit()
returns an empty list only when the unattended work was all measurement and drafting, and
flags any outward or non-always action that slipped into the loop.

The pattern is keyed to this engine's action set (sweep, diff, rank, draft, write, update
coverage as ALWAYS, the benchmark and edge scaffold as ASK, send and post and push and
overspend as NEVER)."""
from engine import gate


def test_clean_loop_has_no_violations():
    did = [{"id": "sweep_docs", "gate": gate.ALWAYS, "outward": False}]
    assert gate.audit(did) == []


def test_every_always_action_passes_unattended():
    did = [{"id": a.id, "gate": a.gate, "outward": a.outward} for a in gate.ALWAYS_ACTIONS]
    assert gate.audit(did) == []


def test_outward_action_is_caught():
    did = [{"id": "run_benchmark", "gate": gate.ASK, "outward": True}]
    violations = gate.audit(did)
    assert violations and any("run_benchmark" in v for v in violations)


def test_send_mail_is_caught_as_outward():
    did = [{"id": "send_mail", "gate": gate.NEVER, "outward": True}]
    violations = gate.audit(did)
    assert violations and any("send_mail" in v for v in violations)


def test_every_ask_and_never_action_is_caught():
    for a in gate.ASK_ACTIONS + gate.NEVER_ACTIONS:
        did = [{"id": a.id, "gate": a.gate, "outward": a.outward}]
        violations = gate.audit(did)
        assert violations, f"{a.id} ({a.gate}) ran unattended without being flagged"


def test_non_always_internal_action_still_flagged():
    # An ASK action with outward False must still be caught: changing the repo or the
    # spend is not an unattended motion even when nothing leaves the machine.
    did = [{"id": "scaffold_edge", "gate": gate.ASK, "outward": False}]
    violations = gate.audit(did)
    assert violations and any("non-always" in v for v in violations)


def test_boundary_has_three_buckets():
    b = gate.boundary()
    assert set(b) == {"always", "ask", "never"}
    assert b["always"] and b["ask"] and b["never"]


def test_no_always_action_is_outward():
    # The unattended set must never contain an outward action, by construction.
    assert all(not a.outward for a in gate.ALWAYS_ACTIONS)
