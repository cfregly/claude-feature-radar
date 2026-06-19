"""coverage: per-demoKind, what is built vs adapt vs build, so the engine surfaces its own gaps.

A complete-by-construction engine should be able to answer "which demoKinds can I prove today, and
which still need a demonstrator" without a human reading the tree. This view reports, for every
canonical demoKind:

  - registered      is a Demonstrator registered for the kind (the registry has a plugin for it).
  - bundle          is there a built edges/<key>/ bundle (README + sample + emails) for the kind.
  - port_status     the coverage status: exists (built into the engine), adapt (adapted from a prior
                    implementation), or build (new here). A label, so a reader sees where each kind's
                    code came from.
  - spend           the lane the demonstrator runs in: $0 ALWAYS, or a credit-spending ASK.

Stdlib only, no key, no network, no model call. It reads the demoKind taxonomy (engine/demokinds), the
live REGISTRY (engine/demonstrators/registry), and the committed edges/ tree, so re-running refreshes
as new demonstrators register and new bundles land. The output is a small table plus a one-line gap
summary the cadence prints and a manifest the run records.
"""

from __future__ import annotations

import pathlib

from common.client import repo_root
from engine.demokinds import DEMO_KINDS
from engine.demonstrators.registry import REGISTRY, register_all

# The coverage status per demoKind: where each kind's demonstrator code came from.
#   exists  built into the engine (the token/grounding/long-horizon demos and the discovery loop).
#   adapt   adapted from a prior implementation and refactored behind the interface.
#   build   new here (the pure-pricing cost model, the thin parity-gated candidates).
PORT_STATUS = {
    "token_accounting": "exists",
    "grounding_resolution": "exists",
    "long_horizon_survival": "exists",
    "discovery_loop": "exists",
    "eval_quality": "adapt",
    "retention_resume": "adapt",
    "cost": "build",
    "other": "build",
}

# The built edges/<dir> bundles, mapped to the demoKind each one demonstrates, so the bundle column is
# grounded in the committed tree, not asserted. A kind with no built bundle yet reports bundle: no.
EDGE_DIR_TO_KIND = {
    "programmatic-tool-calling": "token_accounting",
    "citations": "grounding_resolution",
    "context-editing": "long_horizon_survival",
    "eval-quality": "eval_quality",
    "retention-resume": "retention_resume",
    "cost-model": "cost",
    "parity-gated": "other",
}

# The spend lane per demoKind: the discovery loop and the pure-pricing cost model are $0 ALWAYS; the
# parity-gated candidates are held until a parity check passes (and even then ASK); the rest spend a
# credit (ASK). This is display-only context, the gate of record is engine/gate.py + dispatch().
SPEND_LANE = {
    "token_accounting": "ASK (a credit-spending benchmark)",
    "grounding_resolution": "ASK (a credit-spending benchmark)",
    "long_horizon_survival": "ASK (a credit-spending benchmark)",
    "eval_quality": "ASK (a credit-spending grid, the larger slice)",
    "retention_resume": "$0 ALWAYS default (doc-grounded parity); the live kill-resume is opt-in ASK",
    "cost": "$0 ALWAYS (pure pricing model, no API call)",
    "discovery_loop": "$0 ALWAYS (stdlib doc sweep, no API call)",
    "other": "HELD until the parity check passes, then ASK (the opt-in thin proof)",
}


def _built_bundles() -> dict[str, str]:
    """The edges/<dir> bundles that exist on disk, mapped to their demoKind. A bundle counts as built
    only when it carries a README (the deliverable contract)."""
    out: dict[str, str] = {}
    edges_root = repo_root() / "edges"
    if not edges_root.exists():
        return out
    for d in sorted(edges_root.iterdir()):
        if d.is_dir() and (d / "README.md").exists():
            kind = EDGE_DIR_TO_KIND.get(d.name)
            if kind:
                out[kind] = d.name
    return out


def coverage() -> list[dict]:
    """The per-demoKind coverage rows. One row per canonical demoKind, in taxonomy order."""
    if not REGISTRY:
        register_all()
    bundles = _built_bundles()
    rows = []
    for kind in DEMO_KINDS:
        demo = REGISTRY.get(kind)
        rows.append({
            "demo_kind": kind,
            "registered": demo is not None,
            "demonstrator": type(demo).__name__ if demo is not None else None,
            "bundle": bundles.get(kind),
            "has_bundle": kind in bundles,
            "port_status": PORT_STATUS.get(kind, "build"),
            "spend_lane": SPEND_LANE.get(kind, "ASK"),
        })
    return rows


# discovery_loop is proven by the cadence and the gate themselves (engine/cadence.py + sweep_edges.py +
# gate.py), not by a Demonstrator plugin behind the registry, so its "no registered demonstrator" state
# is by design, not a gap. The coverage status marks it "exists" for exactly this reason.
_INTRINSIC_KINDS = {"discovery_loop"}


def gaps(rows: list[dict] | None = None) -> list[str]:
    """The kinds the engine cannot fully prove yet: no registered demonstrator (for a plugin kind), or
    no built bundle. discovery_loop is intrinsic (the cadence itself proves it, not a plugin), and
    "other" is a parity-gated holding pen with no bundle by design, so neither is counted a gap.
    Returns a list of one-line gap descriptions, empty when every kind is covered."""
    rows = rows or coverage()
    out = []
    for r in rows:
        if r["demo_kind"] in _INTRINSIC_KINDS:
            continue  # proven by the cadence, not a registry plugin
        if not r["registered"]:
            out.append(f"{r['demo_kind']}: no demonstrator registered ({r['port_status']})")
        elif not r["has_bundle"] and r["demo_kind"] != "other":
            out.append(f"{r['demo_kind']}: demonstrator registered but no built edges/ bundle yet")
    return out


def manifest() -> dict:
    """The coverage manifest the cadence records in its run file: the rows plus a small summary."""
    rows = coverage()
    return {
        "demo_kinds_total": len(rows),
        "registered": sum(1 for r in rows if r["registered"]),
        "with_bundle": sum(1 for r in rows if r["has_bundle"]),
        "by_port_status": {
            s: sorted(r["demo_kind"] for r in rows if r["port_status"] == s)
            for s in ("exists", "adapt", "build")
        },
        "gaps": gaps(rows),
        "rows": rows,
    }


def main(argv=None) -> int:
    rows = coverage()
    print("\n  Coverage by demoKind: what the engine can prove, where each demonstrator came from.\n")
    print(f"  {'demoKind':<22}{'registered':<12}{'bundle':<27}{'port':<8}{'spend lane'}")
    print("  " + "-" * 112)
    for r in rows:
        reg = "yes" if r["registered"] else "NO"
        bundle = r["bundle"] or ("(the cadence itself)" if r["demo_kind"] == "discovery_loop"
                                 else "(parity-gated)" if r["demo_kind"] == "other" else "none")
        print(f"  {r['demo_kind']:<22}{reg:<12}{bundle:<27}{r['port_status']:<8}{r['spend_lane']}")
    m = manifest()
    print(f"\n  {m['registered']}/{m['demo_kinds_total']} demoKinds have a registered demonstrator, "
          f"{m['with_bundle']} carry a built edges/ bundle.")
    print(f"  by port status: exists {m['by_port_status']['exists']}")
    print(f"                  adapt  {m['by_port_status']['adapt']}")
    print(f"                  build  {m['by_port_status']['build']}")
    g = m["gaps"]
    if g:
        print("\n  Gaps the engine surfaces about itself:")
        for line in g:
            print(f"    - {line}")
    else:
        print("\n  No gaps: every demoKind has a registered demonstrator and a deliverable.")
    print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
