"""programmatic_tool_calling_cache_context: checked model-token proof for programmatic tool calling + cache + 1M context.

This command does not call a model. It reads the committed programmatic-tool-calling receipt in
``programmatic_tool_calling/sample.txt``, verifies that ``receipt.json`` cites the same 54,989 ->
14,299 billed-input-token basis, and prints the declared cache plus 1M-context cost ladder.
"""

from __future__ import annotations

import argparse
import json
import pathlib
import re


ROOT = pathlib.Path(__file__).resolve().parent
RECEIPT = ROOT / "receipt.json"
PROGRAMMATIC_SAMPLE = ROOT.parent / "programmatic_tool_calling" / "sample.txt"


def load_receipt() -> dict:
    return json.loads(RECEIPT.read_text(encoding="utf-8"))


def parse_programmatic_sample(path: pathlib.Path = PROGRAMMATIC_SAMPLE) -> dict:
    text = path.read_text(encoding="utf-8")
    plain = re.search(r"without programmatic tool calling\s+([\d,]+)", text)
    programmatic = re.search(r"with programmatic tool calling\s+([\d,]+)", text)
    if not plain or not programmatic:
        raise SystemExit(f"could not parse programmatic tool calling token rows from {path}")
    plain_tokens = int(plain.group(1).replace(",", ""))
    programmatic_tokens = int(programmatic.group(1).replace(",", ""))
    reduction = round(100 * (plain_tokens - programmatic_tokens) / plain_tokens, 1)
    expected = re.search(r"acct_1842,\s*acct_2199,\s*acct_7731", text)
    return {
        "source": str(path.relative_to(ROOT.parent)),
        "plain_tool_use_billed_input_tokens": plain_tokens,
        "programmatic_tool_calling_billed_input_tokens": programmatic_tokens,
        "input_reduction_pct": reduction,
        "expected_accounts_present": bool(expected),
    }


def validate_receipt(receipt: dict) -> list[str]:
    problems: list[str] = []
    sample_basis = parse_programmatic_sample()
    receipt_basis = receipt["basis"]["programmatic_tool_calling_receipt"]
    for key in (
        "plain_tool_use_billed_input_tokens",
        "programmatic_tool_calling_billed_input_tokens",
        "input_reduction_pct",
    ):
        if receipt_basis.get(key) != sample_basis.get(key):
            problems.append(f"{key}: receipt has {receipt_basis.get(key)!r}, sample has {sample_basis.get(key)!r}")
    if not sample_basis["expected_accounts_present"]:
        problems.append("programmatic sample does not include acct_1842, acct_2199, and acct_7731")

    scenarios = receipt["scenarios"]
    cliff = receipt["cliff"]
    expected_values = [
        ("Claude no cache/no programmatic", scenarios["claude_no_cache_no_programmatic"]["total_usd"], 270.45),
        ("Claude cache/no programmatic", scenarios["claude_cache_no_programmatic"]["total_usd"], 85.44),
        ("Claude cache + programmatic", scenarios["claude_cache_programmatic"]["total_usd"], 26.04),
        ("GPT-5.5 best cache+1M/no programmatic", scenarios["openai_best_cache_1m_no_programmatic"]["total_usd"], 135.55),
        ("Gemini 3.5 Flash cache+1M/no programmatic", scenarios["gemini_best_cache_1m_no_programmatic"]["total_usd"], 40.67),
        ("Claude savings vs cache-only", cliff["savings_vs_claude_cache_no_programmatic_usd"], 59.40),
        ("Claude savings vs GPT-5.5", cliff["savings_vs_openai_best_cache_no_programmatic_usd"], 109.51),
        ("Claude savings vs Gemini", cliff["savings_vs_gemini_best_cache_no_programmatic_usd"], 14.63),
        ("Claude reduction vs GPT-5.5", cliff["reduction_vs_openai_best_cache_no_programmatic_pct"], 80.8),
        ("Claude reduction vs Gemini", cliff["reduction_vs_gemini_best_cache_no_programmatic_pct"], 36.0),
    ]
    for label, actual, wanted in expected_values:
        if round(float(actual), 2) != round(float(wanted), 2):
            problems.append(f"{label}: {actual} != {wanted}")
    return problems


def print_report(receipt: dict) -> None:
    basis = receipt["basis"]
    workload = receipt["workload"]
    scenarios = receipt["scenarios"]
    cliff = receipt["cliff"]
    receipt_basis = basis["programmatic_tool_calling_receipt"]
    competitors = {stack["key"]: stack for stack in basis["competitor_best_stacks"]}
    openai_stack = competitors["gpt-top"]
    gemini_stack = competitors["gem-flash"]

    print("\n  programmatic_tool_calling_cache_context: programmatic tool calling + prompt caching + 1M context cost cliff.")
    print("  This command is deterministic: it reads the committed programmatic-tool-calling receipt and receipt.json.")
    print("  It does not call any model or require an API key.\n")
    print("  committed programmatic tool calling basis")
    print(f"    without programmatic tool calling: {receipt_basis['plain_tool_use_billed_input_tokens']:,} billed input tokens")
    print(f"    with programmatic tool calling:    {receipt_basis['programmatic_tool_calling_billed_input_tokens']:,} billed input tokens")
    print(f"    reduction:                         {receipt_basis['input_reduction_pct']:.0f}%\n")
    print("  declared larger workload")
    print(f"    stable prefix tokens:              {workload['stable_prefix_tokens']:,}")
    print(f"    turns:                             {workload['turns']}")
    print(f"    raw tool-output tokens per turn:   {workload['raw_tool_output_tokens_per_turn']:,}")
    print(f"    programmatic summary tokens/turn:  {workload['programmatic_summary_tokens_per_turn']:,}")
    print(f"    Claude context window:             {basis['claude_model']['context_window']:,}")
    print(f"    {openai_stack['label']} context window:            {openai_stack['context_window']:,}")
    print(f"    {gemini_stack['label']} context window:   {gemini_stack['context_window']:,}\n")

    rows = [
        ("Claude, no cache, no programmatic tool calling", scenarios["claude_no_cache_no_programmatic"]["total_usd"]),
        ("Claude cache, no programmatic tool calling", scenarios["claude_cache_no_programmatic"]["total_usd"]),
        ("GPT-5.5 best cache+1M, no programmatic tool calling", scenarios["openai_best_cache_1m_no_programmatic"]["total_usd"]),
        ("Gemini 3.5 Flash cache+1M, no programmatic tool calling", scenarios["gemini_best_cache_1m_no_programmatic"]["total_usd"]),
        ("Claude cache + programmatic tool calling", scenarios["claude_cache_programmatic"]["total_usd"]),
    ]
    print("  scenario                                                   estimated model-token cost")
    print("  -----------------------------------------------------------------------------------")
    for label, total in rows:
        print(f"  {label:<62}${total:.2f}")
    print("  -----------------------------------------------------------------------------------")
    print(
        "  Claude cache + programmatic tool calling saves "
        f"${cliff['savings_vs_claude_cache_no_programmatic_usd']:.2f} vs Claude cache-only."
    )
    print(
        "  Claude cache + programmatic tool calling saves "
        f"${cliff['savings_vs_openai_best_cache_no_programmatic_usd']:.2f} vs GPT-5.5 best cache+1M without programmatic tool calling."
    )
    print(
        "  Claude cache + programmatic tool calling is "
        f"{cliff['reduction_vs_openai_best_cache_no_programmatic_pct']:.1f}% lower than GPT-5.5 best cache+1M without programmatic tool calling."
    )
    print(
        "  Claude cache + programmatic tool calling saves "
        f"${cliff['savings_vs_gemini_best_cache_no_programmatic_usd']:.2f} vs Gemini 3.5 Flash cache+1M without programmatic tool calling."
    )
    print(
        "  Claude cache + programmatic tool calling is "
        f"{cliff['reduction_vs_gemini_best_cache_no_programmatic_pct']:.1f}% lower than Gemini 3.5 Flash cache+1M without programmatic tool calling."
    )
    print("\n  Cost scope: model-token arithmetic only. Add any separate code-execution runtime charge,")
    print("  including the current $0.0042 floor exposure per new billed code-execution container,")
    print("  plus backend cost, latency, failures, and correctness before claiming production COGS.")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="validate the committed receipt and cost ladder")
    args = parser.parse_args()
    receipt = load_receipt()
    problems = validate_receipt(receipt)
    print_report(receipt)
    if args.check:
        if problems:
            print("\n  CHECK FAILED:")
            for problem in problems:
                print(f"    - {problem}")
            return 1
        print("\n  CHECK PASSED: committed 74% basis and declared cost ladder are internally consistent.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
