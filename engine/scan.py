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
        "key": "programmatic-tool-calling", "axis": "cost", "rank": 1,
        "claim": "The model writes one sandbox script that calls the developer's own tools in a loop "
                 "and keeps the bulky tool outputs out of the model context.",
        "why": "No named OpenAI or Google equivalent keeps a developer's own custom-tool OUTPUTS out "
               "of context (allowed_callers). OpenAI ships a code interpreter and tool search but not "
               "this, an absence-of-evidence lead. GA, no beta header (2026-06-18). Measured (make "
               "ptc): on a 240-row fan-out task billed input fell from 9,451 to 6,828 tokens, about "
               "28% (Anthropic's own doc reports about 24%), and the sandbox code answered correctly "
               "where the in-context model failed. Fan-out-shaped (sequential tasks flat to +8%), it "
               "adds round-trips, and it is not on Bedrock or Vertex and not ZDR-eligible.",
    },
    {
        "key": "citations", "axis": "reliability", "rank": 2,
        "claim": "Document-grounded citations: a guaranteed-valid char/page pointer into the user's "
                 "own document, with the verbatim quote extracted by the API, free of output tokens.",
        "why": "OpenAI file citations index the model's OWN output, not the source. Gemini File "
               "Search (shipped 2026-05) returns a PAGE-level pointer into the uploaded document, so "
               "the absolute 'no competitor' line is refuted: the surviving edge is that Claude is "
               "the only GA API with a per-CHARACTER source pointer plus an API-extracted verbatim "
               "quote it guarantees valid and free of output tokens. GA, no beta header. Measured "
               "(make citations): on clean text the DIY path (model quote + your own str.find) "
               "resolves 8/8 on every vendor, so the edge is not that they cannot cite. The edge is "
               "the in-API resolve, guaranteed valid (DIY find is expected to break on paraphrase, "
               "not measured here on clean text), free of output tokens (308 vs 586), zero resolver "
               "code, char granularity, and the guarantees no competitor matches.",
    },
    {
        "key": "long-horizon-autonomy", "axis": "reliability", "rank": 3,
        "claim": "Longest autonomous task horizon of any released model on the independent referee.",
        "why": "METR's 50% task time-horizon (neutral, not a vendor): the top released Claude model "
               "is the only one flagged top, about 1.9x the best non-Claude before reliability falls "
               "to 50% (Claude about 12 hr, Gemini 3.1 Pro about 6.4 hr, GPT-5.2 about 5.9 hr). "
               "Claude does NOT lead the headline coding boards, so this is the dimension where "
               "'finishes long jobs' survives a skeptic on neutral data.",
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
    "The sharpest edge is programmatic tool calling: add allowed_callers to a tool and Claude writes "
    "one sandbox script that calls it in a loop and keeps the bulky outputs out of the model context. "
    "GA, no named competitor equivalent. Measured (make ptc): billed input fell about 28% on a 240-row "
    "fan-out task (Anthropic's doc reports about 24%), and the code answered correctly where the "
    "in-context model failed. Fan-out-shaped, it adds round-trips, and it is not on Bedrock or Vertex "
    "or ZDR. The cleanest near-binary edge is Citations: the only GA API with a per-character source "
    "pointer into the user's own document, the verbatim quote extracted and free of output tokens "
    "(Gemini File Search is page-level and still preview, OpenAI cites its own output). The third is "
    "long-horizon autonomy: the longest task horizon on METR's independent referee, about 1.9x the next "
    "best, though our own cross-vendor long run is a tie at affordable scale. Each edge has its own "
    "folder under edges/ with its demo, receipt, and emails. Re-run the sweep, do not cache a winner."
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
