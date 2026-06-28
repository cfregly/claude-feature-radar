"""The gate: what the engine may do on its own, what waits for you, and what it
refuses by design, re-keyed to this engine's ALWAYS/ASK/NEVER lanes. The boundary
is fixed in code, not discovered at runtime, and audit() proves nothing crossed it.

The recurring loop is a doc sweep, a diff against the last run, a value-times-lead
rank, a fresh draft into an inert outbox, and the written brief, changelog, and
coverage update. That whole chain is measurement and drafting, so it runs unattended.
Spending credits on a benchmark, scaffolding or refreshing an edges/<key>/ bundle, and
raising the spend cap change the repo or the bill, so they wait for you. Sending mail,
posting in public, pushing a remote, and spending past a cap never run on a schedule,
by design: the boundary is the absence of the capability in the unattended path, not a
flag that could be flipped.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass

ALWAYS = "always"  # safe and internal: runs unattended in the cadence
ASK = "ask"        # changes your repo or your spend: proposed, waits for approval
NEVER = "never"    # refused on a schedule, by design


@dataclass(frozen=True)
class Action:
    id: str
    gate: str
    outward: bool   # does it change something outside the engine (your repo, the bill, the world)?
    motion: str
    rationale: str


# What the cadence does unattended. Doc sweep, diff, rank, draft, and the written record.
# Nothing here leaves the repo or spends credits.
ALWAYS_ACTIONS = [
    Action("sweep_docs", ALWAYS, False, "Fetch the live Claude, OpenAI, and Gemini doc, changelog, and pricing pages.",
           "A read-only HTTP fetch changes nothing outside the engine and spends no credits."),
    Action("diff", ALWAYS, False, "Diff this run's capabilities against the last landscape to find new, changed, and gone edges.",
           "Comparing two snapshots is measurement."),
    Action("rank", ALWAYS, False, "Rank candidate edges by value times genuine lead, sorting parity and behind cells aside.",
           "Ranking is a deterministic read over the diff."),
    Action("draft_to_outbox", ALWAYS, False, "Draft a fresh email anchored on the newest uncovered edge into the inert state/outbox/.",
           "Drafting writes an internal file. It is never a send."),
    Action("write_brief", ALWAYS, False, "Write the dated brief and the landscape CHANGELOG of what changed since the last run.",
           "A written record is internal."),
    Action("update_coverage", ALWAYS, False, "Append to the state/coverage.jsonl ledger so the stream never repeats an edge.",
           "The coverage ledger is internal bookkeeping that keeps the stream varied."),
]

# What waits for you. Anything that changes your repo or spends credits.
ASK_ACTIONS = [
    Action("run_benchmark", ASK, True, "Run a credit-spending benchmark (programmatic tool calling, compare, longhorizon, citations).",
           "A benchmark spends real credits, so it runs only on your explicit token."),
    Action("scaffold_edge", ASK, True, "Scaffold or refresh an edges/<key>/ bundle in the committed tree.",
           "Writing a new published bundle into the repo is your call, not a loop step."),
    Action("raise_cap", ASK, True, "Raise the per-run spend cap.",
           "Spending more is your decision."),
]

# What it will not do, ever, on a schedule. The boundary is the absence of the
# capability in the unattended path, not a flag that could be flipped.
NEVER_ACTIONS = [
    Action("send_mail", NEVER, True, "Send mail in your name.",
           "Sending is a human decision. The unattended path has no send transport, by design."),
    Action("post_public", NEVER, True, "Post publicly.",
           "Publishing in your name is never a loop step."),
    Action("push_remote", NEVER, True, "Push to a remote.",
           "Pushing is a human decision, not a cadence step."),
    Action("overspend", NEVER, True, "Spend past the per-run cap.",
           "The cap is a hard ceiling, not a suggestion."),
]


def audit(did: list[dict], routing: list[dict] | None = None) -> list[str]:
    """The check that makes autonomy accountable: nothing that changes your repo,
    your spend, or the world may appear in the unattended work. Returns the
    violations. An empty list means the boundary held.

    The estimate-surfaced check: a routing decision that proposes spending a credit
    (gate ask, a demonstrator that runs an arm) must carry a surfaced cost estimate,
    because no demonstrator may spend until its estimate is shown and approved. A
    proposed ask-run with estimate_surfaced False is a boundary violation: the cadence
    would be queuing a spend the human never saw a number for. A $0 demonstrator (gate
    always) needs no estimate, it spends nothing."""
    out: list[str] = []
    for a in did:
        if a.get("outward"):
            out.append(f"outward action ran unattended: {a['id']}")
        if a.get("gate") != ALWAYS:
            out.append(f"non-always action ran unattended: {a['id']} ({a.get('gate')})")
    for r in (routing or []):
        if r.get("gate") == ASK and r.get("demonstrator") and not r.get("estimate_surfaced"):
            out.append(f"spend proposed without a surfaced estimate: {r.get('key')} "
                       f"({r.get('demonstrator')})")
    return out


def boundary() -> dict:
    """The full, stated boundary, for the report and for tests."""
    return {
        "always": [asdict(a) for a in ALWAYS_ACTIONS],
        "ask": [asdict(a) for a in ASK_ACTIONS],
        "never": [asdict(a) for a in NEVER_ACTIONS],
    }
