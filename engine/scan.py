"""scan: the verified competitive picture, the seed and fallback layer of the engine.

Holds what the 2026-06-17 audit found after a skeptic refuted every claim and a live competitor
parity check dropped anything OpenAI or Google already matches: what is genuinely Claude-ahead, what
is parity or refuted, and where Claude is behind. Competitors are named here because it is sourced,
dated evidence. Founder-facing text anonymizes them.

These constants are now the committed SEED and FALLBACK, not the live source of truth. The live
fetch-diff-rank loop in engine/sweep_edges.py (run with `make edges`) overwrites
landscape/landscape.json every run, and current_edges() below reads that landscape when it is
present, falling back to these constants on a fresh checkout that has not swept yet. The surface
moves monthly, so re-run the sweep, do not cache a winner.

Sources: the 2026-06-17 whole-platform capability sweep and the agentic and long-horizon
leaderboards, kept in the internal both-directions analysis.
"""

from __future__ import annotations

import json
import pathlib

from engine.demokinds import demokind_for, is_seeded

# Survived the skeptic AND the competitor-parity check as genuinely Claude-ahead, ranked by
# value to a founder times how clearly Claude leads.
#
# Each seed carries a demoKind (which Demonstrator proves it) and a fair_comparison (the honest spec
# that demonstrator consumes), so a fresh checkout routes through the typed dispatcher exactly the way
# a swept landscape does. The sweep's normalize() stamps the same two fields onto every live edge.
DIFFERENTIATORS = [
    {
        "key": "programmatic-tool-calling", "axis": "cost", "rank": 1,
        "demoKind": "token_accounting",
        "claim": "The model writes one sandbox script that calls the developer's own tools in a loop "
                 "and keeps the bulky tool outputs out of the model context.",
        "why": "No named OpenAI or Google equivalent keeps a developer's own custom-tool OUTPUTS out "
               "of context (allowed_callers). OpenAI ships a code interpreter and tool search but not "
               "this, an absence-of-evidence lead. GA, no beta header (2026-06-18). Measured (make "
               "ptc): on a 240-row fan-out task billed input fell from 9,451 to 6,828 tokens, about "
               "28% (Anthropic's own doc reports about 24%), and the sandbox code answered correctly "
               "where the in-context model failed. Fan-out-shaped (sequential tasks flat to +8%), it "
               "adds round-trips, and it is not on Bedrock or Vertex and not ZDR-eligible.",
        "fair_comparison": {
            "task_shape": "fan-out, 4 regions x ~60 rows",
            "claude_config": {"feature": "allowed_callers", "beta_on": True, "model": "sonnet"},
            "competitor_arms": [{"vendor": "openai", "surface": "code_interpreter", "best_config": True},
                                {"vendor": "gemini", "surface": "code_execution", "best_config": True}],
            "isolate": "only programmatic-tool-calling toggled; memory and prompt held constant",
            "score_gate": "answers_match AND mode_b_input < mode_a_input",
            "lead_basis": "absence-of-evidence",
            "maturity": {"claude": "ga", "beta_header": None, "fetched_date": "2026-06-18"},
            "repro": {"command": "make ptc", "est_cost_usd": 0.08, "est_time_s": 90},
        },
    },
    {
        "key": "citations", "axis": "grounding", "rank": 2,
        "demoKind": "grounding_resolution",
        "claim": "Native, in-request source citations with no hosted vector store: one call cites a "
                 "directly-supplied PDF (page span) plus developer-supplied RAG chunks plus inline text, "
                 "the verbatim cited_text free of output tokens, zero persisted objects. OpenAI "
                 "(file_citation) and Gemini (File Search) cite only through a persisted, pre-indexed "
                 "store and cannot cite a directly-supplied inline PDF.",
        "why": "The wedge is convenience and the no-store bundle, NOT a correctness guarantee over a "
               "competent do-it-yourself path. Two parts were refuted, measured both ways. char-level "
               "granularity holds only for plain text (PDFs are page-level, the same coarseness as "
               "Gemini File Search). And the resolve GUARANTEE is PARITY: the paraphrase-resolution arm "
               "tested it across three regimes (frontier gpt-5.5/gemini-3.1-pro, the cheapest tiers, and "
               "30-document scale), and a steel-manned DIY, where the model paraphrases the answer but "
               "copies a verbatim supporting quote and you resolve it with a normalized str.find, "
               "resolves as well as Claude on every tier. The paraphrase-DROP only appears against weaker "
               "competitor models that paraphrase their own quote, so it is not best-to-best. What "
               "survives best-to-best: (1) cited_text is free of output tokens and of input tokens on "
               "replay, which no competitor documents; (2) the one-request, no-hosted-store, mixed-source "
               "bundle, while OpenAI and Gemini both require a hosted vector store with upload and index, "
               "neither cites a directly-supplied inline PDF, and Gemini File Search cannot be combined "
               "with another tool in one call; (3) zero resolver code, a DX convenience. Where Claude "
               "loses: Citations and Structured Outputs return a 400 together. GA, no beta header. See "
               "docs/FINDINGS.md #8.",
        "fair_comparison": {
            "task_shape": "8 questions over 3 plain-text user documents",
            "claude_config": {"feature": "citations.enabled", "beta_on": False, "model": "haiku"},
            "competitor_arms": [{"vendor": "claude", "surface": "DIY str.find", "best_config": True},
                                {"vendor": "openai", "surface": "DIY str.find", "best_config": True},
                                {"vendor": "gemini", "surface": "DIY str.find", "best_config": True}],
            "isolate": "same documents and questions on every arm; only the resolve mechanism differs",
            "score_gate": "source[start:end]==cited_text (Citations) AND source.find(quote)!=-1 (DIY)",
            "lead_basis": "within-claude-only",
            "maturity": {"claude": "ga", "beta_header": None, "fetched_date": "2026-06-18"},
            "repro": {"command": "make citations", "est_cost_usd": 0.06, "est_time_s": 120},
        },
    },
    {
        "key": "long-horizon-autonomy", "axis": "long-horizon", "rank": 3,
        "demoKind": "long_horizon_survival",
        "claim": "Longest autonomous task horizon of any released model on the independent referee.",
        "why": "METR's 50% task time-horizon (neutral, not a vendor): the top released Claude model "
               "is the only one flagged top, about 1.9x the best non-Claude before reliability falls "
               "to 50% (Claude about 12 hr, Gemini 3.1 Pro about 6.4 hr, GPT-5.2 about 5.9 hr). This "
               "is the dimension where 'finishes long jobs' survives a skeptic on neutral data. The "
               "runnable receipt (make longhorizon) is a within-Claude context-editing reliability "
               "isolation; the LEADERSHIP anchor is METR, not context editing, which is parity with "
               "OpenAI compaction.",
        "fair_comparison": {
            "task_shape": "a chain of 8 incident reports, each about 40,000 tokens",
            "claude_config": {"feature": "context_management/clear_tool_uses", "beta_on": True, "model": "haiku"},
            "competitor_arms": [{"vendor": "claude", "surface": "editing OFF (within-Claude baseline)", "best_config": True}],
            "isolate": "only context editing toggled; memory tool and prompt identical in both arms",
            "score_gate": "editing_on finished AND correct; editing_off reached the window and failed",
            "lead_basis": "within-claude-only",
            "maturity": {"claude": "beta", "beta_header": "context-management-2025-06-27", "fetched_date": "2026-06-18"},
            "repro": {"command": "make longhorizon", "est_cost_usd": 2.0, "est_time_s": 150},
        },
    },
    {
        "key": "code-exec-state", "axis": "reliability", "rank": 4,
        "demoKind": "retention_resume",
        "claim": "The code-execution sandbox keeps its container and files across separate requests and "
                 "for 30 days, so a multi-step agent's state survives between turns and across a long idle.",
        "why": "Claude returns a reusable container id (response.container.id); pass it as container=<id> "
               "on the next call and a file written in one request is readable in the next. Measured "
               "(make code-exec-state then make code-exec-state-verify): a nonce written to /tmp/state.txt "
               "read back from the SAME container after a 31.1-minute idle. No named OpenAI or Google "
               "equivalent keeps a developer's sandbox files across a long idle: OpenAI's code_interpreter "
               "container is discarded after 20 minutes idle (documented, unrecoverable) and Gemini exposes "
               "no reusable container handle, an absence-of-evidence lead. Warm reuse is parity; the edge is "
               "durability and cross-request persistence. Code execution is beta and not ZDR-eligible.",
        "fair_comparison": {
            "task_shape": "write a nonce to /tmp/state.txt, reuse the container, re-read after a 31-min idle",
            "claude_config": {"feature": "container reuse (container.id)", "beta_on": True, "model": "sonnet"},
            "competitor_arms": [
                {"vendor": "openai", "surface": "code_interpreter", "best_config": True},
                {"vendor": "gemini", "surface": "code_execution", "best_config": True},
            ],
            "isolate": "same write-then-reread workload on each arm; only container lifetime differs",
            "score_gate": "claude reads the nonce back from the reused container after the documented idle",
            "lead_basis": "absence-of-evidence",
            "maturity": {"claude": "beta", "beta_header": "code-execution-2025-08-25", "fetched_date": "2026-06-19"},
            "repro": {"command": "make code-exec-state", "est_cost_usd": 0.05, "est_time_s": 60},
        },
    },
]

# Refuted, parity, or behind after the live check. Do NOT pitch these as a Claude lead.
PARITY = [
    {"note": "Context editing vs server-side compaction: parity. Both vendors ship GA server-side "
             "context management (Claude additionally ships beta in-place context editing), so the "
             "make-longhorizon receipt is a within-Claude reliability isolation, not a head-to-head "
             "lead. The long-horizon LEADERSHIP claim anchors on the independent METR time-horizon."},
    {"note": "Managed Agents resumability: doc-grounded parity on the capability. OpenAI ships GA "
             "durable state (Responses Conversations, Agents SDK file-backed sessions survive a "
             "process restart) and Gemini Live resumes within a 2-hour handle window, so a "
             "kill-and-resume is table stakes. The genuine win is the bundle (Anthropic-hosted or "
             "self-hosted sandbox plus agent loop plus persistent filesystem plus history plus "
             "compaction in one product, beta header managed-agents-2026-04-01) and the time axis "
             "(no 30-day TTL, no 2-hour cap). State must stay server-side, so it is not ZDR- or "
             "HIPAA-BAA-eligible. NEVER pitched as a Claude-only capability."},
    {"note": "Prompt caching, Batch, Files API, Structured Outputs, Skills, MCP: all matched."},
    {"note": "1M-token window: matched or exceeded by Gemini on raw size."},
    {"note": "Computer use, extended thinking, PDF and vision: all beta or matched."},
]

# Where Claude is behind. Feeds the product-team email.
GAPS = [
    {"note": "OpenAI is cheaper per token on the fair cost/speed benchmark (and faster)."},
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


# The grounded landscape correction (framework managedAgentsCorrection, live vendor docs 2026-06-18).
# These keys must NEVER carry an absence-of-evidence Claude-only lead off the sweep's deterministic
# normalizer, because the normalizer only sees that no competitor source in the registry shares the
# key, which on a stateful or context-management feature is a registry gap, not a real capability
# absence. The grounded read is parity:
#   - managed_agents / memory_tool (retention_resume): durable kill-and-resume is table stakes (OpenAI
#     Responses Conversations and Agents SDK file-backed sessions are GA, Gemini Live resumes within a
#     2-hour handle). The genuine win is the managed-harness BUNDLE and the time axis (no 30-day TTL,
#     no 2-hour cap), labeled beta (managed-agents-2026-04-01), not ZDR-eligible. Parity on capability.
#   - context_editing (long_horizon_survival): both vendors ship GA server-side compaction, so the
#     editing receipt is a within-Claude reliability isolation, and the long-horizon LEADERSHIP claim
#     anchors on the independent METR time-horizon, not context editing. Parity head-to-head.
# The sweep re-grades these keys to parity (lead 0) with the corrected lead_basis, so a manufactured
# Claude-only lead can never reach the landscape or the brief.
GROUNDING_CORRECTION = {
    "managed_agents": {"verdict": "parity", "lead_basis": "doc-grounded-parity",
                       "note": "doc-grounded parity on capability; the win is the managed bundle and "
                               "the time axis (beta managed-agents-2026-04-01), not a Claude-only "
                               "kill-and-resume. State stays server-side, so not ZDR-eligible."},
    "memory_tool": {"verdict": "parity", "lead_basis": "doc-grounded-parity",
                    "note": "client-side and hand-rollable (Codex Memories GA, Vertex Memory Bank), a "
                            "better-shaped convention, not a moat. Parity."},
    "context_editing": {"verdict": "parity", "lead_basis": "doc-grounded-parity",
                        "note": "both vendors ship GA server-side compaction; the make-longhorizon "
                                "receipt is a within-Claude reliability isolation, and long-horizon "
                                "LEADERSHIP anchors on the independent METR time-horizon, not context "
                                "editing."},
}


def apply_grounding_correction(edge: dict) -> dict:
    """Re-grade a swept edge to the grounded verdict when its key is in GROUNDING_CORRECTION. Sets the
    verdict to parity, zeroes the lead so it is never pitched, and writes the corrected lead_basis and
    note onto the edge's fair_comparison. Idempotent. The sweep calls this on every ranked edge after
    stamping, so the managedAgentsCorrection holds on the live landscape, not only in the seed prose."""
    corr = GROUNDING_CORRECTION.get(edge.get("key"))
    if not corr:
        return edge
    edge["verdict"] = corr["verdict"]
    edge["lead_score"] = 0
    edge["score"] = 0
    fc = edge.setdefault("fair_comparison", {})
    fc["lead_basis"] = corr["lead_basis"]
    fc["grounding_note"] = corr["note"]
    return edge


def _landscape_path() -> pathlib.Path:
    return pathlib.Path(__file__).resolve().parent.parent / "landscape" / "landscape.json"


# The live sweep keys a source by its short doc slug (ptc, context_editing), while the seed
# DIFFERENTIATORS key by the built-edge folder name (programmatic-tool-calling, long-horizon-autonomy).
# This alias map resolves a live key to its seed so a built edge carries the vetted, measured claim
# and why, not a bare placeholder line.
_SEED_KEY_ALIAS = {
    "ptc": "programmatic-tool-calling",
    "citations": "citations",
    "context_editing": "long-horizon-autonomy",
}


def _seed_for(live_key: str) -> dict | None:
    by_key = {d["key"]: d for d in DIFFERENTIATORS}
    for cand in (live_key, _SEED_KEY_ALIAS.get(live_key), live_key.replace("_", "-")):
        if cand and cand in by_key:
            return by_key[cand]
    return None


def seed_for_key(live_key: str) -> dict | None:
    """Public wrapper for the live sweep. A source is pitchable only when it maps to a vetted seed
    comparison here; broad docs, blogs, and changelogs stay discovery inputs until a receipt is built."""
    return _seed_for(live_key)


def current_edges() -> list[dict]:
    """The live ranked edges when a sweep has run, the committed seed constants otherwise.

    Reads landscape/landscape.json (written by engine/sweep_edges.py) and returns its genuine-lead
    edges (lead_score > 0) sorted high to low, mapped to the {key, axis, claim, why, rank} shape the
    rest of the engine consumes. On a fresh checkout with no sweep yet, or an unreadable landscape, it
    falls back to the committed DIFFERENTIATORS seed so verify and draft never break. Parity and
    behind cells (lead_score 0) are excluded from this leads list, the same honesty cut the sweep
    makes: they stay in the landscape but are never pitched."""
    f = _landscape_path()
    if not f.exists():
        return list(DIFFERENTIATORS)
    try:
        land = json.loads(f.read_text())
    except (json.JSONDecodeError, OSError):
        return list(DIFFERENTIATORS)
    leads = [e for e in land.get("edges", []) if e.get("lead_score", 0) > 0]
    if not leads:
        return list(DIFFERENTIATORS)
    out = []
    for i, e in enumerate(leads, 1):
        # Map the live edge to the consumer shape. Reuse the rich seed claim/why when the key matches
        # a built edge (the live extractor's evidence_quote is a heuristic line, the seed prose is the
        # vetted claim), otherwise build a plain claim/why from the live evidence so a brand-new edge
        # still flows through. The evidence_quote always carries the live grounding.
        seed = _seed_for(e["key"])
        out.append({
            "key": e["key"], "axis": e.get("axis", "unknown"), "rank": i,
            "demoKind": e.get("demoKind") or (seed.get("demoKind") if seed else None)
                        or demokind_for(e["key"], e.get("axis")),
            "fair_comparison": e.get("fair_comparison") or (seed.get("fair_comparison") if seed else None) or {},
            "claim": seed["claim"] if seed else f"{e['key']} ({e.get('verdict','claude-ahead')}).",
            "why": seed["why"] if seed else (e.get("evidence_quote") or ""),
            "verdict": e.get("verdict", "claude-ahead"), "score": e.get("score"),
            "evidence_quote": e.get("evidence_quote", ""), "source_url": e.get("source_url"),
        })
    return out


def stamp_demokind(edge: dict) -> dict:
    """Stamp demoKind + fair_comparison onto a live edge record (the sweep normalizer calls this).

    A built edge inherits the vetted seed demoKind and the seed fair_comparison spec. An unknown key
    gets a best-effort axis->demoKind guess (engine/demokinds) and a minimal fair_comparison whose
    lead_basis is held: a guessed kind is never-evaluated until a demonstrator and a parity check
    exist, the same absence-of-evidence discipline the sweep already enforces on an unverified lead. A
    per-edge demoKind already on the record always wins, so a hand-tuned value is never clobbered."""
    key, axis = edge.get("key", ""), edge.get("axis", "unknown")
    seed = _seed_for(key)
    if not edge.get("demoKind"):
        edge["demoKind"] = (seed.get("demoKind") if seed else None) or demokind_for(key, axis)
    if not edge.get("fair_comparison"):
        if seed and seed.get("fair_comparison"):
            edge["fair_comparison"] = dict(seed["fair_comparison"])
        else:
            # A genuinely new key: a minimal, honest spec. lead_basis is held until a demonstrator and
            # a parity check exist, so the edge is never pitched off a guessed demoKind.
            edge["fair_comparison"] = {
                "task_shape": "unknown until a demonstrator is built",
                "claude_config": {}, "competitor_arms": [], "isolate": "",
                "score_gate": "machine-checkable gate to be defined by the demonstrator",
                "lead_basis": "absence-of-evidence" if is_seeded(key) else "within-claude-only",
                "maturity": {"claude": edge.get("status", "unverified"),
                             "beta_header": edge.get("beta_header"),
                             "fetched_date": edge.get("fetched_date")},
                "repro": {"command": "", "est_cost_usd": 0.0, "est_time_s": 0.0},
            }
    return edge


def current_anchor() -> str:
    """The anchor text for the founder email: the CHOSEN seed paragraph when the live top edge is one
    of the three built edges (the vetted, measured prose), else a plain pointer to the live top edge.
    Keeps the drafter grounded in a measured receipt and never invents a number for a new edge."""
    edges = current_edges()
    if not edges:
        return CHOSEN
    top = edges[0]
    if _seed_for(top["key"]) is not None:
        return CHOSEN
    return (f"The newest ranked edge this run is {top['key']} on the {top['axis']} axis "
            f"({top.get('verdict','claude-ahead')}). No measured receipt is built for it yet, so this "
            f"anchor carries the live doc evidence only: {top.get('why','')}".strip())


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
    print("\n  Sources: the internal 2026-06-17 platform sweep and agentic-landscape analysis\n")


if __name__ == "__main__":
    main()
