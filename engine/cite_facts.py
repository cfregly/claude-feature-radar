"""cite_facts: ground every shipped fact through Claude's own Citations API.

Eat our own dog food. For each claim the deliverable makes (a price, a GA or beta status, a measured
number), we hand Claude the source document with citations enabled and ask it to quote the exact
supporting sentence. The API returns a guaranteed char pointer plus the verbatim cited_text, which we
verify resolves (source[start:end] == cited_text). The output, docs/CITED_FACTS.md, is every fact with
a verbatim quote from its source, located by the same Citations feature this repo pitches.

Sources are committed, dated snapshots under sources/ (live-doc excerpts) and our own committed
receipts under edges/*/sample.txt, so the grounding is reproducible. Run with `make cite`.
"""

from __future__ import annotations

import json

from common.client import get_client, load_env, repo_root
from common.models import get

# Each fact: the claim we make, and the committed source that must support it.
FACTS = [
    # Prices (cited to the live pricing page snapshot)
    {"claim": "Claude Haiku 4.5 input tokens cost $1 per MTok and output tokens cost $5 per MTok.",
     "source": "sources/claude_pricing_2026-06-18.txt"},
    {"claim": "Claude Sonnet 4.6 input tokens cost $3 per MTok and output tokens cost $15 per MTok.",
     "source": "sources/claude_pricing_2026-06-18.txt"},
    {"claim": "Claude Opus 4.8 input tokens cost $5 per MTok and output tokens cost $25 per MTok.",
     "source": "sources/claude_pricing_2026-06-18.txt"},
    {"claim": "A Claude prompt-cache read costs 0.1x the base input price, which is 10 percent.",
     "source": "sources/claude_pricing_2026-06-18.txt"},
    {"claim": "Code execution beyond 1,550 free hours per month is billed at $0.05 per hour per container.",
     "source": "sources/claude_pricing_2026-06-18.txt"},
    {"claim": "The Batch API gives a 50 percent discount on both input and output tokens.",
     "source": "sources/claude_pricing_2026-06-18.txt"},
    # GA / beta / feature facts (cited to the live feature docs)
    {"claim": "The Citations cited_text field does not count towards output tokens.",
     "source": "sources/claude_citations_2026-06-18.txt"},
    {"claim": "Claude citations are guaranteed to contain valid pointers to the provided documents.",
     "source": "sources/claude_citations_2026-06-18.txt"},
    {"claim": "Citations and Structured Outputs are incompatible and return a 400 error.",
     "source": "sources/claude_citations_2026-06-18.txt"},
    {"claim": "Programmatic tool calling used 24 percent fewer input tokens on agentic search benchmarks.",
     "source": "sources/claude_programmatic_tool_calling_2026-06-18.txt"},
    {"claim": "Programmatic tool calling is not eligible for Zero Data Retention.",
     "source": "sources/claude_programmatic_tool_calling_2026-06-18.txt"},
    {"claim": "Programmatic tool calling requires code_execution_20260120.",
     "source": "sources/claude_programmatic_tool_calling_2026-06-18.txt"},
    # Benchmark and competitor facts (cited to the competitor's own doc)
    {"claim": "Gemini File Search may include the page number where the information was found, via the page_number attribute.",
     "source": "sources/gemini_file_search_2026-06-18.txt"},
    {"claim": "OpenAI compaction carries forward key prior state and reasoning rather than traditional summarization.",
     "source": "sources/openai_compaction_2026-06-18.txt"},
    # Our own measured receipts (cited to the committed sample.txt)
    {"claim": "Programmatic tool calling billed 14,299 input tokens versus 54,989 for plain tool use.",
     "source": "edges/programmatic-tool-calling/sample.txt"},
    {"claim": "Claude Citations resolved 8 of 8 pointers to the exact source text.",
     "source": "edges/citations/sample.txt"},
    {"claim": "With context editing off the agent failed 3 of 3 runs, and with it on finished 3 of 3.",
     "source": "edges/context-editing/sample.txt"},
]


def ground(client, model_id, source_text, claim):
    """Ask Citations to quote the supporting text. Returns (resolved, cited_text)."""
    doc = {"type": "document",
           "source": {"type": "text", "media_type": "text/plain", "data": source_text},
           "citations": {"enabled": True}}
    prompt = (f'Quote the exact sentence or phrase from the document that supports this claim, and '
              f'nothing else: "{claim}". If the document does not support it, reply with exactly NONE.')
    msg = client.messages.create(
        model=model_id, max_tokens=1024,
        messages=[{"role": "user", "content": [doc, {"type": "text", "text": prompt}]}])
    cites = []
    for b in msg.content:
        if getattr(b, "type", None) != "text":
            continue
        for c in (getattr(b, "citations", None) or []):
            if getattr(c, "type", None) == "char_location":
                cites.append((c.start_char_index, c.end_char_index, c.cited_text))
    for s, e, txt in cites:
        if txt.strip() and source_text[s:e] == txt:  # the API guarantees this; we verify it
            return True, txt
    return False, (cites[0][2] if cites else "")


def main():
    load_env()
    client = get_client()
    # Grounding is verbatim-span extraction over ~18 facts per run, and the Citations API already
    # guarantees the char pointer. That is mid-tier extraction, not a judgment call, so it runs on
    # Sonnet (a real tier bump from Haiku) without adaptive thinking, which keeps the per-fact loop
    # fast. Bump to Opus only if a grounding miss ever traces to model reasoning rather than the source.
    model_id = get("sonnet").id
    print(f"\n  Grounding {len(FACTS)} shipped facts through Claude's own Citations API ({get('sonnet').label}).\n")

    rows = []
    for f in FACTS:
        text = (repo_root() / f["source"]).read_text()
        resolved, quote = ground(client, model_id, text, f["claim"])
        rows.append({**f, "resolved": resolved, "quote": quote})
        print(f"  {'OK  ' if resolved else 'MISS'} {f['claim'][:66]}")

    n_ok = sum(1 for r in rows if r["resolved"])
    md = [
        "# Cited facts",
        "",
        "Every shipped price and fact in this repo, grounded through Claude's own Citations API. Each "
        "row was produced by handing Claude the source document with `citations.enabled=true` and "
        "asking it to quote the supporting text. The API returned a guaranteed char pointer plus the "
        "verbatim `cited_text`, which this tool re-checks resolves to the source. Regenerate with "
        "`make cite`. Sources are committed, dated snapshots under `sources/` and our own committed "
        "receipts under `edges/*/sample.txt`.",
        "",
        f"**{n_ok} of {len(rows)} facts grounded** with a guaranteed-valid citation, located by the "
        "very feature this repo pitches.",
        "",
        "| # | claim | source | cited verbatim by the Citations API |",
        "|---|---|---|---|",
    ]
    for i, r in enumerate(rows, 1):
        q = r["quote"].replace("|", "\\|").replace("\n", " ").strip()
        tag = "" if r["resolved"] else " (UNGROUNDED, fix the claim or the source)"
        md.append(f"| {i} | {r['claim']} | `{r['source']}` | \"{q}\"{tag} |")
    md.append("")

    (repo_root() / "docs").mkdir(exist_ok=True)
    (repo_root() / "docs" / "CITED_FACTS.md").write_text("\n".join(md) + "\n")
    (repo_root() / "data").mkdir(exist_ok=True)
    (repo_root() / "data" / "last_cite.json").write_text(json.dumps(rows, indent=2))
    print(f"\n  {n_ok}/{len(rows)} grounded. wrote docs/CITED_FACTS.md\n")
    if n_ok < len(rows):
        raise SystemExit("some facts did not ground: fix the claim wording or the source snapshot")


if __name__ == "__main__":
    main()
