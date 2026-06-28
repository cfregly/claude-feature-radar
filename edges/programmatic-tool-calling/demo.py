"""Programmatic tool calling customer-evidence receipt.

Radar owns the canonical public implementation under ``engine/public_hits_bundle``. This edge runner
imports that package, runs the live A/B workload, and writes the local radar receipt used by freshness
and publish gates.
"""

from __future__ import annotations

import argparse
import json
import pathlib
import sys


ROOT = pathlib.Path(__file__).resolve().parents[2]
BUNDLE_ROOT = ROOT / "engine" / "public_hits_bundle"
OUT_PATH = ROOT / "data" / "last_programmatic_tool_calling.json"

# The delegated bundle run engine sends code_execution_20260120 and allowed_callers.
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(BUNDLE_ROOT))

from programmatic_tool_calling.common.anthropic_client import get_client  # noqa: E402
from programmatic_tool_calling.common.model_catalog import get  # noqa: E402
from programmatic_tool_calling.compare_direct_vs_programmatic import (  # noqa: E402
    est_usd,
    print_table,
    programmatic_trace_problems,
    run_token_compare,
)
from engine.demonstrators.base import Arm, BaseDemonstrator, CostEstimate, Verdict  # noqa: E402
from engine.demonstrators.registry import register  # noqa: E402


def _arm_from_run(name: str, run: dict, model_id: str, *, note: str = "") -> Arm:
    trace = run.get("trace") or {}
    return Arm(
        provider="claude",
        model=model_id,
        text=run.get("answer", ""),
        ran=True,
        latency_s=run.get("time", 0.0),
        input_tokens=run.get("billed_input", 0),
        output_tokens=run.get("output_tokens", 0),
        cost_usd=run.get("cost", 0.0),
        ctx=run.get("billed_input", 0),
        metric={
            "mode": name,
            "billed_input_tokens": run.get("billed_input", 0),
            "tool_calls": run.get("tool_calls", 0),
            "turns": run.get("turns", 0),
            "answer_parsed": run.get("answer_parsed"),
            "expected_answer": run.get("expected_answer"),
            "correctness": run.get("correctness"),
            "caller_path_drift": trace.get("caller_path_drift"),
            "server_tool_blocks": trace.get("server_tool_blocks"),
            "container_count": len(trace.get("container_ids") or []),
        },
        note=note,
    )


class ProgrammaticToolCallingDemonstrator(BaseDemonstrator):
    demo_kind = "token_accounting"

    def estimate(self, edge, spec):
        model_key = spec.get("claude_model", spec.get("model", "sonnet"))
        return CostEstimate(
            usd=round(est_usd(model_key), 2),
            wall_clock_s=90.0,
            command="make programmatic-tool-calling",
            note="customer-evidence fan-out, direct tool use vs programmatic tool calling",
        )

    def run_claude_arm(self, edge, spec):
        client = spec.get("client") or get_client()
        model_key = spec.get("claude_model", spec.get("model", "sonnet"))
        result = run_token_compare(client, model_key)
        spec["programmatic_tool_calling_result"] = result
        return _arm_from_run("with_programmatic_tool_calling", result["mode_b"], result["model_id"])

    def run_competitor_arms(self, edge, spec):
        return []

    def score(self, claude, competitors, spec):
        result = spec.get("programmatic_tool_calling_result") or {}
        mode_a = result.get("mode_a") or {}
        mode_b = result.get("mode_b") or {}
        problems = []
        if mode_a and mode_b and mode_b.get("billed_input", 0) >= mode_a.get("billed_input", 0):
            problems.append("programmatic arm did not reduce billed input tokens")
        if result:
            problems.extend(programmatic_trace_problems(result))
        expected = mode_b.get("expected_answer")
        if expected is not None and mode_b.get("answer_parsed") != expected:
            problems.append(f"programmatic arm returned {mode_b.get('answer_parsed')!r}, expected {expected!r}")
        pct = result.get("pct_input_reduction", 0.0)
        return Verdict(
            verdict="claude-ahead" if not problems else "never-evaluated",
            passed=not problems,
            metric={
                "without_programmatic_tool_calling_billed_input_tokens": mode_a.get("billed_input", 0),
                "with_programmatic_tool_calling_billed_input_tokens": mode_b.get("billed_input", 0),
                "input_token_reduction_pct": pct,
                "saved_token_api_usd": result.get("saved_token_api_usd", 0.0),
            },
            note="; ".join(problems),
        )

    def receipt(self, edge, claude, competitors, verdict, spec):
        result = spec.get("programmatic_tool_calling_result") or {}
        mode_a = result.get("mode_a") or {}
        model_id = result.get("model_id", "")
        direct_arm = _arm_from_run(
            "without_programmatic_tool_calling",
            mode_a,
            model_id,
            note="same Claude model, direct tool calls",
        ) if mode_a else None
        arms = [a for a in (([direct_arm] if direct_arm else []) + [claude]) if a is not None]
        return self.build_receipt(
            edge,
            claude,
            arms[:-1],
            verdict,
            spec,
            workload={
                "task": "find the three at-risk customer accounts from raw evidence rows",
                "public_edit_surface": "programmatic_tool_calling/founder_workload.py",
                "basis": "same model, same workload, direct tool calls vs programmatic tool calling",
            },
            grounding=[
                {
                    "claim": "Programmatic tool calling allows developer tools to be called from code execution.",
                    "source_url": "https://platform.claude.com/docs/en/agents-and-tools/tool-use/programmatic-tool-calling",
                    "date": "2026-06-26",
                }
            ],
            fairness={
                "best_to_best": "same Claude model and same founder workload in both arms",
                "isolate": "only allowed_callers plus code execution changes between arms",
            },
        )


register(ProgrammaticToolCallingDemonstrator())


def _write_receipt(result: dict) -> None:
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps(result, indent=2, default=str) + "\n")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", default="sonnet", choices=("opus", "sonnet"))
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args(argv)

    print("\n  Programmatic tool calling: customer-evidence fan-out, direct tool use vs programmatic tool calling.")
    print(f"  Model: {get(args.model).label}. Estimated token/API cost: ${est_usd(args.model):.2f}.")
    print("  The implementation is the manifest-owned public bundle under engine/public_hits_bundle.\n")
    result = run_token_compare(get_client(), args.model)
    print_table(result)
    _write_receipt(result)

    problems = []
    if result["mode_b"]["billed_input"] >= result["mode_a"]["billed_input"]:
        problems.append("Mode B did not reduce billed input tokens")
    problems.extend(programmatic_trace_problems(result))
    expected = result["mode_b"].get("expected_answer")
    if expected is not None and result["mode_b"].get("answer_parsed") != expected:
        problems.append(f"Mode B returned {result['mode_b'].get('answer_parsed')!r}, expected {expected!r}")

    print(f"  wrote receipt to {OUT_PATH.relative_to(ROOT)}\n")
    if args.check and problems:
        print("  CHECK FAILED:")
        for problem in problems:
            print(f"    - {problem}")
        return 1
    if args.check:
        print("  CHECK PASSED: fewer billed input tokens, expected account list, and clean trace gate.\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
