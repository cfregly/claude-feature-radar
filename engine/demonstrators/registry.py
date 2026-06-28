"""registry: the demoKind -> Demonstrator map and the dispatcher.

dispatch(edge, spec) is the typed seam that replaces branching on a specific feature. It reads the
edge's demoKind, looks up the registered demonstrator, asserts it can prove this edge, and returns a
DispatchResult: either a demonstrator to run (with its estimate, for the ASK gate) or an ASK stub that
NAMES the demonstrator a brand-new kind needs. dispatch never crashes on an unknown kind, so the
engine stays complete-by-construction: a kind with no registered demonstrator files a
"build a demonstrator for kind X" stub rather than raising.

Registration is lazy and import-light. The three built demonstrators live in edges/<key>/demo.py and
register themselves by calling register() at import time. register_all() imports those modules once,
inside a try/except so a missing SDK in one demo never breaks the registry the rest of the engine
needs. The base interface and this registry import no SDK, so dispatch() runs offline with no key.
"""

from __future__ import annotations

import importlib
from dataclasses import dataclass

from engine.demokinds import demokind_for, is_known_kind
from engine.demonstrators.base import CostEstimate, Demonstrator

# demo_kind -> a Demonstrator instance. Populated by register() at demonstrator import time.
REGISTRY: dict[str, Demonstrator] = {}
_REGISTERED_ALL = False

# The built demonstrators register from these modules. Imported once by register_all(), each in its
# own try/except so one demo's missing optional SDK never blanks the registry.
_DEMO_MODULES = (
    "edges.programmatic-tool-calling.demo",
    "edges.citations.demo",
    "edges.context-editing.demo",
    "engine.demonstrators.eval_quality",
    "engine.demonstrators.retention_resume",
    "engine.demonstrators.managed_agents_operations",
    "engine.demonstrators.code_execution_state",
    "engine.demonstrators.cost_model",
    "engine.demonstrators.security_posture",
    "engine.demonstrators.other_parity_gated",
    "engine.demonstrators.pdf_citations",
    "engine.demonstrators.search_results_grounding",
    "engine.demonstrators.grounding_stack",
    "engine.demonstrators.web_citations",
    "engine.demonstrators.advisor_routing",
    "engine.demonstrators.bulk_extended_output",
)


@dataclass
class DispatchResult:
    """What dispatch returns. ``demonstrator`` is set when a registered plugin can prove the edge, and
    ``estimate`` carries its declared spend for the ASK gate. ``ask_stub`` is set instead when the kind
    has no demonstrator, naming what to build. Exactly one of the two is set."""

    edge_key: str
    demo_kind: str
    demonstrator: Demonstrator | None = None
    estimate: CostEstimate | None = None
    ask_stub: str | None = None       # the "build a demonstrator for kind X" message, when unmapped
    gate: str = "ask"                 # always for a $0 demonstrator, ask for any spend, ask for a stub

    @property
    def covered(self) -> bool:
        return self.demonstrator is not None


def register(demonstrator: Demonstrator) -> Demonstrator:
    """Register a demonstrator under its demo_kind. Returns it, so it can be used as a decorator or
    called at module import. A second registration for the same kind overwrites the first, which lets a
    fork swap a demonstrator without touching this file."""
    REGISTRY[demonstrator.demo_kind] = demonstrator
    return demonstrator


def register_all() -> dict[str, Demonstrator]:
    """Import the built demonstrator modules so they register, then return the populated REGISTRY. Each
    import is guarded: a demo that needs an optional SDK at import time must not blank the registry for
    the offline core, so an ImportError is swallowed and that one kind stays unmapped (it then files an
    ASK stub on dispatch, which is the honest state)."""
    global _REGISTERED_ALL
    if _REGISTERED_ALL:
        return REGISTRY
    for mod in _DEMO_MODULES:
        try:
            importlib.import_module(mod)
        except Exception:  # noqa: BLE001  a demo's optional dep or import error never breaks dispatch
            continue
    _REGISTERED_ALL = True
    return REGISTRY


def _spec_estimate(edge: dict, spec: dict, demonstrator: Demonstrator) -> CostEstimate:
    """Pull the demonstrator's estimate, surfaced for the ASK gate. A demonstrator declares it via
    estimate(); if that itself fails (a missing key it needs only to estimate against), fall back to
    the edge's committed fair_comparison.repro block so the gate still sees a number."""
    try:
        return demonstrator.estimate(edge, spec)
    except Exception:  # noqa: BLE001
        repro = (edge.get("fair_comparison") or {}).get("repro") or {}
        return CostEstimate(
            usd=float(repro.get("est_cost_usd", 0.0)),
            wall_clock_s=float(repro.get("est_time_s", 0.0)),
            command=repro.get("command", ""),
            note="estimate from the edge's committed fair_comparison.repro",
        )


def dispatch(edge: dict, spec: dict | None = None) -> DispatchResult:
    """Route one edge to its demonstrator by demoKind. The typed replacement for the hardcoded edge
    directory map.

    Reads edge["demoKind"] (falling back to the seed-table guess if the edge was not stamped), looks
    up REGISTRY[kind], asserts the demonstrator can prove THIS edge, and returns it with its estimate.
    If no demonstrator is registered for the kind, returns an ASK stub naming what to build, rather
    than crashing. The gate is "always" only for a surfaced $0 estimate, "ask" for any spend or a
    stub, so the ASK gate and audit() can read the decision off the result."""
    spec = spec or {}
    if not _REGISTERED_ALL:
        register_all()
    kind = edge.get("demoKind") or edge.get("demo_kind") or demokind_for(edge.get("key", ""), edge.get("axis"))
    # Stamp the resolved kind onto the edge so applicable() (which reads edge["demoKind"]) sees it even
    # when the caller passed an unstamped edge. The sweep stamps every edge already; this covers a
    # hand-built or test edge that arrives without the field.
    edge.setdefault("demoKind", kind)
    demonstrator = REGISTRY.get(kind)

    if demonstrator is None:
        known = "" if is_known_kind(kind) else " (kind is not in the canonical taxonomy)"
        stub = (f"build a demonstrator for kind '{kind}' to prove edge '{edge.get('key','')}'"
                f"{known}; until then this edge is held never-evaluated, not pitched")
        return DispatchResult(edge_key=edge.get("key", ""), demo_kind=kind, ask_stub=stub, gate="ask")

    if not demonstrator.applicable(edge):
        # The kind matched but this demonstrator declined the edge (a failed precondition, e.g. a
        # parity check not yet run). That is an ASK stub too: a human decides, the engine never forces.
        stub = (f"demonstrator for kind '{kind}' declined edge '{edge.get('key','')}' "
                f"(a precondition is unmet, e.g. a parity check); held, not pitched")
        return DispatchResult(edge_key=edge.get("key", ""), demo_kind=kind, ask_stub=stub, gate="ask")

    est = _spec_estimate(edge, spec, demonstrator)
    # A $0 estimate is a measurement-only demonstrator (the discovery loop, a pure-pricing cost model):
    # it may run unattended. Anything that spends a credit is ASK, surfaced by its estimate.
    gate = "always" if (est is None or est.usd <= 0.0) else "ask"
    return DispatchResult(edge_key=edge.get("key", ""), demo_kind=kind,
                          demonstrator=demonstrator, estimate=est, gate=gate)
