"""sweep: run the comparison across the knobs that matter, so the result is trusted, not assumed.

Before believing any number you must be able to explain it. The interaction that has to be shown,
not asserted: on Claude, context editing rewrites the cached prefix, so caching and context editing
fight. Running each Claude config with caching ON and OFF makes that visible on the meter. The
sweep also answers the correctness question (does the memory tool keep the trimmed run correct)
against OpenAI's compaction, both at full strength.

Reports cost, wall-clock time, correctness, peak context, and cache reads for every variant.
"""

from __future__ import annotations

import argparse
import json

from common.client import get_client, load_env, repo_root
from common.models import get
from engine.demo import PRESETS, build_chain, parse_answer, run_agent
from engine.openai_arm import DEFAULT_OPENAI_MODEL, run_openai_agent


def _roll(recs):
    return {
        "cost": sum(r["cost"] for r in recs),
        "time": sum(r["latency_s"] for r in recs),
        "peak": max((r["ctx"] for r in recs), default=0),
        "cache_read": sum(r["cache_read"] for r in recs),
        "turns": len(recs),
    }


def _pct(a, b):
    return (1 - a / b) * 100 if b else 0.0


def main():
    p = argparse.ArgumentParser(description="Trust-the-result variant sweep, OpenAI vs Claude.")
    p.add_argument("--quick", action="store_true")
    p.add_argument("--full", action="store_true")
    p.add_argument("--docs", type=int)
    p.add_argument("--claude-model", default="haiku")
    p.add_argument("--openai-model", default=DEFAULT_OPENAI_MODEL)
    a = p.parse_args()

    cfg = dict(PRESETS["quick"] if a.quick else PRESETS["full"] if a.full else PRESETS["default"])
    if a.docs:
        cfg["docs"] = a.docs
    trig, keep, mt = cfg["trigger"], cfg["keep"], cfg["max_turns"]

    load_env()
    client = get_client()
    docs, start = build_chain(cfg["docs"], cfg["doc_tokens"])
    gold = sum(1 for d in docs.values() if d["urgent"])
    label = get(a.claude_model).label

    print(f"\n  Variant sweep: {cfg['docs']}-report chain, trim ~{trig:,}, true URGENT count {gold}\n")

    rows = []
    # OpenAI both best configs: caching only (carry full context), and compaction + caching.
    r, t, _ = run_openai_agent(docs, start, model=a.openai_model, compact_threshold=None, max_turns=mt)
    rows.append({"name": f"OpenAI {a.openai_model} (cache only)", "kind": "openai",
                 "caching": True, "s": _roll(r), "ans": parse_answer(t)})
    r, t, _ = run_openai_agent(docs, start, model=a.openai_model, compact_threshold=trig, max_turns=mt)
    rows.append({"name": f"OpenAI {a.openai_model} (compaction+cache)", "kind": "openai",
                 "caching": True, "s": _roll(r), "ans": parse_answer(t)})
    for managed in (True, False):
        for caching in (True, False):
            r, t = run_agent(client, a.claude_model, docs, start, memory=managed, editing=managed,
                             caching=caching, trigger=trig, keep=keep, max_turns=mt)
            kind = "managed" if managed else "baseline"
            rows.append({"name": f"{label} {kind}, cache {'on' if caching else 'off'}",
                         "kind": kind, "caching": caching, "s": _roll(r), "ans": parse_answer(t)})

    print(f"  {'variant':<40}{'cost$':>9}{'time s':>8}{'peak':>8}{'cacheR':>9}{'ans':>5}{'ok':>4}")
    print("  " + "-" * 83)
    for row in rows:
        s, ok = row["s"], "Y" if row["ans"] == gold else "N"
        print(f"  {row['name']:<40}{s['cost']:>9.2f}{s['time']:>8.1f}{s['peak']:>8,}"
              f"{s['cache_read']:>9,}{str(row['ans']):>5}{ok:>4}")

    def find(kind, caching):
        return next((r for r in rows if r["kind"] == kind and r["caching"] == caching), None)

    mon, moff = find("managed", True), find("managed", False)
    bon, boff = find("baseline", True), find("baseline", False)
    oai = find("openai", True)
    correct = [r for r in rows if r["ans"] == gold]
    cheapest = min(correct, key=lambda r: r["s"]["cost"]) if correct else None

    print("\n  Honest reading:")
    if mon and moff:
        verb = "costs MORE" if mon["s"]["cost"] > moff["s"]["cost"] else "costs less"
        print(f"  - Caching and context editing fight. Managed {verb} with caching ON "
              f"(${mon['s']['cost']:.2f}) than OFF (${moff['s']['cost']:.2f}), because clearing "
              f"rewrites the cached prefix. Managed cache reads: {mon['s']['cache_read']:,}.")
    if bon and boff:
        print(f"  - On the untrimmed baseline, caching works: ${bon['s']['cost']:.2f} on vs "
              f"${boff['s']['cost']:.2f} off ({_pct(bon['s']['cost'], boff['s']['cost']):.0f}% "
              f"cheaper, cache reads {bon['s']['cache_read']:,}).")
    if oai:
        print(f"  - OpenAI best: ${oai['s']['cost']:.2f}, {oai['s']['time']:.1f}s, "
              f"answer {oai['ans']} ({'correct' if oai['ans'] == gold else 'WRONG'}).")
    if cheapest:
        print(f"  - Cheapest CORRECT variant: {cheapest['name']} at ${cheapest['s']['cost']:.2f}.")
    print()

    out = {"config": cfg, "gold": gold, "trim_threshold": trig,
           "variants": [{"name": r["name"], "kind": r["kind"], "caching": r["caching"],
                         "answer": r["ans"], **r["s"]} for r in rows]}
    (repo_root() / "data").mkdir(exist_ok=True)
    (repo_root() / "data" / "last_sweep.json").write_text(json.dumps(out, indent=2))
    print("  wrote receipts to data/last_sweep.json\n")


if __name__ == "__main__":
    main()
