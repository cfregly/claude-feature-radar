"""programmatic_tool_calling_cache_context: programmatic tool calling plus cache plus 1M-context cost cliff.

This proof does not call a model. It combines:

  1. the committed live programmatic tool calling receipt, which proves that custom-tool output can stay in the sandbox
     instead of flowing back into model context.
  2. the verified price registry, which carries Claude and competitor input, output, cache-read,
     cache-write, and context-window facts.
  3. a large-context workload shape where a 700k stable prefix is reused across many turns and each
     turn fans out over bulky tool output.

That is the right boundary: Programmatic tool calling is live-measured, while the cache and 1M-context cliff is
price and token-window arithmetic over dated registry facts.
"""

from __future__ import annotations

import argparse
from decimal import Decimal, ROUND_HALF_UP
import json
import pathlib
import re
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))

from common.models import get
from common.pricing import cost_from_buckets


DEFAULT_WORKLOAD = {
    "stable_prefix_tokens": 700_000,
    "turns": 100,
    "raw_tool_output_tokens_per_turn": 200_000,
    "programmatic_summary_tokens_per_turn": 2_000,
    "answer_output_tokens_per_turn": 300,
    "cache_ttl": "1h",
}

PROGRAMMATIC_TOOL_CALLING_RECEIPT = pathlib.Path("edges/programmatic-tool-calling/sample.txt")
OUT_PATH = pathlib.Path("data/last_programmatic_tool_calling_cache_context.json")
COMMITTED_OUT_PATH = pathlib.Path("edges/programmatic-tool-calling-cache-context/receipt.json")


def _mtok_cost(tokens: int, usd_per_mtok: float) -> float:
    return tokens * usd_per_mtok / 1e6


def _money(value: float) -> float:
    return float(Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def _cache_write_cost(model_key: str, tokens: int, ttl: str) -> float:
    model = get(model_key)
    if ttl == "5m":
        return _mtok_cost(tokens, model.cache_write_5m_per_mtok)
    if ttl == "1h":
        return _mtok_cost(tokens, model.cache_write_1h_per_mtok)
    raise ValueError(f"unknown cache ttl {ttl!r}; expected 5m or 1h")


def _cached_run_cost(model_key: str, *, prefix_tokens: int, turns: int, fresh_per_turn: int,
                     output_per_turn: int, ttl: str) -> dict:
    """One cache write, then cached prefix reads on later turns plus fresh per-turn tokens."""
    write = _cache_write_cost(model_key, prefix_tokens, ttl)
    read = cost_from_buckets(model_key, fresh_input=0, cached=prefix_tokens * max(turns - 1, 0), output=0)
    fresh = cost_from_buckets(model_key, fresh_input=fresh_per_turn * turns, cached=0, output=0)
    output = cost_from_buckets(model_key, fresh_input=0, cached=0, output=output_per_turn * turns)
    return {
        "cache_write_usd": round(write, 6),
        "cache_read_usd": round(read, 6),
        "fresh_input_usd": round(fresh, 6),
        "output_usd": round(output, 6),
        "total_usd": _money(write + read + fresh + output),
    }


def _automatic_cache_run_cost(model_key: str, *, prefix_tokens: int, turns: int, fresh_per_turn: int,
                              output_per_turn: int) -> dict:
    """Best-case automatic cache accounting: no write fee and every post-first turn hits cache."""
    read = cost_from_buckets(model_key, fresh_input=0, cached=prefix_tokens * max(turns - 1, 0), output=0)
    fresh = cost_from_buckets(model_key, fresh_input=fresh_per_turn * turns, cached=0, output=0)
    output = cost_from_buckets(model_key, fresh_input=0, cached=0, output=output_per_turn * turns)
    return {
        "cache_write_usd": 0.0,
        "cache_read_usd": round(read, 6),
        "fresh_input_usd": round(fresh, 6),
        "output_usd": round(output, 6),
        "total_usd": _money(read + fresh + output),
    }


def _uncached_run_cost(model_key: str, *, prefix_tokens: int, turns: int, fresh_per_turn: int,
                       output_per_turn: int) -> dict:
    fresh_tokens = (prefix_tokens + fresh_per_turn) * turns
    fresh = cost_from_buckets(model_key, fresh_input=fresh_tokens, cached=0, output=0)
    output = cost_from_buckets(model_key, fresh_input=0, cached=0, output=output_per_turn * turns)
    return {
        "cache_write_usd": 0.0,
        "cache_read_usd": 0.0,
        "fresh_input_usd": round(fresh, 6),
        "output_usd": round(output, 6),
        "total_usd": _money(fresh + output),
    }


def programmatic_tool_calling_receipt(path: pathlib.Path | None = None) -> dict:
    path = path or PROGRAMMATIC_TOOL_CALLING_RECEIPT
    text = path.read_text()
    plain = re.search(r"without programmatic tool calling\s+([\d,]+)", text)
    programmatic = re.search(r"with programmatic tool calling\s+([\d,]+)", text)
    if not plain or not programmatic:
        plain = re.search(r"Mode A: plain tool use\s+([\d,]+)", text)
        programmatic = re.search(r"Mode B: programmatic .*?\s+([\d,]+)", text)
    if not plain or not programmatic:
        raise SystemExit(f"could not parse programmatic tool calling receipt from {path}")
    plain_tokens = int(plain.group(1).replace(",", ""))
    programmatic_tokens = int(programmatic.group(1).replace(",", ""))
    reduction = 100 * (plain_tokens - programmatic_tokens) / plain_tokens
    return {
        "source": str(path),
        "plain_tool_use_billed_input_tokens": plain_tokens,
        "programmatic_tool_calling_billed_input_tokens": programmatic_tokens,
        "input_reduction_pct": round(reduction, 1),
    }


def compute_proof(workload: dict | None = None, *, claude_model_key: str = "sonnet",
                  openai_model_key: str = "gpt-top", gemini_model_key: str = "gem-flash") -> dict:
    workload = dict(workload or DEFAULT_WORKLOAD)
    prefix = int(workload["stable_prefix_tokens"])
    turns = int(workload["turns"])
    raw_tool = int(workload["raw_tool_output_tokens_per_turn"])
    summary = int(workload["programmatic_summary_tokens_per_turn"])
    output = int(workload["answer_output_tokens_per_turn"])
    ttl = str(workload["cache_ttl"])

    claude = get(claude_model_key)
    openai = get(openai_model_key)
    gemini = get(gemini_model_key)
    no_cache = _uncached_run_cost(
        claude_model_key,
        prefix_tokens=prefix,
        turns=turns,
        fresh_per_turn=raw_tool,
        output_per_turn=output,
    )
    cache_no_programmatic = _cached_run_cost(
        claude_model_key,
        prefix_tokens=prefix,
        turns=turns,
        fresh_per_turn=raw_tool,
        output_per_turn=output,
        ttl=ttl,
    )
    cache_programmatic = _cached_run_cost(
        claude_model_key,
        prefix_tokens=prefix,
        turns=turns,
        fresh_per_turn=summary,
        output_per_turn=output,
        ttl=ttl,
    )
    openai_cache_no_programmatic = _automatic_cache_run_cost(
        openai_model_key,
        prefix_tokens=prefix,
        turns=turns,
        fresh_per_turn=raw_tool,
        output_per_turn=output,
    )
    gemini_cache_no_programmatic = _automatic_cache_run_cost(
        gemini_model_key,
        prefix_tokens=prefix,
        turns=turns,
        fresh_per_turn=raw_tool,
        output_per_turn=output,
    )

    reduction_vs_claude_cache = (
        100 * (cache_no_programmatic["total_usd"] - cache_programmatic["total_usd"]) / cache_no_programmatic["total_usd"]
    )
    reduction_vs_uncached = (
        100 * (no_cache["total_usd"] - cache_programmatic["total_usd"]) / no_cache["total_usd"]
    )
    reduction_vs_openai_best = (
        100 * (openai_cache_no_programmatic["total_usd"] - cache_programmatic["total_usd"])
        / openai_cache_no_programmatic["total_usd"]
    )
    reduction_vs_gemini_best = (
        100 * (gemini_cache_no_programmatic["total_usd"] - cache_programmatic["total_usd"])
        / gemini_cache_no_programmatic["total_usd"]
    )
    return {
        "basis": {
            "programmatic_tool_calling_receipt": programmatic_tool_calling_receipt(),
            "claude_model": {"key": claude.key, "label": claude.label, "context_window": claude.context_window},
            "competitor_best_stacks": [
                {
                    "key": openai.key,
                    "label": openai.label,
                    "context_window": openai.context_window,
                    "assumption": "best-case automatic cache hits on every post-first turn, but no programmatic tool calling equivalent",
                },
                {
                    "key": gemini.key,
                    "label": gemini.label,
                    "context_window": gemini.context_window,
                    "assumption": (
                        "context caching plus function calling or code execution for a high-tool-call "
                        "agent executor, but no programmatic tool calling equivalent"
                    ),
                },
            ],
        },
        "workload": workload,
        "context_fit": {
            "prefix_tokens": prefix,
            "prefix_plus_raw_tool_tokens": prefix + raw_tool,
            "prefix_plus_programmatic_summary_tokens": prefix + summary,
            "fits_claude_1m_with_raw_tool_output": prefix + raw_tool <= claude.context_window,
            "fits_claude_1m_with_programmatic_summary": prefix + summary <= claude.context_window,
            "fits_400k_context_with_prefix": prefix <= 400_000,
        },
        "scenarios": {
            "claude_no_cache_no_programmatic": no_cache,
            "claude_cache_no_programmatic": cache_no_programmatic,
            "openai_best_cache_1m_no_programmatic": openai_cache_no_programmatic,
            "gemini_best_cache_1m_no_programmatic": gemini_cache_no_programmatic,
            "claude_cache_programmatic": cache_programmatic,
        },
        "cliff": {
            "savings_vs_claude_cache_no_programmatic_usd": _money(cache_no_programmatic["total_usd"] - cache_programmatic["total_usd"]),
            "savings_vs_openai_best_cache_no_programmatic_usd": _money(
                openai_cache_no_programmatic["total_usd"] - cache_programmatic["total_usd"]
            ),
            "savings_vs_gemini_best_cache_no_programmatic_usd": _money(
                gemini_cache_no_programmatic["total_usd"] - cache_programmatic["total_usd"]
            ),
            "reduction_vs_claude_cache_no_programmatic_pct": round(reduction_vs_claude_cache, 1),
            "reduction_vs_uncached_no_programmatic_pct": round(reduction_vs_uncached, 1),
            "reduction_vs_openai_best_cache_no_programmatic_pct": round(reduction_vs_openai_best, 1),
            "reduction_vs_gemini_best_cache_no_programmatic_pct": round(reduction_vs_gemini_best, 1),
        },
        "honest_reading": (
            "programmatic tool calling is the unique leg: cache and 1M context are not enough if raw custom-tool output keeps "
            "returning to the model as fresh input. The proof is deterministic cost arithmetic over "
            "verified prices, grounded by the committed programmatic tool calling receipt."
        ),
    }


def _print_receipt(receipt: dict) -> None:
    workload = receipt["workload"]
    programmatic_receipt = receipt["basis"]["programmatic_tool_calling_receipt"]
    scenarios = receipt["scenarios"]
    cliff = receipt["cliff"]
    fit = receipt["context_fit"]
    competitors = {stack["key"]: stack for stack in receipt["basis"]["competitor_best_stacks"]}
    openai_stack = competitors["gpt-top"]
    gemini_stack = competitors["gem-flash"]
    print("\n  programmatic tool calling + cache + 1M-context cost cliff (deterministic, $0):\n")
    print(
        f"    committed programmatic tool calling receipt: {programmatic_receipt['plain_tool_use_billed_input_tokens']:,} -> "
        f"{programmatic_receipt['programmatic_tool_calling_billed_input_tokens']:,} billed input tokens "
        f"({programmatic_receipt['input_reduction_pct']}% lower)"
    )
    print(
        f"    modeled workload: {workload['stable_prefix_tokens']:,}-token stable prefix, "
        f"{workload['turns']} turns, {workload['raw_tool_output_tokens_per_turn']:,} raw tool-output "
        f"tokens/turn vs {workload['programmatic_summary_tokens_per_turn']:,} programmatic summary tokens/turn"
    )
    print("\n    scenario                                      total cost")
    print("    --------------------------------------------------------")
    for label, row in scenarios.items():
        print(f"    {label:<42} ${row['total_usd']:>9,.2f}")
    print("\n    cliff:")
    print(
        f"    - Claude cache+programmatic tool calling saves ${cliff['savings_vs_claude_cache_no_programmatic_usd']:,.2f} "
        f"vs Claude cache without programmatic tool calling ({cliff['reduction_vs_claude_cache_no_programmatic_pct']}% lower)"
    )
    print(
        f"    - Claude cache+programmatic tool calling saves ${cliff['savings_vs_openai_best_cache_no_programmatic_usd']:,.2f} "
        f"vs {openai_stack['label']} 1M+cache without programmatic tool calling "
        f"({cliff['reduction_vs_openai_best_cache_no_programmatic_pct']}% lower)"
    )
    print(
        f"    - Claude cache+programmatic tool calling saves ${cliff['savings_vs_gemini_best_cache_no_programmatic_usd']:,.2f} "
        f"vs {gemini_stack['label']} 1M+cache without programmatic tool calling "
        f"({cliff['reduction_vs_gemini_best_cache_no_programmatic_pct']}% lower)"
    )
    print(
        f"    - 700k prefix fits a 1M window: {fit['fits_claude_1m_with_programmatic_summary']}; "
        f"fits a 400k window: {fit['fits_400k_context_with_prefix']}"
    )
    print(f"\n  wrote receipts to {OUT_PATH} and {COMMITTED_OUT_PATH}\n")


def main(argv=None):
    parser = argparse.ArgumentParser(description="Prove the programmatic tool calling + cache + 1M-context cost cliff.")
    parser.add_argument("--json", action="store_true", help="print the receipt JSON")
    args = parser.parse_args(argv)
    receipt = compute_proof()
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    COMMITTED_OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps(receipt, indent=2) + "\n")
    COMMITTED_OUT_PATH.write_text(json.dumps(receipt, indent=2) + "\n")
    if args.json:
        print(json.dumps(receipt, indent=2))
    else:
        _print_receipt(receipt)


if __name__ == "__main__":
    main()
