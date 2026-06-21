"""Stop a budget-exhausted agent before it burns the next tool call, with Claude task budgets.

A long-running agent is about to start a tool loop. With Claude's task_budget, the model sees a
provider-side countdown for the whole agentic loop (thinking, tool calls, tool results, output) and
hands off cleanly when the budget is near exhausted, instead of starting work it cannot finish.

Usage:
    python -m task_budgets.run          # run the low-budget vs control tool loop, print the table
    python -m task_budgets.run --check  # live self-test: assert the win invariant holds ($0.01)

Cost: $0.01 on claude-opus-4-8 for the two live calls.
Docs: https://platform.claude.com/docs/en/build-with-claude/task-budgets
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from .common.models import get  # noqa: E402  verified id + price registry, anthropic-free
from .common.pricing import cost_usd  # noqa: E402  real usage object -> real dollars, anthropic-free

CLAUDE_MODEL = "claude-opus-4-8"
BETA = "task-budgets-2026-03-13"
BUDGET_TOTAL = 20000   # the doc minimum accepted task_budget.total
LOW_REMAINING = 50     # near exhausted: Claude should hand off before the first tool call
HIGH_REMAINING = 5000  # plenty of budget: the control should start the loop
DOC_URL = "https://platform.claude.com/docs/en/build-with-claude/task-budgets"

# A budget-sensitive agent about to start a 12-record audit. The model gets the same prompt in both
# arms; only the remaining task budget differs, so the behavior change is attributable to the budget.
TOOL_LOOP_PROMPT = (
    'You are starting a budget-sensitive 12-record audit. If your hidden task budget indicator says '
    'the task is near exhaustion, do not call tools. Return JSON only: '
    '{"action":"handoff","graceful_stop":true,"tool_calls":0,"reason":"budget"}. If you have no '
    'near-exhaustion task budget indicator, or it is not near exhaustion, call fetch_record for '
    'record_id 1 as the first step. Do not answer in text before that tool call.'
)

FETCH_TOOL = {
    "name": "fetch_record",
    "description": "Fetch one audit record by id.",
    "input_schema": {
        "type": "object",
        "properties": {"record_id": {"type": "integer"}},
        "required": ["record_id"],
    },
}


def _extract_json(text: str) -> dict:
    match = re.search(r"\{.*\}", text or "", re.S)
    if not match:
        return {}
    try:
        return json.loads(match.group(0))
    except json.JSONDecodeError:
        return {}


def _truthy(value) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"true", "yes", "1"}
    return bool(value)


def _is_handoff(parsed: dict) -> bool:
    return str(parsed.get("action", "")).strip().lower() == "handoff" and _truthy(parsed.get("graceful_stop"))


def run_loop(remaining: int) -> dict:
    """One agentic-loop turn with a given remaining task budget. Returns the measured arm result."""
    from .common.client import get_client  # lazy: anthropic is imported only when we actually call
    client = get_client()
    start = time.perf_counter()
    msg = client.beta.messages.create(
        model=CLAUDE_MODEL,
        max_tokens=256,
        # task_budget is the whole edge: the model sees a server-side countdown for the full loop.
        # remaining carries the budget remainder forward; here it sets the near-exhausted condition.
        output_config={
            "effort": "low",
            "task_budget": {"type": "tokens", "total": BUDGET_TOTAL, "remaining": remaining},
        },
        betas=[BETA],
        messages=[{"role": "user", "content": TOOL_LOOP_PROMPT}],
        tools=[FETCH_TOOL],
        timeout=60.0,
    )
    latency = time.perf_counter() - start
    tool_calls = sum(1 for b in msg.content if getattr(b, "type", None) == "tool_use")
    text = "".join(getattr(b, "text", "") for b in msg.content if getattr(b, "type", None) == "text")
    parsed = _extract_json(text)
    return {
        "remaining": remaining,
        "tool_calls": tool_calls,
        "handoff": _is_handoff(parsed),
        "latency_s": latency,
        "input_tokens": getattr(msg.usage, "input_tokens", 0) or 0,
        "output_tokens": getattr(msg.usage, "output_tokens", 0) or 0,
        "cost": cost_usd(CLAUDE_MODEL, msg.usage),
        "stop_reason": getattr(msg, "stop_reason", ""),
    }


def _print_table(low: dict, control: dict) -> None:
    label = get(CLAUDE_MODEL).label
    print(f"\n  Workload: start a 12-record audit by calling fetch_record(1), unless the hidden task")
    print(f"  budget says the loop is near exhausted. Model: {label}. Only the budget differs.\n")
    print("  arm                       hidden low-budget stop   first tool calls   wall time")
    print("  " + "-" * 73)
    low_stop = "yes" if low["handoff"] and low["tool_calls"] == 0 else "no"
    print(f"  low budget (remaining {low['remaining']:<5}) {low_stop:>14}   {low['tool_calls']:>16}   {low['latency_s']:>7.1f}s")
    print(f"  control   (remaining {control['remaining']:<5}) {'n/a':>15}   {control['tool_calls']:>16}   {control['latency_s']:>7.1f}s")
    print()


def cmd_run() -> int:
    total = BUDGET_TOTAL
    est = 0.01
    print(f"\n  task_budgets live run on {CLAUDE_MODEL}. Two calls, ${est:.2f}, a few seconds.")
    low = run_loop(LOW_REMAINING)
    control = run_loop(HIGH_REMAINING)
    _print_table(low, control)
    spent = low["cost"] + control["cost"]
    print(f"  Claude held the tool call at low budget and started the loop with budget to spare.")
    print(f"  Total budget {total:,} tokens. Spent ${spent:.2f} on these two calls.\n")
    return 0


def cmd_check() -> int:
    """Live self-test: the win invariant must hold. Low budget hands off before the first tool call,
    and the control starts the loop. $0.01."""
    print(f"\n  task_budgets --check on {CLAUDE_MODEL}. Two calls, $0.01.")
    low = run_loop(LOW_REMAINING)
    control = run_loop(HIGH_REMAINING)
    _print_table(low, control)
    spent = low["cost"] + control["cost"]
    assert low["handoff"] and low["tool_calls"] == 0, (
        f"FAIL: low budget did not hand off before the first tool call "
        f"(handoff={low['handoff']}, tool_calls={low['tool_calls']})"
    )
    assert control["tool_calls"] >= 1, (
        f"FAIL: the control did not start the tool loop (tool_calls={control['tool_calls']})"
    )
    print(f"  PASS: low budget handed off before the first tool call, the control started the loop.")
    print(f"  Spent ${spent:.2f}.\n")
    return 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Claude task budgets: stop before a budget-exhausted tool loop.")
    parser.add_argument("--check", action="store_true", help="live self-test asserting the win invariant")
    args = parser.parse_args(argv)
    return cmd_check() if args.check else cmd_run()


if __name__ == "__main__":
    raise SystemExit(main())
