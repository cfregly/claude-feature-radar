"""cadence: the recurring engine, self-driving and self-auditing.

This is the orchestrator the CLAUDE.md "the cadence runs on its own, and the gate is the boundary"
section describes. On a schedule it sweeps the live docs, diffs against the last run, ranks by value
times genuine lead, dispatches each lead edge to its demonstrator by demoKind, drafts a fresh email
for the newest uncovered edge into the inert outbox, updates the coverage ledger, and writes a per-run
manifest. That whole chain is measurement and drafting, so it runs unattended for $0. It does NOT run a
benchmark (every demonstrator run is ASK, surfaced by its estimate) and it does NOT send (no send
transport is wired into this path, by design).

THE STEPS, each tagged with its gate so audit() can prove the boundary held:

  1. sweep_docs       ALWAYS  stdlib doc fetch, diff, rank, stamp demoKind + fair_comparison.
  2. rank             ALWAYS  value times genuine lead; parity and behind sort aside, never pitched.
  3. dispatch         ALWAYS  route each lead to its demonstrator by demoKind. The DECISION is a $0
                              read. RUNNING a demonstrator is ASK and is NOT done here: dispatch only
                              surfaces which demonstrator would run and its estimate, for the human.
  4. draft_to_outbox  ALWAYS  a $0 DETERMINISTIC draft (no model call) for the newest uncovered lead,
                              written to the inert state/outbox/. Never a send.
  5. update_coverage  ALWAYS  append the (edge, run_date, action) rows to state/coverage.jsonl so the
                              stream never repeats an edge and the run is auditable.
  6. write_manifest   ALWAYS  append state/runs/<date>.json: the dispatch decisions, the outbox draft,
                              and the coverage-by-demoKind view, pinned for checkpoint and resume.

Then the entrypoint runs gate.audit() over what the run DID and the routing decisions. audit() must
return empty: nothing outward or non-ALWAYS ran unattended, and no spend was proposed without a
surfaced estimate. A non-empty audit aborts with a nonzero exit, so a cadence that ever crossed the
boundary fails loud instead of shipping.

THE DRAFT IS $0 AND DETERMINISTIC. The founder email here is NOT a Claude call (engine/draft_email.py
is the live, polished drafter the operator runs by hand). The cadence's draft is a deterministic
template filled from the edge's standard Receipt-shaped fields, so the ALWAYS lane spends nothing and
the outbox file is reproducible. It is written deslop-clean by construction, and deslop_outbox() runs
the same banned-character check the prose gate runs, on every generated email, before the manifest is
written.

Stdlib only on this path, no key, no network beyond the sweep's read-only doc fetch, no model call.
"""

from __future__ import annotations

import json
import pathlib

from common.client import repo_root
from engine import coverage as coverage_view
from engine import gate, scan, sweep_edges
from engine.demonstrators.registry import register_all

# The banned characters the prose deslop gate forbids. The cadence drafts deslop-clean by construction
# and asserts it here, so "run the deslop gate on every generated email" holds on the outbox too (the
# outbox is not under the paths scripts/deslop_check.py scans, so the cadence checks it itself).
BANNED = {"—": "em-dash", "–": "en-dash", ";": "semicolon"}


# ----- draft-to-outbox (ALWAYS, $0, deterministic, no model call) --------------------------------

def _anchor_edge(ranked: list[dict], covered_keys: set[str]) -> dict | None:
    """The newest UNCOVERED lead edge: the top-ranked genuine lead whose key the stream has not already
    drafted. Falls back to the top lead when every lead is covered (so a run always has an anchor when a
    lead exists). Returns None when there is no genuine lead this run."""
    leads = [e for e in ranked if e.get("lead_score", 0) > 0]
    if not leads:
        return None
    for e in leads:
        if e["key"] not in covered_keys:
            return e
    return leads[0]


def _draft_email(edge: dict, routing_for_edge: dict | None) -> str:
    """A deterministic, deslop-clean founder email for one edge, filled from the edge's standard fields
    (claim, verdict, axis, fair_comparison.repro). NO model call: this is the $0 cadence draft, not the
    live drafter. The hero stays competitor-neutral per the repo convention. The reproduction command
    and the estimate come straight from the dispatch decision, so the cost and the one command to check
    are on the surface, up front, the way every outbound surface must carry them."""
    fc = edge.get("fair_comparison") or {}
    repro = fc.get("repro") or {}
    est = (routing_for_edge or {}).get("estimate") or {}
    command = est.get("command") or repro.get("command") or "make"
    cost = est.get("usd", repro.get("est_cost_usd", 0.0)) or 0.0
    minutes = round((est.get("wall_clock_s", repro.get("est_time_s", 0.0)) or 0.0) / 60.0, 1)
    claim = (edge.get("claim") or edge.get("evidence_quote") or edge.get("key", "")).strip()
    cost_line = ("It costs nothing to check" if cost <= 0
                 else f"It costs about ${cost:.2f} and a few minutes to check using your own API key")
    time_clause = f" (about {minutes} minutes)" if minutes else ""

    lines = [
        f"# Founder email draft (cadence, {edge.get('key','')}, {edge.get('axis','')})",
        "",
        "Drafted by the unattended cadence into the inert outbox. No model call, no send. "
        "A deterministic template filled from the edge's measured fields and the Chris Fregly voice "
        "guide, for a human to review, edit, and decide whether to send.",
        "",
        "---",
        "",
        "**Subject:** A Claude edge you can test using your own API key",
        "",
        "Hey {first_name},",
        "",
        "Quick builder note. If this workload looks like yours, the repo below lets you check the "
        "number using your own API key before you trust the claim.",
        "",
        claim,
        "",
        f"Here is the receipt path: {cost_line}{time_clause}. Clone the repo and run one command:",
        "",
        "```",
        f"{command}",
        "```",
        "",
        "The run prints its own receipt: the workload, the exact models on each side, the dollar cost "
        "off the real usage object, and the assumptions your own task would change. If your numbers "
        "move the result, that is the point, the repo is built for you to swap in your own workload. "
        "The gap can move as the platforms ship, so the repo re-runs the whole search instead of "
        "caching a winner.",
        "",
        "Link: {repo_link}",
        "",
        "Go build,",
        "Chris",
        "",
        "---",
        "",
        "Provenance (not part of the email body):",
        f"- edge key: {edge.get('key','')}",
        f"- axis: {edge.get('axis','')}",
        f"- verdict: {edge.get('verdict','')}",
        f"- reproduce: {command} (about ${cost:.2f})",
        "- This draft is inert. The cadence never sends. A human reviews, runs the deslop and "
        "outbound-scrutiny panel, and decides.",
        "",
    ]
    return "\n".join(lines) + "\n"


def deslop_outbox(text: str) -> list[str]:
    """Run the prose deslop gate on a generated email: no em-dashes, no en-dashes, no semicolons
    outside fenced code. Returns the violations (empty when clean). The cadence asserts this on every
    draft before the manifest is written, so the outbox can never carry slop the rest of the repo
    forbids."""
    bad = []
    in_code = False
    for i, line in enumerate(text.splitlines(), 1):
        if line.lstrip().startswith("```"):
            in_code = not in_code
            continue
        if in_code:
            continue
        for ch, label in BANNED.items():
            if ch in line:
                bad.append(f"outbox draft line {i}: {label}")
    return bad


def write_outbox(edge: dict, text: str, date: str) -> str:
    """Write the inert draft to state/outbox/<date>-<key>.md. Inert: a file, never a send. Returns the
    repo-relative path."""
    outbox = repo_root() / "state" / "outbox"
    outbox.mkdir(parents=True, exist_ok=True)
    rel = f"state/outbox/{date}-{edge.get('key','edge')}.md"
    (repo_root() / rel).write_text(text)
    return rel


# ----- coverage ledger (ALWAYS, $0) --------------------------------------------------------------

def _drafted_keys() -> set[str]:
    """The edge keys the stream has already drafted, read off state/coverage.jsonl, so the cadence
    never repeats an edge to the same reader. A fresh checkout has an empty ledger."""
    f = repo_root() / "state" / "coverage.jsonl"
    if not f.exists():
        return set()
    keys = set()
    for line in f.read_text().splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if row.get("action") == "drafted" and row.get("edge_key"):
            keys.add(row["edge_key"])
    return keys


def append_coverage(rows: list[dict]) -> None:
    """Append rows to state/coverage.jsonl, one JSON object per line. The committed, durable ledger that
    survives a clone (per state/README.md)."""
    f = repo_root() / "state" / "coverage.jsonl"
    f.parent.mkdir(parents=True, exist_ok=True)
    with f.open("a") as fh:
        for row in rows:
            fh.write(json.dumps(row) + "\n")


# ----- the run manifest (ALWAYS, $0) -------------------------------------------------------------

def write_manifest(date: str, did: list[dict], routing: list[dict], anchor: dict | None,
                   outbox_path: str | None, cov: dict, audit_violations: list[str]) -> str:
    """Append the per-run manifest to state/runs/<date>.json: the steps the run took (each with its
    gate), the dispatch decisions, the outbox draft, the coverage-by-demoKind view, and the audit
    result, pinned for checkpoint and resume. Returns the repo-relative path."""
    runs = repo_root() / "state" / "runs"
    runs.mkdir(parents=True, exist_ok=True)
    rel = f"state/runs/{date}.json"
    manifest = {
        "date": date,
        "tier": 1,
        "steps": did,
        "dispatch": routing,
        "anchor_edge": (anchor or {}).get("key"),
        "outbox_draft": outbox_path,
        "coverage": cov,
        "audit_violations": audit_violations,
        "spent_usd": 0.0,
        "sent": False,
        "note": "Tier-1 weekly cadence: sweep, rank, dispatch decision, $0 deterministic draft to the "
                "inert outbox, coverage update. No benchmark spend, no send. Tier-2 (engine/managed.py) "
                "is the optional monthly resumable deep run, ASK, never on a schedule.",
    }
    (repo_root() / rel).write_text(json.dumps(manifest, indent=2) + "\n")
    return rel


# ----- orchestrate -------------------------------------------------------------------------------

def run(date: str | None = None, *, do_sweep: bool = True) -> dict:
    """The full unattended cadence: sweep, rank, dispatch, draft-to-outbox, update coverage, write the
    manifest, and audit the boundary. Returns the run result (the steps, the routing, the audit). Spends
    $0: no benchmark runs, no send. do_sweep=False reuses the last landscape (for a fast dry-run that
    does not even hit the network), still $0.

    The audit is the load-bearing check: it must return empty, or the entrypoint aborts. A cadence that
    ever queued an outward action, a non-ALWAYS action, or a spend without a surfaced estimate fails
    loud here instead of shipping it."""
    register_all()
    date = date or sweep_edges.today()
    did: list[dict] = []

    # 1 + 2. SWEEP + RANK (ALWAYS, $0). Reuse the discovery loop end to end when do_sweep, else read the
    # last committed landscape so a dry-run can run with no network at all.
    if do_sweep:
        prior = sweep_edges.load_landscape()
        prior_hashes = prior.get("content_hashes", {})
        caps, hashes, unknowns = {}, {}, []
        fetched_ok = {"openai": False, "gemini": False, "claude": False}
        for src in __import__("engine.sources_registry", fromlist=["sources"]).sources():
            res = sweep_edges.fetch_one(src, prior_hashes.get(src.url))
            cid = sweep_edges._cap_id(src.vendor, src.key)
            if res["status"] == "fetched":
                sweep_edges.write_snapshot(src, res["text"], date)
                cap = sweep_edges.normalize(res, sweep_edges._seed_axis_for(src.key))
                caps[cid] = cap
                hashes[src.url] = {"hash": res["hash"], "etag": res.get("etag"),
                                   "last_modified": res.get("last_modified")}
                fetched_ok[src.vendor] = True
            elif res["status"] == "unchanged":
                if cid in prior.get("capabilities", {}):
                    caps[cid] = prior["capabilities"][cid]
                hashes[src.url] = prior_hashes.get(src.url)
                fetched_ok[src.vendor] = True
            else:
                cap = sweep_edges.normalize(res, sweep_edges._seed_axis_for(src.key))
                caps[cid] = cap
                unknowns.append(cap)
                if prior_hashes.get(src.url):
                    hashes[src.url] = prior_hashes[src.url]
        delta = sweep_edges.diff(caps, prior)
        all_competitor_fetched_ok = fetched_ok["openai"] and fetched_ok["gemini"]
        ranked = sweep_edges.rank(caps, all_competitor_fetched_ok)
        covered_dirs = sweep_edges._covered_dirs()
        coverage_carried = dict(prior.get("coverage", {}))
        sweep_edges.write_landscape(caps, hashes, ranked, coverage_carried, date)
        sweep_edges.write_changelog(delta, ranked, covered_dirs, unknowns, date)
        sweep_edges.write_brief(ranked, covered_dirs, date)
        did.append({"id": "sweep_docs", "gate": gate.ALWAYS, "outward": False})
        did.append({"id": "diff", "gate": gate.ALWAYS, "outward": False})
        did.append({"id": "write_brief", "gate": gate.ALWAYS, "outward": False})
    else:
        # No network: read the last ranked landscape, falling back to the seed edges on a fresh checkout.
        ranked = [dict(e) for e in scan.current_edges()]
        for e in ranked:
            e.setdefault("lead_score", 1)  # current_edges returns only genuine leads
            scan.stamp_demokind(e)
    did.append({"id": "rank", "gate": gate.ALWAYS, "outward": False})

    # 3. DISPATCH (ALWAYS decision, $0). route() surfaces which demonstrator would run for each lead and
    # its estimate. It does NOT run a demonstrator: every demonstrator run is ASK, surfaced for a human.
    routing = sweep_edges.route(ranked, sweep_edges._covered_dirs())

    # 4. DRAFT TO OUTBOX (ALWAYS, $0, deterministic, no model call). The newest uncovered lead.
    drafted_keys = _drafted_keys()
    anchor = _anchor_edge(ranked, drafted_keys)
    outbox_path = None
    coverage_rows = []
    if anchor is not None:
        routing_for_anchor = next((r for r in routing if r.get("key") == anchor["key"]), None)
        text = _draft_email(anchor, routing_for_anchor)
        slop = deslop_outbox(text)
        if slop:
            # A generated email must be deslop-clean. If the template ever introduces a banned char,
            # fail loud rather than ship slop to the outbox.
            raise RuntimeError("cadence draft failed the deslop gate: " + "; ".join(slop))
        outbox_path = write_outbox(anchor, text, date)
        did.append({"id": "draft_to_outbox", "gate": gate.ALWAYS, "outward": False})
        coverage_rows.append({"edge_key": anchor["key"], "demo_kind": anchor.get("demoKind"),
                              "run_date": date, "action": "drafted", "outbox": outbox_path})

    # 5. UPDATE COVERAGE (ALWAYS, $0).
    for r in routing:
        coverage_rows.append({"edge_key": r.get("key"), "demo_kind": r.get("demoKind"),
                              "run_date": date, "action": r.get("action"), "gate": r.get("gate")})
    append_coverage(coverage_rows)
    did.append({"id": "update_coverage", "gate": gate.ALWAYS, "outward": False})

    # 6. WRITE MANIFEST (ALWAYS, $0), including the coverage-by-demoKind view.
    cov = coverage_view.manifest()
    audit_violations = gate.audit(did, routing)
    manifest_path = write_manifest(date, did, routing, anchor, outbox_path, cov, audit_violations)
    did.append({"id": "write_brief", "gate": gate.ALWAYS, "outward": False})  # the manifest is a record

    return {
        "date": date, "did": did, "routing": routing, "anchor": anchor,
        "outbox_draft": outbox_path, "manifest": manifest_path,
        "coverage": cov, "audit_violations": audit_violations,
    }


def main(argv=None) -> int:
    import argparse

    p = argparse.ArgumentParser(
        description="cadence: the unattended recurring engine. Sweep, rank, dispatch decision, $0 "
                    "deterministic draft to the inert outbox, coverage update, run manifest, and a "
                    "gate.audit() that must return empty. NO benchmark spend, NO send.")
    p.add_argument("--dry-run", action="store_true",
                   help="a full $0 unattended cadence: sweep + draft to outbox, NO benchmark spend, NO "
                        "send. This is the default behavior of the cadence; the flag is explicit.")
    p.add_argument("--no-sweep", action="store_true",
                   help="skip the live doc fetch and reuse the last committed landscape (no network); "
                        "still $0")
    a = p.parse_args(argv)

    print("\n  Cadence run: the unattended engine. sweep -> rank -> dispatch -> draft-to-outbox -> "
          "coverage.")
    print("  $0: no benchmark spend, no send. Every demonstrator run is ASK, surfaced for a human.\n")

    result = run(do_sweep=not a.no_sweep)

    routing = result["routing"]
    n_use = sum(1 for r in routing if r["action"] == "use-existing")
    n_run = sum(1 for r in routing if r["action"] == "ask-run-demonstrator")
    n_build = sum(1 for r in routing if r["action"] == "ask-build-demonstrator")
    n_decline = sum(1 for r in routing if r["action"] == "ask-build-demonstrator"
                    and "declined" in (r.get("note") or ""))
    print(f"  dispatch by demoKind: {n_use} $0 use-existing, {n_run} ASK run-demonstrator "
          f"(estimate surfaced), {n_build} ASK build/parity stub(s).")
    if result["anchor"]:
        print(f"  drafted the newest uncovered lead ({result['anchor']['key']}) to "
              f"{result['outbox_draft']} (inert, no send).")
    else:
        print("  no genuine lead this run, so no email drafted (parity and behind are never pitched).")
    cov = result["coverage"]
    print(f"  coverage: {cov['registered']}/{cov['demo_kinds_total']} demoKinds registered, "
          f"{cov['with_bundle']} with a built bundle. gaps: {len(cov['gaps'])}.")
    print(f"  wrote {result['manifest']}.")

    # The boundary check. audit() MUST be empty: nothing outward or non-ALWAYS ran unattended, and no
    # spend was proposed without a surfaced estimate. A non-empty audit aborts with a nonzero exit.
    violations = result["audit_violations"]
    if violations:
        print("\n  GATE AUDIT FAILED: the cadence crossed the boundary. Violations:")
        for v in violations:
            print(f"    - {v}")
        print("  Aborting nonzero. Nothing was sent, but a boundary breach must fail loud.\n")
        return 1
    print("\n  gate.audit(): empty. Nothing outward or non-ALWAYS ran unattended, every proposed spend "
          "carried a surfaced estimate. The boundary held.\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
