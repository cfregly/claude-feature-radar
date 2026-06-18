"""scan: the verified competitive picture, the data layer of the engine.

Holds what the 2026-06-17 audit found after a skeptic refuted every claim: what is genuinely
Claude-ahead, what is parity or refuted, and where Claude is behind. Competitors are named here
because it is sourced evidence. Founder-facing text anonymizes them. Re-run the audit to refresh.

Source: briefs/2026-06-17-verified-picture.md
"""

from __future__ import annotations

# Survived the skeptic as genuinely Claude-ahead.
DIFFERENTIATORS = [
    {
        "key": "context-editing", "axis": "cost/context",
        "claim": "Server-side in-place clearing of stale tool results (clear_tool_uses_20250919).",
        "why": "OpenAI's trimmer is client-side, its compaction summarizes, Gemini's is "
               "realtime-only. Only Claude ships in-place clearing as a managed API feature. It "
               "bounds context, it is not a raw cost win when caching is on.",
    },
    {
        "key": "self-hosted-sandbox", "axis": "maintenance",
        "claim": "Managed agent loop on Anthropic, tool execution on your own infrastructure.",
        "why": "No competitor ships this exact hybrid (others host everything or you host "
               "everything). Beta.",
    },
    {
        "key": "memory-tool", "axis": "developer-experience",
        "claim": "A memory tool the model itself drives over durable files.",
        "why": "Only Anthropic has model-driven plus read-write plus durable files plus "
               "cross-session as an API primitive. Architecture-shape lead, beta.",
    },
]

# Refuted or parity. Do NOT pitch these.
PARITY = [
    {"note": "Claude Code is parity with OpenAI Codex and Google Antigravity."},
    {"note": "Hosted agent runtime is parity (OpenAI Responses loop, Google Vertex Agent Engine)."},
    {"note": "Dreaming (async memory consolidation): parity (Codex Memories plus Vertex Memory Bank)."},
    {"note": "Outcomes (rubric self-grade plus retry): refuted (Google Jules' critic plus Vertex)."},
]

# Where Claude is behind. Feeds the product-team email.
GAPS = [
    {"note": "OpenAI is cheaper on the fair benchmark."},
    {"note": "Cache retention: Gemini arbitrary TTL, OpenAI 24h, vs Claude fixed 5m or 1h."},
    {"note": "OpenAI's Secure MCP Tunnel went GA 2026-05-27, ahead of Claude's beta."},
    {"note": "Long-context billing: GPT-5.5 larger ceiling, Gemini arbitrary-TTL caching over 1M."},
]

CHOSEN = (
    "context editing (clear_tool_uses_20250919): server-side, in-place clearing of stale tool "
    "results, the only managed-API in-place clearing primitive. It bounds a long tool-heavy "
    "agent's context with one beta header, without you building eviction logic. Honest scope: it "
    "bounds context, it is not a cheaper bill when caching is on."
)


def main():
    print("\n  Verified competitive picture, 2026-06-17 (every claim skeptic-refuted)\n")
    print("  Claude-ahead (survived the skeptic):")
    for d in DIFFERENTIATORS:
        print(f"    + [{d['axis']}] {d['claim']}")
        print(f"        {d['why']}")
    print("\n  Parity or refuted (do not pitch):")
    for p in PARITY:
        print(f"    = {p['note']}")
    print("\n  Where Claude is behind (the product email):")
    for g in GAPS:
        print(f"    - {g['note']}")
    print(f"\n  Anchor for the founder email:\n    {CHOSEN}")
    print("\n  Source: briefs/2026-06-17-verified-picture.md\n")


if __name__ == "__main__":
    main()
