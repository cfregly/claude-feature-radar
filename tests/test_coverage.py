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


def test_built_kinds_report_a_bundle_and_a_registered_demonstrator():
    register_all()
    by_kind = {r["demo_kind"]: r for r in cov.coverage()}
    for kind in ("token_accounting", "grounding_resolution", "long_horizon_survival",
                 "eval_quality", "retention_resume", "cost"):
        assert by_kind[kind]["registered"] is True
        assert by_kind[kind]["has_bundle"] is True
        assert by_kind[kind]["bundle"]                # the edges/<dir> name


def test_port_status_labels_match_the_framework_asset_mapping():
    by_kind = {r["demo_kind"]: r for r in cov.coverage()}
    assert by_kind["token_accounting"]["port_status"] == "exists"
    assert by_kind["eval_quality"]["port_status"] == "adapt"
    assert by_kind["retention_resume"]["port_status"] == "adapt"
    assert by_kind["cost"]["port_status"] == "build"
    assert by_kind["other"]["port_status"] == "build"


def test_gaps_do_not_flag_discovery_loop_or_other():
    register_all()
    rows = cov.coverage()
    g = cov.gaps(rows)
    # discovery_loop is intrinsic (the cadence proves it, not a plugin); "other" is a parity-gated
    # holding pen with no bundle by design. Neither is a gap.
    assert not any("discovery_loop" in line for line in g)
    assert not any(line.startswith("other:") for line in g)


def test_manifest_summarizes_by_port_status_and_lists_gaps():
    m = cov.manifest()
    assert m["demo_kinds_total"] == len(DEMO_KINDS)
    assert m["registered"] >= 7                       # every plugin kind registers
    assert set(m["by_port_status"]) == {"exists", "adapt", "build"}
    assert "cost" in m["by_port_status"]["build"]
    assert "eval_quality" in m["by_port_status"]["adapt"]
    assert isinstance(m["gaps"], list)


def test_no_gaps_when_every_plugin_kind_is_covered():
    # The Phase-5 engine has a demonstrator for every plugin demoKind and a bundle for every built one,
    # so the engine should report no gaps about itself.
    register_all()
    assert cov.gaps() == []
