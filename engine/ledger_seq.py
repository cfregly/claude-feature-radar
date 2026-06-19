"""ledger_seq: the context-editing exact-list win, with navigation removed as a confound.

The chain version (engine/ledger_compare.py, owned by another workstream) couples two things:
following a pointer chain AND preserving an accumulated list. A competitor that loses the pointer to
compaction stops reading early, which confounds the list-preservation claim (verified: gpt-5.4-mini
stopped after 10 of ~31 turns with a partial list and no final answer). This variant removes the
chain: the agent reads reports 0..N-1 in numeric order, no pointer to lose, so the ONLY thing a
context manager can hurt is the running list the agent accumulates in its own reasoning.

  Claude : context editing clears the bulky tool RESULTS in place, and leaves the reasoning (the list).
  OpenAI : compaction summarizes the whole history, the list included.
  Gemini : carries the full window, and pays for every token.

Same corpus, same prompt, same agent strategy on every arm. Only the context manager differs, so the
result is attributable to it. Every number is read off the real usage object. Measured, not asserted:
if a competitor holds the list too, that is parity and the finding goes to claude-feature-misses.

This file is self-contained on purpose, so it never edits the file another session is rewriting.
"""

from __future__ import annotations

import argparse
import json
import re
import time

from common.client import fmt_usd, get_client, load_env, repo_root
from engine.demo import build_chain, run_agent
from engine.gemini_arm import run_gemini_agent
from engine.openai_arm import run_openai_agent

# Best-to-best: the competitor's STRONGER model, so a Claude win is not a cheap-tier artifact.
OPENAI_MODEL = "gpt-5.5"
GEMINI_MODEL = "gemini-3.1-pro-preview"
URGENT_EVERY = 3  # every third id is URGENT, deterministic, so the ground truth is computed in code

PRESETS = {
    "smoke": dict(docs=12, doc_tokens=4000, trigger=12000, keep=1, max_turns=20),
    "full": dict(docs=30, doc_tokens=20000, trigger=45000, keep=1, max_turns=44),
}


def build_sequential(n_docs: int, approx_tokens: int):
    """Reports 0..n-1, read in order. No pointer chain, so navigation is trivial and the only precious
    state is the accumulated URGENT-id list. Deterministic, so the ground truth is fixed."""
    unit = "The on-call engineer reviewed the trace and confirmed the rollback completed. "
    repeats = max(1, (approx_tokens * 4) // len(unit))
    docs = {}
    for i in range(n_docs):
        urgent = (i % URGENT_EVERY == 0)
        head = (f"Incident report #{i}\nPriority: {'URGENT' if urgent else 'normal'}\n"
                f"Service: checkout-{i % 5}\n")
        docs[i] = {"id": i, "urgent": urgent, "text": head + unit * repeats}
    return docs


def seq_prompt(n_docs: int) -> str:
    last = n_docs - 1
    return (
        f"You are auditing incident reports 0 through {last} for URGENT items. Read them one at a time "
        f"in numeric order with the read_document tool: report 0, then 1, then 2, and so on through "
        f"report {last}.\n\n"
        f"A report is URGENT when its header says `Priority: URGENT`. Collect the exact ids of every "
        f"URGENT report.\n\n"
        f"You cannot rely on re-reading earlier reports, so maintain your list as you go. After you "
        f"read each report, write a single line `Running URGENT ids: [ ... ]` with your complete sorted "
        f"list of every URGENT id so far, complete and accurate on every turn.\n\n"
        f"After you read report {last}, reply with a single final line in the form `Answer: [id, id, "
        f"id]`, the complete sorted list of all URGENT report ids (for example `Answer: [0, 3, 6]`). "
        f"Output nothing else on that final line."
    )


def parse_list(text: str):
    if not text:
        return None
    m = re.search(r"Answer:\s*\[([0-9,\s]*)\]", text)
    if not m:
        return None
    return sorted({int(x) for x in m.group(1).split(",") if x.strip()})


def score(answer, gold):
    gset = set(gold)
    if answer is None:
        return dict(exact=False, recall=0.0, missing=sorted(gset), extra=[])
    aset = set(answer)
    tp = len(aset & gset)
    return dict(exact=(aset == gset), recall=(tp / len(gset)) if gset else 0.0,
                missing=sorted(gset - aset), extra=sorted(aset - gset))


def _peak(recs):
    return max((r["ctx"] for r in recs if not r.get("crashed")), default=0)


def _cost(recs):
    return sum(r["cost"] for r in recs)


def arm_claude(client, docs, cfg, prompt, model="haiku"):
    recs, text = run_agent(client, model, docs, 0, memory=False, editing=True, stop_on_overflow=True,
                           trigger=cfg["trigger"], keep=cfg["keep"], max_turns=cfg["max_turns"],
                           prompt=prompt)
    return dict(platform=f"Claude {model} (context editing)", crashed=any(r.get("crashed") for r in recs),
                answer=parse_list(text), cost=_cost(recs), peak=_peak(recs), turns=len(recs), note="")


def arm_openai(docs, cfg, prompt, model=OPENAI_MODEL):
    try:
        recs, text, m = run_openai_agent(docs, 0, model=model, compact_threshold=cfg["trigger"],
                                         max_turns=cfg["max_turns"], prompt=prompt)
        return dict(platform=f"OpenAI {m} (compaction)", crashed=False, answer=parse_list(text),
                    cost=_cost(recs), peak=_peak(recs), turns=len(recs), note="")
    except Exception as e:  # noqa: BLE001 - an API/window error is an outcome
        return dict(platform=f"OpenAI {model} (compaction)", crashed=True, answer=None, cost=0.0,
                    peak=0, turns=0, note=str(e)[:120])


def arm_gemini(docs, cfg, prompt, model=GEMINI_MODEL):
    try:
        recs, text, m = run_gemini_agent(docs, 0, model=model, max_turns=cfg["max_turns"], prompt=prompt)
        return dict(platform=f"Gemini {m} (full context)", crashed=False, answer=parse_list(text),
                    cost=_cost(recs), peak=_peak(recs), turns=len(recs), note="")
    except Exception as e:  # noqa: BLE001
        return dict(platform=f"Gemini {model} (full context)", crashed=True, answer=None, cost=0.0,
                    peak=0, turns=0, note=str(e)[:120])


# ---- stack mode: Claude's full long-agent stack (context editing + the memory tool) on the same
# exact-list task, over the chain corpus so navigation works via the pointer. The memory tool holds the
# durable list, and context editing keeps the long job feasible. Competitors hold the list in reasoning
# (no model-driven memory primitive), so compaction is their only state keeper. This is a best-to-best
# PLATFORM comparison: each side runs its strongest long-agent config.

def memory_list_prompt(start: int) -> str:
    return (
        f"You are auditing a chain of incident reports for URGENT items. Start by reading report "
        f"{start} with the read_document tool. Each report ends with the id of the next report to "
        f"read. Follow that pointer one report at a time until a report says the next one is `done`.\n\n"
        f"A report is URGENT when its header says `Priority: URGENT`. Do not rely on remembering "
        f"earlier reports. The first time you see an URGENT report, create a memory file at "
        f"`/memories/urgent.txt` and write its id on its own line. For each later URGENT report, append "
        f"its id on a new line.\n\n"
        f"When you reach `done`, view `/memories/urgent.txt`, then reply with a single final line in "
        f"the form `Answer: [id, id, id]`, the complete sorted list of all URGENT report ids from that "
        f"file (for example `Answer: [0, 3, 6]`). Output nothing else on that final line."
    )


def reasoning_list_prompt(start: int) -> str:
    return (
        f"You are auditing a chain of incident reports for URGENT items. Start by reading report "
        f"{start} with the read_document tool. Each report ends with the id of the next report to "
        f"read. Follow that pointer one report at a time until a report says the next one is `done`.\n\n"
        f"A report is URGENT when its header says `Priority: URGENT`. You cannot rely on re-reading "
        f"earlier reports, so maintain your list as you go. After you read each report, write a single "
        f"line `Running URGENT ids: [ ... ]` with your complete sorted list of every URGENT id so far, "
        f"complete and accurate on every turn.\n\n"
        f"When you reach `done`, reply with a single final line in the form `Answer: [id, id, id]`, the "
        f"complete sorted list of all URGENT report ids (for example `Answer: [0, 3, 6]`). Output "
        f"nothing else on that final line."
    )


def arm_claude_stack(client, docs, start, cfg, model="haiku"):
    recs, text = run_agent(client, model, docs, start, memory=True, editing=True, stop_on_overflow=True,
                           trigger=cfg["trigger"], keep=cfg["keep"], max_turns=cfg["max_turns"],
                           prompt=memory_list_prompt(start))
    return dict(platform=f"Claude {model} (editing + memory)", crashed=any(r.get("crashed") for r in recs),
                answer=parse_list(text), cost=_cost(recs), peak=_peak(recs), turns=len(recs), note="")


def print_round(rows, gold):
    print(f"\n  Exact-list, navigation removed. Ground-truth URGENT ids ({len(gold)}): {gold}\n")
    print(f"  {'platform':<34}{'exact':>7}{'recall':>8}{'turns':>7}{'peak ctx':>10}{'cost':>9}")
    print("  " + "-" * 75)
    for r in rows:
        s = score(r["answer"], gold)
        exact = "errored" if r["crashed"] else ("YES" if s["exact"] else "no")
        rec = "-" if r["crashed"] else f"{s['recall']*100:.0f}%"
        print(f"  {r['platform']:<34}{exact:>7}{rec:>8}{r['turns']:>7}{r['peak']:>10,}{fmt_usd(r['cost']):>9}")
        if not r["crashed"] and not s["exact"] and s["missing"]:
            print(f"      dropped ids: {s['missing']}")
        if not r["crashed"] and s["extra"]:
            print(f"      hallucinated ids: {s['extra']}")
        if r["note"]:
            print(f"      note: {r['note']}")
    print()


def run_once(client, a, cfg):
    """One run of every arm in the chosen mode. Returns (rows, gold). The corpus is seeded, so it is
    identical every run: the only variance across runs is each platform's own model/API stochasticity,
    which is exactly what --repeat measures."""
    if a.stack:
        docs, start = build_chain(cfg["docs"], cfg["doc_tokens"])
        comp_prompt = reasoning_list_prompt(start)
        claude_fn = lambda: arm_claude_stack(client, docs, start, cfg, a.claude_model)
    elif a.chain:
        # editing-only over the chain: the pointer is the navigation anchor (which clearing keeps,
        # because it is in the most recent tool result), so the list is the only thing at risk. This
        # is the clean isolation, the one the no-pointer --seq run got wrong.
        docs, start = build_chain(cfg["docs"], cfg["doc_tokens"])
        comp_prompt = reasoning_list_prompt(start)
        claude_fn = lambda: arm_claude(client, docs, cfg, comp_prompt, a.claude_model)
    else:
        docs = build_sequential(cfg["docs"], cfg["doc_tokens"])
        comp_prompt = seq_prompt(cfg["docs"])
        claude_fn = lambda: arm_claude(client, docs, cfg, comp_prompt, a.claude_model)
    gold = sorted(d["id"] for d in docs.values() if d["urgent"])
    rows = []
    for fn in (claude_fn,
               lambda: arm_openai(docs, cfg, comp_prompt),
               *([] if a.no_gemini else [lambda: arm_gemini(docs, cfg, comp_prompt)])):
        t = time.perf_counter()
        r = fn()
        r["elapsed_s"] = round(time.perf_counter() - t, 1)
        r["score"] = score(r["answer"], gold)
        rows.append(r)
    return rows, gold


def _outcome(r):
    return "err" if r["crashed"] else ("exact" if r["score"]["exact"] else "miss")


def main():
    p = argparse.ArgumentParser(description="Context editing on an exact-list workload.")
    p.add_argument("--full", action="store_true", help="the large long-stream run (default: smoke)")
    p.add_argument("--stack", action="store_true", help="Claude stack: context editing + memory tool")
    p.add_argument("--chain", action="store_true",
                   help="editing only, over the chain corpus (the pointer is the nav anchor)")
    p.add_argument("--claude-model", default="haiku", help="Claude tier: haiku | sonnet | opus")
    p.add_argument("--keep", type=int, help="context-editing keep (recent tool results); default from preset")
    p.add_argument("--repeat", type=int, default=1, help="run each cell N times, report the success rate")
    p.add_argument("--no-gemini", action="store_true")
    p.add_argument("--docs", type=int)
    p.add_argument("--doc-tokens", type=int)
    a = p.parse_args()

    cfg = dict(PRESETS["full"] if a.full else PRESETS["smoke"])
    for k in ("docs", "doc_tokens"):
        if getattr(a, k) is not None:
            cfg[k] = getattr(a, k)
    if a.keep is not None:
        cfg["keep"] = a.keep

    load_env()
    client = get_client()
    mode = ("stack (editing + memory)" if a.stack else
            "chain (editing only)" if a.chain else "sequential (editing only)")
    kind = "full" if a.full else "smoke"
    n = max(1, a.repeat)
    print(f"\n  Exact-list [{mode}, {kind}, keep={cfg['keep']}]: {cfg['docs']} reports x ~"
          f"{cfg['doc_tokens']:,} tokens. Claude={a.claude_model} vs OpenAI gpt-5.5"
          f"{'' if a.no_gemini else ' vs Gemini 3.1 Pro'}, {n} run(s)/cell.")

    t0 = time.perf_counter()
    all_runs, gold = [], None
    for i in range(n):
        rows, gold = run_once(client, a, cfg)
        all_runs.append(rows)
        tag = " | ".join(f"{r['platform'].split('(')[0].strip()}: {_outcome(r)}" for r in rows)
        print(f"  run {i + 1}/{n}: {tag}")
    elapsed = time.perf_counter() - t0

    print_round(all_runs[0], gold)
    if n > 1:
        agg = {}
        for rows in all_runs:
            for r in rows:
                d = agg.setdefault(r["platform"], {"exact": 0, "miss": 0, "err": 0, "n": 0, "cost": 0.0})
                d["n"] += 1
                d["cost"] += r["cost"]
                d[_outcome(r)] += 1
        print(f"  SUCCESS RATE over {n} runs (exact list):")
        for plat, d in agg.items():
            extra = (f", {d['miss']} wrong" if d["miss"] else "") + (f", {d['err']} errored" if d["err"] else "")
            print(f"    {plat:<34} {d['exact']}/{d['n']} exact{extra}   avg {fmt_usd(d['cost'] / d['n'])}/run")
        print()

    spend = sum(r["cost"] for rows in all_runs for r in rows)
    print(f"  total wall-clock {elapsed:.0f}s, total spend {fmt_usd(spend)}\n")

    out = {"date": "2026-06-19", "mode": mode, "claude_model": a.claude_model, "config": cfg,
           "repeat": n, "gold": gold,
           "runs": [[{k: r[k] for k in ("platform", "crashed", "answer", "cost", "peak", "turns",
                                        "note", "elapsed_s", "score")} for r in rows] for rows in all_runs]}
    (repo_root() / "data").mkdir(exist_ok=True)
    (repo_root() / "data" / "last_ledger_seq.json").write_text(json.dumps(out, indent=2))
    print(f"  wrote receipts to data/last_ledger_seq.json\n")


if __name__ == "__main__":
    main()
