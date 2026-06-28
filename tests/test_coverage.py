"""Offline tests for the per-demoKind coverage view.

No key, no network, no model call: the coverage view is a deterministic read over the demoKind
taxonomy, the live REGISTRY, and the committed edges/ tree. These tests protect that every canonical
demoKind is reported, that the built kinds show their bundle and a registered demonstrator, and that
the gap logic does not flag the intrinsic discovery_loop (proven by the cadence itself, not a plugin)
or the parity-gated "other" holding pen.
"""

from engine import coverage as cov
from engine.demokinds import DEMO_KINDS
from engine.demonstrators.registry import register_all


def test_coverage_reports_every_canonical_demokind():
    register_all()
    rows = cov.coverage()
    assert {r["demo_kind"] for r in rows} == set(DEMO_KINDS)
    assert len(rows) == len(DEMO_KINDS)


def test_public_kinds_report_a_bundle_and_internal_kinds_register_without_one():
    register_all()
    by_kind = {r["demo_kind"]: r for r in cov.coverage()}
    # The public kinds ship a built bundle (README + sample + emails) and a registered demonstrator.
    for kind in ("token_accounting", "grounding_resolution", "long_horizon_survival",
                 "code_execution_state"):
        assert by_kind[kind]["registered"] is True
        assert by_kind[kind]["has_bundle"] is True
        assert by_kind[kind]["bundle"]                # the edges/<dir> name
    # The internal kinds have a registered demonstrator but ship no public bundle (the publish gate
    # refuses them as regime-bounded or parity); the analysis runs and is kept local, never a gap.
    for kind in ("eval_quality", "retention_resume", "cost", "security_posture", "other"):
        assert by_kind[kind]["registered"] is True
    assert by_kind["agent_runtime_operations"]["registered"] is True


def test_port_status_labels_match_the_framework_asset_mapping():
    by_kind = {r["demo_kind"]: r for r in cov.coverage()}
    assert by_kind["token_accounting"]["port_status"] == "exists"
    assert by_kind["code_execution_state"]["port_status"] == "build"
    assert by_kind["eval_quality"]["port_status"] == "adapt"
    assert by_kind["retention_resume"]["port_status"] == "adapt"
    assert by_kind["agent_runtime_operations"]["port_status"] == "adapt"
    assert by_kind["cost"]["port_status"] == "build"
    assert by_kind["security_posture"]["port_status"] == "build"
    assert by_kind["other"]["port_status"] == "build"


def test_gaps_do_not_flag_discovery_loop_or_internal_kinds():
    register_all()
    rows = cov.coverage()
    g = cov.gaps(rows)
    # discovery_loop is intrinsic (the cadence proves it, not a plugin); the internal kinds ship no
    # public bundle by design (the publish gate refuses them). None of these is a gap.
    assert not any("discovery_loop" in line for line in g)
    for kind in ("other", "cost", "eval_quality", "retention_resume", "agent_runtime_operations",
                 "security_posture"):
        assert not any(line.startswith(f"{kind}:") for line in g)


def test_manifest_summarizes_by_port_status_and_lists_gaps():
    m = cov.manifest()
    assert m["demo_kinds_total"] == len(DEMO_KINDS)
    assert m["registered"] >= 7                       # every plugin kind registers
    assert set(m["by_port_status"]) == {"exists", "adapt", "build"}
    assert "cost" in m["by_port_status"]["build"]
    assert "eval_quality" in m["by_port_status"]["adapt"]
    assert isinstance(m["gaps"], list)


def test_no_gaps_when_every_plugin_kind_is_covered():
    # The engine has a demonstrator for every plugin demoKind and a bundle for every built one,
    # so the engine should report no gaps about itself.
    register_all()
    assert cov.gaps() == []
