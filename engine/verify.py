"""verify: the skeptic pass. Hand each candidate gap to Claude and tell it to break the claim.

A gap a skeptic cannot break is one a founder cannot break either. This is the discipline that
separates the engine from a marketing generator: it actively tries to refute its own pitch before
anything reaches an inbox.
"""

from __future__ import annotations

import argparse
import os

from common.client import get_client
from common.models import get, request_kwargs
from common.runner import call as runner_call, get_openai_client
from engine.budget import BudgetLedger
from engine.scan import current_edges

SYSTEM = (
    "You are a skeptical startup CTO who has shipped on OpenAI, Google Gemini, and Anthropic "
    "Claude. For each claimed capability gap, decide whether it survives scrutiny or is "
    "overstated. Be harsh. If a competitor has a near-equivalent, the claim is overstated. Think "
    "combinatorially: a single Claude feature can read as a real edge while the competitor can "
    "assemble an equivalent STACK of two or three of its own features on the same workload, so try "
    "to build that competing combination before you let a claim survive. Reply with exactly one "
    "line per claim, in the form: <KILLED|SURVIVES> - <key> - <one sentence why>."
)


def _body() -> str:
    return "\n\n".join(
        f"key: {c['key']}\nclaim Claude is ahead: {c['claim']}\nwhy: {c['why']}"
        for c in current_edges()  # the freshly ranked landscape edges, the seed on a fresh checkout
    )


def _claude_effort() -> str:
    return os.environ.get("RADAR_CLAUDE_EFFORT", "xhigh")


def _verdict_max_tokens() -> int:
    raw = os.environ.get("RADAR_VERIFY_MAX_TOKENS")
    if raw:
        return int(raw)
    return 32000 if _claude_effort() == "max" else 8000


def _create_claude_message(client, **kwargs):
    if _claude_effort() == "max" or kwargs.get("max_tokens", 0) > 16000:
        with client.messages.stream(**kwargs) as stream:
            stream.until_done()
            return stream.get_final_message()
    return client.messages.create(**kwargs)


def _message_text(msg) -> str:
    return "".join(getattr(b, "text", "") for b in msg.content if getattr(b, "type", None) == "text").strip()


def _run_claude(body: str, budget: BudgetLedger) -> None:
    messages = [{"role": "user", "content": body}]
    max_tokens = _verdict_max_tokens()
    effort = _claude_effort()
    reservation = budget.preflight("verify:claude-opus-skeptic", "opus",
                                   messages=messages, max_tokens=max_tokens, system=SYSTEM)
    client = get_client()
    try:
        msg = _create_claude_message(
            client,
            max_tokens=max_tokens,
            system=SYSTEM,
            messages=messages,
            **request_kwargs("opus", effort=effort, adaptive_thinking=True),
        )
    except Exception as e:
        budget.mark_failed(reservation, e)
        raise
    budget.commit_usage(reservation, msg.usage)
    text = _message_text(msg)
    if not text:
        kinds = ", ".join(getattr(b, "type", "?") for b in msg.content)
        raise SystemExit(
            f"Claude verifier returned no visible verdict text after {max_tokens} max_tokens "
            f"(content blocks: {kinds or 'none'})."
        )
    print(f"\n  Skeptic pass ({get('opus').label}, {effort} effort, adaptive thinking):\n")
    for line in text.splitlines():
        if line.strip():
            print(f"    {line.strip()}")
    print()


def _run_openai(body: str, budget: BudgetLedger) -> None:
    client = get_openai_client()
    if client is None:
        print("\n  OpenAI skeptic skipped: OPENAI_API_KEY is not set.\n")
        return
    messages = [{"role": "user", "content": body}]
    max_tokens = _verdict_max_tokens()
    reservation = budget.preflight("verify:openai-gpt-5.5-xhigh-skeptic", "gpt-top",
                                   messages=messages, max_tokens=max_tokens, system=SYSTEM)
    try:
        result = runner_call(client, "gpt-top", messages, max_tokens=max_tokens, effort="xhigh")
    except Exception as e:
        budget.mark_failed(reservation, e)
        raise
    budget.commit_result_cost(
        reservation,
        result.cost_usd,
        usage={"input_tokens": result.input_tokens, "output_tokens": result.output_tokens},
    )
    print(f"\n  Skeptic pass ({get('gpt-top').label}, xhigh reasoning):\n")
    for line in result.text.splitlines():
        if line.strip():
            print(f"    {line.strip()}")
    print()


def main(argv=None):
    parser = argparse.ArgumentParser(description="Run the paid skeptic pass under a budget cap.")
    parser.add_argument("--budget-usd", type=float, default=None,
                        help="Daily budget cap. Defaults to RADAR_BUDGET_USD or $2.")
    parser.add_argument("--budget-label", default=None,
                        help="Budget ledger label. Defaults to RADAR_BUDGET_LABEL or grind-deep.")
    parser.add_argument("--judges", default=os.environ.get("RADAR_VERIFY_JUDGES", "claude"),
                        help="Comma-separated judges: claude or claude,openai. OpenAI uses GPT-5.5 xhigh.")
    args = parser.parse_args(argv)
    budget = BudgetLedger.from_env(cap_usd=args.budget_usd, label=args.budget_label)
    body = _body()
    for judge in [j.strip().lower() for j in args.judges.split(",") if j.strip()]:
        if judge == "claude":
            _run_claude(body, budget)
        elif judge == "openai":
            _run_openai(body, budget)
        else:
            raise SystemExit(f"unknown judge {judge!r}; expected claude or openai")


if __name__ == "__main__":
    main()
