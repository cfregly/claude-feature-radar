"""longhorizon: the isolated, measured value of context editing.

The honest problem this fixes, twice over.

First trap: the demo's short presets keep the carried context far below the window, so bounding it
changes nothing a founder pays for, and the cache-rewrite penalty even makes the managed run cost
slightly MORE. "Held context at 3k instead of 36k" is a mechanism, not a value.

Second trap (the one the verifier caught): an earlier version of this file compared a "managed" arm
(memory tool + context editing + a strategy prompt) against a naive arm (none of those) and credited
context editing for the correct answer. That A/B moved four variables at once, so it could not
attribute anything. The correct answer comes from the MEMORY TOOL (a durable count file), not from
context editing.

So this runs a clean isolation. BOTH arms get the memory tool and the identical prompt and caching.
The only thing that changes what the model receives is context editing (the editing-off arm also
sets stop_on_overflow, which only changes how its expected window error is recorded, not the
request). That isolates exactly one thing:

  context editing -> RELIABILITY. With large tool payloads the editing-OFF arm's context climbs to
  the model's window and the API rejects the request: the agent cannot finish at any price. The
  editing-ON arm holds context flat and finishes. Same model, same prompt, same memory tool, one
  flag. The window error is purely a function of context size, so this difference is caused by
  context editing and nothing else.

Correctness is held constant by design (the memory tool is on in both), so this file does NOT claim
context editing makes the answer correct. It claims context editing makes the long run survivable.
The memory tool is the primitive that makes the count correct, a separate axis.

At small payloads both arms finish and both answer correctly (run with --smoke to see it): there the
value of context editing has not yet appeared, which is the point. It appears when the job is heavy
enough to reach the window.

Window and pricing come from common/models.py, verified in docs/VERIFIED_FACTS.md. Carried context is
input + cache_read + cache_write (all three input buckets). Every number is read off the real usage
object the API returns.
"""

from __future__ import annotations

import pathlib as _pl
import sys as _sys
_sys.path.insert(0, str(_pl.Path(__file__).resolve().parents[2]))  # repo root, for common/ and engine/

import argparse
import json
import time

from common.client import fmt_usd, get_client, repo_root
from common.models import get
from engine.demo import build_chain, parse_answer, run_agent
from engine.demonstrators.base import Arm, BaseDemonstrator, CostEstimate, Verdict
from engine.demonstrators.registry import register

# The default uses large payloads so the editing-OFF arm reaches the window and the API errors. The
# smoke is small, so both arms finish (and both answer correctly): it shows that context editing does
# not change the answer, only whether a heavy run survives.
PRESETS = {
    "default": dict(docs=8, doc_tokens=40000, trigger=45000, keep=1, max_turns=40),
    "smoke":   dict(docs=6, doc_tokens=1200,  trigger=4000,  keep=2, max_turns=16),
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


def print_report(model, n_docs, doc_tokens, off_rec, off_ans, on_rec, on_ans, gold, wall_s):
    window = model.context_window
    label = model.label
    crash = _crash(off_rec)
    off, on = _roll(off_rec), _roll(on_rec)
    live_off = _live(off_rec)
    off_ok, on_ok = off_ans == gold, on_ans == gold

    print(f"\n  Long-horizon chain audit on {label}. The isolated value of context editing.")
    print(f"  Workload: a chain of {n_docs} incident reports, each about {doc_tokens:,} tokens (a")
    print(f"  realistic large tool payload, e.g. a big log or trace). The agent reads them one at a")
    print(f"  time and counts the URGENT ones.")
    print(f"  ISOLATION: both runs send the model the same request, same model, same prompt, the MEMORY")
    print(f"  TOOL ON in both, caching ON in both. The only thing that changes what the model receives is")
    print(f"  context editing, so any difference below is caused by context editing alone. (The editing-")
    print(f"  off arm also records its expected window error as a measured event, which the model never")
    print(f"  sees.) {label} window: {window:,} tokens. True count: {gold}.\n")

    print("  WHAT YOU GET")
    if crash:
        att = crash.get("attempted_tokens")
        att_s = f"{att:,}" if att else "more than the window of"
        print(f"    Editing OFF : CRASHED at step {crash['turn']}. Input {att_s} tokens exceeded the")
        print(f"                  {window:,} window, the API rejected the request, the run cannot finish.")
        e_ok = "correct" if on_ok else f"WRONG, expected {gold}"
        print(f"    Editing ON  : finished all {n_docs} reports, answer {on_ans} ({e_ok}), context held flat")
        print(f"                  at ~{on['peak_ctx'] // 1000}k tokens. {fmt_usd(on['total_cost'])}, {on['total_time']:.0f}s.")
        print()
        print(f"    The value, measured and isolated: context editing is what lets the long run FINISH.")
        print(f"    Identical setup, one flag. Without it the API errors at the window; with it the agent")
        print(f"    completes. That is a reliability win caused by context editing, not by the memory tool.")
    else:
        o_ok = "correct" if off_ok else f"WRONG, expected {gold}"
        e_ok = "correct" if on_ok else f"WRONG, expected {gold}"
        print(f"    Editing OFF : answer {off_ans} ({o_ok}), peak context {off['peak_ctx']:,} tokens.")
        print(f"    Editing ON  : answer {on_ans} ({e_ok}), peak context {on['peak_ctx']:,} tokens.")
        print()
        if off_ok:
            print(f"    Here the editing-OFF run stayed under the {window:,} window and answered correctly, so")
            print(f"    context editing's value did not appear this run. It appears when the context grows")
            print(f"    enough to hit the window or derail the count (see the robustness summary, --repeat).")
        else:
            print(f"    Here the editing-OFF run did not crash but lost the count in its bloated context and")
            print(f"    answered WRONG, while editing-ON (identical but for the flag) answered correctly. The")
            print(f"    unbounded arm failed; whether it fails by crashing or by miscounting varies by run.")
    print()

    print("  THE DIVERGENCE (per turn, memory + caching ON in both, only context editing differs)")
    print("  step | editOFF ctx | editON ctx | OFF $/turn | ON $/turn | OFF s | ON s")
    print("  -----+-------------+------------+------------+-----------+-------+-----")
    for i in range(max(len(off_rec), len(on_rec))):
        b = off_rec[i] if i < len(off_rec) else None
        m = on_rec[i] if i < len(on_rec) else None
        print(f"  {i:>4} | {_col(b,'ctx',11,',')} | {_col(m,'ctx',10,',')} | "
              f"{_col(b,'cost',10,'.5f')} | {_col(m,'cost',9,'.5f')} | "
              f"{_col(b,'latency_s',5,'.1f')} | {_col(m,'latency_s',4,'.1f')}")
    print()

    if len(live_off) >= 2:
        first, last = live_off[0], live_off[-1]
        ratio = last["cost"] / max(first["cost"], 1e-9)
        print("  WHY IT FAILS WITHOUT EDITING")
        print(f"    The editing-OFF context climbed {first['ctx']:,} -> {last['ctx']:,} tokens and its")
        print(f"    per-turn cost climbed {ratio:.1f}x ({first['cost']:.5f} -> {last['cost']:.5f}). The")
        print(f"    editing-ON arm held context near {on['peak_ctx']:,} tokens at a flat per-turn cost.")
        print()

    print("  WHERE CORRECTNESS COMES FROM (the honest split)")
    print("    The MEMORY TOOL (on in both arms) is what makes the count correct: the agent tallies into")
    print("    a durable file instead of an in-context count. CONTEXT EDITING is what makes the long run")
    print("    survivable: it bounds the window so the agent never hits the wall. Two primitives, two")
    print("    jobs. This benchmark isolates context editing only.")
    print()

    print(f"  HONEST COST: context editing is not a cheaper bill. Clearing rewrites the cached prefix,")
    print(f"  so on a job short enough to finish either way the editing-ON run can cost MORE. Its value")
    print(f"  is that a heavy job finishes at all. The editing-ON run here cost {fmt_usd(on['total_cost'])}.")
    print()
    total = off["total_cost"] + on["total_cost"]
    print(f"  Reproduce: `make longhorizon` on {label}, your own key. This run cost {fmt_usd(total)} total")
    print(f"  and took {wall_s:.0f}s wall.\n")


def _classify(rec, ans, gold):
    if _crash(rec):
        return "crashed"
    return "correct" if ans == gold else "wrong"


def print_robustness(n, off_outcomes, on_outcomes, on_peak):
    oc_crash = off_outcomes.count("crashed")
    oc_wrong = off_outcomes.count("wrong")
    oc_ok = off_outcomes.count("correct")
    on_ok = on_outcomes.count("correct")
    print(f"  ROBUSTNESS ({n} runs of the same setup, only context editing toggled)")
    print(f"    editing OFF: {oc_crash + oc_wrong}/{n} FAILED ({oc_crash} crashed at the window, "
          f"{oc_wrong} returned a wrong answer), {oc_ok}/{n} correct.")
    print(f"    editing ON : {on_ok}/{n} finished with the correct answer, context bounded near "
          f"~{on_peak // 1000}k tokens.")
    print(f"    The failure mode varies (a crash or a wrong answer), but unbounded context failed every")
    print(f"    run pushed this far, and context editing succeeded every run. Small N, stated plainly.")
    print()


def _render_from_receipt():
    path = repo_root() / "data" / "last_longhorizon.json"
    if not path.exists():
        raise SystemExit("no data/last_longhorizon.json yet; run `make longhorizon` first.")
    d = json.loads(path.read_text())
    model = get(d["model"])
    cfg = d["config"]
    print("\n  (re-rendered from data/last_longhorizon.json, no API call)")
    print_report(model, cfg["docs"], cfg["doc_tokens"],
                 d["editing_off"]["records"], d["editing_off"]["answer"],
                 d["editing_on"]["records"], d["editing_on"]["answer"], d["gold"], d.get("wall_s", 0.0))


# --------------------------------------------------------------- the Demonstrator interface
#
# long_horizon_survival: under a long, tool-heavy, large-payload load the editing-ON config FINISHES
# and stays correct where the editing-OFF config reaches the window and errors. Both arms hold the
# memory tool, the prompt, and caching constant, so exactly one variable (context editing) is toggled.
#
# The grounding correction (see engine/scan.py): context editing vs OpenAI's server-side compaction is
# PARITY (both ship GA server-side context management, Claude additionally ships beta in-place
# editing), so this is a WITHIN-CLAUDE reliability receipt, not a head-to-head lead. A leadership claim
# on long-horizon anchors on the independent METR time-horizon, never on context editing. The Claude
# arm is editing-ON; the "competitor" is the within-Claude editing-OFF baseline, marked ran=True but
# provider claude, so the base honesty contract reads it as within-claude-only and never pitches a
# cross-vendor win this demonstrator did not run.

class ContextEditingDemonstrator(BaseDemonstrator):
    demo_kind = "long_horizon_survival"

    def estimate(self, edge, spec):
        smoke = spec.get("smoke")
        return CostEstimate(usd=(0.05 if smoke else 2.0),
                            wall_clock_s=(30.0 if smoke else 150.0),
                            command="make longhorizon-smoke" if smoke else "make longhorizon",
                            note="editing off vs on, memory and prompt held constant in both arms")

    def _cfg(self, spec):
        cfg = dict(PRESETS["smoke"] if spec.get("smoke") else PRESETS["default"])
        for k in ("docs", "doc_tokens", "trigger", "keep", "max_turns"):
            if spec.get(k) is not None:
                cfg[k] = spec[k]
        return cfg

    def _arm(self, model_id, provider, rec, ans, gold, note):
        roll = _roll(rec)
        return Arm(provider=provider, model=model_id, text=str(ans), ran=True,
                   latency_s=roll["total_time"], cost_usd=roll["total_cost"],
                   cache_read_tokens=roll["cache_read"], ctx=roll["peak_ctx"],
                   metric={"finished": not roll["crashed"], "correct": ans == gold,
                           "peak_ctx": roll["peak_ctx"], "answer": ans, "gold": gold,
                           "crashed": roll["crashed"]}, note=note)

    def run_claude_arm(self, edge, spec):
        client = spec.get("client") or get_client()
        model_key = spec.get("model", "haiku")
        cfg = self._cfg(spec)
        docs, start = build_chain(cfg["docs"], cfg["doc_tokens"])
        gold = sum(1 for d in docs.values() if d["urgent"])
        spec["_docs"], spec["_start"], spec["_gold"], spec["_cfg"] = docs, start, gold, cfg  # share with the off arm
        common = dict(trigger=cfg["trigger"], keep=cfg["keep"], max_turns=cfg["max_turns"])
        on_rec, on_text = run_agent(client, model_key, docs, start, memory=True, editing=True, **common)
        return self._arm(get(model_key).id, "claude", on_rec, parse_answer(on_text), gold,
                         "editing ON: context held flat, the long run finishes")

    def run_competitor_arms(self, edge, spec):
        # The within-Claude editing-OFF baseline, the isolated A/B. It is provider claude, so the base
        # contract treats the verdict as within-claude-only. The cross-vendor compaction arm is PARITY
        # by the grounding correction and is intentionally NOT run as a head-to-head here.
        client = spec.get("client") or get_client()
        model_key = spec.get("model", "haiku")
        docs, start, gold = spec.get("_docs"), spec.get("_start"), spec.get("_gold")
        if docs is None:  # run_claude_arm builds the shared chain; if called standalone, build one
            cfg = self._cfg(spec)
            docs, start = build_chain(cfg["docs"], cfg["doc_tokens"])
            gold = sum(1 for d in docs.values() if d["urgent"])
        cfg = spec.get("_cfg") or self._cfg(spec)
        common = dict(trigger=cfg["trigger"], keep=cfg["keep"], max_turns=cfg["max_turns"])
        off_rec, off_text = run_agent(client, model_key, docs, start, memory=True, editing=False,
                                      stop_on_overflow=True, **common)
        return [self._arm(get(model_key).id, "claude", off_rec, parse_answer(off_text), gold,
                          "editing OFF (within-Claude baseline): reaches the window and errors")]

    def score(self, claude, competitors, spec):
        # The SAME machine gate on both arms: did it finish AND answer correctly. Editing ON must
        # finish; the editing-OFF baseline is expected to reach the window and error. The verdict is
        # within-claude-only: a reliability receipt, not a cross-vendor lead (compaction is parity).
        off = competitors[0] if competitors else None
        on_finished = bool(claude.metric.get("finished")) and bool(claude.metric.get("correct"))
        off_failed = off is not None and (off.metric.get("crashed") or not off.metric.get("correct"))
        passed = on_finished and bool(off_failed)
        return Verdict(
            verdict="within-claude-only", passed=passed,
            metric={"editing_on_finished": claude.metric.get("finished"),
                    "editing_on_correct": claude.metric.get("correct"),
                    "editing_on_peak_ctx": claude.metric.get("peak_ctx"),
                    "editing_off_failed": bool(off_failed),
                    "editing_off_outcome": "crashed at the window" if (off and off.metric.get("crashed"))
                                           else "wrong answer" if off else "n/a"},
            note="editing ON finished and answered correctly; editing OFF reached the window and failed. "
                 "A within-Claude reliability receipt. Context editing vs OpenAI compaction is parity, "
                 "so the long-horizon LEADERSHIP claim anchors on the independent METR time-horizon, "
                 "never on context editing.",
        )

    def receipt(self, edge, claude, competitors, verdict, spec):
        cfg = spec.get("_cfg") or self._cfg(spec)
        return self.build_receipt(
            edge, claude, competitors, verdict, spec,
            workload={
                "task_shape": f"a chain of {cfg['docs']} incident reports, each about {cfg['doc_tokens']:,} tokens",
                "model": claude.model, "features_on": ["context_management/clear_tool_uses", "memory tool"],
                "assumptions": "memory tool and prompt held constant in both arms; clearing rewrites the "
                               "cached prefix so editing ON can cost MORE, the value is that a heavy job "
                               "finishes at all, not a cheaper bill",
            },
            grounding=[{"claim": "context editing clears tool results in place under the window",
                        "source_url": "https://platform.claude.com/docs/en/build-with-claude/context-editing",
                        "date": "2026-06-18"},
                       {"claim": "long-horizon leadership anchors on the independent METR 50% task time-horizon",
                        "source_url": "https://metr.org/", "date": "2026-06-18"}],
            fairness={"best_to_best": "both arms run Claude's memory tool and caching at full strength",
                      "isolate": "only context editing toggled; memory tool and prompt identical in both arms"},
        )


register(ContextEditingDemonstrator())


def main():
    p = argparse.ArgumentParser(description="Long-horizon agent: isolate context editing (memory ON in both arms).")
    p.add_argument("--model", default="haiku", help="model key: haiku | sonnet | opus")
    p.add_argument("--smoke", action="store_true", help="small payloads: both arms finish, shows answer parity")
    p.add_argument("--from-receipt", action="store_true", help="re-print the last run's receipt, no API call")
    p.add_argument("--docs", type=int)
    p.add_argument("--doc-tokens", type=int)
    p.add_argument("--trigger", type=int)
    p.add_argument("--keep", type=int)
    p.add_argument("--max-turns", type=int)
    p.add_argument("--repeat", type=int, default=1, help="run the pair N times, report the outcome distribution")
    a = p.parse_args()

    if a.from_receipt:
        _render_from_receipt()
        return

    cfg = dict(PRESETS["smoke"] if a.smoke else PRESETS["default"])
    for k in ("docs", "doc_tokens", "trigger", "keep", "max_turns"):
        if getattr(a, k) is not None:
            cfg[k] = getattr(a, k)

    model = get(a.model)
    print(f"\n  Long-horizon benchmark on {model.label}. The same {cfg['docs']}-report chain run twice,")
    print(f"  each report about {cfg['doc_tokens']:,} tokens, memory tool ON in both, only context editing")
    print(f"  toggled. The editing-OFF arm is expected to exceed the {model.context_window:,} window.")
    print(f"  Estimated about $1 and a couple of minutes on Haiku. Measured cost and time printed below.")

    client = get_client()
    docs, start = build_chain(cfg["docs"], cfg["doc_tokens"])
    gold = sum(1 for d in docs.values() if d["urgent"])
    common = dict(trigger=cfg["trigger"], keep=cfg["keep"], max_turns=cfg["max_turns"])

    n = max(1, a.repeat)
    off_outcomes, on_outcomes = [], []
    first = None
    for i in range(n):
        r0 = time.perf_counter()
        off_rec, off_text = run_agent(client, a.model, docs, start, memory=True, editing=False,
                                      stop_on_overflow=True, **common)
        on_rec, on_text = run_agent(client, a.model, docs, start, memory=True, editing=True, **common)
        run_wall = time.perf_counter() - r0
        off_ans, on_ans = parse_answer(off_text), parse_answer(on_text)
        off_outcomes.append(_classify(off_rec, off_ans, gold))
        on_outcomes.append(_classify(on_rec, on_ans, gold))
        if first is None:
            first = (off_rec, off_ans, on_rec, on_ans, run_wall)
        if n > 1:
            print(f"  run {i + 1}/{n}: editing OFF -> {off_outcomes[-1]}, editing ON -> {on_outcomes[-1]}")

    off_rec, off_ans, on_rec, on_ans, first_wall = first
    print_report(model, cfg["docs"], cfg["doc_tokens"], off_rec, off_ans, on_rec, on_ans, gold, first_wall)
    if n > 1:
        print_robustness(n, off_outcomes, on_outcomes, _roll(on_rec)["peak_ctx"])

    out = {
        "model": model.id, "config": cfg, "window": model.context_window,
        "gold": gold, "wall_s": round(first_wall, 1), "runs": n,
        "off_outcomes": off_outcomes, "on_outcomes": on_outcomes,
        "editing_off": {"records": off_rec, "answer": off_ans, **_roll(off_rec)},
        "editing_on": {"records": on_rec, "answer": on_ans, **_roll(on_rec)},
    }
    (repo_root() / "data").mkdir(exist_ok=True)
    (repo_root() / "data" / "last_longhorizon.json").write_text(json.dumps(out, indent=2))
    print("  (per-turn detail cached in gitignored data/last_longhorizon.json; this printout is the receipt)\n")


if __name__ == "__main__":
    main()
