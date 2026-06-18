"""demokinds: the canonical demoKind taxonomy and the key->demoKind seed table.

A demoKind names HOW an edge must be proven, not WHICH feature it is. The discovery loop finds and
ranks edges, each ranked edge declares a demoKind, and a Demonstrator plugin (one per demoKind) knows
how to run the Claude arm, run the competitor arms at their best, score with a machine-checkable gate,
and emit the standard Receipt. Adding a brand-new edge type means writing one new Demonstrator and
registering it under its demoKind. Discovery, ranking, the gate, drafting, and packaging never change.

This module holds three things, all deterministic and offline:

  DEMO_KINDS      the canonical list of demoKind strings the engine knows how to talk about.
  KEY_TO_DEMOKIND the seed table mapping a source key (ptc, citations, swebench) to its demoKind.
  demokind_for()  the resolver: the seed table first, then a best-effort axis guess for an unknown
                  key, so a brand-new edge still routes instead of crashing.

The seed table is the committed default. The sweep's normalizer stamps demoKind onto every edge from
this table, and a per-edge override on the landscape record always wins, so a hand-tuned demoKind is
never clobbered by the table.
"""

from __future__ import annotations

# The canonical demoKind list. Each names a way to prove an edge. The taxonomy is the one the
# framework design fixed, kept here as the single source of truth the registry and tests read.
#   token_accounting    a Claude mechanism bills fewer input/context tokens for the same answer.
#   grounding_resolution a guaranteed-valid, output-token-free source pointer into the user's doc.
#   long_horizon_survival a long, tool-heavy load FINISHES and stays correct where the other errors.
#   retention_resume    a stateful feature survives a kill and re-attach, with a negative control.
#   agentic_grading     the model iterates against a real test suite and resolves where the field ties.
#   eval_quality        one (model, effort, prompt) cell wins on the believable held-out test number.
#   cost                a workload-shaped pure-pricing-model edge, no model call, both regimes shown.
#   discovery_loop      the fetch-diff-rank-persist landscape loop runs unattended for $0.
#   other               the catch-all for narrow never-evaluated candidates behind a parity check.
DEMO_KINDS = [
    "token_accounting",
    "grounding_resolution",
    "long_horizon_survival",
    "retention_resume",
    "agentic_grading",
    "eval_quality",
    "cost",
    "discovery_loop",
    "other",
]

# The seed table: a source key (the short doc slug the sweep keys on, or a built-edge folder name)
# maps to the demoKind that proves it. The framework's edgeModelChanges fixed these assignments.
# Both the slug form (ptc, context_editing) and the built-edge folder form (programmatic-tool-calling,
# long-horizon-autonomy) are listed so the live sweep key and the seed key both resolve.
KEY_TO_DEMOKIND = {
    # token_accounting: a mechanism that keeps bytes out of the billed context.
    "ptc": "token_accounting",
    "programmatic-tool-calling": "token_accounting",
    "advisor_tool": "token_accounting",
    "mid_conversation_system": "token_accounting",
    # grounding_resolution: a guaranteed-valid source pointer into the user's own document.
    "citations": "grounding_resolution",
    "search_results": "grounding_resolution",
    "cite_facts": "grounding_resolution",
    # long_horizon_survival: a heavy, tool-heavy run finishes where the unmanaged one errors.
    "context_editing": "long_horizon_survival",
    "context-editing": "long_horizon_survival",
    "long-horizon-autonomy": "long_horizon_survival",
    "compaction": "long_horizon_survival",
    "metr": "long_horizon_survival",
    # retention_resume: a stateful feature survives a kill, proven with a continuity receipt. The
    # memory tool and managed agents both prove durability across a clear or a kill, so they route
    # here. The framework's managedAgentsCorrection scopes the verdict to doc-grounded parity plus a
    # bundle and time-axis win, never a Claude-only capability (see engine/scan.py).
    "memory_tool": "retention_resume",
    "managed_agents": "retention_resume",
    # agentic_grading: the model iterates against a real test suite.
    "swebench": "agentic_grading",
    "agentic-coding": "agentic_grading",
    "computer_use": "agentic_grading",
    "swebench_pro": "agentic_grading",
    "mcp_atlas": "agentic_grading",
    # eval_quality: a (model, effort, prompt) cell wins on the held-out test number.
    "cost-and-effort": "eval_quality",
    "cost_and_effort": "eval_quality",
    "effort": "eval_quality",
    "model_tier_migration": "eval_quality",
    "tier": "eval_quality",
    "claude_code": "eval_quality",
    # cost: a pure-pricing-model edge, no model call, both win and lose regimes shown.
    "pricing": "cost",
    "prompt_caching": "cost",
    "caching": "cost",
    "code_execution": "cost",
    "long_context": "cost",
    # discovery_loop: the engine's own $0 cadence and honesty posture.
    "edges": "discovery_loop",
    "discovery_loop": "discovery_loop",
    # other(): narrow candidates that each need a parity check FIRST.
    "fallback_credit": "other",
    "cache_diagnostics": "other",
    "build_velocity": "other",
}

# When a key is not in the seed table, the demoKind is guessed from the edge's value axis, so a
# brand-new edge still routes to a plausible demonstrator instead of crashing. The guess is recorded
# as a guess (status never-evaluated) until a demonstrator and a parity check exist, exactly as the
# absence-of-evidence rule already holds for an unevaluated lead.
AXIS_TO_DEMOKIND = {
    "cost": "cost",
    "reliability": "long_horizon_survival",
    "long-horizon": "long_horizon_survival",
    "retention": "retention_resume",
    "grounding": "grounding_resolution",
    "agentic-success": "agentic_grading",
    "correctness": "agentic_grading",
    "throughput": "token_accounting",
    "speed": "token_accounting",
    "observability": "other",
    "dx": "other",
    "unknown": "other",
}


def _norm(key: str) -> str:
    return (key or "").strip().lower()


def demokind_for(key: str, axis: str | None = None) -> str:
    """Resolve a key (and its value axis) to a demoKind. The seed table wins. An unknown key falls
    back to a best-effort axis guess, then to "other", so a never-before-seen edge always routes.

    The caller stamps the result onto the edge. A guessed kind (not in the seed table) is the signal
    that the edge is not yet covered by a built demonstrator, which the sweep records as
    never-evaluated until a demonstrator and a parity check exist."""
    k = _norm(key)
    if k in KEY_TO_DEMOKIND:
        return KEY_TO_DEMOKIND[k]
    dashed = k.replace("_", "-")
    if dashed in KEY_TO_DEMOKIND:
        return KEY_TO_DEMOKIND[dashed]
    undashed = k.replace("-", "_")
    if undashed in KEY_TO_DEMOKIND:
        return KEY_TO_DEMOKIND[undashed]
    return AXIS_TO_DEMOKIND.get(_norm(axis or "") or "unknown", "other")


def is_seeded(key: str) -> bool:
    """True when the key has an explicit seed-table demoKind, False when the kind was guessed from
    the axis. The sweep uses this to mark a guessed edge never-evaluated until it is covered."""
    k = _norm(key)
    return k in KEY_TO_DEMOKIND or k.replace("_", "-") in KEY_TO_DEMOKIND or k.replace("-", "_") in KEY_TO_DEMOKIND


def is_known_kind(kind: str) -> bool:
    return _norm(kind) in {_norm(x) for x in DEMO_KINDS}


def main():
    print(f"\n  {len(DEMO_KINDS)} canonical demoKinds:\n")
    for k in DEMO_KINDS:
        keys = sorted(src for src, dk in KEY_TO_DEMOKIND.items() if dk == k)
        print(f"    {k:22s} <- {', '.join(keys) if keys else '(axis guess only)'}")
    print()


if __name__ == "__main__":
    main()
