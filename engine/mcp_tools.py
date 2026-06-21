"""The engine's tool surface, made callable from a chat window, with the gate boundary built in.

This is the logic layer the MCP server (engine/mcp_server.py) exposes as tools, kept SDK-free on
purpose: it imports only stdlib and the engine's own modules, never `mcp`. So the one-dependency gate
(scripts/check_core_imports.py) proves it imports with `anthropic` alone, and the boundary test
(tests/test_mcp_server.py) drives it offline with no key, no network, and no MCP SDK installed. The
thin FastMCP wrapper that does need the SDK lives in engine/mcp_server.py and is the only file that
imports it.

THE BOUNDARY IS THE SAME ONE engine/gate.py FIXES IN CODE, mirrored onto the tool surface so a chat
caller (a human in Claude Code or Claude Desktop, attended) and an automated caller (a routine or a
loop, unattended) both hit it:

  ALWAYS, runs unattended for $0. The read tools (list_edges, show_landscape, show_coverage,
    show_boundary) and the discovery loop (run_discovery: the stdlib sweep, diff, rank, draft to the
    inert outbox, coverage, manifest, audit). All reversible, all internal, nothing leaves the repo
    and nothing spends. These need no confirmation and are safe to wire to a schedule.

  ASK, waits for an explicit human token. publish_brief writes a public brief into the sibling
    claude-feature-hits checkout (it changes a repo), and run_benchmark spends real credits on a
    paid proof. Both REFUSE to act until the caller passes confirm=True, and run_benchmark surfaces
    the dollar estimate first and refuses any spend over the cap. Without the token they do nothing
    outward: publish_brief returns the verdict-gate preview and run_benchmark returns the estimate,
    each for $0.

  NEVER on a schedule, by design. Send mail, post in public, push a remote, or spend past the hard
    ceiling. The boundary here is the ABSENCE of the capability: this server exposes no tool that
    sends, posts, or pushes, the same way the cadence wires in no send transport. A future cap raise
    is the caller passing a higher max_usd by hand (an ASK), never automatic, and the hard ceiling
    over that is refused outright (the overspend NEVER lane).

audit_unattended() proves it the way engine.gate.audit() proves the cadence: the set of actions an
unattended caller can take without a human token contains nothing outward and nothing non-ALWAYS.
"""

from __future__ import annotations

import json
import os
import pathlib
import subprocess
from dataclasses import asdict, dataclass

from common.client import load_env, repo_root
from engine import coverage as coverage_view
from engine import gate
from engine.publish_brief import (
    PLANS,
    _find_edge,
    _landscape_edges,
    _plan_for,
    publish,
    verdict_gate,
)

# The per-call spend cap a caller may raise by hand (the ASK raise_cap lane), and the hard ceiling no
# call may cross no matter what max_usd is passed (the NEVER overspend lane). A paid proof whose
# estimate is over the cap is refused with an ask-to-raise message; one over the ceiling is refused
# outright. Both numbers are dollars.
DEFAULT_MAX_USD = 0.25
HARD_CAP_USD = 5.00

# The verdict values a landscape edge can carry. list_edges validates a verdict filter against this so
# a typo comes back as a clear error instead of a silent empty result.
VALID_VERDICTS = ("claude-ahead", "parity", "claude-behind", "never-evaluated")


# --------------------------------------------------------------------------- the tool registry (tiers)


@dataclass(frozen=True)
class ToolSpec:
    """One MCP tool, tagged with its gate tier the same way engine/gate.py tags an Action. ``outward``
    means it changes something outside the engine (a repo, the bill, the world). ``spends`` means it
    bills credits. ``confirm_required`` means it refuses to act until the caller passes confirm=True.
    ``gate_action`` is the engine/gate.py Action id this tool maps to, when it has one."""

    name: str
    tier: str  # gate.ALWAYS or gate.ASK. gate.NEVER is never here: those actions have no tool.
    outward: bool
    spends: bool
    confirm_required: bool
    gate_action: str | None
    summary: str


# The contract. Every tool the server exposes appears here exactly once, with its tier. This is the
# single source of truth the server registers from and the boundary test asserts against, so a new
# tool cannot be added without declaring its lane.
TOOLS: tuple[ToolSpec, ...] = (
    ToolSpec("list_edges", gate.ALWAYS, False, False, False, None,
             "Read the ranked edges from landscape/landscape.json. Read-only, $0."),
    ToolSpec("show_landscape", gate.ALWAYS, False, False, False, None,
             "Summarize the landscape: counts by verdict, the top leads, coverage gaps. Read-only, $0."),
    ToolSpec("show_coverage", gate.ALWAYS, False, False, False, None,
             "Read the per-demoKind coverage and the recent coverage ledger. Read-only, $0."),
    ToolSpec("show_boundary", gate.ALWAYS, False, False, False, None,
             "Print the gate boundary and the per-tool tier mapping. Read-only, $0."),
    ToolSpec("run_discovery", gate.ALWAYS, False, False, False, "sweep_docs",
             "Run the $0 discovery loop: sweep live docs, diff, rank, draft to the inert outbox, "
             "update coverage, audit the boundary. No spend, no send, no push."),
    ToolSpec("publish_brief", gate.ASK, True, False, True, "scaffold_edge",
             "Generate a public brief for a verified-win edge into the sibling hits repo. ASK: "
             "writes files, so it refuses until confirm=True. Never pushes, never sends."),
    ToolSpec("run_benchmark", gate.ASK, True, True, True, "run_benchmark",
             "Run a paid proof for an edge. ASK: spends credits, so it surfaces the estimate and "
             "refuses until confirm=True and the estimate is under the cap."),
)

_SPEC = {t.name: t for t in TOOLS}


def tool_specs() -> list[dict]:
    """The tool registry as plain dicts, for show_boundary and the tests."""
    return [asdict(t) for t in TOOLS]


# --------------------------------------------------------------------------- the boundary proof


def unattended_did() -> list[dict]:
    """The actions an unattended caller (no human token) can actually take: every tool that does not
    require confirmation. Shaped like the engine.gate.audit() input, so the audit can run over it."""
    return [{"id": t.name, "gate": t.tier, "outward": t.outward}
            for t in TOOLS if not t.confirm_required]


def confirm_gated_did() -> list[dict]:
    """The actions that DO require a human token, shaped for the audit. audit() must flag every one of
    these (they are ASK or outward), which is the proof that none of them may run unattended."""
    return [{"id": t.name, "gate": t.tier, "outward": t.outward}
            for t in TOOLS if t.confirm_required]


def audit_unattended() -> list[str]:
    """The load-bearing check, the MCP-surface twin of engine.gate.audit(): nothing an unattended
    caller can do without a human token is outward or non-ALWAYS. Returns the violations. Empty means
    the boundary held."""
    return gate.audit(unattended_did())


# --------------------------------------------------------------------------- reading the landscape


def _edge_row(e: dict) -> dict:
    """One landscape edge, projected to the fields a reader wants: the verdict, the genuine-lead basis
    and score, the value score, the axis, and the reproduction command and estimate when present."""
    fc = e.get("fair_comparison") or {}
    repro = fc.get("repro") or {}
    return {
        "key": e.get("key"),
        "vendor": e.get("vendor"),
        "axis": e.get("axis"),
        "verdict": e.get("verdict"),
        "lead_score": e.get("lead_score", 0),
        "value_score": e.get("value_score"),
        "score": e.get("score"),
        "lead_basis": fc.get("lead_basis"),
        "demoKind": e.get("demoKind"),
        "status": e.get("status"),
        "source_url": e.get("source_url"),
        "repro_command": repro.get("command"),
        "est_cost_usd": repro.get("est_cost_usd"),
        "est_time_s": repro.get("est_time_s"),
    }


def list_edges(leads_only: bool = False, verdict: str = "", limit: int = 0) -> dict:
    """The ranked edges from the committed landscape (or the seed leads on a fresh checkout). Read-only.

    leads_only keeps only genuine leads (lead_score > 0). verdict filters to one verdict
    (claude-ahead, parity, claude-behind, never-evaluated), and an unknown verdict comes back as a
    clear error rather than a silent empty list. limit caps the row count (0 or less means all). Rows
    come back sorted by score, highest first."""
    edges, src = _landscape_edges()
    if verdict and verdict not in VALID_VERDICTS:
        return {"source": src, "count": 0, "edges": [],
                "error": f"unknown verdict {verdict!r}. Use one of {list(VALID_VERDICTS)}, or leave it "
                         "empty for all verdicts.",
                "valid_verdicts": list(VALID_VERDICTS)}
    rows = [_edge_row(e) for e in edges]
    if leads_only:
        rows = [r for r in rows if (r.get("lead_score") or 0) > 0]
    if verdict:
        rows = [r for r in rows if r.get("verdict") == verdict]
    rows.sort(key=lambda r: (r.get("score") or 0), reverse=True)
    if limit > 0:
        rows = rows[:limit]
    return {"source": src, "count": len(rows), "edges": rows}


def show_landscape() -> dict:
    """A quick orientation over the landscape: the as-of date, total edges, counts by verdict, the top
    genuine leads, and the count of coverage gaps the engine surfaces about itself. Read-only, $0."""
    edges, src = _landscape_edges()
    by_verdict: dict[str, int] = {}
    for e in edges:
        by_verdict[e.get("verdict", "unknown")] = by_verdict.get(e.get("verdict", "unknown"), 0) + 1
    leads = sorted((e for e in edges if (e.get("lead_score") or 0) > 0),
                   key=lambda e: (e.get("score") or 0), reverse=True)
    land_path = repo_root() / "landscape" / "landscape.json"
    as_of = None
    if land_path.exists():
        try:
            as_of = json.loads(land_path.read_text()).get("as_of_date")
        except (json.JSONDecodeError, OSError):
            as_of = None
    return {
        "source": src,
        "as_of_date": as_of,
        "total_edges": len(edges),
        "by_verdict": by_verdict,
        "lead_count": len(leads),
        "top_leads": [
            {"key": e.get("key"), "axis": e.get("axis"), "score": e.get("score"),
             "lead_basis": (e.get("fair_comparison") or {}).get("lead_basis")}
            for e in leads[:8]
        ],
        "coverage_gaps": coverage_view.gaps(),
    }


def show_coverage(ledger_tail: int = 12) -> dict:
    """The per-demoKind coverage view (what the engine can prove, where each demonstrator came from,
    which lane it spends in) plus the tail of the committed coverage ledger (state/coverage.jsonl),
    so a reader sees what the stream has already drafted and dispatched. Read-only, $0.

    ledger_tail caps how many recent ledger rows come back (0 means none)."""
    manifest = coverage_view.manifest()
    ledger: list[dict] = []
    f = repo_root() / "state" / "coverage.jsonl"
    if f.exists() and ledger_tail:
        lines = [ln for ln in f.read_text().splitlines() if ln.strip()]
        for ln in lines[-ledger_tail:]:
            try:
                ledger.append(json.loads(ln))
            except json.JSONDecodeError:
                continue
    return {
        "demo_kinds_total": manifest["demo_kinds_total"],
        "registered": manifest["registered"],
        "with_bundle": manifest["with_bundle"],
        "gaps": manifest["gaps"],
        "rows": manifest["rows"],
        "ledger_tail": ledger,
    }


def show_boundary() -> dict:
    """The whole stated safety posture, for inspection from chat: the engine.gate.py ALWAYS / ASK /
    NEVER lanes, the per-tool tier mapping this server exposes, and the audit over what an unattended
    caller can do (which must be empty). Read-only, $0.

    The NEVER actions (send mail, post in public, push a remote, overspend) appear in the gate lanes
    but map to NO tool: the boundary is the absence of the capability, not a flag that could be
    flipped."""
    violations = audit_unattended()
    return {
        "gate": gate.boundary(),
        "tools": tool_specs(),
        "unattended_audit_violations": violations,
        "boundary_held": violations == [],
        "never_actions_have_no_tool": [a.id for a in gate.NEVER_ACTIONS],
        "note": "ASK tools refuse until confirm=True. The NEVER actions are not exposed as tools at "
                "all. The discovery loop and the read tools run unattended for $0.",
    }


# --------------------------------------------------------------------------- run_discovery (ALWAYS, $0)


def run_discovery(sweep: bool = True) -> dict:
    """Run the $0 discovery loop and report what it did. ALWAYS tier: it sweeps the live docs, diffs
    against the last run, ranks by value times genuine lead, drafts the newest uncovered lead into the
    inert state/outbox/, updates the coverage ledger, writes the run manifest, and audits the
    boundary. It spends nothing, sends nothing, and pushes nothing.

    sweep=True does the live read-only doc fetch (the full loop). sweep=False reuses the last committed
    landscape with no network at all. Either way it is $0 and the result carries the gate audit, which
    must be empty."""
    from engine import cadence  # local import: cadence pulls the registry, keep module import light

    result = cadence.run(do_sweep=sweep)
    routing = result.get("routing", [])
    anchor = result.get("anchor")
    return {
        "ok": result.get("audit_violations") == [],
        "date": result.get("date"),
        "swept": sweep,
        "spent_usd": 0.0,
        "sent": False,
        "pushed": False,
        "anchor_edge": (anchor or {}).get("key") if anchor else None,
        "outbox_draft": result.get("outbox_draft"),
        "manifest": result.get("manifest"),
        "dispatch": {
            "use_existing": sum(1 for r in routing if r.get("action") == "use-existing"),
            "ask_run_demonstrator": sum(1 for r in routing if r.get("action") == "ask-run-demonstrator"),
            "ask_build_demonstrator": sum(1 for r in routing if r.get("action") == "ask-build-demonstrator"),
        },
        "lead_count": sum(1 for r in routing if (r.get("lead_score") or 0) > 0) or None,
        "coverage_gaps": result.get("coverage", {}).get("gaps", []),
        "audit_violations": result.get("audit_violations", []),
        "note": "The discovery loop ran unattended for $0. No benchmark spend, no send, no push. The "
                "audit_violations list must be empty: nothing outward or non-ALWAYS crossed the boundary.",
    }


# --------------------------------------------------------------------------- publish_brief (ASK)


def _briefs_root() -> pathlib.Path:
    """The public hits repo the publisher writes into (the sibling claude-feature-hits checkout)."""
    return repo_root().parent / "claude-feature-hits"


def publish_brief(edge: str, confirm: bool = False) -> dict:
    """Generate a public brief for a verified-win edge. ASK tier: this writes files into the public
    hits repo, so it does nothing until the caller passes confirm=True.

    With confirm=False (the default) it runs the fail-closed verdict gate and returns a PREVIEW: would
    it publish, the gate reason, and the target repo. It writes nothing, $0. With confirm=True and a
    clean gate it assembles and writes the brief, then reports the files written. It never pushes a
    remote and never sends anything: the writer touches files in a local checkout only.

    The verdict gate refuses any edge that is not a clean, ranked, non-regime-bounded Claude win, and a
    refusal writes nothing, so an unverified or regime-bounded edge can never publish even with
    confirm=True."""
    spec = _SPEC["publish_brief"]
    g = verdict_gate(edge)
    base = {
        "tool": "publish_brief",
        "tier": spec.tier,
        "edge": edge,
        "gate_ok": g.ok,
        "verdict": g.verdict,
        "lead_basis": g.lead_basis,
        "gate_reason": g.reason,
        "gate_source": g.source,
        "target_repo": str(_briefs_root()),
        "pushed": False,
        "sent": False,
        "spent_usd": 0.0,
    }
    if not g.ok:
        return {**base, "published": False, "requires_confirmation": False,
                "refused": True,
                "message": f"REFUSED by the verdict gate: {g.reason}. Wrote nothing."}
    if not confirm:
        plan = _plan_for(edge)
        return {
            **base,
            "published": False,
            "requires_confirmation": True,
            "would_write_slug": plan.slug if plan else None,
            "would_write_doc": plan.doc_url if plan else None,
            "message": "PREVIEW only. The verdict gate passes. Re-call with confirm=true to write the "
                       "brief into the hits repo. This writes files. It never pushes or sends.",
        }
    briefs_root = _briefs_root()
    command = f"make publish-brief EDGE={edge}"
    rc = publish(edge, briefs_root, command)
    plan = _plan_for(edge)
    slug = plan.slug if plan else edge
    wrote: list[str] = []
    brief_dir = briefs_root / slug
    if rc == 0 and brief_dir.exists():
        wrote = sorted(str(p.relative_to(briefs_root)) for p in brief_dir.rglob("*") if p.is_file())
    return {
        **base,
        "published": rc == 0,
        "requires_confirmation": False,
        "exit_code": rc,
        "slug": slug,
        "wrote": wrote,
        "message": (f"Published {slug} into {briefs_root}. Files were written locally. Nothing was "
                    "pushed or sent: review the diff and push by hand if you want it public.")
                   if rc == 0 else
                   (f"Publish refused or failed (exit {rc}). Wrote nothing. If the hits repo is "
                    f"missing, clone it next to the engine at {briefs_root}."),
    }


# --------------------------------------------------------------------------- run_benchmark (ASK, spends)


def _benchmark_plan(edge: str) -> dict | None:
    """The reproduction command and dollar estimate for an edge, read off the landscape's
    fair_comparison.repro. Returns None when the edge has no runnable paid benchmark."""
    rec, _src = _find_edge(edge)
    if rec is None:
        return None
    repro = (rec.get("fair_comparison") or {}).get("repro") or {}
    command = repro.get("command")
    if not command:
        return None
    return {
        "command": command,
        "est_cost_usd": float(repro.get("est_cost_usd") or 0.0),
        "est_time_s": float(repro.get("est_time_s") or 0.0),
        "verdict": rec.get("verdict"),
        "axis": rec.get("axis"),
    }


def run_benchmark(edge: str, confirm: bool = False, max_usd: float = DEFAULT_MAX_USD,
                  timeout_s: int = 1200) -> dict:
    """Run a paid proof for an edge. ASK tier: this SPENDS real credits on your ANTHROPIC_API_KEY, so
    it surfaces the dollar estimate first and does nothing until the caller passes confirm=True.

    With confirm=False (the default) it returns the estimate (the command, the dollar cost, the wall
    time) and the cap, and spends nothing. With confirm=True it enforces the cap before spending: an
    estimate over max_usd is refused with an ask-to-raise message (raising the cap is your call, the
    ASK raise_cap lane), and an estimate over the hard ceiling is refused outright no matter what
    max_usd you pass (the NEVER overspend lane). When the estimate clears the cap and a key is present,
    it runs the engine's own make target and returns the exit code and the tail of the output.

    It never sends and never pushes: the only outward effect is the credit spend on the named
    benchmark, and that happens only past the explicit confirm and the cap."""
    spec = _SPEC["run_benchmark"]
    plan = _benchmark_plan(edge)
    base = {"tool": "run_benchmark", "tier": spec.tier, "edge": edge, "pushed": False, "sent": False}
    if max_usd < 0:
        return {**base, "ran": False, "spent_usd": 0.0, "requires_confirmation": False, "refused": True,
                "message": f"REFUSED: max_usd must be non-negative, got {max_usd}. The cap is a dollar "
                           "ceiling, so pass 0 or a positive number."}
    if plan is None:
        return {**base, "ran": False, "spent_usd": 0.0, "requires_confirmation": False, "refused": True,
                "message": f"No runnable paid benchmark for edge {edge!r}: the landscape carries no "
                           "fair_comparison.repro.command for it."}
    est = plan["est_cost_usd"]
    estimate = {
        "command": plan["command"],
        "est_cost_usd": est,
        "est_time_s": plan["est_time_s"],
        "cap_usd": max_usd,
        "hard_cap_usd": HARD_CAP_USD,
    }
    if not confirm:
        return {**base, "ran": False, "spent_usd": 0.0, "requires_confirmation": True,
                "estimate": estimate,
                "message": f"ESTIMATE only. {plan['command']} costs about ${est:.2f} and roughly "
                           f"{plan['est_time_s']:.0f}s using your API key. Re-call with confirm=true to run "
                           f"it. This spends real credits. It never sends or pushes."}
    # confirm is True: enforce the ceiling, then the cap, then the key, before any spend.
    if est > HARD_CAP_USD:
        return {**base, "ran": False, "spent_usd": 0.0, "requires_confirmation": False, "refused": True,
                "estimate": estimate,
                "message": f"REFUSED: the estimate ${est:.2f} is over the hard ceiling "
                           f"${HARD_CAP_USD:.2f}. That ceiling is not raisable from a tool call (the "
                           "overspend lane is never on a schedule). Run it by hand if you mean to."}
    if est > max_usd:
        return {**base, "ran": False, "spent_usd": 0.0, "requires_confirmation": True, "refused": True,
                "estimate": estimate,
                "message": f"REFUSED: the estimate ${est:.2f} is over the cap ${max_usd:.2f}. Raising "
                           "the cap is your call: re-call with a higher max_usd (up to the hard ceiling "
                           f"${HARD_CAP_USD:.2f}) to proceed."}
    load_env()
    if not os.environ.get("ANTHROPIC_API_KEY"):
        return {**base, "ran": False, "spent_usd": 0.0, "requires_confirmation": False, "refused": True,
                "estimate": estimate,
                "message": "REFUSED: ANTHROPIC_API_KEY is not set. Paste it into the engine's .env or "
                           "export it, then re-call. Wrote nothing, spent nothing."}
    argv = _benchmark_argv(plan["command"])
    if argv is None:
        return {**base, "ran": False, "spent_usd": 0.0, "requires_confirmation": False, "refused": True,
                "estimate": estimate,
                "message": f"REFUSED: the reproduction command {plan['command']!r} is not a recognized "
                           "make target, so it is not run from here. Run it by hand."}
    proc = subprocess.run(argv, cwd=str(repo_root()), capture_output=True, text=True, timeout=timeout_s)
    tail = "\n".join((proc.stdout or "").splitlines()[-25:])
    return {**base, "ran": True, "spent_usd": est, "requires_confirmation": False,
            "exit_code": proc.returncode, "estimate": estimate, "command": plan["command"],
            "output_tail": tail,
            "message": f"Ran {plan['command']} (exit {proc.returncode}). It spent about ${est:.2f} on "
                       "your key. Nothing was sent or pushed. The receipt is in the engine's data/ "
                       "and the printed tail above."}


def _benchmark_argv(command: str) -> list[str] | None:
    """Turn a landscape repro command into an argv to run, accepting only the engine's own make targets
    and run.py subcommands so a stray command string can never become an arbitrary shell call. Returns
    None for anything else."""
    parts = command.split()
    if len(parts) >= 2 and parts[0] == "make":
        return ["make", parts[1]]
    if len(parts) >= 2 and parts[0] in ("python", "python3") and parts[1] == "run.py":
        return [str(repo_root() / ".venv" / "bin" / "python"), "run.py", *parts[2:]]
    return None
