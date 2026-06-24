"""ptc_cache_context: the PTC plus cache plus 1M-context cost cliff, as a deterministic receipt.

This proof does not call a model. It combines:

  1. the committed live PTC receipt, which proves that custom-tool output can stay in the sandbox
     instead of flowing back into model context.
  2. the verified price registry, which carries Claude and competitor input, output, cache-read,
     cache-write, and context-window facts.
  3. a large-context workload shape where a 700k stable prefix is reused across many turns and each
     turn fans out over bulky tool output.

That is the right boundary: PTC mechanism is live-measured, while the cache and 1M-context cliff is
price and token-window arithmetic over dated registry facts.
"""

from __future__ import annotations

import argparse
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
    "ptc_summary_tokens_per_turn": 2_000,
    "answer_output_tokens_per_turn": 300,
    "cache_ttl": "1h",
}

PTC_RECEIPT = pathlib.Path("edges/programmatic-tool-calling/sample.txt")
OUT_PATH = pathlib.Path("data/last_ptc_cache_context.json")


def _mtok_cost(tokens: int, usd_per_mtok: float) -> float:
    return tokens * usd_per_mtok / 1e6


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
        "total_usd": round(write + read + fresh + output, 6),
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
        "total_usd": round(read + fresh + output, 6),
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
        "total_usd": round(fresh + output, 6),
    }


def ptc_receipt(path: pathlib.Path | None = None) -> dict:
    path = path or PTC_RECEIPT
    text = path.read_text()
    plain = re.search(r"Mode A: plain tool use\s+([\d,]+)", text)
    programmatic = re.search(r"Mode B: programmatic .*?\s+([\d,]+)", text)
    if not plain or not programmatic:
        raise SystemExit(f"could not parse PTC receipt from {path}")
    plain_tokens = int(plain.group(1).replace(",", ""))
    programmatic_tokens = int(programmatic.group(1).replace(",", ""))
    reduction = 100 * (plain_tokens - programmatic_tokens) / plain_tokens
    return {
        "source": str(path),
        "plain_tool_use_billed_input_tokens": plain_tokens,
        "programmatic_tool_calling_billed_input_tokens": programmatic_tokens,
        "input_reduction_pct": round(reduction, 1),
    }


def compute_proof(workload: dict | None = None, *, claude_model_key: str = "opus",
                  competitor_model_key: str = "gpt-top") -> dict:
    workload = dict(workload or DEFAULT_WORKLOAD)
    prefix = int(workload["stable_prefix_tokens"])
    turns = int(workload["turns"])
    raw_tool = int(workload["raw_tool_output_tokens_per_turn"])
    summary = int(workload["ptc_summary_tokens_per_turn"])
    output = int(workload["answer_output_tokens_per_turn"])
    ttl = str(workload["cache_ttl"])

    claude = get(claude_model_key)
    competitor = get(competitor_model_key)
    no_cache = _uncached_run_cost(
        claude_model_key,
        prefix_tokens=prefix,
        turns=turns,
        fresh_per_turn=raw_tool,
        output_per_turn=output,
    )
    cache_no_ptc = _cached_run_cost(
        claude_model_key,
        prefix_tokens=prefix,
        turns=turns,
        fresh_per_turn=raw_tool,
        output_per_turn=output,
        ttl=ttl,
    )
    cache_ptc = _cached_run_cost(
        claude_model_key,
        prefix_tokens=prefix,
        turns=turns,
        fresh_per_turn=summary,
        output_per_turn=output,
        ttl=ttl,
    )
    competitor_cache_no_ptc = _automatic_cache_run_cost(
        competitor_model_key,
        prefix_tokens=prefix,
        turns=turns,
        fresh_per_turn=raw_tool,
        output_per_turn=output,
    )

    reduction_vs_claude_cache = (
        100 * (cache_no_ptc["total_usd"] - cache_ptc["total_usd"]) / cache_no_ptc["total_usd"]
    )
    reduction_vs_uncached = (
        100 * (no_cache["total_usd"] - cache_ptc["total_usd"]) / no_cache["total_usd"]
    )
    reduction_vs_competitor_best = (
        100 * (competitor_cache_no_ptc["total_usd"] - cache_ptc["total_usd"])
        / competitor_cache_no_ptc["total_usd"]
    )
    return {
        "basis": {
            "ptc_live_receipt": ptc_receipt(),
            "claude_model": {"key": claude.key, "label": claude.label, "context_window": claude.context_window},
            "competitor_best_stack": {
                "key": competitor.key,
                "label": competitor.label,
                "context_window": competitor.context_window,
                "assumption": "best-case automatic cache hits on every post-first turn, but no PTC equivalent",
            },
        },
        "workload": workload,
        "context_fit": {
            "prefix_tokens": prefix,
            "prefix_plus_raw_tool_tokens": prefix + raw_tool,
            "prefix_plus_ptc_summary_tokens": prefix + summary,
            "fits_claude_1m_with_raw_tool_output": prefix + raw_tool <= claude.context_window,
            "fits_claude_1m_with_ptc_summary": prefix + summary <= claude.context_window,
            "fits_400k_context_with_prefix": prefix <= 400_000,
        },
        "scenarios": {
            "claude_no_cache_no_ptc": no_cache,
            "claude_cache_no_ptc": cache_no_ptc,
            "openai_best_cache_1m_no_ptc": competitor_cache_no_ptc,
            "claude_cache_ptc": cache_ptc,
        },
        "cliff": {
            "savings_vs_claude_cache_no_ptc_usd": round(cache_no_ptc["total_usd"] - cache_ptc["total_usd"], 6),
            "savings_vs_openai_best_cache_no_ptc_usd": round(
                competitor_cache_no_ptc["total_usd"] - cache_ptc["total_usd"], 6
            ),
            "reduction_vs_claude_cache_no_ptc_pct": round(reduction_vs_claude_cache, 1),
            "reduction_vs_uncached_no_ptc_pct": round(reduction_vs_uncached, 1),
            "reduction_vs_openai_best_cache_no_ptc_pct": round(reduction_vs_competitor_best, 1),
        },
        "honest_reading": (
            "PTC is the unique leg: cache and 1M context are not enough if raw custom-tool output keeps "
            "returning to the model as fresh input. The proof is deterministic cost arithmetic over "
            "verified prices, grounded by the committed live PTC receipt."
        ),
    }


def _print_receipt(receipt: dict) -> None:
    workload = receipt["workload"]
    ptc = receipt["basis"]["ptc_live_receipt"]
    scenarios = receipt["scenarios"]
    cliff = receipt["cliff"]
    fit = receipt["context_fit"]
    print("\n  PTC + cache + 1M-context cost cliff (deterministic, $0):\n")
    print(
        f"    live PTC receipt: {ptc['plain_tool_use_billed_input_tokens']:,} -> "
        f"{ptc['programmatic_tool_calling_billed_input_tokens']:,} billed input tokens "
        f"({ptc['input_reduction_pct']}% lower)"
    )
    print(
        f"    modeled workload: {workload['stable_prefix_tokens']:,}-token stable prefix, "
        f"{workload['turns']} turns, {workload['raw_tool_output_tokens_per_turn']:,} raw tool-output "
        f"tokens/turn vs {workload['ptc_summary_tokens_per_turn']:,} PTC summary tokens/turn"
    )
    print("\n    scenario                                      total cost")
    print("    --------------------------------------------------------")
    for label, row in scenarios.items():
        print(f"    {label:<42} ${row['total_usd']:>9,.2f}")
    print("\n    cliff:")
    print(
        f"    - Claude cache+PTC saves ${cliff['savings_vs_claude_cache_no_ptc_usd']:,.2f} "
        f"vs Claude cache without PTC ({cliff['reduction_vs_claude_cache_no_ptc_pct']}% lower)"
    )
    print(
        f"    - Claude cache+PTC saves ${cliff['savings_vs_openai_best_cache_no_ptc_usd']:,.2f} "
        f"vs best-case GPT-5.5 1M+cache without PTC "
        f"({cliff['reduction_vs_openai_best_cache_no_ptc_pct']}% lower)"
    )
    print(
        f"    - 700k prefix fits a 1M window: {fit['fits_claude_1m_with_ptc_summary']}; "
        f"fits a 400k window: {fit['fits_400k_context_with_prefix']}"
    )
    print(f"\n  wrote receipt to {OUT_PATH}\n")


def main(argv=None):
    parser = argparse.ArgumentParser(description="Prove the PTC + cache + 1M-context cost cliff.")
    parser.add_argument("--json", action="store_true", help="print the receipt JSON")
    args = parser.parse_args(argv)
    receipt = compute_proof()
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps(receipt, indent=2) + "\n")
    if args.json:
        print(json.dumps(receipt, indent=2))
    else:
        _print_receipt(receipt)


if __name__ == "__main__":
    main()
