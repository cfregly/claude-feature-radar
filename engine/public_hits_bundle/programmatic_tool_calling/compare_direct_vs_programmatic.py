"""compare_direct_vs_programmatic: run your fan-out task twice over your own tool, print your before-and-after token bill.

The founder-facing artifact for programmatic_tool_calling. It runs the SAME task two ways over the tool in
founder_workload.py, on the same model, and prints YOUR own numbers:

  Mode A  plain tool use. The model calls your tool directly, once per input, so every record it pulls
          back flows through the model's context and is billed as input tokens.
  Mode B  programmatic tool calling. Your tool gets allowed_callers: ["code_execution_20260120"] and the
          code execution tool is added, so Claude writes ONE script in a sandbox that calls your tool in
          a loop and filters the records there. The irrelevant records stay in the sandbox, not the
          model, so you are not billed input tokens for data the model never reads.

It prints the billed-input table for both modes, the input-token reduction, the weighted token/API
dollar delta, and an upfront cost-and-time line BEFORE it spends anything. Token/API dollars include
uncached input, cache reads, cache writes, output, and server-tool charges from the usage object. Code
execution runtime is separate from token usage, so the programmatic path also prints the post-free-allowance
runtime floor exposure.
This receipt path uses no beta header.
Programmatic tool calling requires `code_execution_20260120` or later. Source, re-fetched 2026-06-26:
https://platform.claude.com/docs/en/agents-and-tools/tool-use/programmatic-tool-calling

  python -m programmatic_tool_calling.compare_direct_vs_programmatic            run the example (or your tool) and print the before-and-after table
  python -m programmatic_tool_calling.compare_direct_vs_programmatic --check    the self-test: run the shipped example and ASSERT the programmatic tool calling gate
                                   (fewer input tokens, correct answer, clean caller-path trace)
  python -m programmatic_tool_calling.compare_direct_vs_programmatic --model opus    use Opus 4.8 instead of the default Sonnet 4.6

This prints an estimated $0.08 token/API cost on the shipped example on Sonnet 4.6, plus a separate
code-execution runtime floor exposure for the programmatic arm when the org is outside the monthly free
allowance and the request is not paired with web search or web fetch. anthropic is imported lazily,
inside main(), so importing this module needs no SDK.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Make the repo root importable when run as a file (python programmatic_tool_calling/compare_direct_vs_programmatic.py), not just as a module.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from .common.model_catalog import get  # noqa: E402  the verified id + price registry, anthropic-free
from .common.usage_costs import code_execution_runtime_floor_usd, cost_usd  # noqa: E402  real usage object -> real dollars, anthropic-free
from .run_engine import PROGRAMMATIC_CALLER, run_mode  # noqa: E402  the ONE audited counter + run loop

from programmatic_tool_calling import founder_workload as tool  # noqa: E402  the single edit surface

# The programmatic tool calling docs list Fable 5, Mythos 5, Opus 4.5 to 4.8, and Sonnet 4.5 to 4.6, not Haiku (verified
# 2026-06-26 against the live doc). This artifact runs Sonnet and Opus, the two practical founder paths.
PROGRAMMATIC_TOOL_CALLING_MODELS = {"sonnet": "claude-sonnet-4-6", "opus": "claude-opus-4-8"}


# Upfront cost estimate for the shipped example, tied to the selected model. The committed example
# bills estimated $0.08 on Sonnet 4.6. Opus 4.8 prices input and output at the same 5/3 multiple, so the
# estimate scales with the model's input price (Opus comes out higher). Derived from the committed run.
_REF_MODEL, _REF_USD = "sonnet", 0.0835


def est_usd(model_key: str) -> float:
    """The upfront dollar estimate for `model_key`, scaled from the committed Sonnet reference run."""
    return _REF_USD * get(model_key).input_per_mtok / get(_REF_MODEL).input_per_mtok


def fmt_usd(x: float) -> str:
    return f"${x:,.2f}"


def fmt_usd4(x: float) -> str:
    return f"${x:,.4f}"


def fmt_answer(value) -> str:
    if isinstance(value, (tuple, list)):
        return ",".join(str(item) for item in value)
    return str(value)


def run_token_compare(client, model_key: str) -> dict:
    """Run Mode A and Mode B over founder_workload, on top of the one audited run_engine engine. Returns both
    runs plus the reduction and the dollar delta, all from the real usage objects."""
    model_id = get(model_key).id
    a = run_mode(client, model_id, tool.TOOL_SPEC, tool.call, tool.QUESTION,
                 programmatic=False, cost_fn=lambda u: cost_usd(model_key, u), label="A")
    b = run_mode(client, model_id, tool.TOOL_SPEC, tool.call, tool.QUESTION,
                 programmatic=True, cost_fn=lambda u: cost_usd(model_key, u), label="B")
    a_in, b_in = a["billed_input"], b["billed_input"]
    pct = (1 - b_in / a_in) * 100 if a_in else 0.0
    saved_usd = a["cost"] - b["cost"]
    expected = getattr(tool, "EXPECTED_ANSWER", None)
    a["answer_parsed"] = tool.parse_answer(a["answer"])
    b["answer_parsed"] = tool.parse_answer(b["answer"])
    for run in (a, b):
        run["expected_answer"] = expected
        run["correctness"] = (expected is None) or (run["answer_parsed"] == expected)
        run["trace"]["answer_parsed"] = run["answer_parsed"]
        run["trace"]["expected_answer"] = expected
        run["trace"]["correctness"] = run["correctness"]
    return {"model_key": model_key, "model_id": model_id, "mode_a": a, "mode_b": b,
            "pct_input_reduction": round(pct, 1), "saved_token_api_usd": saved_usd}


def _caller_path(trace: dict) -> str:
    callers = {r.get("caller_type") for r in trace.get("tool_call_records", []) if r.get("caller_type")}
    return ",".join(sorted(callers)) or "(none)"


def programmatic_trace_problems(result: dict) -> list[str]:
    """Return reasons the programmatic arm is not a promotable programmatic-tool-calling receipt."""
    trace = result["mode_b"]["trace"]
    callers = {r.get("caller_type") for r in trace.get("tool_call_records", []) if r.get("caller_type")}
    problems = []
    if PROGRAMMATIC_CALLER not in callers:
        problems.append(f"Mode B caller_path is {_caller_path(trace)}, not {PROGRAMMATIC_CALLER}")
    if trace.get("caller_path_drift"):
        problems.append("Mode B trace marked caller_path_drift=True")
    if not trace.get("server_tool_blocks"):
        problems.append("Mode B observed no server_tool_use block")
    if not trace.get("container_ids"):
        problems.append("Mode B returned no code-execution container id")
    if trace.get("fallback_reason"):
        problems.append(f"Mode B fallback_reason={trace['fallback_reason']}")
    return problems


def print_trace_summary(result: dict) -> None:
    print("  Trace summary:")
    print("    - trace fields are emitted by the demo runner, not slide-only claims.")
    for label, run in [("Mode A", result["mode_a"]), ("Mode B", result["mode_b"])]:
        trace = run["trace"]
        code_requests = trace.get("server_tool_use", {}).get("code_execution_requests", 0)
        print(
            f"    - {label}: caller_path={_caller_path(trace)} "
            f"raw_tool_bytes={trace['raw_tool_bytes']:,} final_bytes={trace['final_bytes']:,} "
            f"containers={len(trace['container_ids'])} server_tool_blocks={trace['server_tool_blocks']} "
            f"code_execution_requests={code_requests} caller_path_drift={trace['caller_path_drift']} "
            f"correctness={trace['correctness']}"
        )
    problems = programmatic_trace_problems(result)
    if problems:
        print("    - Trace gate: FAIL " + "; ".join(problems))
    else:
        print("    - Trace gate: PASS caller path, server block, container, and fallback checks")
    print()


def print_table(result: dict) -> None:
    a, b = result["mode_a"], result["mode_b"]
    runtime_floor = code_execution_runtime_floor_usd()
    b_with_floor = b["cost"] + runtime_floor
    all_in_floor_delta = a["cost"] - b_with_floor
    print(f"\n  {'mode':<44}{'billed input tok':>18}{'round-trips':>13}{'answer':>36}{'token/API':>11}")
    print("  " + "-" * 122)
    for name, r in [("Mode A: plain tool use", a),
                    ("Mode B: programmatic (allowed_callers)", b)]:
        ans = fmt_answer(r["answer_parsed"]) if r["answer_parsed"] is not None else "(unparsed)"
        print(f"  {name:<44}{r['billed_input']:>18,}{r['turns']:>13}{ans:>36}{fmt_usd(r['cost']):>11}")
    print()
    print(f"  Your before and after: Mode B billed {b['billed_input']:,} input tokens vs Mode A's "
          f"{a['billed_input']:,},")
    print(f"  a {result['pct_input_reduction']:.0f}% reduction worth {fmt_usd(result['saved_token_api_usd'])} "
          f"in weighted token/API dollars on THIS run, because the raw evidence rows went")
    print(f"  to the sandbox, not the model context. The saving scales with how often you run the task.\n")
    print("  Cost accounting:")
    print("    - token/API dollars include uncached input, cache reads, cache writes, output, and")
    print("      server-tool charges from the API usage object.")
    print("    - code-execution runtime is separate from token usage. Outside the free allowance,")
    print(f"      one new billed programmatic tool calling container has a 5-minute floor exposure of {fmt_usd4(runtime_floor)}.")
    print(f"    - Mode B token/API + one runtime floor: {fmt_usd(b_with_floor)} "
          f"(delta vs Mode A token/API: {fmt_usd(all_in_floor_delta)}).")
    print("      Exact invoice impact depends on free allowance, container reuse, runtime, and whether")
    print("      the request is paired with web search or web fetch.\n")
    print_trace_summary(result)


def cmd_run(model_key: str) -> int:
    from .common.anthropic_client import get_client  # lazy: anthropic is imported only when we actually call

    label = get(model_key).label
    n = len(getattr(tool, "EXAMPLE_INPUTS", []) or [])
    print(f"\n  Token bill: the same fan-out task two ways over your tool ({tool.TOOL_SPEC['name']}),")
    print(f"  on {label}. Mode A calls the tool directly, Mode B (programmatic tool calling) runs it")
    print(f"  from a sandbox so the raw evidence rows stay out of the model's context.")
    print(f"  Upfront: this run makes 2 task runs over {n} inputs and costs estimated ${est_usd(model_key):.2f} token/API")
    print("  cost and roughly 90 seconds using your API key.")
    print("  Cost scope: cached-token buckets are included in token/API dollars when present. Code")
    print(f"  execution runtime is separate; one new billed programmatic tool calling container has a {fmt_usd4(code_execution_runtime_floor_usd())}")
    print("  5-minute floor exposure after the monthly free allowance when not paired with web search or web fetch.\n")
    client = get_client()
    result = run_token_compare(client, model_key)
    print_table(result)
    return 0


def cmd_check(model_key: str) -> int:
    """Run the shipped example and assert the programmatic tool calling gate.

    A promotable receipt needs fewer input tokens, the expected answer, and a clean programmatic trace:
    expected caller path, observed server-tool block, code-execution container id, and no fallback.
    """
    from .common.anthropic_client import get_client  # lazy

    expected = getattr(tool, "EXPECTED_ANSWER", None)
    print(f"\n  --check: running the shipped example on {get(model_key).label} and asserting the programmatic tool calling")
    print("  gate: fewer input tokens, expected answer, caller path, server block, container, and no fallback.")
    print(f"  Estimated ${est_usd(model_key):.2f}")
    print("  token/API cost, including cached-token buckets when present. Separate code-execution")
    print(f"  runtime floor exposure: {fmt_usd4(code_execution_runtime_floor_usd())} after the free allowance")
    print("  for one new billed programmatic tool calling container when not paired with web search or web fetch.\n")
    client = get_client()
    result = run_token_compare(client, model_key)
    print_table(result)

    a, b = result["mode_a"], result["mode_b"]
    fewer = b["billed_input"] < a["billed_input"]
    a_correct = (expected is None) or (a["answer_parsed"] == expected)
    b_correct = (expected is None) or (b["answer_parsed"] == expected)
    problems = []
    if not fewer:
        problems.append(f"Mode B billed {b['billed_input']:,} input tokens, not fewer than Mode A's "
                        f"{a['billed_input']:,}")
    if not a_correct:
        problems.append(f"Mode A answered {a['answer_parsed']!r}, expected {expected!r}")
    if not b_correct:
        problems.append(f"Mode B answered {b['answer_parsed']!r}, expected {expected!r}")
    problems.extend(programmatic_trace_problems(result))
    if problems:
        print("\n  CHECK FAILED:")
        for p in problems:
            print(f"    - {p}")
        return 1
    print(f"\n  CHECK PASSED: Mode B billed {result['pct_input_reduction']:.0f}% fewer input tokens "
          f"({b['billed_input']:,} vs {a['billed_input']:,})" +
          (f", both modes answered {expected!r}," if expected is not None else ",") +
          " and passed the trace gate.")
    print("  The token saving holds on the example. Now swap your tool into founder_workload.py.\n")
    return 0


def main() -> int:
    p = argparse.ArgumentParser(
        description="Run a fan-out task over your tool twice (plain vs programmatic) and print the token bill.")
    p.add_argument("--model", default="sonnet", choices=sorted(PROGRAMMATIC_TOOL_CALLING_MODELS),
                   help="sonnet (default) or opus, Haiku does not support programmatic tool calling")
    p.add_argument("--check", action="store_true",
                   help="self-test: assert tokens, answer, and trace gate")
    a = p.parse_args()
    return cmd_check(a.model) if a.check else cmd_run(a.model)


if __name__ == "__main__":
    raise SystemExit(main())
