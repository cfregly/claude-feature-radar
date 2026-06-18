"""scan: the candidate capability gaps, each grounded in both sides' own docs.

The data layer of the engine. It holds the gaps the 2026-06-17 scan surfaced: what Claude has,
what the competitors have, and the verdict from the skeptic pass (engine/verify.py). The committed
snapshot is what the README and the brief are built on. Re-running against live docs refreshes it.

Competitors are named here because this is sourced evidence. Founder-facing text anonymizes them.
"""

from __future__ import annotations

CANDIDATES = [
    {
        "key": "managed-runtime",
        "claim": "Only Claude has a managed agent runtime.",
        "claude": "Claude Managed Agents (beta): hosted loop, sandbox, sessions, tools.",
        "competitors": "OpenAI Responses API runs the loop server-side. Google Agent Engine has "
                       "been GA since 2025.",
        "verdict": "killed",
        "why": "Both competitors ship a hosted agent runtime. Nothing exclusive here.",
    },
    {
        "key": "agent-memory",
        "claim": "Only Claude has agent memory.",
        "claude": "A memory tool the model itself drives (memory_20250818), plus hosted stores.",
        "competitors": "Google Memory Bank is a managed memory service (GA 2025-12-16). OpenAI has "
                       "conversation persistence and a client-side SDK pattern, no managed service.",
        "verdict": "survives-narrow",
        "why": "The gap is shape, not existence: Claude's memory is a tool the model drives. State "
               "it that way, never as 'they have no memory'.",
    },
    {
        "key": "context-management",
        "claim": "Only Claude does server-side context management.",
        "claude": "Context editing clears stale tool results in place, server-side. Claude also "
                  "offers compaction, so it is the only one with both.",
        "competitors": "OpenAI has server-side compaction (summarize). Google has a client-side "
                       "ADK compaction toggle, nothing managed.",
        "verdict": "survives-narrow",
        "why": "The gap is mechanism: in-place clearing of tool results, distinct from "
               "summarize-and-replace. Do not claim a wholesale gap against OpenAI.",
    },
    {
        "key": "self-improvement",
        "claim": "Claude agents learn and improve from past runs.",
        "claude": "Memory plus edited plans. Not weight-level learning.",
        "competitors": "Same everywhere: retrieval plus memory, no weight-level continual learning.",
        "verdict": "killed",
        "why": "Nobody ships autonomous self-improvement. Easiest claim to puncture.",
    },
]

# What the two surviving-narrow dimensions combine into, and what the demo proves.
CHOSEN = (
    "the pair: a memory tool the model drives, plus in-place server-side context editing. "
    "Together they hold a long agent's per-turn cost roughly flat while keeping it correct."
)


def survivors():
    return [c for c in CANDIDATES if c["verdict"].startswith("survives")]


def main():
    print("\n  Candidate gaps, 2026-06-17 scan (competitors named here, anonymized for founders)\n")
    for c in CANDIDATES:
        mark = "KILLED  " if c["verdict"] == "killed" else "SURVIVES"
        print(f"  [{mark}] {c['claim']}")
        print(f"            Claude:      {c['claude']}")
        print(f"            Competitors: {c['competitors']}")
        print(f"            Verdict:     {c['why']}\n")
    print("  Chosen anchor:")
    print(f"    {CHOSEN}\n")
    print("  Proof:   engine/demo.py")
    print("  Sources: briefs/2026-06-17-context-editing-and-memory.md\n")


if __name__ == "__main__":
    main()
