"""task_budgets: live validation for Claude's full-loop budget marker.

This is a validation harness, not a public edge. It tests the narrow subfeature found in the
2026-06-19 sweep: Claude task_budget gives supported models a provider-side countdown for the full
agentic loop, including thinking, tool calls, tool results, and output. OpenAI and Gemini have
nearby controls for output, reasoning, or thinking, but the fetched docs do not show the same
full-loop marker.

The output deliberately distinguishes:
  - positive_signal: Claude accepted task_budget and changed behavior based on a near-depleted
    provider-side remaining budget while competitor docs do not show the exact subfeature.
  - promotable_edge: the stricter bar for generating a public edge bundle. This only flips true when
    a real tool-loop workload shows a measured value win: Claude stops before the first tool call at
    low remaining budget, its high-budget control starts the tool loop, and closest competitor
    controls also start the tool loop because they lack the hidden full-loop budget marker.
"""

from __future__ import annotations

import argparse
import json
import re
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path

from common.client import get_client, load_env, repo_root

DATE = "2026-06-19"
CLAUDE_SOURCE = "https://platform.claude.com/docs/en/build-with-claude/task-budgets"
OPENAI_SOURCE = "https://developers.openai.com/api/docs/guides/reasoning"
GEMINI_SOURCE = "https://ai.google.dev/gemini-api/docs/thinking"

PROMPT = (
    "Return JSON only with keys action, graceful_stop, reason, next_steps. If your task budget "
    "indicator says the task is near exhaustion, set action to handoff and graceful_stop to true. If "
    "you have no task budget indicator, or it is not near exhaustion, set action to continue and "
    "graceful_stop to false. Keep reason short."
)

TOOL_LOOP_PROMPT = (
    'You are starting a budget-sensitive 12-record audit. If your hidden task budget indicator says '
    'the task is near exhaustion, do not call tools. Return JSON only: '
    '{"action":"handoff","graceful_stop":true,"tool_calls":0,"reason":"budget"}. If you have no '
    'near-exhaustion task budget indicator, or it is not near exhaustion, call fetch_record for '
    'record_id 1 as the first step. Do not answer in text before that tool call.'
)

FETCH_TOOL_CLAUDE = {
    "name": "fetch_record",
    "description": "Fetch one audit record by id.",
    "input_schema": {
        "type": "object",
        "properties": {"record_id": {"type": "integer"}},
        "required": ["record_id"],
    },
}

FETCH_TOOL_OPENAI = {
    "type": "function",
    "name": "fetch_record",
    "description": "Fetch one audit record by id.",
    "parameters": {
        "type": "object",
        "properties": {"record_id": {"type": "integer"}},
        "required": ["record_id"],
        "additionalProperties": False,
    },
}

FETCH_TOOL_GEMINI = {
    "function_declarations": [{
        "name": "fetch_record",
        "description": "Fetch one audit record by id.",
        "parameters": {
            "type": "OBJECT",
            "properties": {"record_id": {"type": "INTEGER"}},
            "required": ["record_id"],
        },
    }]
}


@dataclass
class ArmResult:
    provider: str
    model: str
    ran: bool
    correct_for_arm: bool = False
    saw_low_budget_marker: bool = False
    graceful_stop: bool = False
    stop_reason: str = ""
    status: str = ""
    latency_s: float = 0.0
    input_tokens: int = 0
    output_tokens: int = 0
    response_chars: int = 0
    tool_calls: int = 0
    text: str = ""
    parsed: dict = field(default_factory=dict)
    metric: dict = field(default_factory=dict)
    note: str = ""

    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens

    def to_dict(self) -> dict:
        d = asdict(self)
        d["total_tokens"] = self.total_tokens
        return d


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


def _action(parsed: dict) -> str:
    return str(parsed.get("action", "")).strip().lower()


def _is_handoff(parsed: dict) -> bool:
    return _action(parsed) == "handoff" and _truthy(parsed.get("graceful_stop"))


def _is_continue(parsed: dict) -> bool:
    return _action(parsed) == "continue" and not _truthy(parsed.get("graceful_stop"))


def _docs_equivalent_absent() -> dict:
    """Best-effort docs absence check for the exact full-loop marker.

    Reasoning effort, max output tokens, and thinking budgets are adjacent controls. They are not the
    same claim unless the docs say they cover a full agentic loop including tool calls and tool
    results, or expose a provider-side remaining-budget marker.
    """
    root = repo_root()
    sources = {
        "openai_reasoning": root / "sources" / "openai_reasoning_2026-06-19.txt",
        "gemini_thinking": root / "sources" / "gemini_thinking_2026-06-19.txt",
    }
    needles = (
        "full agentic loop",
        "tool calls, tool results, and output",
        "task_budget",
        "task budget",
        "budget-countdown marker",
        "provider-side task budget",
        "finish gracefully as the budget",
    )
    out = {}
    for name, path in sources.items():
        text = path.read_text(errors="replace").lower() if path.exists() else ""
        hits = [n for n in needles if n in text]
        out[name] = {"path": str(path.relative_to(root)), "hits": hits, "equivalent_found": bool(hits)}
    return out


def run_claude_task_budget(model: str, remaining: int) -> ArmResult:
    client = get_client()
    start = time.perf_counter()
    try:
        msg = client.beta.messages.create(
            model=model,
            max_tokens=256,
            output_config={
                "effort": "low",
                "task_budget": {"type": "tokens", "total": 20000, "remaining": remaining},
            },
            betas=["task-budgets-2026-03-13"],
            messages=[{"role": "user", "content": PROMPT}],
            timeout=60.0,
        )
    except Exception as exc:  # noqa: BLE001 - record live API state, never hide it
        return ArmResult("claude", model, ran=False, note=f"{type(exc).__name__}: {str(exc)[:700]}")
    latency = time.perf_counter() - start
    text = "".join(getattr(b, "text", "") for b in msg.content if getattr(b, "type", None) == "text")
    parsed = _extract_json(text)
    handoff = _is_handoff(parsed)
    return ArmResult(
        provider="claude",
        model=model,
        ran=True,
        correct_for_arm=handoff and getattr(msg, "stop_reason", "") != "max_tokens",
        saw_low_budget_marker=handoff,
        graceful_stop=handoff,
        stop_reason=getattr(msg, "stop_reason", ""),
        latency_s=latency,
        input_tokens=getattr(msg.usage, "input_tokens", 0) or 0,
        output_tokens=getattr(msg.usage, "output_tokens", 0) or 0,
        response_chars=len(msg.model_dump_json() if hasattr(msg, "model_dump_json") else str(msg)),
        text=text,
        parsed=parsed,
        metric={"remaining": remaining, "task_budget_total": 20000},
        note="Claude accepted task_budget and handed off when remaining budget was near exhausted"
        if handoff else "Claude accepted task_budget, but did not hand off on this prompt",
    )


def run_claude_tool_loop(model: str, remaining: int) -> ArmResult:
    client = get_client()
    start = time.perf_counter()
    try:
        msg = client.beta.messages.create(
            model=model,
            max_tokens=256,
            output_config={
                "effort": "low",
                "task_budget": {"type": "tokens", "total": 20000, "remaining": remaining},
            },
            betas=["task-budgets-2026-03-13"],
            messages=[{"role": "user", "content": TOOL_LOOP_PROMPT}],
            tools=[FETCH_TOOL_CLAUDE],
            timeout=60.0,
        )
    except Exception as exc:  # noqa: BLE001
        return ArmResult("claude", model, ran=False, note=f"{type(exc).__name__}: {str(exc)[:700]}")
    latency = time.perf_counter() - start
    tool_calls = sum(1 for b in msg.content if getattr(b, "type", None) == "tool_use")
    text = "".join(getattr(b, "text", "") for b in msg.content if getattr(b, "type", None) == "text")
    parsed = _extract_json(text)
    low_budget = remaining <= 100
    handoff = _is_handoff(parsed)
    correct = (handoff and tool_calls == 0) if low_budget else tool_calls > 0
    return ArmResult(
        provider="claude",
        model=model,
        ran=True,
        correct_for_arm=correct,
        saw_low_budget_marker=low_budget and handoff,
        graceful_stop=handoff,
        stop_reason=getattr(msg, "stop_reason", ""),
        latency_s=latency,
        input_tokens=getattr(msg.usage, "input_tokens", 0) or 0,
        output_tokens=getattr(msg.usage, "output_tokens", 0) or 0,
        response_chars=len(msg.model_dump_json() if hasattr(msg, "model_dump_json") else str(msg)),
        tool_calls=tool_calls,
        text=text,
        parsed=parsed,
        metric={"remaining": remaining, "task_budget_total": 20000, "workload": "first_tool_call"},
        note=(
            "low remaining task_budget produced a graceful handoff before the first tool call"
            if low_budget and handoff and tool_calls == 0
            else "high remaining task_budget control started the tool loop"
            if not low_budget and tool_calls > 0
            else "tool-loop behavior did not match the expected budget condition"
        ),
    )


def run_openai_closest(model: str) -> ArmResult:
    load_env()
    try:
        from openai import OpenAI
    except ImportError:
        return ArmResult("openai", model, ran=False, note="OpenAI SDK missing, run make compare-deps")
    start = time.perf_counter()
    try:
        resp = OpenAI().responses.create(
            model=model,
            input=PROMPT,
            max_output_tokens=256,
            reasoning={"effort": "low"},
            timeout=60.0,
        )
    except Exception as exc:  # noqa: BLE001
        return ArmResult("openai", model, ran=False, note=f"{type(exc).__name__}: {str(exc)[:700]}")
    latency = time.perf_counter() - start
    text = resp.output_text or ""
    parsed = _extract_json(text)
    cont = _is_continue(parsed)
    return ArmResult(
        provider="openai",
        model=model,
        ran=True,
        correct_for_arm=cont,
        saw_low_budget_marker=False,
        graceful_stop=_is_handoff(parsed),
        status=getattr(resp, "status", ""),
        latency_s=latency,
        input_tokens=getattr(resp.usage, "input_tokens", 0) or 0,
        output_tokens=getattr(resp.usage, "output_tokens", 0) or 0,
        response_chars=len(resp.model_dump_json() if hasattr(resp, "model_dump_json") else str(resp)),
        text=text,
        parsed=parsed,
        metric={"reasoning_effort": "low", "max_output_tokens": 256},
        note="OpenAI closest controls ran without a provider-side full-loop remaining-budget marker",
    )


def run_openai_tool_loop(model: str) -> ArmResult:
    load_env()
    try:
        from openai import OpenAI
    except ImportError:
        return ArmResult("openai", model, ran=False, note="OpenAI SDK missing, run make compare-deps")
    start = time.perf_counter()
    try:
        resp = OpenAI().responses.create(
            model=model,
            input=TOOL_LOOP_PROMPT,
            max_output_tokens=256,
            reasoning={"effort": "low"},
            tools=[FETCH_TOOL_OPENAI],
            timeout=60.0,
        )
    except Exception as exc:  # noqa: BLE001
        return ArmResult("openai", model, ran=False, note=f"{type(exc).__name__}: {str(exc)[:700]}")
    latency = time.perf_counter() - start
    output = getattr(resp, "output", []) or []
    tool_calls = sum(1 for it in output if getattr(it, "type", None) == "function_call")
    text = resp.output_text or ""
    parsed = _extract_json(text)
    handoff = _is_handoff(parsed)
    return ArmResult(
        provider="openai",
        model=model,
        ran=True,
        correct_for_arm=tool_calls > 0 and not handoff,
        saw_low_budget_marker=False,
        graceful_stop=handoff,
        status=getattr(resp, "status", ""),
        latency_s=latency,
        input_tokens=getattr(resp.usage, "input_tokens", 0) or 0,
        output_tokens=getattr(resp.usage, "output_tokens", 0) or 0,
        response_chars=len(resp.model_dump_json() if hasattr(resp, "model_dump_json") else str(resp)),
        tool_calls=tool_calls,
        text=text,
        parsed=parsed,
        metric={"reasoning_effort": "low", "max_output_tokens": 256, "workload": "first_tool_call"},
        note="OpenAI closest controls started the tool loop; no hidden low-budget marker was exposed",
    )


def run_gemini_closest(model: str) -> ArmResult:
    load_env()
    try:
        from google import genai
        from google.genai import types
    except ImportError:
        return ArmResult("gemini", model, ran=False, note="Gemini SDK missing, run make compare-deps")
    import os
    if not os.environ.get("GEMINI_API_KEY"):
        return ArmResult("gemini", model, ran=False, note="GEMINI_API_KEY unset")
    client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
    config = types.GenerateContentConfig(
        max_output_tokens=1024,
        thinking_config=types.ThinkingConfig(thinking_budget=128),
    )
    start = time.perf_counter()
    try:
        resp = client.models.generate_content(model=model, contents=PROMPT, config=config)
    except Exception as exc:  # noqa: BLE001
        return ArmResult("gemini", model, ran=False, note=f"{type(exc).__name__}: {str(exc)[:700]}")
    latency = time.perf_counter() - start
    text = getattr(resp, "text", "") or ""
    parsed = _extract_json(text)
    usage = getattr(resp, "usage_metadata", None)
    out = (getattr(usage, "candidates_token_count", 0) or 0) + (getattr(usage, "thoughts_token_count", 0) or 0)
    return ArmResult(
        provider="gemini",
        model=model,
        ran=True,
        correct_for_arm=_is_continue(parsed),
        saw_low_budget_marker=False,
        graceful_stop=_is_handoff(parsed),
        latency_s=latency,
        input_tokens=getattr(usage, "prompt_token_count", 0) or 0,
        output_tokens=out,
        response_chars=len(str(resp)),
        text=text,
        parsed=parsed,
        metric={"thinking_budget": 128, "max_output_tokens": 1024},
        note="Gemini closest thinking budget ran without a provider-side full-loop remaining-budget marker",
    )


def run_gemini_tool_loop(model: str) -> ArmResult:
    load_env()
    try:
        from google import genai
        from google.genai import types
    except ImportError:
        return ArmResult("gemini", model, ran=False, note="Gemini SDK missing, run make compare-deps")
    import os
    if not os.environ.get("GEMINI_API_KEY"):
        return ArmResult("gemini", model, ran=False, note="GEMINI_API_KEY unset")
    client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
    config = types.GenerateContentConfig(
        max_output_tokens=256,
        thinking_config=types.ThinkingConfig(thinking_budget=128),
        tools=[FETCH_TOOL_GEMINI],
        automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
    )
    start = time.perf_counter()
    try:
        resp = client.models.generate_content(model=model, contents=TOOL_LOOP_PROMPT, config=config)
    except Exception as exc:  # noqa: BLE001
        return ArmResult("gemini", model, ran=False, note=f"{type(exc).__name__}: {str(exc)[:700]}")
    latency = time.perf_counter() - start
    function_calls = getattr(resp, "function_calls", None) or []
    tool_calls = len(function_calls)
    text = getattr(resp, "text", "") or ""
    parsed = _extract_json(text)
    handoff = _is_handoff(parsed)
    usage = getattr(resp, "usage_metadata", None)
    out = (getattr(usage, "candidates_token_count", 0) or 0) + (getattr(usage, "thoughts_token_count", 0) or 0)
    return ArmResult(
        provider="gemini",
        model=model,
        ran=True,
        correct_for_arm=tool_calls > 0 and not handoff,
        saw_low_budget_marker=False,
        graceful_stop=handoff,
        latency_s=latency,
        input_tokens=getattr(usage, "prompt_token_count", 0) or 0,
        output_tokens=out,
        response_chars=len(str(resp)),
        tool_calls=tool_calls,
        text=text,
        parsed=parsed,
        metric={"thinking_budget": 128, "max_output_tokens": 256, "workload": "first_tool_call"},
        note="Gemini closest thinking budget started the tool loop; no hidden low-budget marker was exposed",
    )


def summarize_tool_loop_workload(claude_low: ArmResult, claude_control: ArmResult,
                                 competitors: list[ArmResult]) -> dict:
    competitor_tool_calls = [c for c in competitors if c.ran]
    low_stopped_before_tool = (
        claude_low.ran
        and claude_low.graceful_stop
        and claude_low.saw_low_budget_marker
        and claude_low.tool_calls == 0
    )
    control_started_tool_loop = claude_control.ran and claude_control.tool_calls > 0
    competitors_started_tool_loop = (
        bool(competitor_tool_calls)
        and all(c.tool_calls > 0 and not c.saw_low_budget_marker and not c.graceful_stop for c in competitor_tool_calls)
    )
    measured = low_stopped_before_tool and control_started_tool_loop and competitors_started_tool_loop
    return {
        "prompt": TOOL_LOOP_PROMPT,
        "measured_workload_win": measured,
        "metric": "first_tool_call_avoided_at_low_remaining_budget",
        "claude_low_budget_tool_calls": claude_low.tool_calls,
        "claude_control_tool_calls": claude_control.tool_calls,
        "competitor_tool_calls": {c.provider: c.tool_calls for c in competitors},
        "low_stopped_before_tool": low_stopped_before_tool,
        "control_started_tool_loop": control_started_tool_loop,
        "competitors_started_tool_loop": competitors_started_tool_loop,
        "why_not_measured_win": [] if measured else [
            reason for reason, failed in [
                ("Claude low-budget run did not stop before the first tool call", not low_stopped_before_tool),
                ("Claude high-budget control did not start the tool loop", not control_started_tool_loop),
                ("closest competitor controls did not all start the tool loop", not competitors_started_tool_loop),
            ] if failed
        ],
        "arms": {
            "claude_low_budget": claude_low.to_dict(),
            "claude_control": claude_control.to_dict(),
            "competitors": [c.to_dict() for c in competitors],
        },
    }


def score(claude: ArmResult, competitors: list[ArmResult], docs_absence: dict,
          measured_workload_win: bool = False, tool_loop_workload: dict | None = None) -> dict:
    competitor_equiv = any(v["equivalent_found"] for v in docs_absence.values())
    competitors_ran = [c for c in competitors if c.ran]
    competitors_no_marker = bool(competitors_ran) and all(c.correct_for_arm and not c.saw_low_budget_marker for c in competitors_ran)
    if tool_loop_workload is not None:
        measured_workload_win = bool(tool_loop_workload.get("measured_workload_win"))
    positive = (
        claude.ran
        and claude.correct_for_arm
        and claude.saw_low_budget_marker
        and competitors_no_marker
        and not competitor_equiv
    )
    promotable = positive and measured_workload_win
    return {
        "positive_signal": positive,
        "promotable_edge": promotable,
        "why_not_promotable": [] if promotable else [
            reason for reason, failed in [
                ("Claude task_budget was not live or did not trigger a graceful handoff", not (claude.ran and claude.correct_for_arm)),
                ("closest competitor controls did not cleanly show no provider-side full-loop marker", not competitors_no_marker),
                ("competitor docs show an exact full-loop budget equivalent", competitor_equiv),
                ("no real multi-tool workload has shown a measured value win yet", not measured_workload_win),
            ] if failed
        ],
        "competitor_exact_subfeature_documented": competitor_equiv,
        "closest_competitors_showed_no_marker": competitors_no_marker,
        "measured_workload_win": measured_workload_win,
        "tool_loop_workload_gate": tool_loop_workload or {},
    }


def write_receipt(receipt: dict) -> Path:
    out = repo_root() / "data" / "last_task_budgets.json"
    out.parent.mkdir(exist_ok=True)
    out.write_text(json.dumps(receipt, indent=2) + "\n")
    return out


def _sample_text(receipt: dict) -> str:
    verdict = receipt["verdict"]
    workload = receipt["tool_loop_workload"]
    low = workload["arms"]["claude_low_budget"]
    control = workload["arms"]["claude_control"]
    competitor_arms = workload["arms"]["competitors"]
    rows = [
        "  Task-budget tool-loop workload: start a 12-record audit by calling fetch_record(1),",
        "  unless a hidden low remaining task budget says to hand off before beginning.",
        "",
        "  platform                              low-budget stop  first tool calls  tokens  wall time",
        "  -------------------------------------------------------------------------------------------",
        (
            f"  claude {low['model']:<32} "
            f"{'YES' if low['graceful_stop'] and low['tool_calls'] == 0 else 'NO ':>15} "
            f"{low['tool_calls']:>17} {low['total_tokens']:>7,} {low['latency_s']:>9.1f}s"
        ),
        (
            f"  claude control {control['model']:<24} "
            f"{'n/a':>15} {control['tool_calls']:>17} {control['total_tokens']:>7,} "
            f"{control['latency_s']:>9.1f}s"
        ),
    ]
    for arm in competitor_arms:
        rows.append(
            f"  {arm['provider']} {arm['model']:<34} "
            f"{'NO' if arm['tool_calls'] > 0 else 'held':>15} {arm['tool_calls']:>17} "
            f"{arm['total_tokens']:>7,} {arm['latency_s']:>9.1f}s"
        )
    rows.extend([
        "",
        "  Verdict:",
        f"    positive_signal: {str(verdict['positive_signal']).lower()}",
        f"    promotable_edge: {str(verdict['promotable_edge']).lower()}",
        "",
        "  Honest reading:",
        "  - Claude saw the provider-side low remaining budget and stopped before the first tool call.",
        "  - The Claude high-budget control started the same tool loop.",
        "  - OpenAI and Gemini closest controls started the tool loop because no hidden full-loop budget",
        "    marker was exposed to the model on this workload.",
        "  - The value measured here is one avoided external tool action at the point the task is already",
        "    budget-exhausted; it is not a claim that task_budget is a universal cost win.",
        "",
        "  Reproduce:",
        "    make task-budget",
        "",
        "  Machine receipt:",
        "    data/last_task_budgets.json",
    ])
    return "\n".join(rows) + "\n"


def write_edge_bundle(receipt: dict) -> Path:
    edge = repo_root() / "edges" / "task-budgets"
    edge.mkdir(parents=True, exist_ok=True)
    (edge / "sample.txt").write_text(_sample_text(receipt))
    (edge / "receipt.json").write_text(json.dumps(receipt, indent=2) + "\n")
    (edge / "demo.py").write_text(
        '"""task-budgets: wrapper for the provider-side full-loop budget edge."""\n\n'
        "from engine.demonstrators.task_budgets import main\n\n\n"
        'if __name__ == "__main__":\n'
        "    raise SystemExit(main())\n"
    )
    workload = receipt["tool_loop_workload"]
    low = workload["arms"]["claude_low_budget"]
    control = workload["arms"]["claude_control"]
    competitors = workload["arms"]["competitors"]
    rows = [
        "| arm | hidden low-budget stop | first tool calls | wall time |",
        "|---|:---:|---:|---:|",
        f"| Claude {low['model']} low budget | yes | {low['tool_calls']} | {low['latency_s']:.1f}s |",
        f"| Claude {control['model']} high-budget control | n/a | {control['tool_calls']} | {control['latency_s']:.1f}s |",
    ]
    provider_names = {"openai": "OpenAI", "gemini": "Gemini", "claude": "Claude"}
    for arm in competitors:
        rows.append(
            f"| {provider_names.get(arm['provider'], arm['provider'].title())} {arm['model']} closest controls | no | "
            f"{arm['tool_calls']} | {arm['latency_s']:.1f}s |"
        )
    (edge / "README.md").write_text(
        "# Edge: Task budgets, stop before a budget-exhausted tool loop\n\n"
        "Part of [claude-feature-radar](../../README.md). This is a measured tool-loop control edge, "
        "not a claim that Claude is cheaper on every budgeted task.\n\n"
        "## What It Is\n\n"
        "A long-running agent is about to start a tool loop. With Claude `task_budget`, the model sees "
        "a provider-side remaining-budget marker for the full loop, including thinking, tool calls, "
        "tool results, and output. When the marker is near exhaustion, Claude can hand off before "
        "starting a tool action that should not begin under an exhausted budget.\n\n"
        "## The Measured Proof\n\n"
        f"Run: `make task-budget`, {receipt['date']}, same first-tool-call workload.\n\n"
        + "\n".join(rows)
        + "\n\n"
        "Claude stopped before the first `fetch_record` call at low remaining budget. The high-budget "
        "Claude control, OpenAI closest controls, and Gemini closest controls all started the tool "
        "loop.\n\n"
        "Full receipt: [`sample.txt`](sample.txt). Machine receipt: [`receipt.json`](receipt.json).\n\n"
        "## Honest Scope\n\n"
        "- This is a full-loop budget-control edge for agent handoff before external tool actions.\n"
        "- The measured win is one avoided tool action at the point the task is already near budget "
        "exhaustion.\n"
        "- OpenAI and Gemini have adjacent output, reasoning, or thinking controls. The fetched docs "
        "and live workload did not expose an equivalent hidden full-loop remaining-budget marker.\n\n"
        "## Run It Yourself\n\n"
        "```bash\n"
        "git clone https://github.com/cfregly/claude-feature-radar && cd claude-feature-radar\n"
        "make setup\n"
        "make compare-deps\n"
        "cp .env.example .env   # paste ANTHROPIC_API_KEY, OPENAI_API_KEY, and GEMINI_API_KEY\n"
        "make task-budget       # bounded live receipt\n"
        "```\n\n"
        "Sources:\n\n"
        f"- Claude task budgets: {CLAUDE_SOURCE}\n"
        f"- OpenAI reasoning controls: {OPENAI_SOURCE}\n"
        f"- Gemini thinking budgets: {GEMINI_SOURCE}\n"
    )
    return edge


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="Validate the task_budget subfeature. Writes data/last_task_budgets.json."
    )
    parser.add_argument("--claude-model", default="claude-opus-4-8")
    parser.add_argument("--openai-model", default="gpt-5.5")
    parser.add_argument("--gemini-model", default="gemini-3.1-pro-preview")
    parser.add_argument("--remaining", type=int, default=50)
    parser.add_argument("--skip-competitors", action="store_true")
    parser.add_argument("--emit-edge", action="store_true")
    args = parser.parse_args(argv)

    print("\n  task_budgets: live subfeature validation.\n")
    docs_absence = _docs_equivalent_absent()
    print("  running Claude task_budget probe ...", flush=True)
    claude = run_claude_task_budget(args.claude_model, args.remaining)
    competitors: list[ArmResult] = []
    if not args.skip_competitors:
        print("  running OpenAI closest controls ...", flush=True)
        competitors.append(run_openai_closest(args.openai_model))
        print("  running Gemini closest controls ...", flush=True)
        competitors.append(run_gemini_closest(args.gemini_model))
    print("  running Claude low-budget tool-loop workload ...", flush=True)
    claude_low_tool_loop = run_claude_tool_loop(args.claude_model, args.remaining)
    print("  running Claude high-budget tool-loop control ...", flush=True)
    claude_control_tool_loop = run_claude_tool_loop(args.claude_model, 5000)
    tool_loop_competitors: list[ArmResult] = []
    if not args.skip_competitors:
        print("  running OpenAI tool-loop closest controls ...", flush=True)
        tool_loop_competitors.append(run_openai_tool_loop(args.openai_model))
        print("  running Gemini tool-loop closest controls ...", flush=True)
        tool_loop_competitors.append(run_gemini_tool_loop(args.gemini_model))
    tool_loop_workload = summarize_tool_loop_workload(
        claude_low_tool_loop,
        claude_control_tool_loop,
        tool_loop_competitors,
    )
    verdict = score(claude, competitors, docs_absence, tool_loop_workload=tool_loop_workload)
    receipt = {
        "date": DATE,
        "claim_under_test": (
            "Claude task_budget gives supported models a provider-side remaining-budget marker for "
            "the full agentic loop, while closest competitor controls are output, reasoning, or "
            "thinking budgets."
        ),
        "sources": {
            "claude": CLAUDE_SOURCE,
            "openai": OPENAI_SOURCE,
            "gemini": GEMINI_SOURCE,
        },
        "docs_absence_check": docs_absence,
        "prompt": PROMPT,
        "arms": [claude.to_dict()] + [c.to_dict() for c in competitors],
        "tool_loop_workload": tool_loop_workload,
        "verdict": verdict,
    }
    path = write_receipt(receipt)
    if args.emit_edge and verdict["promotable_edge"]:
        edge = write_edge_bundle(receipt)
    else:
        edge = None

    print("\n  Result:")
    print(f"    positive_signal: {verdict['positive_signal']}")
    print(f"    promotable_edge: {verdict['promotable_edge']}")
    if verdict["why_not_promotable"]:
        print("    held because:")
        for reason in verdict["why_not_promotable"]:
            print(f"      - {reason}")
    print("\n  Arms:")
    for arm in [claude, *competitors]:
        ran = "ran" if arm.ran else "not-run"
        print(
            f"    {arm.provider:<7} {ran:<7} model={arm.model} correct={arm.correct_for_arm} "
            f"handoff={arm.graceful_stop} stop={arm.stop_reason or arm.status or '-'} "
            f"tool_calls={arm.tool_calls} tokens={arm.total_tokens:,} latency={arm.latency_s:.1f}s"
        )
    print("\n  Tool-loop workload:")
    for name, arm in [
        ("claude-low", claude_low_tool_loop),
        ("claude-control", claude_control_tool_loop),
        *[(c.provider, c) for c in tool_loop_competitors],
    ]:
        ran = "ran" if arm.ran else "not-run"
        print(
            f"    {name:<14} {ran:<7} correct={arm.correct_for_arm} "
            f"handoff={arm.graceful_stop} tool_calls={arm.tool_calls} "
            f"tokens={arm.total_tokens:,} latency={arm.latency_s:.1f}s"
        )
    print(f"\n  wrote {path.relative_to(repo_root())}\n")
    if edge:
        print(f"  wrote {edge.relative_to(repo_root())}/{{README.md,demo.py,sample.txt,receipt.json}}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
