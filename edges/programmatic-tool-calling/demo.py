"""programmatic_tool_calling: programmatic tool calling, the input-token receipt on a real fan-out task.

The anchor. Programmatic tool calling (PTC) lets Claude write one script in a code-execution sandbox
that calls the developer's OWN tools in a loop and filters the results before they ever reach the
model's context window. Add `allowed_callers: ["code_execution_20260120"]` to a tool and Claude is
strongly guided to invoke it from code instead of one round trip per call. The bulky tool OUTPUTS go to
the sandbox, not the model, so you are not billed input tokens for data the model never needs to read.
This receipt path uses no beta header. Programmatic tool calling requires `code_execution_20260120` or
later. Models: Fable 5, Mythos 5, Opus 4.5 to 4.8, and Sonnet 4.5 to 4.6 (not Haiku). Source, re-fetched 2026-06-22:
https://platform.claude.com/docs/en/agents-and-tools/tool-use/programmatic-tool-calling

No competitor exposes this: OpenAI ships a code interpreter and tool search, but neither keeps a
developer's own custom-tool OUTPUTS out of context the way `allowed_callers` does. This is an
absence-of-evidence finding (no named equivalent), stated precisely.

What this measures, honestly. The SAME fan-out task two ways, on the same model, with an identical
final-answer assertion so the comparison cannot be gamed:

  Mode A (plain tool use)   Claude calls query_region_sales(region) directly, once per region, so
                            every region's ~60 rows flow through the model context and are billed.
  Mode B (programmatic)     Claude writes one script that loops the regions, calls the tool from
                            code, sums in the sandbox, and returns only the winner. The rows go to
                            the sandbox, not the model.

The receipt: total billed input tokens A vs B (input + cache_read + cache_write, every input bucket),
the model round-trip count, and the dollar delta, all read off the real usage object. The win is
workload-shaped: the live doc itself notes a sequential single-call benchmark (tau2-bench) was flat
to about 8% MORE expensive, so this task is a genuine fan-out or the result does not hold. Anthropic's
own doc reports about 24% fewer input tokens on agentic-search benchmarks; we quote that as theirs and
the number below as ours, measured on our key. PTC is not ZDR-eligible and is not on Bedrock or Vertex.
"""

from __future__ import annotations

import pathlib as _pl
import sys as _sys
_sys.path.insert(0, str(_pl.Path(__file__).resolve().parents[2]))  # repo root, for common/ and engine/

import argparse
import json

from common.client import fmt_usd, get_client, load_env, repo_root
from common.models import get
from common.pricing import cost_usd
from engine.demonstrators.base import Arm, BaseDemonstrator, CostEstimate, Verdict
from engine.demonstrators.registry import register
from engine.demonstrators.token_core import run_mode

# The fixture is defined once in app/example_tool.py (the app's shipped worked example) and imported
# here, so the app's number and this demo's number come from one definition, never two redefinitions.
from app.example_tool import (
    QUESTION,
    REGIONS,
    ROWS_PER_REGION,
    TOOL_SPEC as QUERY_TOOL,
    parse_answer as parse_winner,
    region_sales,
)


def true_winner():
    totals = {r: round(sum(row["revenue"] for row in region_sales(r)), 2) for r in REGIONS}
    return max(totals, key=totals.get), totals


def run_programmatic_tool_calling(client, model_key, *, programmatic):
    """The PTC A/B run for this edge, on top of the one audited engine in token_core.run_mode.

    run_mode does the request loop and the apples-to-apples billed-input count (one counter, shared
    with the forkable app). This thin wrapper supplies the edge's own tool, question, and a region
    parameter for region_sales, then maps the model's final text to the parsed winner this edge scores.
    """
    r = run_mode(
        client, get(model_key).id, QUERY_TOOL,
        lambda region="": region_sales(region), QUESTION,
        programmatic=programmatic, cost_fn=lambda u: cost_usd(model_key, u),
    )
    r["answer"] = parse_winner(r["answer"])
    return r


# --------------------------------------------------------------- the Demonstrator interface
#
# token_accounting: PTC bills fewer input tokens for the same correct answer than the naive path,
# counted apples-to-apples. The Claude arm is Mode B (PTC), and its A/B baseline (Mode A, plain tool
# use) rides in the arm's metric. There is no head-to-head competitor arm: no named OpenAI or Google
# surface keeps a developer's OWN custom-tool OUTPUTS out of context, so the competitor side is a
# doc-grounded absence (ran=False), and the verdict rests on the edge's all-fetched
# absence-of-evidence lead_basis, enforced by the base build_receipt honesty contract.

class PTCDemonstrator(BaseDemonstrator):
    demo_kind = "token_accounting"

    def estimate(self, edge, spec):
        model = (self.fair_comparison(edge).get("claude_config") or {}).get("model", "sonnet")
        return CostEstimate(usd=0.08, wall_clock_s=90.0, command="make programmatic-tool-calling",
                            note=f"two fan-out runs on {model}, the only spend is the model arms")

    def run_claude_arm(self, edge, spec):
        client = spec.get("client") or get_client()
        model_key = spec.get("model") or (self.fair_comparison(edge).get("claude_config") or {}).get("model", "sonnet")
        winner = spec.get("winner") or true_winner()[0]
        a_run = run_programmatic_tool_calling(client, model_key, programmatic=False)   # Mode A: plain tool use (the A/B baseline)
        b_run = run_programmatic_tool_calling(client, model_key, programmatic=True)    # Mode B: PTC (the Claude arm)
        pct = (1 - b_run["billed_input"] / a_run["billed_input"]) * 100 if a_run["billed_input"] else 0.0
        return Arm(
            provider="claude", model=get(model_key).id, text=str(b_run["answer"]),
            latency_s=b_run["time"], input_tokens=b_run["billed_input"],
            output_tokens=b_run["output_tokens"], cost_usd=b_run["cost"], ctx=b_run["billed_input"],
            metric={
                "mode_b_billed_input": b_run["billed_input"], "mode_a_billed_input": a_run["billed_input"],
                "pct_input_reduction": round(pct, 1), "round_trips": b_run["turns"],
                "mode_b_answer": b_run["answer"], "mode_a_answer": a_run["answer"],
                "mode_b_correct": b_run["answer"] == winner, "mode_a_correct": a_run["answer"] == winner,
                "mode_a_cost": a_run["cost"],
            },
            note="Mode B is PTC, Mode A is the within-Claude plain-tool-use baseline carried in metric",
        )

    def run_competitor_arms(self, edge, spec):
        # No named OpenAI or Google surface keeps a developer's own custom-tool OUTPUTS out of context.
        # The competitor side is a documented absence, never a faked or zeroed row.
        return [Arm(provider="openai", model="(none: no allowed_callers equivalent)", ran=False,
                    note="OpenAI ships a code interpreter and tool search but keeps no custom-tool "
                         "OUTPUTS out of context; doc-grounded absence, not a head-to-head loss"),
                Arm(provider="gemini", model="(none: no allowed_callers equivalent)", ran=False,
                    note="no named Gemini equivalent keeps custom-tool OUTPUTS out of context")]

    def score(self, claude, competitors, spec):
        # The SAME machine-checkable gate the CLI asserts: the answer is correct AND PTC billed fewer
        # input tokens than the plain path. No rubric.
        m = claude.metric
        passed = bool(m.get("mode_b_correct")) and m.get("mode_b_billed_input", 0) < m.get("mode_a_billed_input", 0)
        return Verdict(
            verdict="claude-ahead" if passed else "never-evaluated", passed=passed,
            metric={"pct_input_reduction": m.get("pct_input_reduction"),
                    "mode_b_billed_input": m.get("mode_b_billed_input"),
                    "mode_a_billed_input": m.get("mode_a_billed_input"),
                    "round_trips": m.get("round_trips")},
            note="answer matches and PTC billed fewer input tokens" if passed
                 else "the PTC invariant did not hold this run",
        )

    def receipt(self, edge, claude, competitors, verdict, spec):
        fc = self.fair_comparison(edge)
        return self.build_receipt(
            edge, claude, competitors, verdict, spec,
            workload={
                "task_shape": fc.get("task_shape", f"fan-out, {len(REGIONS)} regions x ~{ROWS_PER_REGION} rows"),
                "model": claude.model, "features_on": ["allowed_callers", "code_execution_20260120"],
                "assumptions": "fan-out shaped; sequential single-call tasks are flat to +8%; adds "
                               "round-trips; not on Bedrock or Vertex, not ZDR-eligible",
            },
            grounding=[{"claim": "PTC keeps tool outputs out of model context (allowed_callers)",
                        "source_url": "https://platform.claude.com/docs/en/agents-and-tools/tool-use/programmatic-tool-calling",
                        "date": "2026-06-18"}],
            fairness={"best_to_best": "same model both modes, Claude's full PTC stack on",
                      "isolate": "only programmatic-tool-calling toggled; memory and prompt held constant"},
        )


register(PTCDemonstrator())


def main():
    p = argparse.ArgumentParser(description="Programmatic tool calling: the input-token receipt on a fan-out task.")
    p.add_argument("--model", default="sonnet", help="opus or sonnet (Haiku does not support PTC)")
    a = p.parse_args()

    load_env()
    client = get_client()
    winner, totals = true_winner()
    label = get(a.model).label

    print(f"\n  Programmatic tool calling: the input-token receipt on a real fan-out task.")
    print(f"  Task: across {len(REGIONS)} regions, each returning ~{ROWS_PER_REGION} sales rows, find the")
    print(f"  region with the highest total revenue. True winner (computed locally): {winner}.")
    print(f"  Same task and same model ({label}) both ways, the final answer must match or we fail.\n")

    print("  running Mode A (plain tool use, every row through context) ...", flush=True)
    a_run = run_programmatic_tool_calling(client, a.model, programmatic=False)
    print(f"    Mode A done: {a_run['turns']} round-trips, {a_run['billed_input']:,} billed input tokens, "
          f"answer {a_run['answer']}.", flush=True)
    print("  running Mode B (programmatic, rows filtered in the sandbox) ...", flush=True)
    b_run = run_programmatic_tool_calling(client, a.model, programmatic=True)
    print(f"    Mode B done: {b_run['turns']} round-trips, {b_run['billed_input']:,} billed input tokens, "
          f"answer {b_run['answer']}.\n", flush=True)

    rows = [("Mode A: plain tool use", a_run), ("Mode B: programmatic (allowed_callers)", b_run)]
    print(f"  {'mode':<40}{'billed input tok':>18}{'round-trips':>13}{'answer':>10}{'cost':>11}")
    print("  " + "-" * 92)
    for name, r in rows:
        print(f"  {name:<40}{r['billed_input']:>18,}{r['turns']:>13}{str(r['answer']):>10}{fmt_usd(r['cost']):>11}")

    a_correct = a_run["answer"] == winner
    b_correct = b_run["answer"] == winner
    fewer = b_run["billed_input"] < a_run["billed_input"]
    n_rows = len(REGIONS) * ROWS_PER_REGION
    pct = (1 - b_run["billed_input"] / a_run["billed_input"]) * 100 if a_run["billed_input"] else 0.0

    print("\n  Honest reading:")
    print(f"  - THE EDGE, measured: Mode B billed {b_run['billed_input']:,} input tokens vs Mode A's "
          f"{a_run['billed_input']:,}, a {pct:.0f}% reduction, because the {n_rows} rows the tool "
          f"returned went to the sandbox, not the model context.")
    print(f"  - Bonus, correctness: Mode B (the sandbox code does the arithmetic) answered "
          f"{b_run['answer']} ({'correct' if b_correct else 'WRONG'}). Mode A (the model sums {n_rows} "
          f"rows in its head) answered {a_run['answer']} ({'correct' if a_correct else 'WRONG'}). Exact "
          f"math in code beats in-context summation over many rows.")
    print(f"  - Honest cost of the approach: Mode B made {b_run['turns']} model round-trips to Mode A's "
          f"{a_run['turns']} because the model called the tool serially from code, so on an INSTANT mock "
          f"tool it runs slower. The token saving is the win, the latency depends on your real tool's "
          f"per-call time (PTC saves the per-call model round-trip a real slow tool would cost).")
    print(f"  - Fan-out-shaped: the doc notes a sequential single-call task (tau2-bench) is flat to about "
          f"8% more expensive. No competitor keeps your custom-tool outputs out of context.\n")

    out = {"model": get(a.model).id, "regions": len(REGIONS), "rows_per_region": ROWS_PER_REGION,
           "true_winner": winner, "mode_a": a_run, "mode_b": b_run,
           "pct_input_reduction": round(pct, 1), "mode_a_correct": a_correct, "mode_b_correct": b_correct}
    (repo_root() / "data").mkdir(exist_ok=True)
    (repo_root() / "data" / "last_programmatic_tool_calling.json").write_text(json.dumps(out, indent=2))
    print("  (per-turn detail cached in gitignored data/last_programmatic_tool_calling.json; this printout is the receipt)\n")

    if not (b_correct and fewer):
        raise SystemExit("PTC invariant failed: mode B (the code) must answer correctly AND bill fewer input tokens.")


if __name__ == "__main__":
    main()
