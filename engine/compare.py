"""compare: OpenAI vs Claude on the same long-horizon chain agent, both at full strength.

Best-to-best, latest-to-latest. Each platform runs its best long-agent config on an identical
sequential task, and we measure the three things a founder pays for: total cost, wall-clock time,
and correctness (did it return the right answer). Carried context is a secondary diagnostic.

  OpenAI   : Responses API, compaction ON, caching ON, natural parallel. gpt-5.4-mini.
  Claude   : Messages API, context editing + memory ON, caching ON. (baseline shown for reference.)

Both trim carried context at the same token threshold (OpenAI compaction compact_threshold equals
the Claude context-editing trigger), so neither is configured to carry more than the other.

We report whatever wins. If OpenAI is cheaper or faster at equal correctness, that is the finding,
and `make alert` (engine/product_alert.py) drafts the product-team note. Honesty runs both ways.
"""

from __future__ import annotations

import argparse
import json

from common.client import get_client, load_env, repo_root
from common.models import get
from engine.demo import PRESETS, build_chain, parse_answer, run_agent
from engine.gemini_arm import DEFAULT_GEMINI_MODEL, run_gemini_agent
from engine.openai_arm import DEFAULT_OPENAI_MODEL, run_openai_agent


def _roll(records):
    return {
        "cost": sum(r["cost"] for r in records),
        "time": sum(r["latency_s"] for r in records),
        "peak": max((r["input_tokens"] for r in records), default=0),
        "turns": len(records),
        "cache_read": sum(r["cache_read"] for r in records),
    }


def main():
    p = argparse.ArgumentParser(description="OpenAI vs Claude, the same long agent, both best config.")
    p.add_argument("--quick", action="store_true")
    p.add_argument("--full", action="store_true")
    p.add_argument("--claude-model", default="haiku")
    p.add_argument("--openai-model", default=DEFAULT_OPENAI_MODEL)
    p.add_argument("--gemini-model", default=DEFAULT_GEMINI_MODEL)
    p.add_argument("--docs", type=int)
    a = p.parse_args()

    cfg = dict(PRESETS["quick"] if a.quick else PRESETS["full"] if a.full else PRESETS["default"])
    if a.docs:
        cfg["docs"] = a.docs
    trig = cfg["trigger"]

    load_env()
    client = get_client()
    docs, start = build_chain(cfg["docs"], cfg["doc_tokens"])
    gold = sum(1 for d in docs.values() if d["urgent"])
    label = get(a.claude_model).label

    print(f"\n  Same {cfg['docs']}-report chain audit, both platforms at full strength.")
    print(f"  OpenAI {a.openai_model} (Responses, compaction+caching)  vs  {label} "
          f"(context editing+memory+caching)")
    print(f"  Both trim carried context at ~{trig:,} tokens. True URGENT count: {gold}\n")

    oai_r, oai_t, oai_model = run_openai_agent(
        docs, start, model=a.openai_model, compact_threshold=trig, max_turns=cfg["max_turns"])
    cm_r, cm_t = run_agent(client, a.claude_model, docs, start, managed=True,
                           trigger=trig, keep=cfg["keep"], max_turns=cfg["max_turns"])
    cb_r, cb_t = run_agent(client, a.claude_model, docs, start, managed=False,
                           trigger=trig, keep=cfg["keep"], max_turns=cfg["max_turns"])

    # Gemini degrades gracefully: a free-tier key can trip 429 on a long run.
    gem_row = None
    try:
        gem_r, gem_t, gem_model = run_gemini_agent(docs, start, model=a.gemini_model,
                                                   max_turns=cfg["max_turns"])
        gem_row = (f"Gemini {gem_model} (prices unverified)", _roll(gem_r), parse_answer(gem_t))
    except Exception as e:  # noqa: BLE001
        print(f"  (Gemini skipped, quota or load: {str(e)[:70]})")

    rows = [(f"OpenAI {oai_model}", _roll(oai_r), parse_answer(oai_t))]
    if gem_row:
        rows.append(gem_row)
    rows += [
        (f"{label} (best)", _roll(cm_r), parse_answer(cm_t)),
        (f"{label} (baseline)", _roll(cb_r), parse_answer(cb_t)),
    ]

    print("  outcomes a founder pays for")
    print(f"  {'platform':<26}{'cost(USD)':>11}{'time(s)':>9}{'peak ctx':>10}{'answer':>8}{'correct':>9}")
    print("  " + "-" * 73)
    for name, s, ans in rows:
        ok = "yes" if ans == gold else "no"
        print(f"  {name:<26}{s['cost']:>11.5f}{s['time']:>9.1f}{s['peak']:>10,}{str(ans):>8}{ok:>9}")

    # Headline: best config vs best config (OpenAI vs Claude managed), both at equal correctness.
    oai_s, cm_s = rows[0][1], rows[1][1]
    oai_ok, cm_ok = rows[0][2] == gold, rows[1][2] == gold
    print()
    print("  Verdict (OpenAI best vs Claude best, the fair head-to-head):")
    if oai_ok and cm_ok:
        cheaper = "OpenAI" if oai_s["cost"] < cm_s["cost"] else "Claude"
        faster = "OpenAI" if oai_s["time"] < cm_s["time"] else "Claude"
        print(f"  - both correct. cheaper: {cheaper}. faster: {faster}.")
        print(f"  - cost  OpenAI ${oai_s['cost']:.5f}  vs  Claude ${cm_s['cost']:.5f}")
        print(f"  - time  OpenAI {oai_s['time']:.1f}s  vs  Claude {cm_s['time']:.1f}s")
        if cheaper == "OpenAI" or faster == "OpenAI":
            print("  - a competitor is ahead on at least one axis. Run `make alert` to draft the "
                  "product-team note. Honesty runs both ways.")
    else:
        print(f"  - correctness differs (OpenAI {'ok' if oai_ok else 'WRONG'}, "
              f"Claude {'ok' if cm_ok else 'WRONG'}). Report correctness first, cost second.")
    print()

    out = {
        "config": cfg, "gold": gold, "trim_threshold": trig,
        "openai": {"model": oai_model, "answer": rows[0][2], **oai_s, "records": oai_r},
        "claude_best": {"model": get(a.claude_model).id, "answer": rows[1][2], **cm_s, "records": cm_r},
        "claude_baseline": {"model": get(a.claude_model).id, "answer": rows[2][2], **rows[2][1],
                            "records": cb_r},
    }
    (repo_root() / "data").mkdir(exist_ok=True)
    (repo_root() / "data" / "last_compare.json").write_text(json.dumps(out, indent=2))
    print("  wrote receipts to data/last_compare.json\n")


if __name__ == "__main__":
    main()
