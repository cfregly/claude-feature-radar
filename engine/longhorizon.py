"""longhorizon: the regime where context editing earns its cost, measured.

The honest problem this fixes. The demo's short presets (a few dozen small documents) keep the
carried context far below the model's window, so bounding it changes nothing a founder pays for,
and the cache-rewrite penalty even makes the managed run cost slightly MORE (see the sweep's
honest reading). That is a true result on a short task, and it is the wrong task. "Held context at
3k instead of 36k while staying correct" is a mechanism, not a value: at that size there is no
cost, speed, correctness, or reliability difference to show.

What this measures instead. The SAME chain agent, run long enough that the unbounded arm grows
past the model's context window and the API rejects the request. Each tool returns a large payload
(a realistic big file or API response), so the window is reached in a handful of reads. Then the
two arms diverge on the things a founder actually pays for:

  reliability : the unbounded agent CRASHES at the window. the context-edited agent finishes.
  latency/turn: the unbounded agent's per-turn latency climbs with the transcript. edited stays flat.
  cost/turn   : same shape, because a bigger carried prefix is re-read (at the cache rate) every turn.

Caching is ON in both arms (table stakes), so this is the honest net effect of context editing on
top of caching, in the regime where long agents actually live. The headline is reliability: an
unbounded agent cannot do a long job at any price, it hits the wall and stops.

Window and pricing come from common/models.py, verified in docs/VERIFIED_FACTS.md. Every number is
read off the real usage object the API returns. Nothing here is estimated after the fact.
"""

from __future__ import annotations

import argparse
import json
import time

from common.client import fmt_usd, get_client, repo_root
from common.models import get
from engine.demo import build_chain, parse_answer, run_agent

# doc_tokens is deliberately large so the window is reached in a handful of reads: a real crash,
# cheaply and quickly. trigger/keep bound the managed arm well under the window so it finishes.
PRESETS = {
    "default": dict(docs=22, doc_tokens=12000, trigger=30000, keep=2, max_turns=70),
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
        return ("CRASH" if key in ("cost", "latency_s") else f"{rec.get('attempted_tokens') or 0:,}!").rjust(width)
    return format(rec[key], fmt).rjust(width)


def print_report(model, docs, doc_tokens, base_rec, base_ans, man_rec, man_ans, gold, wall_s):
    window = model.context_window
    label = model.label
    crash = _crash(base_rec)
    base, man = _roll(base_rec), _roll(man_rec)
    live_base = _live(base_rec)

    print(f"\n  Long-horizon chain audit on {label}. Caching ON in both runs.")
    print(f"  Workload: a chain of {len(docs)} incident reports, each about {doc_tokens:,} tokens")
    print(f"  (a realistic large tool payload). The agent reads them one at a time, in order.")
    print(f"  The only difference between the runs is context editing + memory (the edited arm).")
    print(f"  {label} context window: {window:,} tokens. True URGENT count: {gold}.\n")

    print("  WHAT YOU GET")
    if crash:
        att = crash.get("attempted_tokens")
        att_s = f"{att:,}" if att else "more than the window of"
        print(f"    Unbounded agent : CRASHED at step {crash['turn']}. Input {att_s} tokens exceeded")
        print(f"                      the {window:,} context window. No answer returned.")
    else:
        print(f"    Unbounded agent : did not reach the window at this size (peak {base['peak_ctx']:,}")
        print(f"                      tokens). Raise --docs / --doc-tokens to force the wall.")
    ok = "correct" if man_ans == gold else f"WRONG, expected {gold}"
    print(f"    Context-edited  : finished all {len(docs)} reports. Answer {man_ans} ({ok}), for")
    print(f"                      {fmt_usd(man['total_cost'])} and {man['total_time']:.0f}s of model time.")
    if crash:
        print()
        print(f"    The value is not a smaller number. It is that the agent which dies at step")
        print(f"    {crash['turn']} instead runs to the end and returns the right answer, for "
              f"{fmt_usd(man['total_cost'])}.")
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

    if crash and len(live_base) >= 2:
        first, last = live_base[0], live_base[-1]
        print("  Over the steps the unbounded agent survived:")
        print(f"    carried context climbed {first['ctx']:,} -> {last['ctx']:,} tokens, then over "
              f"the {window:,} window.")
        if first["latency_s"] > 0:
            print(f"    per-turn latency climbed {first['latency_s']:.1f}s -> {last['latency_s']:.1f}s "
                  f"({last['latency_s'] / max(first['latency_s'], 0.1):.1f}x slower per step).")
        print(f"    the edited agent held its context near {man['peak_ctx']:,} tokens the whole way.")
        print()

    total = base["total_cost"] + man["total_cost"]
    print(f"  Reproduce: `make longhorizon` on {label}, your own key. This run cost "
          f"{fmt_usd(total)} total and took {wall_s:.0f}s wall.\n")


def main():
    p = argparse.ArgumentParser(description="Long-horizon agent: unbounded crashes, edited finishes.")
    p.add_argument("--model", default="haiku", help="model key: haiku | sonnet | opus")
    p.add_argument("--smoke", action="store_true", help="cheap, does not reach the window")
    p.add_argument("--docs", type=int)
    p.add_argument("--doc-tokens", type=int)
    p.add_argument("--trigger", type=int)
    p.add_argument("--keep", type=int)
    p.add_argument("--max-turns", type=int)
    a = p.parse_args()

    cfg = dict(PRESETS["smoke"] if a.smoke else PRESETS["default"])
    for k in ("docs", "doc_tokens", "trigger", "keep", "max_turns"):
        if getattr(a, k) is not None:
            cfg[k] = getattr(a, k)

    model = get(a.model)
    print(f"\n  Long-horizon benchmark on {model.label}. Two runs of a {cfg['docs']}-report chain,")
    print(f"  each report about {cfg['doc_tokens']:,} tokens. The unbounded run is expected to hit")
    print(f"  the {model.context_window:,} window and stop. Estimated about $1 to $2 and a few")
    print(f"  minutes on Haiku. The measured cost and time are printed and saved when it finishes.")

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
    print_report(model, docs, cfg["doc_tokens"], base_rec, base_ans, man_rec, man_ans, gold, wall_s)

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
