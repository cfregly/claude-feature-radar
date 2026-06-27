"""run_tokens: run your fan-out task twice over your own tool, print your before-and-after token bill.

The founder-facing artifact. It runs the SAME task two ways over the tool in app/my_tool.py, on the
same model, and prints YOUR own numbers:

  Mode A  plain tool use. The model calls your tool directly, once per input, so every bulky tool
          OUTPUT flows through the model's context and is billed as input tokens.
  Mode B  programmatic tool calling. Your tool gets allowed_callers: ["code_execution_20260120"] and
          the code execution tool is added, so Claude writes ONE script in a sandbox that calls your
          tool in a loop and filters the results there. The outputs go to the sandbox, not the model,
          so you are not billed input tokens for data the model never reads.

It prints the billed-input table for both modes, the input-token reduction, the token/API dollar delta,
and an upfront "this run costs about $X and Y seconds using your API key" line BEFORE it spends
anything. Source, re-fetched 2026-06-18:
https://platform.claude.com/docs/en/agents-and-tools/tool-use/programmatic-tool-calling

The honest scope, stated as part of the result. The win is FAN-OUT shaped: it shows up when the model
calls a tool many times and the outputs would otherwise fill its context. The live doc notes a
sequential single-call benchmark (tau2-bench) is flat to about 8% MORE expensive, so on a one-shot task
the bill will not drop. The shipped example (region_sales, 240 rows over 4 regions) is a genuine
fan-out. When you swap in your own tool, keep the task fan-out shaped or the number will not hold.

  python -m app.run_tokens            run the example (or your tool) and print the before-and-after table
  python -m app.run_tokens --check    the self-test: run the shipped example and ASSERT the PTC invariant
                                   (Mode B bills fewer input tokens AND answers correctly) before you
                                   trust it on your own tool
  python -m app.run_tokens --model opus    use Opus 4.8 instead of the default Sonnet 4.6

This prints about $0.08 token/API cost on the shipped example on Sonnet 4.6. Code execution runtime can
bill separately after the monthly free allowance, so production COGS must add that line item. There is
no Docker and nothing to install for the sandbox itself. anthropic is imported lazily, inside main(), so
importing this module needs no SDK.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Make the repo root importable when run as a file (python app/run_tokens.py), not just as a module.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from common.models import get  # noqa: E402  the verified id + price registry, anthropic-free
from common.pricing import cost_usd  # noqa: E402  real usage object -> real dollars, anthropic-free
from engine.demonstrators.token_core import run_mode  # noqa: E402  the ONE audited counter + run loop
from common.client import fmt_usd  # noqa: E402  the one shared dollar formatter

from app import my_tool as tool  # noqa: E402  the single edit surface

# Programmatic tool calling is supported on Fable 5, Mythos 5, Opus 4.5 to 4.8, and Sonnet 4.5 to 4.6,
# not Haiku (verified 2026-06-18 against the live doc). The app exposes the two a founder would pick.
PTC_MODELS = {"sonnet": "claude-sonnet-4-6", "opus": "claude-opus-4-8"}


# Upfront cost estimate for the shipped example, tied to the selected model. The committed example
# bills about $0.08 on Sonnet 4.6. Opus 4.8 prices input and output at the same 5/3 multiple, so the
# estimate scales with the model's input price (Opus comes out higher). Derived from the committed run.
_REF_MODEL, _REF_USD = "sonnet", 0.0835


def est_usd(model_key: str) -> float:
    """The upfront dollar estimate for `model_key`, scaled from the committed Sonnet reference run."""
    return _REF_USD * get(model_key).input_per_mtok / get(_REF_MODEL).input_per_mtok


def run_token_compare(client, model_key: str, *, progress: bool = True) -> dict:
    """Run Mode A and Mode B over my_tool, on top of the one audited token_core engine.

    Returns both runs plus the reduction and the dollar delta, all from the real usage objects. The
    same run_mode the programmatic-tool-calling demo calls, so the app's number and the demo's number
    come from one counter.
    """
    model_id = get(model_key).id
    a = run_mode(client, model_id, tool.TOOL_SPEC, tool.call, tool.QUESTION,
                 programmatic=False, cost_fn=lambda u: cost_usd(model_key, u),
                 label="A", progress=progress)
    b = run_mode(client, model_id, tool.TOOL_SPEC, tool.call, tool.QUESTION,
                 programmatic=True, cost_fn=lambda u: cost_usd(model_key, u),
                 label="B", progress=progress)
    a_in, b_in = a["billed_input"], b["billed_input"]
    pct = (1 - b_in / a_in) * 100 if a_in else 0.0
    # The dollar delta the saved input tokens are worth, at this model's published input price. This is
    # the per-run saving on THIS workload, and it scales with how often you run the task.
    saved_usd = (a_in - b_in) * get(model_key).input_per_mtok / 1e6
    a["answer_parsed"] = tool.parse_answer(a["answer"])
    b["answer_parsed"] = tool.parse_answer(b["answer"])
    return {"model_key": model_key, "model_id": model_id, "mode_a": a, "mode_b": b,
            "pct_input_reduction": round(pct, 1), "saved_input_usd": saved_usd}


def print_table(result: dict) -> None:
    a, b = result["mode_a"], result["mode_b"]
    print(f"\n  {'mode':<44}{'billed input tok':>18}{'round-trips':>13}{'answer':>10}{'token/API':>11}")
    print("  " + "-" * 96)
    for name, r in [("Mode A: plain tool use", a),
                    ("Mode B: programmatic (allowed_callers)", b)]:
        ans = str(r["answer_parsed"]) if r["answer_parsed"] is not None else "(unparsed)"
        print(f"  {name:<44}{r['billed_input']:>18,}{r['turns']:>13}{ans:>10}{fmt_usd(r['cost']):>11}")
    print()
    print(f"  Your before and after: Mode B billed {b['billed_input']:,} input tokens vs Mode A's "
          f"{a['billed_input']:,},")
    print(f"  a {result['pct_input_reduction']:.0f}% reduction worth {fmt_usd(result['saved_input_usd'])} "
          f"on THIS run at {get(result['model_key']).label}'s input price, because the tool outputs went")
    print(f"  to the sandbox, not the model context. The saving scales with how often you run the task.")
    print("  Cost scope: code execution runtime can bill separately after the monthly free allowance.")
    print(f"  Fan-out shaped: the win needs the model to call your tool many times. On a sequential")
    print(f"  single-call task the doc reports it is flat to about 8% more expensive.\n")


def cmd_run(model_key: str) -> int:
    """Run the token comparison and print the table. Lazy-imports anthropic only here."""
    from common.client import get_client  # lazy: anthropic is imported only when we actually call

    label = get(model_key).label
    n = len(getattr(tool, "EXAMPLE_INPUTS", []) or [])
    print(f"\n  Token bill: the same fan-out task two ways over your tool ({tool.TOOL_SPEC['name']}),")
    print(f"  on {label}. Mode A calls the tool directly, Mode B (programmatic tool calling) runs it")
    print(f"  from a sandbox so the outputs stay out of the model's context.")
    print(f"  Upfront: this run makes 2 task runs over {n} inputs and costs about ${est_usd(model_key):.2f} token/API")
    print("  cost and roughly 90 seconds using your API key.")
    print("  Cost scope: code execution runtime can bill separately after the monthly free allowance.\n")
    client = get_client()
    result = run_token_compare(client, model_key)
    print_table(result)
    return 0


def cmd_check(model_key: str) -> int:
    """The self-test: run the shipped example and assert the PTC invariant before a founder trusts it.

    Asserts BOTH halves of the win on the same run: Mode B bills strictly fewer input tokens than Mode
    A, AND Mode B answers correctly (matching my_tool.EXPECTED_ANSWER). A reduction with a wrong answer
    is not a win, and a right answer that costs more is not the edge, so the gate requires both.
    """
    from common.client import get_client  # lazy

    expected = getattr(tool, "EXPECTED_ANSWER", None)
    print(f"\n  --check: running the shipped example on {get(model_key).label} and asserting the PTC")
    print(f"  invariant (Mode B bills fewer input tokens AND answers correctly). About ${est_usd(model_key):.2f}")
    print("  token/API cost, excluding any separate code-execution runtime charge after the free allowance.\n")
    client = get_client()
    result = run_token_compare(client, model_key)
    print_table(result)

    a, b = result["mode_a"], result["mode_b"]
    fewer = b["billed_input"] < a["billed_input"]
    correct = (expected is None) or (b["answer_parsed"] == expected)
    if expected is None:
        print("  note: my_tool.EXPECTED_ANSWER is None, so --check asserts only the token invariant, "
              "not correctness.")

    problems = []
    if not fewer:
        problems.append(f"Mode B billed {b['billed_input']:,} input tokens, not fewer than Mode A's "
                        f"{a['billed_input']:,}")
    if not correct:
        problems.append(f"Mode B answered {b['answer_parsed']!r}, expected {expected!r}")
    if problems:
        print("\n  CHECK FAILED:")
        for p in problems:
            print(f"    - {p}")
        return 1
    print(f"\n  CHECK PASSED: Mode B billed {result['pct_input_reduction']:.0f}% fewer input tokens "
          f"({b['billed_input']:,} vs {a['billed_input']:,})" +
          (f" and answered {b['answer_parsed']!r} correctly." if expected is not None else "."))
    print("  The token saving holds on the example. Now swap your tool into app/my_tool.py.\n")
    return 0


def main() -> int:
    p = argparse.ArgumentParser(
        description="Run a fan-out task over your tool twice (plain vs programmatic) and print the token bill.")
    p.add_argument("--model", default="sonnet", choices=sorted(PTC_MODELS),
                   help="sonnet (default) or opus, Haiku does not support programmatic tool calling")
    p.add_argument("--check", action="store_true",
                   help="self-test: run the shipped example and assert the PTC invariant")
    a = p.parse_args()
    return cmd_check(a.model) if a.check else cmd_run(a.model)


if __name__ == "__main__":
    raise SystemExit(main())
