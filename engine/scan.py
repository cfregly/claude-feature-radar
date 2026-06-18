"""scan: the verified competitive picture, the data layer of the engine.

Holds what the 2026-06-17 audit found after a skeptic refuted every claim and a live competitor
parity check dropped anything OpenAI or Google already matches: what is genuinely Claude-ahead, what
is parity or refuted, and where Claude is behind. Competitors are named here because it is sourced,
dated evidence. Founder-facing text anonymizes them. Re-run the audit to refresh, the surface moves
monthly.

Sources:
  briefs/2026-06-17-platform-edge.md       the whole-platform capability sweep
  briefs/2026-06-17-agentic-landscape.md   the agentic and long-horizon leaderboards
"""

from __future__ import annotations

# Survived the skeptic AND the competitor-parity check as genuinely Claude-ahead, ranked by
# value to a founder times how clearly Claude leads.
DIFFERENTIATORS = [
    {
        "key": "citations", "axis": "reliability", "rank": 1,
        "claim": "Document-grounded citations: a guaranteed-valid char/page pointer into the user's "
                 "own document, with the verbatim quote extracted by the API, free of output tokens.",
        "why": "OpenAI and Google only annotate web-search URLs. Neither exposes a pointer into a "
               "user-supplied document. GA, no beta header. Measured (make citations): Claude "
               "resolves 8/8 pointers to the exact source text, the prompt-for-quotes workaround "
               "resolves 0/8 on OpenAI and on Claude without the feature, and the one competitor "
               "that resolves (Gemini, 7/8) burns 148x the output tokens to brute-force the offsets.",
    },
    {
        "key": "long-horizon-autonomy", "axis": "reliability", "rank": 2,
        "claim": "Longest autonomous task horizon of any released model on the independent referee.",
        "why": "METR's 50% task time-horizon (neutral, not a vendor): the top released Claude model "
               "is the only one flagged top, about 1.9x the best non-Claude before reliability falls "
               "to 50% (Claude about 12 hr, Gemini 3.1 Pro about 6.4 hr, GPT-5.2 about 5.9 hr). "
               "Claude does NOT lead the headline coding boards, so this is the dimension where "
               "'finishes long jobs' survives a skeptic on neutral data.",
    },
    {
        "key": "programmatic-tool-calling", "axis": "cost", "rank": 3,
        "claim": "The model writes sandbox code that calls the developer's own function tools and "
                 "keeps bulky tool outputs out of context.",
        "why": "No named OpenAI or Google equivalent (absence of evidence, not a head-to-head loss). "
               "Anthropic's own measurement is a 37% input-token cut on complex tasks. BETA on the "
               "live pages, and the 37% is not reproduced on our key, so it does not anchor an email.",
    },
]

# Refuted, parity, or behind after the live check. Do NOT pitch these as a Claude lead.
PARITY = [
    {"note": "SWE-bench Verified: a ceiling tie at 79.2 percent, no clean three-way, no 90+ is real."},
    {"note": "Terminal-Bench 2.0 and 2.1: GPT-5.5 leads or ties at the top."},
    {"note": "Context editing: beta, and OpenAI's /responses/compact endpoint is arguably ahead."},
    {"note": "Prompt caching, Batch, Files API, Structured Outputs, Skills, MCP: all matched."},
    {"note": "1M-token window: matched or exceeded by Gemini on raw size."},
    {"note": "Computer use, extended thinking, PDF and vision: all beta or matched."},
]

# Where Claude is behind. Feeds the product-team email.
GAPS = [
    {"note": "OpenAI is cheaper per token on the fair cost/speed benchmark (and faster)."},
    {"note": "Terminal-Bench coding-agent leaderboards: GPT-5.5 ahead."},
    {"note": "BrowseComp agentic web search: GPT-5.5 Pro leads at about 90 percent."},
    {"note": "Cache retention: Gemini arbitrary TTL, OpenAI 24h, vs Claude fixed 5m or 1h."},
    {"note": "Citations cannot be combined with Structured Outputs (the API returns a 400)."},
]

CHOSEN = (
    "Citations: a GA, document-grounded source pointer (char index for text, page for PDF) into the "
    "user's OWN document, with the verbatim quote extracted by the API and free of output tokens. No "
    "competitor exposes a pointer into a user-supplied document, they only cite web URLs. Measured: "
    "Claude resolves 8/8 pointers to the exact source text by construction, the prompt-for-quotes "
    "workaround resolves 0/8 on OpenAI and on Claude without the feature, and the only competitor "
    "that resolves at all (Gemini) costs 37x more to brute-force the offsets. This is the trust layer "
    "for any product built over the user's own documents. Second pillar: Claude has the longest "
    "autonomous task horizon of any released model on METR's independent referee, about 1.9x the next "
    "best, for the founder building agents that must finish long jobs."
)


def main():
    print("\n  Verified competitive picture, 2026-06-17 (skeptic-refuted + live parity check)\n")
    print("  Claude-ahead (survived the skeptic and the parity check), ranked:")
    for d in DIFFERENTIATORS:
        print(f"    {d['rank']}. [{d['axis']}] {d['claim']}")
        print(f"        {d['why']}")
    print("\n  Parity or refuted (do not pitch as a lead):")
    for p in PARITY:
        print(f"    = {p['note']}")
    print("\n  Where Claude is behind (the product email):")
    for g in GAPS:
        print(f"    - {g['note']}")
    print(f"\n  Anchor for the founder email:\n    {CHOSEN}")
    print("\n  Sources: briefs/2026-06-17-platform-edge.md, briefs/2026-06-17-agentic-landscape.md\n")


if __name__ == "__main__":
    main()
