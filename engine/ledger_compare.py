"""ledger_compare: the context-editing competitive win on an EXACT-LIST workload.

The long-horizon count task answers a single integer, and a lossy summary keeps a number, which is
why that task reads parity. This task answers the EXACT LIST of flagged ids, held in the agent's
reasoning (no memory tool), so the mechanism difference between the platforms actually bites:

  Claude : context editing clears the bulky tool RESULTS in place but leaves the agent's reasoning
           turns (the running list) untouched, so the list stays exact.
  OpenAI : compaction SUMMARIZES the whole history, reasoning included, so the running list is
           blurred and ids drop.
  Gemini : carries the full window, so the list is exact but it pays for every token.

Same chain corpus, same prompt, same agent strategy on every arm. The only thing that differs is each
platform's context-management mechanism, so the result is attributable to it. Every number is read off
the real usage object the API returns. Measured, not asserted: if OpenAI's compaction holds the list
too, that is the finding, and it belongs in the internal both-directions analysis, not on the public radar.
"""

from __future__ import annotations

import argparse
import json
import re
import time

from common.client import fmt_usd, get_client, load_env, repo_root
from engine.demo import build_chain, run_agent
from engine.gemini_arm import DEFAULT_GEMINI_MODEL, run_gemini_agent
from engine.openai_arm import DEFAULT_OPENAI_MODEL, run_openai_agent

DEFAULT_LEDGER_OPENAI_MODEL = "gpt-5.5"
DEFAULT_LEDGER_GEMINI_MODEL = "gemini-3.1-pro-preview"

# smoke: small + cheap, just enough batches to cross the trigger a few times so each context manager
# fires. full: large payloads and a long chain, the real long-stream condition.
PRESETS = {
    "smoke": dict(docs=12, doc_tokens=4000, trigger=12000, keep=1, max_turns=22),
    "full": dict(docs=30, doc_tokens=20000, trigger=45000, keep=1, max_turns=44),
}


def ledger_prompt(start: int) -> str:
    """The exact-list task. The agent must keep the full running list in its own reply each turn,
    because it cannot re-read earlier reports once they are cleared or compacted. That is the whole
    point: the precious state lives in the reasoning, and we measure whose context manager preserves
    it."""
    return (
        f"You are auditing a chain of incident reports for URGENT items. Start by reading report "
        f"{start} with the read_document tool. Each report ends with the id of the next report to "
        f"read. Follow that pointer one report at a time until a report says the next one is `done`.\n\n"
        f"A report is URGENT when its header says `Priority: URGENT`. Your job is to collect the exact "
        f"ids of every URGENT report.\n\n"
        f"You cannot rely on re-reading earlier reports, so maintain your list as you go. After you "
        f"read each report, write a single line `Running URGENT ids: [ ... ]` containing your complete "
        f"sorted list of every URGENT id found so far. Keep that line complete and accurate on every "
        f"turn.\n\n"
        f"When you reach `done`, reply with a single final line in the form `Answer: [id, id, id]`, the "
        f"complete sorted list of all URGENT report ids (for example `Answer: [0, 3, 6]`). Output "
        f"nothing else on that final line."
    )


def parse_list(text: str):
    """Pull the final `Answer: [..]` list. Ignores the per-turn `Running URGENT ids:` lines."""
    if not text:
        return None
    m = re.search(r"Answer:\s*\[([0-9,\s]*)\]", text)
    if not m:
        return None
    ids = [int(x) for x in m.group(1).split(",") if x.strip()]
    return sorted(set(ids))


def score(answer, gold):
    gset = set(gold)
    if answer is None:
        return dict(exact=False, precision=0.0, recall=0.0, missing=sorted(gset), extra=[])
    aset = set(answer)
    tp = len(aset & gset)
    return dict(
        exact=(aset == gset),
        precision=(tp / len(aset)) if aset else 0.0,
        recall=(tp / len(gset)) if gset else 0.0,
        missing=sorted(gset - aset),
        extra=sorted(aset - gset),
    )


def _peak(recs):
    return max((r["ctx"] for r in recs if not r.get("crashed")), default=0)


def _cost(recs):
    return sum(r["cost"] for r in recs)


def arm_claude(client, docs, start, cfg):
    recs, text = run_agent(client, "haiku", docs, start, memory=False, editing=True,
                           stop_on_overflow=True, trigger=cfg["trigger"], keep=cfg["keep"],
                           max_turns=cfg["max_turns"], prompt=ledger_prompt(start))
    crashed = any(r.get("crashed") for r in recs)
    return dict(platform="Claude Haiku 4.5 (context editing)", crashed=crashed,
                answer=parse_list(text), cost=_cost(recs), peak=_peak(recs), note="")


def arm_openai(docs, start, cfg, model=DEFAULT_LEDGER_OPENAI_MODEL):
    try:
        recs, text, model = run_openai_agent(docs, start, model=model,
                                             compact_threshold=cfg["trigger"],
                                             max_turns=cfg["max_turns"], prompt=ledger_prompt(start))
        return dict(platform=f"OpenAI {model} (compaction)", crashed=False,
                    answer=parse_list(text), cost=_cost(recs), peak=_peak(recs), note="")
    except Exception as e:  # noqa: BLE001 - an API/window error is an outcome, not a stop
        return dict(platform=f"OpenAI {model or DEFAULT_OPENAI_MODEL} (compaction)", crashed=True,
                    answer=None, cost=0.0, peak=0, note=str(e)[:120])


def arm_gemini(docs, start, cfg, model=DEFAULT_LEDGER_GEMINI_MODEL):
    try:
        recs, text, model = run_gemini_agent(docs, start, model=model,
                                             max_turns=cfg["max_turns"], prompt=ledger_prompt(start))
        return dict(platform=f"Gemini {model} (full context)", crashed=False,
                    answer=parse_list(text), cost=_cost(recs), peak=_peak(recs), note="")
    except Exception as e:  # noqa: BLE001
        return dict(platform=f"Gemini {model or DEFAULT_GEMINI_MODEL} (full context)", crashed=True,
                    answer=None, cost=0.0, peak=0, note=str(e)[:120])


def verdict(rows):
    """Promote only when Claude is exact and beats every exact competitor on cost and time."""
    claude = next((r for r in rows if r["platform"].startswith("Claude ")), None)
    competitors = [r for r in rows if not r["platform"].startswith("Claude ")]
    ran = [r for r in competitors if not r.get("crashed")]
    exact_competitors = [r for r in ran if r.get("score", {}).get("exact")]
    claude_exact = bool(claude and claude.get("score", {}).get("exact"))
    all_competitors_exact = len(ran) >= 2 and len(exact_competitors) == len(ran)
    cost_win = bool(claude_exact and all_competitors_exact
                    and all(claude["cost"] < r["cost"] for r in exact_competitors))
    time_win = bool(claude_exact and all_competitors_exact
                    and all(claude.get("elapsed_s", 0) < r.get("elapsed_s", 0)
                            for r in exact_competitors))
    promotable = claude_exact and all_competitors_exact and cost_win and time_win
    return {
        "positive_signal": claude_exact,
        "promotable_edge": promotable,
        "why_not_promotable": [] if promotable else [
            reason for reason, failed in [
                ("Claude did not return the exact list", not claude_exact),
                ("not every competitor returned the exact list", not all_competitors_exact),
                ("Claude did not beat every exact competitor on cost", not cost_win),
                ("Claude did not beat every exact competitor on wall-clock time", not time_win),
            ] if failed
        ],
        "measured_axis": ["exactness", "cost", "wall_clock_time", "peak_context"],
        "cost_win_against_exact_competitors": cost_win,
        "time_win_against_exact_competitors": time_win,
        "all_competitors_exact": all_competitors_exact,
    }


def print_round(rows, gold):
    print(f"\n  Exact-list head-to-head, one run. Ground-truth URGENT ids ({len(gold)}): {gold}\n")
    print(f"  {'platform':<34}{'exact':>7}{'recall':>8}{'missed':>8}{'peak ctx':>10}{'cost':>9}")
    print("  " + "-" * 76)
    for r in rows:
        s = score(r["answer"], gold)
        exact = "errored" if r["crashed"] else ("YES" if s["exact"] else "no")
        miss = "-" if r["crashed"] else str(len(s["missing"]))
        rec = "-" if r["crashed"] else f"{s['recall']*100:.0f}%"
        print(f"  {r['platform']:<34}{exact:>7}{rec:>8}{miss:>8}{r['peak']:>10,}{fmt_usd(r['cost']):>9}")
        if not r["crashed"] and not s["exact"]:
            if s["missing"]:
                print(f"      dropped ids: {s['missing']}")
            if s["extra"]:
                print(f"      hallucinated ids: {s['extra']}")
        if r["note"]:
            print(f"      note: {r['note']}")
    print()


def main():
    p = argparse.ArgumentParser(description="Context editing on an exact-list long-stream workload.")
    p.add_argument("--full", action="store_true", help="the large long-stream run (default: smoke)")
    p.add_argument("--no-gemini", action="store_true", help="skip Gemini (free-tier keys 429 on long runs)")
    p.add_argument("--openai-model", default=DEFAULT_LEDGER_OPENAI_MODEL)
    p.add_argument("--gemini-model", default=DEFAULT_LEDGER_GEMINI_MODEL)
    p.add_argument("--docs", type=int)
    p.add_argument("--doc-tokens", type=int)
    a = p.parse_args()

    cfg = dict(PRESETS["full"] if a.full else PRESETS["smoke"])
    for k in ("docs", "doc_tokens"):
        if getattr(a, k) is not None:
            cfg[k] = getattr(a, k)

    load_env()
    client = get_client()
    kind = "full long-stream" if a.full else "smoke"
    print(f"\n  Exact-list workload ({kind}): a {cfg['docs']}-report chain, each report about "
          f"{cfg['doc_tokens']:,} tokens.\n  The agent must report the EXACT sorted list of URGENT ids, "
          f"held in its own reasoning, no memory tool.\n  Claude clears tool results in place, OpenAI "
          f"compacts (summarizes), Gemini carries the full window.")

    docs, start = build_chain(cfg["docs"], cfg["doc_tokens"])
    gold = sorted(d["id"] for d in docs.values() if d["urgent"])

    t0 = time.perf_counter()
    rows = []
    t = time.perf_counter()
    rows.append(arm_claude(client, docs, start, cfg))
    rows[-1]["elapsed_s"] = time.perf_counter() - t
    t = time.perf_counter()
    rows.append(arm_openai(docs, start, cfg, a.openai_model))
    rows[-1]["elapsed_s"] = time.perf_counter() - t
    if not a.no_gemini:
        t = time.perf_counter()
        rows.append(arm_gemini(docs, start, cfg, a.gemini_model))
        rows[-1]["elapsed_s"] = time.perf_counter() - t
    elapsed = time.perf_counter() - t0
    for r in rows:
        r["score"] = score(r["answer"], gold)

    print_round(rows, gold)
    print(f"  total wall-clock {elapsed:.0f}s, total spend {fmt_usd(sum(r['cost'] for r in rows))}\n")

    v = verdict(rows)
    print("  Verdict:")
    print(f"    positive_signal: {v['positive_signal']}")
    print(f"    promotable_edge: {v['promotable_edge']}")
    if v["why_not_promotable"]:
        print("    held because:")
        for reason in v["why_not_promotable"]:
            print(f"      - {reason}")
    print()

    out = {
        "date": "2026-06-19",
        "claim_under_test": (
            "On an exact-list long-stream workload, Claude context editing can preserve the running "
            "ledger exactly while using less cost and time than best competitor context paths."
        ),
        "sources": {
            "claude": "https://platform.claude.com/docs/en/build-with-claude/context-editing",
            "openai": "https://developers.openai.com/api/docs/guides/compaction",
            "gemini": "https://ai.google.dev/gemini-api/docs/long-context",
        },
        "config": cfg,
        "gold": gold,
        "rows": [{k: r[k] for k in (
            "platform", "crashed", "answer", "cost", "peak", "note", "elapsed_s", "score"
        )} for r in rows],
        "verdict": v,
    }
    (repo_root() / "data").mkdir(exist_ok=True)
    (repo_root() / "data" / "last_ledger_compare.json").write_text(json.dumps(out, indent=2))
    print(f"  wrote receipts to data/last_ledger_compare.json\n")


if __name__ == "__main__":
    main()
