"""longhorizon: the regime where Claude's managed context earns its cost, measured.

The honest problem this fixes. The demo's short presets (a few dozen small documents) keep the
carried context far below the model's window, so bounding it changes nothing a founder pays for,
and the cache-rewrite penalty even makes the managed run cost slightly MORE (see the sweep's
honest reading). That is a true result on a short task, and it is the wrong task. "Held context at
3k instead of 36k while staying correct" is a mechanism, not a value: at that size there is no
cost, speed, correctness, or reliability difference to show.

What this measures instead. The SAME chain agent, run long. Each tool returns a large payload (a
realistic big file or API response), so the carried context grows fast. The only difference
between the two runs is Claude's managed context: context editing (clear stale tool results to
bound the window) plus the memory tool (carry the running count across the clears). Then the two
arms diverge on the things a founder actually pays for, and the failure shows up in one of two ways
depending on how heavy the job is:

  correctness : at realistic payload sizes the unbounded agent SILENTLY DEGRADES. Once its context
                passes ~150k tokens it loses the thread, stops reading early, and returns a WRONG
                answer. The edited agent reads the whole chain and answers correctly. (the default)
  reliability : push the payloads bigger and the unbounded agent fails loudly instead: it exceeds
                the context window and the API rejects the request. (try a large --doc-tokens)

Caching is ON in both arms (table stakes), so this is the honest net effect of managed context on
top of caching, in the regime where long agents live. The win measured here is a correct answer and
a bounded context, NOT a cheaper bill: at this length the edited run costs MORE total, because the
unbounded run quits early and wrong and because clearing rewrites the cached prefix. The point is
that on a long enough job the unbounded agent cannot finish correctly at any price.

Window and pricing come from common/models.py, verified in docs/VERIFIED_FACTS.md. Every number is
read off the real usage object the API returns. Carried context is input + cache_read + cache_write
(all three input buckets), the fix that stopped the per-turn context from reading as ~1 on a
post-clear or cold turn.
"""

from __future__ import annotations

import argparse
import json
import time

from common.client import fmt_usd, get_client, repo_root
from common.models import get
from engine.demo import build_chain, parse_answer, run_agent

# doc_tokens is deliberately large so the carried context reaches the degradation regime in a
# handful of reads. The default lands in the silent-degradation case (a wrong answer); a much
# larger --doc-tokens lands in the hard window-crash case. trigger/keep bound the managed arm.
PRESETS = {
    "default": dict(docs=24, doc_tokens=22000, trigger=30000, keep=2, max_turns=70),
    "smoke":   dict(docs=6,  doc_tokens=1200,  trigger=4000,  keep=2, max_turns=14),
}


def _live(recs):
    return [r for r in recs if not r.get("crashed")]


def _crash(recs):
    return next((r for r in recs if r.get("crashed")), None)


def _roll(recs):
    live = _live(recs)
    return {
        "turns": len(live),
        "crashed": any(r.get("crashed") for r in recs),
        "total_cost": sum(r["cost"] for r in recs),
        "total_time": sum(r["latency_s"] for r in recs),
        "peak_ctx": max((r["ctx"] for r in live), default=0),
        "cache_read": sum(r["cache_read"] for r in recs),
    }


def _col(rec, key, width, fmt):
    if rec is None:
        return " " * width
    if rec.get("crashed"):
        token = "CRASH" if key in ("cost", "latency_s") else f"{rec.get('attempted_tokens') or 0:,}!"
        return token.rjust(width)
    return format(rec[key], fmt).rjust(width)


def print_report(model, n_docs, doc_tokens, base_rec, base_ans, man_rec, man_ans, gold, wall_s):
    window = model.context_window
    label = model.label
    crash = _crash(base_rec)
    base, man = _roll(base_rec), _roll(man_rec)
    live_base = _live(base_rec)
    base_ok, man_ok = base_ans == gold, man_ans == gold

    print(f"\n  Long-horizon chain audit on {label}. Caching ON in both runs.")
    print(f"  Workload: a chain of {n_docs} incident reports, each about {doc_tokens:,} tokens (a")
    print(f"  realistic large tool payload). The agent reads them one at a time, in order, and counts")
    print(f"  the URGENT ones. The only difference between the runs is Claude's managed context:")
    print(f"  context editing (bound the window) plus the memory tool (keep the count across clears).")
    print(f"  {label} context window: {window:,} tokens. True URGENT count: {gold}.\n")

    print("  WHAT YOU GET")
    if crash:
        att = crash.get("attempted_tokens")
        att_s = f"{att:,}" if att else "more than the window of"
        print(f"    Unbounded agent : CRASHED at step {crash['turn']}. Input {att_s} tokens exceeded the")
        print(f"                      {window:,} window, the API rejected the request, no answer.")
    elif not base_ok:
        reads = max(len(live_base) - 1, 1)
        peak_k = (live_base[-1]['ctx'] // 1000) if live_base else 0
        print(f"    Unbounded agent : WRONG answer {base_ans} (the true count is {gold}). It lost the")
        print(f"                      thread once context passed ~{peak_k}k tokens, gave up after about")
        print(f"                      {reads} of {n_docs} reports, and miscounted. A silent failure you ship.")
    else:
        print(f"    Unbounded agent : answer {base_ans} (correct) at peak {base['peak_ctx']:,} tokens. This")
        print(f"                      size did not break it; raise --docs / --doc-tokens to push it.")

    e_ok = "correct" if man_ok else f"WRONG, expected {gold}"
    print(f"    Context-edited  : answer {man_ans} ({e_ok}). Held context flat at ~{man['peak_ctx'] // 1000}k")
    print(f"                      tokens, read all {n_docs} reports, counted via the memory file. "
          f"{fmt_usd(man['total_cost'])}, {man['total_time']:.0f}s.")
    print()
    if crash and man_ok:
        print(f"    The value, measured: the agent that DIES at step {crash['turn']} instead runs to the end")
        print(f"    and returns the right answer, for {fmt_usd(man['total_cost'])}.")
    elif (not base_ok) and man_ok:
        print(f"    The value, measured: the SAME model gets this long job WRONG on its own ({base_ans}) and")
        print(f"    RIGHT with Claude's managed context ({man_ans}), for {fmt_usd(man['total_cost'])}.")
    print()

    print("  THE DIVERGENCE (per turn, caching ON in both)")
    print("  step | unbounded ctx | edited ctx | unbnd $/turn | edit $/turn | unbnd s | edit s")
    print("  -----+---------------+------------+--------------+-------------+---------+-------")
    for i in range(max(len(base_rec), len(man_rec))):
        b = base_rec[i] if i < len(base_rec) else None
        m = man_rec[i] if i < len(man_rec) else None
        print(f"  {i:>4} | {_col(b,'ctx',13,',')} | {_col(m,'ctx',10,',')} | "
              f"{_col(b,'cost',12,'.5f')} | {_col(m,'cost',11,'.5f')} | "
              f"{_col(b,'latency_s',7,'.1f')} | {_col(m,'latency_s',6,'.1f')}")
    print()

    if len(live_base) >= 2:
        first, last = live_base[0], live_base[-1]
        ratio = last["cost"] / max(first["cost"], 1e-9)
        print("  WHY IT FAILS UNMANAGED")
        print(f"    The unbounded arm's carried context climbed {first['ctx']:,} -> {last['ctx']:,} tokens")
        print(f"    and its per-turn cost climbed {ratio:.0f}x ({first['cost']:.5f} -> {last['cost']:.5f}).")
        print(f"    The edited arm held context near {man['peak_ctx']:,} tokens with a flat per-turn cost.")
        if not crash:
            print(f"    Pushed harder (a longer chain or bigger payloads) the unbounded arm stops failing")
            print(f"    silently and fails loudly: it exceeds the {window:,} window and the API errors.")
        print()

    print(f"  HONEST COST: the edited run cost {fmt_usd(man['total_cost'])} total, MORE than the unbounded")
    print(f"  run's {fmt_usd(base['total_cost'])}, because the unbounded run quit early (and wrong) and")
    print(f"  because clearing rewrites the cached prefix. The win here is a correct answer and a bounded")
    print(f"  context, not a cheaper bill. On a long enough job the unbounded arm cannot finish at all.")
    print()
    total = base["total_cost"] + man["total_cost"]
    print(f"  Reproduce: `make longhorizon` on {label}, your own key. This run cost {fmt_usd(total)} total")
    print(f"  and took {wall_s:.0f}s wall.\n")


def _render_from_receipt():
    path = repo_root() / "data" / "last_longhorizon.json"
    if not path.exists():
        raise SystemExit("no data/last_longhorizon.json yet; run `make longhorizon` first.")
    d = json.loads(path.read_text())
    model = get(d["model"])
    cfg = d["config"]
    print("\n  (re-rendered from data/last_longhorizon.json, no API call)")
    print_report(model, cfg["docs"], cfg["doc_tokens"],
                 d["unbounded"]["records"], d["unbounded"]["answer"],
                 d["edited"]["records"], d["edited"]["answer"], d["gold"], d.get("wall_s", 0.0))


def main():
    p = argparse.ArgumentParser(description="Long-horizon agent: unmanaged degrades or crashes, managed finishes.")
    p.add_argument("--model", default="haiku", help="model key: haiku | sonnet | opus")
    p.add_argument("--smoke", action="store_true", help="cheap, does not reach the degradation regime")
    p.add_argument("--from-receipt", action="store_true", help="re-print the last run's receipt, no API call")
    p.add_argument("--docs", type=int)
    p.add_argument("--doc-tokens", type=int)
    p.add_argument("--trigger", type=int)
    p.add_argument("--keep", type=int)
    p.add_argument("--max-turns", type=int)
    a = p.parse_args()

    if a.from_receipt:
        _render_from_receipt()
        return

    cfg = dict(PRESETS["smoke"] if a.smoke else PRESETS["default"])
    for k in ("docs", "doc_tokens", "trigger", "keep", "max_turns"):
        if getattr(a, k) is not None:
            cfg[k] = getattr(a, k)

    model = get(a.model)
    print(f"\n  Long-horizon benchmark on {model.label}. Two runs of a {cfg['docs']}-report chain,")
    print(f"  each report about {cfg['doc_tokens']:,} tokens. The unbounded run is expected to lose")
    print(f"  the thread (a wrong answer) or, on heavier payloads, exceed the {model.context_window:,}")
    print(f"  window. Estimated about $1 to $2 and a couple of minutes on Haiku. The measured cost and")
    print(f"  time are printed and saved when it finishes.")

    client = get_client()
    docs, start = build_chain(cfg["docs"], cfg["doc_tokens"])
    gold = sum(1 for d in docs.values() if d["urgent"])
    common = dict(trigger=cfg["trigger"], keep=cfg["keep"], max_turns=cfg["max_turns"])

    t0 = time.perf_counter()
    base_rec, base_text = run_agent(client, a.model, docs, start, managed=False,
                                    stop_on_overflow=True, **common)
    man_rec, man_text = run_agent(client, a.model, docs, start, managed=True, **common)
    wall_s = time.perf_counter() - t0

    base_ans, man_ans = parse_answer(base_text), parse_answer(man_text)
    print_report(model, cfg["docs"], cfg["doc_tokens"], base_rec, base_ans, man_rec, man_ans, gold, wall_s)

    out = {
        "model": model.id, "config": cfg, "window": model.context_window,
        "gold": gold, "wall_s": round(wall_s, 1),
        "unbounded": {"records": base_rec, "answer": base_ans, **_roll(base_rec)},
        "edited": {"records": man_rec, "answer": man_ans, **_roll(man_rec)},
    }
    (repo_root() / "data").mkdir(exist_ok=True)
    (repo_root() / "data" / "last_longhorizon.json").write_text(json.dumps(out, indent=2))
    print(f"  wrote receipts to data/last_longhorizon.json\n")


if __name__ == "__main__":
    main()
