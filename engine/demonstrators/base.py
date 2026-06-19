"""base: the Demonstrator interface and the standard dataclasses every demonstrator emits and every
downstream step reads.

A Demonstrator is a plugin that proves one demoKind. It implements a small interface so the pipeline
can dispatch any edge to its demonstrator instead of branching on the specific feature:

    applicable(edge)            can I prove THIS edge? (reads edge.demoKind + fair_comparison)
    estimate(edge, spec)        declared $ and wall-clock BEFORE any spend (drives the ASK gate)
    run_claude_arm(edge, spec)  the Claude side, best config (alpha/beta on), via the common harness
    run_competitor_arms(...)    OpenAI/Gemini at their best, access-probed, never faked
    score(claude, competitors)  the machine-checkable gate, identical on every arm
    receipt(...)                the standard Receipt dataclass

Two hard interface contracts, lifted from CLAUDE.md so honesty is enforced by the interface, not by a
reviewer remembering it:

  1. score() runs the SAME machine-checkable gate on every arm. No rubric-only verdict. The gate is a
     function of measured outputs (answers match, tokens fell, the suite passed), never a judgment.
  2. receipt() refuses to emit a claude-ahead verdict unless EITHER every competitor arm actually ran
     OR the edge's fair_comparison.lead_basis is an explicit, all-fetched absence-of-evidence. A
     manufactured lead off a blocked fetch or an unrun arm is the one thing the engine must never do.
     receipt() downgrades the verdict to never-evaluated rather than ship an unproven lead.

estimate() is what the ASK gate consults. No demonstrator spends a credit until its estimate is
surfaced and approved (see engine/gate.py and the route -> dispatch step in engine/sweep_edges.py).

Nothing here imports anthropic, openai, or google. The base interface is provider-blind on purpose, so
the core engine compiles and the tests run with no SDK and no key. A concrete demonstrator pulls the
SDK lazily inside its own run_*_arm so the one-command, one-dependency core is never broken.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Protocol, runtime_checkable

# The verdict vocabulary, fixed. Every Receipt carries exactly one of these.
VERDICTS = (
    "claude-ahead",        # measured or all-fetched absence-of-evidence lead
    "parity",              # both ship it, no measured separation
    "claude-behind",       # the competitor wins, this ships as the product-team note
    "never-evaluated",     # a competitor arm did not run, so the lead is held, never pitched
    "within-claude-only",  # a within-Claude value-add (feature on vs off), no cross-vendor arm yet
)

# The lead_basis vocabulary on an edge's fair_comparison. receipt() reads it to decide whether a
# claude-ahead verdict is allowed to stand when not every competitor arm ran.
LEAD_BASES = (
    "head-to-head",          # every competitor arm ran and Claude won on the gate
    "absence-of-evidence",   # no named competitor equivalent AND every competitor source fetched
    "within-claude-only",    # feature on vs off, no cross-vendor arm
    "doc-grounded-parity",   # both ship it, the win is a bundle/time axis, not a capability (managed agents)
)


@dataclass
class Arm:
    """One provider's run, provider-blind. The shape mirrors the cross-vendor runner Result so
    a grader, a grid, or a table never branches on the vendor.

    ``ctx`` is the per-turn carried context summed with the correct buckets per vendor (CLAUDE.md): on
    Claude input + cache_read + cache_creation, on OpenAI/Gemini the inclusive field. It is the one
    number that makes a long-horizon claim apples-to-apples. ``ran`` is False when the arm was
    access-gated or its key was absent, so score() and receipt() can tell "lost" from "did not run"."""

    provider: str            # claude, openai, gemini
    model: str               # the exact model id, for the receipt
    text: str = ""
    ran: bool = True         # False if access-gated or key absent (never faked, never counted as a loss)
    latency_s: float = 0.0
    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_tokens: int = 0
    cache_write_tokens: int = 0
    thinking_tokens: int = 0
    cost_usd: float = 0.0
    ctx: int = 0             # carried context, correct buckets per vendor (the apples-to-apples field)
    truncated: bool = False
    metric: dict = field(default_factory=dict)  # the kind-specific numbers (resolve rate, K/N, finish)
    note: str = ""           # why it did not run, or any honest caveat for this arm

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class CostEstimate:
    """What a demonstrator declares it will spend BEFORE it runs. The ASK gate surfaces this and waits
    for approval. A $0 demonstrator (the discovery loop, a pure-pricing cost model) estimates zero, and
    still flows through the same interface so even the free calculators are gated the same way."""

    usd: float
    wall_clock_s: float
    command: str             # the one command that reproduces it (make ptc, make citations, ...)
    note: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class Verdict:
    """The output of score(): the machine-checkable gate result, before it is wrapped in a Receipt."""

    verdict: str             # one of VERDICTS
    passed: bool             # did the score gate pass (the kind-specific machine check)
    metric: dict = field(default_factory=dict)  # the comparison numbers (percent reduction, K/N, ...)
    note: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class Receipt:
    """The one dataclass every demonstrator emits and every downstream step reads.

    The fields are the framework's demonstratorInterface spec, verbatim in intent: what was claimed,
    what verdict the gate reached, the workload a founder would change, the kind-specific numbers, the
    cost and time to run AND to reproduce, the grounding urls and dates, the fairness attestation, the
    per-vendor raw arms, and whether the score gate passed. draft_email.py and product_alert.py read
    this and only this, so they are demoKind-agnostic."""

    edge_key: str
    demo_kind: str
    axis: str
    claim: str
    verdict: str                      # one of VERDICTS
    passed: bool                      # did the score gate pass
    workload: dict = field(default_factory=dict)   # task shape, model ids each side, features on, assumptions
    metric: dict = field(default_factory=dict)     # the kind-specific numbers
    cost_usd: float = 0.0
    wall_clock_s: float = 0.0
    repro_cost_usd: float = 0.0
    repro_time_s: float = 0.0
    repro_command: str = ""
    grounding: list = field(default_factory=list)  # [{"claim":..., "source_url":..., "date":...}]
    fairness: dict = field(default_factory=dict)   # {best_to_best:..., isolate:..., lead_basis:...}
    arms: list = field(default_factory=list)       # per-vendor raw Arm dicts
    note: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


def reconcile_verdict(proposed: str, claude: Arm, competitors: list[Arm], lead_basis: str) -> tuple[str, str]:
    """The interface-level honesty contract for receipt(): a claude-ahead verdict may stand only when
    EITHER every competitor arm actually ran OR the lead_basis is an explicit all-fetched
    absence-of-evidence (or a doc-grounded parity, which is not a claude-ahead claim to begin with).

    Returns (verdict, note). If a proposed claude-ahead verdict cannot be backed, it is downgraded to
    never-evaluated with a note, never shipped as an unproven lead. This is the single most important
    rule in the engine, enforced here so every demonstrator inherits it rather than re-implementing it."""
    if proposed != "claude-ahead":
        return proposed, ""
    all_ran = bool(competitors) and all(a.ran for a in competitors)
    if all_ran:
        return "claude-ahead", ""
    if lead_basis == "absence-of-evidence":
        # The lead rests on a documented absence, valid only when the sweep fetched every competitor
        # source. The edge carries that all-fetched basis (set by the sweep), so it stands.
        return "claude-ahead", "absence-of-evidence lead, every competitor source fetched"
    return ("never-evaluated",
            "a competitor arm did not run and the lead is not an all-fetched absence-of-evidence, "
            "so the claude-ahead verdict is held, never pitched")


@runtime_checkable
class Demonstrator(Protocol):
    """The interface every demonstrator implements. A Protocol, so a class satisfies it structurally
    (no base class to import), which keeps the three built demos and the future ports decoupled from
    this module. demo_kind is the kind this plugin proves; the registry keys on it."""

    demo_kind: str

    def applicable(self, edge: dict) -> bool: ...
    def estimate(self, edge: dict, spec: dict) -> CostEstimate: ...
    def run_claude_arm(self, edge: dict, spec: dict) -> Arm: ...
    def run_competitor_arms(self, edge: dict, spec: dict) -> list[Arm]: ...
    def score(self, claude: Arm, competitors: list[Arm], spec: dict) -> Verdict: ...
    def receipt(self, edge: dict, claude: Arm, competitors: list[Arm],
                verdict: Verdict, spec: dict) -> Receipt: ...


class BaseDemonstrator:
    """A small convenience base the built demonstrators use. It is NOT required (the interface is a
    Protocol), but it supplies the two pieces every demonstrator shares: applicable() reads the edge's
    demoKind and fair_comparison, and a build_receipt() helper that runs the reconcile_verdict honesty
    contract so no demonstrator can forget it. A demonstrator overrides demo_kind and the run/score
    methods; applicable() and build_receipt() come for free."""

    demo_kind: str = ""

    def applicable(self, edge: dict) -> bool:
        """Can I prove THIS edge? True when the edge's demoKind matches mine. A demonstrator with extra
        preconditions (a parity check, a required key) overrides this to add them."""
        return (edge.get("demoKind") or edge.get("demo_kind")) == self.demo_kind

    def fair_comparison(self, edge: dict) -> dict:
        return edge.get("fair_comparison") or {}

    def lead_basis(self, edge: dict) -> str:
        return self.fair_comparison(edge).get("lead_basis", "within-claude-only")

    def build_receipt(self, edge: dict, claude: Arm, competitors: list[Arm],
                      verdict: Verdict, spec: dict, *, workload: dict, grounding: list,
                      fairness: dict | None = None) -> Receipt:
        """Assemble the standard Receipt and run the honesty contract on the verdict. Every concrete
        demonstrator routes its final receipt through here so the reconcile_verdict downgrade is never
        skipped."""
        final_verdict, contract_note = reconcile_verdict(
            verdict.verdict, claude, competitors, self.lead_basis(edge)
        )
        est = spec.get("estimate") or {}
        fair = dict(fairness or {})
        fair.setdefault("lead_basis", self.lead_basis(edge))
        note = "; ".join(n for n in (verdict.note, contract_note) if n)
        return Receipt(
            edge_key=edge.get("key", ""),
            demo_kind=self.demo_kind,
            axis=edge.get("axis", "unknown"),
            claim=edge.get("claim") or (edge.get("evidence_quote") or ""),
            verdict=final_verdict,
            passed=verdict.passed,
            workload=workload,
            metric=verdict.metric or {},
            cost_usd=sum(a.cost_usd for a in [claude, *competitors] if a and a.ran),
            wall_clock_s=sum(a.latency_s for a in [claude, *competitors] if a and a.ran),
            repro_cost_usd=est.get("usd", 0.0),
            repro_time_s=est.get("wall_clock_s", 0.0),
            repro_command=est.get("command", ""),
            grounding=grounding,
            fairness=fair,
            arms=[a.to_dict() for a in [claude, *competitors] if a is not None],
            note=note,
        )
