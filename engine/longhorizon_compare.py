"""longhorizon_compare: the cross-vendor head-to-head on the long-horizon task.

The within-Claude isolation (longhorizon.py) shows context editing is a value-add OVER CLAUDE
WITHOUT IT. This shows whether Claude's best long-agent stack beats the COMPETITORS' best on the
same heavy task: the same 8-report chain of ~40k-token payloads, each platform at full strength.

  Claude : context editing (in-place clearing) + the memory tool + caching. Bounds context and
           keeps the running count in a durable file.
  OpenAI : Responses API + server-side compaction (which SUMMARIZES the trimmed context) + caching.
  Gemini : full context carried (no server-side trim) + implicit caching, on the 1M window.

Each platform uses the best long-agent config it ships. Claude's includes the memory tool, which the
others do not ship as a model-driven primitive, so this is a PLATFORM comparison (Claude's long-agent
stack vs theirs), not an isolation of context editing alone. We measure the outcomes a founder pays
for: did it finish, did it answer correctly, peak carried context, and cost. Every number is read off
the real usage object each API returns.
"""

from __future__ import annotations

import argparse
import json
import time

from common.client import fmt_usd, get_client, load_env, repo_root
from engine.demo import build_chain, parse_answer, run_agent
from engine.gemini_arm import DEFAULT_GEMINI_MODEL, run_gemini_agent
from engine.openai_arm import DEFAULT_OPENAI_MODEL, run_openai_agent

# Same heavy preset as the longhorizon default, so the cross-vendor run is the same task.
PRESET = dict(docs=8, doc_tokens=40000, trigger=45000, keep=1, max_turns=40)


def _peak(recs):
    return max((r["ctx"] for r in recs if not r.get("crashed")), default=0)


def _cost(recs):
    return sum(r["cost"] for r in recs)


def _arm_claude(client, docs, start, cfg):
    recs, text = run_agent(client, "haiku", docs, start, memory=True, editing=True,
                           stop_on_overflow=True, trigger=cfg["trigger"], keep=cfg["keep"],
                           max_turns=cfg["max_turns"])
    crashed = any(r.get("crashed") for r in recs)
    return {"platform": "Claude Haiku 4.5 (editing + memory)", "crashed": crashed,
            "answer": parse_answer(text), "cost": _cost(recs), "peak": _peak(recs), "note": ""}


def _arm_openai(docs, start, cfg):
    try:
        recs, text, model = run_openai_agent(docs, start, compact_threshold=cfg["trigger"],
                                             max_turns=cfg["max_turns"])
        return {"platform": f"OpenAI {model} (compaction)", "crashed": False,
                "answer": parse_answer(text), "cost": _cost(recs), "peak": _peak(recs), "note": ""}
    except Exception as e:  # noqa: BLE001 - window overflow or API error is an outcome, not a stop
        return {"platform": f"OpenAI {DEFAULT_OPENAI_MODEL} (compaction)", "crashed": True,
                "answer": None, "cost": 0.0, "peak": 0, "note": str(e)[:110]}


def _arm_gemini(docs, start, cfg):
    try:
        recs, text, model = run_gemini_agent(docs, start, max_turns=cfg["max_turns"])
        return {"platform": f"Gemini {model} (full context)", "crashed": False,
                "answer": parse_answer(text), "cost": _cost(recs), "peak": _peak(recs), "note": ""}
    except Exception as e:  # noqa: BLE001
        return {"platform": f"Gemini {DEFAULT_GEMINI_MODEL} (full context)", "crashed": True,
                "answer": None, "cost": 0.0, "peak": 0, "note": str(e)[:110]}


def _outcome(row, gold):
    if row["crashed"]:
        return "errored"
    return "correct" if row["answer"] == gold else "wrong"


def print_round(rows, gold):
    print(f"\n  Cross-vendor head-to-head, one run. True URGENT count: {gold}.")
    print(f"  {'platform':<38}{'finished':>9}{'answer':>7}{'correct':>8}{'peak ctx':>10}{'cost':>10}")
    print("  " + "-" * 82)
    for r in rows:
        fin = "no" if r["crashed"] else "yes"
        ok = "-" if r["crashed"] else ("yes" if r["answer"] == gold else "NO")
        ans = "-" if r["answer"] is None else str(r["answer"])
        print(f"  {r['platform']:<38}{fin:>9}{ans:>7}{ok:>8}{r['peak']:>10,}{fmt_usd(r['cost']):>10}")
        if r["note"]:
            print(f"      note: {r['note']}")
    print()


def print_robustness(n, by_platform, gold):
    print(f"  ROBUSTNESS ({n} runs of the same task)")
    for plat, outs in by_platform.items():
        ok = outs.count("correct")
        bad = ", ".join(f"{outs.count(k)} {k}" for k in ("errored", "wrong") if outs.count(k))
        tail = f" ({bad})" if bad else ""
        print(f"    {plat:<38} {ok}/{n} finished correctly{tail}")
    print()


def print_workload_and_edge(cfg):
    print("  THE WORKLOAD (the real-world condition, stated plainly, not a toy)")
    print(f"    A tool-using agent reads a chain of {cfg['docs']} documents, each about {cfg['doc_tokens']:,}")
    print(f"    tokens (a big file, a long PDF, a fat API response), and counts a detail spread across")
    print(f"    them. This is the shape of a real product agent: many large tool results pile into the")
    print(f"    context. It is where the three platforms' DIFFERENT context mechanisms diverge, which a")
    print(f"    short prompt never reveals.")
    print()
    print("  THE EDGE THIS SURFACES (and where it does not)")
    print("    Claude clears stale tool results in place and keeps the running count in a durable memory")
    print("    file, so the count survives. OpenAI's compaction SUMMARIZES the trimmed context, which can")
    print("    drop the detail and miscount (seen above when OpenAI is wrong). Gemini carries the full")
    print("    window, paying for every token. On a short job all three finish, so the answer ties: the")
    print("    edge is reliability under a long, heavy workload, plus context size, measured not asserted.")
    print()


def main():
    p = argparse.ArgumentParser(description="Cross-vendor head-to-head on the long-horizon task.")
    p.add_argument("--repeat", type=int, default=1)
    p.add_argument("--docs", type=int)
    p.add_argument("--doc-tokens", type=int)
    p.add_argument("--no-gemini", action="store_true", help="skip Gemini (free-tier keys 429 on long runs)")
    a = p.parse_args()

    cfg = dict(PRESET)
    for k in ("docs", "doc_tokens"):
        if getattr(a, k) is not None:
            cfg[k] = getattr(a, k)

    load_env()
    client = get_client()
    print(f"\n  Long-horizon cross-vendor head-to-head. The same {cfg['docs']}-report chain, each report")
    print(f"  about {cfg['doc_tokens']:,} tokens, each platform at its best long-agent config. Claude uses")
    print(f"  context editing + the memory tool, OpenAI uses summarizing compaction, Gemini carries the")
    print(f"  full context on its 1M window. Estimated a few dollars and a few minutes.")

    docs, start = build_chain(cfg["docs"], cfg["doc_tokens"])
    gold = sum(1 for d in docs.values() if d["urgent"])
    n = max(1, a.repeat)
    by_platform, first_rows, all_rows = {}, None, []

    for i in range(n):
        rows = [_arm_claude(client, docs, start, cfg), _arm_openai(docs, start, cfg)]
        if not a.no_gemini:
            rows.append(_arm_gemini(docs, start, cfg))
        for r in rows:
            by_platform.setdefault(r["platform"], []).append(_outcome(r, gold))
        if first_rows is None:
            first_rows = rows
        all_rows.append(rows)
        if n > 1:
            tags = " | ".join(f"{r['platform'].split('(')[0].strip()}: {_outcome(r, gold)}" for r in rows)
            print(f"  run {i + 1}/{n}: {tags}")

    print_round(first_rows, gold)
    if n > 1:
        print_robustness(n, by_platform, gold)
    print_workload_and_edge(cfg)

    out = {"config": cfg, "gold": gold, "runs": n,
           "by_platform": by_platform,
           "first_round": [{k: r[k] for k in ("platform", "crashed", "answer", "cost", "peak", "note")}
                           for r in first_rows]}
    (repo_root() / "data").mkdir(exist_ok=True)
    (repo_root() / "data" / "last_longhorizon_compare.json").write_text(json.dumps(out, indent=2))
    print(f"  wrote receipts to data/last_longhorizon_compare.json\n")


if __name__ == "__main__":
    main()
