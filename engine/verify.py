"""verify: the skeptic pass. Hand each candidate gap to Claude and tell it to break the claim.

A gap a skeptic cannot break is one a founder cannot break either. This is the discipline that
separates the engine from a marketing generator: it actively tries to refute its own pitch before
anything reaches an inbox.
"""

from __future__ import annotations

import argparse
import json
import os
import pathlib
import re

from common.client import get_client
from common.models import get, request_kwargs
from common.runner import call as runner_call, get_openai_client
from engine.adversarial import write_report
from engine.budget import BudgetLedger
from engine.scan import current_edges

JUDGE_SYSTEM = (
    "You are a skeptical startup CTO who has shipped on OpenAI, Google Gemini, and Anthropic "
    "Claude. For each claimed capability gap, decide whether it survives scrutiny or is "
    "overstated. Be harsh. If a competitor has a near-equivalent, the claim is overstated. Think "
    "combinatorially: a single Claude feature can read as a real edge while the competitor can "
    "assemble an equivalent STACK of two or three of its own features on the same workload, so try "
    "to build that competing combination before you let a claim survive. KILL claims where the "
    "difference is only native packaging, DX, a thinner integration path, a feature name, or a "
    "mechanism with no measured founder-valued outcome. SURVIVES only when the evidence shows an "
    "outcome a founder pays for: lower cost, higher speed, stronger reliability, better accuracy, "
    "stronger security, or less glue code that a best competitor stack cannot recreate on the same "
    "workload.\n\n"
    "Return only strict JSON, with no markdown, no code fence, no table, and no prose outside the "
    "JSON object. The schema is exactly: "
    '{"verdicts":[{"key":"<claim key>","verdict":"KILLED|SURVIVES","why":"<one sentence>"}]}. '
    "Return exactly one verdict for every expected key, and no extra keys."
)

# Back-compat alias for old imports/tests.
SYSTEM = JUDGE_SYSTEM
OPENAI_SYSTEM = JUDGE_SYSTEM


def _claim_keys(body: str) -> list[str]:
    return re.findall(r"^key:\s*(\S+)\s*$", body, flags=re.MULTILINE)


def _parse_openai_verdicts(text: str, expected_keys: list[str]) -> dict[str, dict[str, str]]:
    """Parse and validate the OpenAI judge contract.

    This intentionally rejects markdown tables, bullet lists, code fences, and loose prose. A judge
    that cannot produce the exact machine-readable shape is not allowed to silently pass the gate.
    """
    try:
        data = json.loads(text.strip())
    except json.JSONDecodeError as exc:
        raise SystemExit(f"OpenAI skeptic returned invalid JSON: {exc.msg}") from exc
    if not isinstance(data, dict):
        raise SystemExit("OpenAI skeptic returned invalid JSON verdicts: top level must be an object")
    verdicts = data.get("verdicts")
    if not isinstance(verdicts, list):
        raise SystemExit("OpenAI skeptic returned invalid JSON verdicts: missing verdicts list")

    expected = set(expected_keys)
    found: dict[str, dict[str, str]] = {}
    for i, row in enumerate(verdicts, start=1):
        if not isinstance(row, dict):
            raise SystemExit(f"OpenAI skeptic returned invalid verdict row {i}: row must be an object")
        key = row.get("key")
        verdict = row.get("verdict")
        why = row.get("why")
        if not isinstance(key, str) or key not in expected:
            raise SystemExit(f"OpenAI skeptic returned invalid verdict row {i}: unknown or missing key")
        if key in found:
            raise SystemExit(f"OpenAI skeptic returned duplicate verdict for key {key!r}")
        if verdict not in {"KILLED", "SURVIVES"}:
            raise SystemExit(f"OpenAI skeptic returned invalid verdict for key {key!r}")
        if not isinstance(why, str) or not why.strip():
            raise SystemExit(f"OpenAI skeptic returned empty why for key {key!r}")
        found[key] = {"key": key, "verdict": verdict, "why": why.strip()}

    missing = [key for key in expected_keys if key not in found]
    extra = [key for key in found if key not in expected]
    if missing or extra:
        raise SystemExit(
            "OpenAI skeptic returned incomplete verdict coverage: "
            f"missing={missing or []} extra={extra or []}"
        )
    return found


def _verdict_prompt(body: str, expected_keys: list[str]) -> str:
    return (
        f"{JUDGE_SYSTEM}\n\n"
        f"Expected keys, in order: {json.dumps(expected_keys)}\n\n"
        f"Claims:\n{body}"
    )


def _print_verdicts(label: str, expected_keys: list[str], verdicts: dict[str, dict[str, str]]) -> None:
    print(f"\n  Skeptic pass ({label}):\n")
    for key in expected_keys:
        row = verdicts[key]
        print(f"    {row['verdict']} - {key} - {row['why']}")
    print()


def _report_rows(expected_keys: list[str], verdicts: dict[str, dict[str, str]]) -> list[dict[str, str]]:
    return [verdicts[key] for key in expected_keys]


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
    expected_keys = _claim_keys(body)
    messages = [{"role": "user", "content": _verdict_prompt(body, expected_keys)}]
    max_tokens = _verdict_max_tokens()
    effort = _claude_effort()
    reservation = budget.preflight("verify:claude-opus-skeptic", "opus",
                                   messages=messages, max_tokens=max_tokens, system=JUDGE_SYSTEM)
    client = get_client()
    try:
        msg = _create_claude_message(
            client,
            max_tokens=max_tokens,
            system=JUDGE_SYSTEM,
            messages=messages,
            **request_kwargs("opus", effort=effort, adaptive_thinking=True),
        )
    except Exception as e:
        budget.mark_failed(reservation, e)
        raise
    actual = budget.commit_usage(reservation, msg.usage)
    text = _message_text(msg)
    if not text:
        kinds = ", ".join(getattr(b, "type", "?") for b in msg.content)
        raise SystemExit(
            f"Claude verifier returned no visible verdict text after {max_tokens} max_tokens "
            f"(content blocks: {kinds or 'none'})."
        )
    verdicts = _parse_openai_verdicts(text, expected_keys)
    _print_verdicts(f"{get('opus').label}, {effort} effort, adaptive thinking", expected_keys, verdicts)
    return {
        "judge": "claude",
        "model": get("opus").id,
        "label": get("opus").label,
        "effort": effort,
        "cost_usd": round(actual, 6),
        "verdicts": _report_rows(expected_keys, verdicts),
    }


def _run_openai(body: str, budget: BudgetLedger) -> None:
    client = get_openai_client()
    if client is None:
        print("\n  OpenAI skeptic skipped: OPENAI_API_KEY is not set.\n")
        return
    expected_keys = _claim_keys(body)
    messages = [{"role": "user", "content": _verdict_prompt(body, expected_keys)}]
    max_tokens = _verdict_max_tokens()
    reservation = budget.preflight("verify:openai-gpt-5.5-xhigh-skeptic", "gpt-top",
                                   messages=messages, max_tokens=max_tokens, system=JUDGE_SYSTEM)
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
    verdicts = _parse_openai_verdicts(result.text, expected_keys)
    _print_verdicts(f"{get('gpt-top').label}, xhigh reasoning", expected_keys, verdicts)
    return {
        "judge": "openai",
        "model": get("gpt-top").id,
        "label": get("gpt-top").label,
        "effort": "xhigh",
        "cost_usd": round(result.cost_usd, 6),
        "verdicts": _report_rows(expected_keys, verdicts),
    }


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
    reports = []
    for judge in [j.strip().lower() for j in args.judges.split(",") if j.strip()]:
        if judge == "claude":
            report = _run_claude(body, budget)
        elif judge == "openai":
            report = _run_openai(body, budget)
        else:
            raise SystemExit(f"unknown judge {judge!r}; expected claude or openai")
        if report:
            reports.append(report)
    if reports:
        path = write_report(reports)
        print(f"  wrote adversarial value report to {path.relative_to(pathlib.Path.cwd())}\n")


if __name__ == "__main__":
    main()
