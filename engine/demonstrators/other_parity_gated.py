"""other_parity_gated: the thin demonstrators for the narrow never-evaluated candidates.

These are the long-tail edges from the master brief that each need a PARITY CHECK FIRST, before any
demonstration is even valid: a fallback-credit refusal-recovery, a cache_miss_reason observability
signal, and the Claude Code issue-to-PR build-velocity loop. All three route to the single demoKind
"other" (the registry keys one demonstrator per demoKind), and this one demonstrator dispatches
internally by edge key to the right thin proof.

WHY A PARITY-CHECK PRECONDITION. Each of these is a candidate Claude surface with NO head-to-head
evidence yet that a competitor lacks an equivalent. The engine's own honesty rule (CLAUDE.md, "Verify
both sides, then keep what survives") forbids pitching a lead that a skeptic has not first failed to
break. So this demonstrator REFUSES to pitch until the parity check passes:

    applicable(edge) returns False until the edge's parity check is recorded as passed.

A declined edge files an ASK "precondition unmet" stub on dispatch (see registry.dispatch), so the
cadence surfaces "run the parity check for fallback_credit" to the human and the edge stays
never-evaluated, never pitched, exactly the absence-of-evidence discipline the rest of the engine
already enforces. This is the whole point of the catch-all kind: it is the holding pen for an edge
the engine will not assert until a skeptic has been pointed at it.

THE PARITY CHECK. The skeptic pass is engine/verify.py (Claude tries to break each candidate). That is
a paid, live call, so it is NOT run inside the offline cadence or the tests. Instead the parity-check
RESULT is recorded deterministically per edge in PARITY_CHECKS below: a recorded verdict of
"survives" (the skeptic could not break it AND every competitor source was checked) flips applicable()
to True; "killed" or "unchecked" keeps the edge held. parity_check_passed(edge) is the single gate
both applicable() and the CLI read, so the rule lives in one place. The default state of every entry
here is unchecked, because none of these candidates has survived a head-to-head skeptic yet, which is
exactly why they are in the long tail and not in the three built leads.

DEPENDENCIES: none on the default path. The thin proofs that would spend a credit (a live refusal to
trigger the fallback, a deliberate cache miss, a Claude Code run) are described and gated, not run in
the offline cadence; the live runner is an opt-in, the same shape as retention_resume's live arm. The
SDK is never imported at module load.
"""

from __future__ import annotations

import pathlib
import sys

# repo root on the path, for common/ and engine/ when run as a script.
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))

from engine.demonstrators.base import Arm, BaseDemonstrator, CostEstimate, Verdict
from engine.demonstrators.registry import register
from engine.demonstrators.shared import platform

# --------------------------------------------------------------------------- the parity-check ledger
#
# Each candidate edge, its claimed Claude surface, the competitor surface to parity-check it against,
# the machine-checkable gate the thin proof would run, and the recorded parity-check verdict. The
# verdict is "unchecked" by default for every entry, because none of these has yet survived a live
# skeptic against a fetched competitor surface. A human runs engine/verify.py (the skeptic pass) and
# records "survives" or "killed" here; only "survives" flips the edge to pitchable. Until then the
# edge is held never-evaluated, never pitched, which is the honest state.
#
# PARITY_VERDICTS:
#   "unchecked" the default. No skeptic pass has been run against a fetched competitor surface, so the
#               edge is held. applicable() returns False, dispatch files a "run the parity check" stub.
#   "survives"  the skeptic could not break the claim AND the competitor surface was fetched and shows
#               no named equivalent. applicable() returns True, the thin proof may run (still ASK on
#               any spend). The lead_basis is absence-of-evidence, all-fetched.
#   "killed"    the skeptic broke it or a competitor ships a near-equivalent. The edge is parity or
#               behind, never pitched. applicable() stays False.

PARITY_CHECKS = {
    "fallback_credit": {
        "axis": "correctness",
        "claude_surface": "server-side model fallback (Fable/Mythos) with a fallback credit: recover "
                          "from a refusal by falling back to another model inside a single call",
        "competitor_surface": "client-side retry loop a founder builds on a competitor (no named "
                              "single-call server-side cross-model fallback with a credit)",
        "thin_proof": ("trigger a refusal/failure on the primary model, show the server-side fallback "
                       "recovering in ONE call with the credit applied, vs the client-side retry loop"),
        "score_gate": "recovery_happened_in_one_call AND credit_applied",
        "maturity_note": ("Fable/Mythos may be access-gated (a dev key reaches Haiku/Sonnet/Opus, not "
                          "Fable without Mythos access); an inaccessible tier is reported unavailable, "
                          "never faked"),
        "source_url": "https://platform.claude.com/docs/en/api/openai-sdk",
        "parity_verdict": "unchecked",   # no skeptic pass run against a fetched competitor surface yet
    },
    "cache_diagnostics": {
        "axis": "observability",
        "claude_surface": "per-request cache_miss_reason in the usage object: an explainer of WHY a "
                          "cache read missed (prefix below the minimum, changed prefix, expired TTL)",
        "competitor_surface": "OpenAI and Gemini usage objects (no named per-request cache-miss-reason "
                              "field surfaced to the caller)",
        "thin_proof": ("construct each cache-miss condition deliberately and show Claude reports the "
                       "miss reason per request where the competitor usage object is silent, turning a "
                       "silent cost leak into a debuggable signal"),
        "score_gate": "miss_reason_present_on_claude AND absent_on_every_fetched_competitor",
        "maturity_note": "a narrow observability candidate; confirm the field name against the live "
                         "usage schema before quoting, it can move",
        "source_url": "https://platform.claude.com/docs/en/build-with-claude/prompt-caching",
        "parity_verdict": "unchecked",
    },
    "build_velocity": {
        "axis": "agentic-success",
        "claude_surface": "Claude Code as a programmable build surface: the @claude GitHub Action opens "
                          "PRs following CLAUDE.md, runs review on every PR, runs headless in CI; "
                          "plugins bundle skills, agents, hooks, and MCP as one marketplace unit",
        "competitor_surface": "OpenAI Codex CLI and SKILL.md, Google Gemini CLI (every headline "
                              "primitive now has a shipping competitor equivalent)",
        "thin_proof": ("time the end-to-end loop, issue to merged PR following CLAUDE.md headless in "
                       "CI, against Codex CLI and Gemini CLI on the same repo and issue, counting "
                       "human-intervention steps and glue-code lines"),
        "score_gate": "pr_merged_following_claude_md AND fewer_human_steps_than_competitor",
        "maturity_note": ("the master brief flags this is hard to prove with one clean number and "
                          "every headline primitive now has a competitor equivalent, so it is treated "
                          "as supporting color, not an anchored head-to-head; parity is the likely read"),
        "source_url": "https://docs.claude.com/en/docs/claude-code/github-actions",
        "parity_verdict": "unchecked",
    },
}


def parity_check_passed(edge_key: str) -> bool:
    """The single gate both applicable() and the CLI read: an edge is pitchable only when its recorded
    parity-check verdict is "survives". Any other state (unchecked, killed, or an unknown key) holds the
    edge never-evaluated. The rule lives here so the demonstrator cannot forget it."""
    entry = PARITY_CHECKS.get(edge_key)
    return bool(entry) and entry.get("parity_verdict") == "survives"


def parity_check_state(edge_key: str) -> str:
    """The recorded parity-check verdict for an edge: unchecked, survives, killed, or unknown."""
    entry = PARITY_CHECKS.get(edge_key)
    return entry.get("parity_verdict", "unknown") if entry else "unknown"


# --------------------------------------------------------------------------- the Demonstrator interface
#
# One demonstrator for the "other" demoKind. It dispatches internally by edge key, and its applicable()
# is the parity-check precondition: it declines (returns False) until the edge's parity check is
# recorded as "survives". A declined edge files a "precondition unmet" ASK stub on dispatch, so the
# cadence proposes running the parity check and the edge stays never-evaluated, never pitched.

class OtherParityGatedDemonstrator(BaseDemonstrator):
    demo_kind = "other"

    def applicable(self, edge: dict) -> bool:
        """The parity-check precondition. True only when the edge's demoKind is "other", the edge is a
        known candidate, AND its parity check passed. An unchecked or killed candidate returns False, so
        dispatch files the "precondition unmet, run the parity check" stub and the edge is held."""
        kind = edge.get("demoKind") or edge.get("demo_kind")
        if kind != self.demo_kind:
            return False
        return parity_check_passed(edge.get("key", ""))

    def estimate(self, edge, spec):
        """The thin proof's declared spend. The default cadence never gets here (applicable() is False
        until the parity check passes), so this estimate is what the ASK gate would surface once an edge
        is unblocked. Each thin proof is a small bounded run, well under the per-demo cap. fallback and
        cache-miss are cents, the Claude Code loop is a few minutes of headless CI."""
        key = edge.get("key", "")
        if key == "build_velocity":
            return CostEstimate(
                usd=0.5, wall_clock_s=300.0, command="(opt-in) the Claude Code issue-to-PR loop",
                note="a bounded headless Claude Code run on a fixed repo and issue, gated behind a "
                     "passing parity check; not run in the offline cadence",
            )
        return CostEstimate(
            usd=0.05, wall_clock_s=30.0, command=f"(opt-in) the {key} thin proof",
            note=f"a cents-scale {key} proof (a deliberate refusal or cache miss), gated behind a "
                 f"passing parity check; not run in the offline cadence",
        )

    def run_claude_arm(self, edge, spec):
        """The Claude side. On the default path (parity check not passed) this returns a held arm that
        does NOT run the proof, carrying the parity-check state so the receipt records why it is held.
        The live thin proof is an opt-in, the same shape as retention_resume's live arm, and is not run
        inside this offline method."""
        key = edge.get("key", "")
        entry = PARITY_CHECKS.get(key, {})
        platform.used("cost", f"parity-gated candidate ({key}), held until the parity check passes")
        passed = parity_check_passed(key)
        return Arm(
            provider="anthropic", model="(candidate, no model run on the default path)",
            ran=False, cost_usd=0.0,
            metric={
                "candidate": key,
                "parity_check": parity_check_state(key),
                "claude_surface": entry.get("claude_surface", ""),
                "score_gate": entry.get("score_gate", ""),
                "pitchable": passed,
            },
            note=("the parity check passed, the thin proof may run as an opt-in" if passed
                  else "held: the parity check has not passed, so this candidate is never-evaluated and "
                       "is not pitched (run engine/verify.py, then record the verdict)"),
        )

    def run_competitor_arms(self, edge, spec):
        """No competitor arm runs on the default path. The whole point of the parity gate is that the
        head-to-head is NOT yet valid: until a skeptic has been pointed at the candidate against a
        fetched competitor surface, there is no honest arm to run. Returning an empty list keeps the
        receipt's honesty contract from ever reading a claude-ahead verdict (it stands only when every
        competitor arm ran or the lead is an all-fetched absence-of-evidence), which is exactly the
        held state these candidates must stay in."""
        return []

    def score(self, claude, competitors, spec):
        """The gate. On the default path the verdict is never-evaluated by construction: the candidate
        is held until its parity check passes. When the recorded parity check is "survives", the verdict
        becomes within-claude-only (the thin proof is the opt-in that would then run), never an
        unconditional claude-ahead off an unrun head-to-head."""
        key = (claude.metric or {}).get("candidate", "")
        state = parity_check_state(key)
        if parity_check_passed(key):
            return Verdict(
                verdict="within-claude-only", passed=False,
                metric={"candidate": key, "parity_check": state,
                        "next": "run the opt-in thin proof to measure the within-Claude value-add"},
                note="parity check passed; the candidate may be proven by the opt-in thin proof, still "
                     "ASK on spend, and even then the verdict stays within-Claude until a head-to-head "
                     "runs",
            )
        return Verdict(
            verdict="never-evaluated", passed=False,
            metric={"candidate": key, "parity_check": state,
                    "held_reason": "the parity check has not passed"},
            note="never-evaluated and not pitched: the parity check (engine/verify.py skeptic pass) has "
                 "not been recorded as surviving against a fetched competitor surface",
        )

    def receipt(self, edge, claude, competitors, verdict, spec):
        key = edge.get("key", "")
        entry = PARITY_CHECKS.get(key, {})
        return self.build_receipt(
            edge, claude, competitors, verdict, spec,
            workload={
                "task_shape": entry.get("thin_proof", "a thin parity-gated candidate proof"),
                "models": {"claude": claude.model, "competitors": entry.get("competitor_surface", "")},
                "features_on": [entry.get("claude_surface", "")],
                "assumptions": ("this is a NEVER-EVALUATED candidate from the long tail. It is held and "
                                "not pitched until the parity check (the engine/verify.py skeptic pass) "
                                "is run against a fetched competitor surface and recorded as surviving. "
                                "Even then the thin proof is an opt-in (ASK on spend) and the verdict "
                                "stays within-Claude until a real head-to-head runs. " +
                                entry.get("maturity_note", "")),
                "scope": "a parity-check precondition, not a measured head-to-head",
            },
            grounding=[{"claim": entry.get("claude_surface", ""),
                        "source_url": entry.get("source_url", ""), "date": "2026-06-18"}],
            fairness={
                "best_to_best": "the competitor surface to parity-check against is named "
                                "(" + entry.get("competitor_surface", "") + "), not a strawman",
                "isolate": "the parity check isolates whether a competitor ships a named equivalent "
                           "before any claim; until it passes, the edge is held, never pitched",
            },
        )


register(OtherParityGatedDemonstrator())


# --------------------------------------------------------------------------- the CLI receipt

def main(argv=None) -> int:
    import argparse

    p = argparse.ArgumentParser(
        description="other_parity_gated: the thin parity-gated candidates (fallback credit, "
                    "cache_miss_reason, Claude Code build velocity). Each is HELD never-evaluated and "
                    "not pitched until its parity check (the engine/verify.py skeptic pass) survives "
                    "against a fetched competitor surface. NO API call on this view, $0.")
    p.add_argument("--edge", default=None, help="show one candidate (fallback_credit, cache_diagnostics, "
                                                "build_velocity); default shows all")
    a = p.parse_args(argv)

    keys = [a.edge] if a.edge else list(PARITY_CHECKS)
    print("\n  Parity-gated candidates (the long tail). Each is HELD until its parity check survives.")
    print("  Run the skeptic pass (engine/verify.py), then record the verdict here. $0 view, no API call.\n")
    for key in keys:
        entry = PARITY_CHECKS.get(key)
        if not entry:
            print(f"  unknown candidate: {key}")
            continue
        state = entry["parity_verdict"]
        pitch = "PITCHABLE" if parity_check_passed(key) else "HELD (never-evaluated, not pitched)"
        print(f"  === {key} [{entry['axis']}] ===")
        print(f"    parity check: {state}  ->  {pitch}")
        print(f"    Claude surface:     {entry['claude_surface']}")
        print(f"    parity-check vs:    {entry['competitor_surface']}")
        print(f"    thin proof (gated): {entry['thin_proof']}")
        print(f"    score gate:         {entry['score_gate']}")
        print(f"    note:               {entry['maturity_note']}")
        print(f"    source:             {entry['source_url']} (2026-06-18)\n")
    held = [k for k in keys if not parity_check_passed(k)]
    print(f"  {len(held)} of {len(keys)} candidate(s) held: the parity check has not survived, so they")
    print("  stay never-evaluated and are never pitched. This is the honest state of the long tail.\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
