"""Managed Agents operations comparison.

This demonstrator owns the cross-stack promotion check for Managed Agents. The
retention_resume demonstrator keeps the separate durable-resume parity claim.
This file measures a small operations workload across:

  - Claude Managed Agents
  - a self-managed Claude Messages tool loop
  - OpenAI Agents SDK
  - Google ADK with Gemini

The default verdict is conservative. A correct Managed Agents run against
correct competitors is parity, not a promoted win. The result becomes
claude-ahead only when the same workload shows a measured operations advantage
that a founder would value. Missing keys, missing SDKs, beta access failures,
or model access failures are held, not counted as losses.
"""

from __future__ import annotations

import argparse
import asyncio
import inspect
import json
import os
import pathlib
import re
import sys
import time
import uuid
from types import SimpleNamespace
from typing import Any

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))

from common.models import get as get_model
from common.pricing import cost_from_buckets, cost_usd
from engine.demonstrators.base import Arm, BaseDemonstrator, CostEstimate, Verdict
from engine.demonstrators.registry import register
from engine.demonstrators.shared import platform
from engine.operations_scorecard import build_operations_scorecard

ROOT = pathlib.Path(__file__).resolve().parents[2]
DATA = ROOT / "data"
LAST_JSON = DATA / "last_managed_agents_operations.json"
LAST_MD = DATA / "last_managed_agents_operations.md"

COMPARE_PREFIX = "radar-managed-agents-ops"
MANAGED_MODEL = os.environ.get("MANAGED_AGENT_MODEL", "claude-haiku-4-5")
CLAUDE_SELF_MODEL = os.environ.get("CLAUDE_SELF_MANAGED_MODEL", "claude-haiku-4-5-20251001")
OPENAI_MODEL = os.environ.get("OPENAI_AGENT_MODEL", "gpt-5.5")
GEMINI_MODEL = os.environ.get("GEMINI_AGENT_MODEL", "gemini-3.5-flash")
TEARDOWN_TRIALS = int(os.environ.get("MANAGED_AGENT_TEARDOWN_TRIALS", "3"))
RESUME_PROBE_DEFAULT = os.environ.get("MANAGED_AGENT_RESUME_PROBE", "1").lower() not in {"0", "false", "no"}

STACK_MANAGED = "Claude Managed Agents"
STACK_SELF_MANAGED = "self-managed Messages tool loop"
STACK_OPENAI = "OpenAI Agents SDK"
STACK_GEMINI = "Google ADK with Gemini"

COMPONENT_INVENTORY: dict[str, dict[str, list[str]]] = {
    STACK_MANAGED: {
        "app_owned": [
            "agent configuration",
            "environment creation",
            "session creation",
            "event stream drain",
            "resource teardown",
        ],
        "provider_owned": [
            "agent turn loop",
            "session event log",
            "sandbox filesystem",
            "tool execution runtime",
            "resume reattach surface",
        ],
    },
    STACK_SELF_MANAGED: {
        "app_owned": [
            "agent turn loop",
            "message transcript state",
            "tool schema wiring",
            "tool dispatch",
            "tool result envelope",
            "retry policy",
            "resume store",
            "artifact storage",
        ],
        "provider_owned": [],
    },
    STACK_OPENAI: {
        "app_owned": [
            "agent declaration",
            "function tool wrappers",
            "result extraction",
        ],
        "provider_owned": [
            "agent turn loop",
            "tool dispatch",
            "session state when configured",
        ],
    },
    STACK_GEMINI: {
        "app_owned": [
            "agent declaration",
            "function tool wrappers",
            "session service",
            "event iteration",
            "result extraction",
        ],
        "provider_owned": [
            "agent turn loop",
            "tool dispatch",
        ],
    },
}

MANAGED_COMPONENTS_AVOIDED_VS_SELF_MANAGED = [
    {
        "component": "agent turn loop",
        "self_managed": "app-owned Messages loop",
        "managed_agents": "provider-owned hosted loop",
    },
    {
        "component": "message transcript state",
        "self_managed": "app-owned message array or external store",
        "managed_agents": "provider-owned session event log",
    },
    {
        "component": "sandbox filesystem",
        "self_managed": "app-owned artifact or workspace store",
        "managed_agents": "provider-owned session filesystem",
    },
    {
        "component": "tool execution runtime",
        "self_managed": "app-owned dispatcher and execution layer",
        "managed_agents": "provider-owned agent toolset runtime",
    },
    {
        "component": "resume reattach surface",
        "self_managed": "app-owned resume store and replay logic",
        "managed_agents": "provider-owned session reattach surface",
    },
]

EVIDENCE: dict[str, list[dict[str, Any]]] = {
    "logs": [
        {
            "id": "log-auth-1",
            "service": "auth",
            "level": "error",
            "message": "cache ttl jumped to 3600s after deploy dpl-17",
        },
        {
            "id": "log-api-2",
            "service": "api",
            "level": "warn",
            "message": "northwind and acme login retries above baseline",
        },
        {
            "id": "log-web-3",
            "service": "web",
            "level": "info",
            "message": "static asset deploy completed cleanly",
        },
    ],
    "tickets": [
        {"id": "ticket-884", "account": "acme", "symptom": "login loop after password reset"},
        {"id": "ticket-885", "account": "northwind", "symptom": "session cookie rejected after auth refresh"},
    ],
    "deploys": [
        {"id": "dpl-16", "service": "web", "change": "css bundle"},
        {"id": "dpl-17", "service": "auth", "change": "increase token cache ttl"},
    ],
}

EXPECTED_REPORT = {
    "incident_id": "inc-042",
    "severity": "sev2",
    "root_cause": "auth cache ttl regression",
    "action": "rollback dpl-17 and invalidate auth cache",
    "affected_accounts": ["acme", "northwind"],
    "evidence_ids": ["log-auth-1", "log-api-2", "ticket-884", "ticket-885", "dpl-17"],
}

PROMPT = (
    "You are running an ops triage. Use the available tools to inspect logs, tickets, and deploys. "
    "Then emit one JSON report with keys incident_id, severity, root_cause, action, "
    "affected_accounts, and evidence_ids. Do not invent evidence. The expected incident id is inc-042."
)


def _load_env() -> None:
    """Load keys from a repo-local .env without adding python-dotenv to the core dependency set."""
    env = ROOT / ".env"
    if not env.exists():
        return
    for line in env.read_text().splitlines():
        s = line.strip()
        if not s or s.startswith("#") or "=" not in s:
            continue
        key, value = s.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def _pricing_key(model: str, provider: str) -> str:
    candidates = [model]
    lowered = model.lower()
    if provider == "anthropic" and "haiku" in lowered:
        candidates.append("haiku")
    if provider == "anthropic" and "sonnet" in lowered:
        candidates.append("sonnet")
    if provider == "anthropic" and "opus" in lowered:
        candidates.append("opus")
    if provider == "openai" and "5.5" in lowered:
        candidates.append("gpt-top")
    if provider == "openai" and "mini" in lowered:
        candidates.append("gpt-mini")
    if provider == "openai" and "nano" in lowered:
        candidates.append("gpt-nano")
    if provider == "google" and "flash-lite" in lowered:
        candidates.append("gem-lite")
    if provider == "google" and "flash" in lowered:
        candidates.append("gem-flash")
    if provider == "google" and "pro" in lowered:
        candidates.append("gem-pro")
    for candidate in candidates:
        try:
            get_model(candidate)
            return candidate
        except KeyError:
            continue
    return model


def _namespace(value: Any) -> Any:
    if isinstance(value, dict):
        return SimpleNamespace(**{k: _namespace(v) for k, v in value.items()})
    if isinstance(value, list):
        return [_namespace(v) for v in value]
    return value


def _public_data(obj: Any, *, depth: int = 0) -> Any:
    if obj is None or isinstance(obj, str | int | float | bool):
        return obj
    if depth > 5:
        return str(type(obj).__name__)
    if isinstance(obj, dict):
        return {str(k): _public_data(v, depth=depth + 1) for k, v in obj.items()}
    if isinstance(obj, list | tuple):
        return [_public_data(v, depth=depth + 1) for v in obj[:50]]
    if hasattr(obj, "to_dict"):
        try:
            return _public_data(obj.to_dict(), depth=depth + 1)
        except Exception:  # noqa: BLE001
            pass
    if hasattr(obj, "model_dump"):
        try:
            return _public_data(obj.model_dump(), depth=depth + 1)
        except Exception:  # noqa: BLE001
            pass
    if hasattr(obj, "__dict__"):
        data = {k: v for k, v in vars(obj).items() if not k.startswith("_")}
        return _public_data(data, depth=depth + 1)
    return str(obj)


def _has_token_fields(data: dict[str, Any]) -> bool:
    token_keys = {
        "input_tokens",
        "output_tokens",
        "cache_read_input_tokens",
        "cache_creation_input_tokens",
        "prompt_token_count",
        "candidates_token_count",
        "thoughts_token_count",
        "total_token_count",
    }
    return any(k in data for k in token_keys)


def _collect_usage_dicts(data: Any, out: list[dict[str, Any]]) -> None:
    if isinstance(data, dict):
        if _has_token_fields(data):
            out.append(data)
        for key, value in data.items():
            if key in {"usage", "usage_metadata", "cumulative_usage", "session_usage"}:
                if isinstance(value, dict) and _has_token_fields(value):
                    out.append(value)
                else:
                    _collect_usage_dicts(value, out)
            elif isinstance(value, dict | list):
                _collect_usage_dicts(value, out)
    elif isinstance(data, list):
        for item in data:
            _collect_usage_dicts(item, out)


def _usage_dict(obj: Any) -> dict[str, Any]:
    data = _public_data(obj)
    found: list[dict[str, Any]] = []
    _collect_usage_dicts(data, found)
    if not found:
        return {}
    return _sum_usage_dicts(found)


def _details_cached_tokens(usage: dict[str, Any]) -> int:
    details = usage.get("input_tokens_details") or usage.get("prompt_tokens_details") or {}
    if isinstance(details, dict):
        return int(details.get("cached_tokens", 0) or 0)
    return 0


def _sum_usage_dicts(usages: list[dict[str, Any]]) -> dict[str, Any]:
    totals: dict[str, Any] = {}
    numeric_fields = {
        "input_tokens",
        "output_tokens",
        "cache_read_input_tokens",
        "cache_creation_input_tokens",
        "prompt_token_count",
        "cached_content_token_count",
        "candidates_token_count",
        "thoughts_token_count",
        "total_token_count",
    }
    cached_from_details = 0
    for usage in usages:
        for field in numeric_fields:
            totals[field] = totals.get(field, 0) + int(usage.get(field, 0) or 0)
        cached_from_details += _details_cached_tokens(usage)
    if cached_from_details:
        totals["cached_tokens"] = cached_from_details
    return {k: v for k, v in totals.items() if v}


def _normalize_usage(provider: str, model: str, raw_usage: dict[str, Any] | None) -> dict[str, Any]:
    usage = dict(raw_usage or {})
    if not usage:
        return {}
    if not _has_token_fields(usage):
        return usage
    pricing_key = _pricing_key(model, provider)
    try:
        if provider == "anthropic":
            usage.setdefault("input_tokens", int(usage.get("input_tokens", 0) or 0))
            usage.setdefault("output_tokens", int(usage.get("output_tokens", 0) or 0))
            usage.setdefault("cache_read_input_tokens", int(usage.get("cache_read_input_tokens", 0) or 0))
            usage["token_api_cost_usd"] = cost_usd(pricing_key, _namespace(usage))
        elif provider == "openai":
            input_tokens = int(usage.get("input_tokens", 0) or 0)
            output_tokens = int(usage.get("output_tokens", 0) or 0)
            cached = int(usage.get("cached_tokens", 0) or _details_cached_tokens(usage))
            usage["cached_tokens"] = cached
            usage["token_api_cost_usd"] = cost_from_buckets(
                pricing_key,
                fresh_input=max(0, input_tokens - cached),
                cached=cached,
                output=output_tokens,
            )
        elif provider == "google":
            prompt = int(usage.get("prompt_token_count", usage.get("input_tokens", 0)) or 0)
            cached = int(usage.get("cached_content_token_count", usage.get("cached_tokens", 0)) or 0)
            output = int(usage.get("candidates_token_count", usage.get("output_tokens", 0)) or 0)
            output += int(usage.get("thoughts_token_count", 0) or 0)
            usage["input_tokens"] = prompt
            usage["output_tokens"] = output
            usage["cached_tokens"] = cached
            usage["token_api_cost_usd"] = cost_from_buckets(
                pricing_key,
                fresh_input=max(0, prompt - cached),
                cached=cached,
                output=output,
            )
        usage["pricing_model_key"] = pricing_key
        usage["cost_scope"] = "token/API usage only"
    except Exception as exc:  # noqa: BLE001
        usage["cost_error"] = f"{exc.__class__.__name__}: {exc}"
    return usage


def _session_usage(client: Any, session_id: str) -> dict[str, Any]:
    try:
        session = client.beta.sessions.retrieve(session_id=session_id)
    except TypeError:
        session = client.beta.sessions.retrieve(session_id)
    except Exception as exc:  # noqa: BLE001
        return {"usage_available": False, "usage_source": "sessions.retrieve", "error": str(exc)}
    usage = _usage_dict(session)
    if not usage:
        return {"usage_available": False, "usage_source": "sessions.retrieve"}
    usage["usage_available"] = True
    usage["usage_source"] = "sessions.retrieve"
    return usage


def fetch_ops_slice(kind: str) -> str:
    if kind in {"all", "incident", "incidents", "evidence"}:
        return json.dumps(EVIDENCE, sort_keys=True)
    if kind not in EVIDENCE:
        return json.dumps({"error": f"unknown slice: {kind}", "available": sorted(EVIDENCE)}, sort_keys=True)
    return json.dumps(EVIDENCE[kind], sort_keys=True)


def _now_ms(start: float) -> int:
    return int((time.monotonic() - start) * 1000)


def _jsonish(text: str) -> dict[str, Any] | None:
    blocks = re.findall(r"\{.*?\}", text or "", flags=re.S)
    for block in reversed(blocks):
        try:
            parsed = json.loads(block)
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, dict):
            return parsed
    return None


def score_report(text: str, emitted: dict[str, Any] | None = None) -> tuple[bool, dict[str, Any], list[str]]:
    report = emitted or _jsonish(text) or {}
    failures: list[str] = []

    if str(report.get("incident_id", "")).strip().lower() != EXPECTED_REPORT["incident_id"]:
        failures.append(f"incident_id={report.get('incident_id')!r}")

    severity = str(report.get("severity", "")).strip().lower()
    if severity not in {"sev2", "severe", "high", "high severity", "major"}:
        failures.append(f"severity={report.get('severity')!r}")

    root = str(report.get("root_cause", "")).strip().lower()
    for token in ("auth", "cache", "ttl"):
        if token not in root:
            failures.append(f"root_cause missing {token!r}")

    action = str(report.get("action", "")).strip().lower()
    if not any(token in action for token in ("rollback", "roll back", "revert")):
        failures.append(f"action lacks rollback/revert: {report.get('action')!r}")
    if "dpl-17" not in action:
        failures.append("action missing 'dpl-17'")
    if "cach" not in action and "ttl" not in action:
        failures.append("action missing cache or ttl")

    for key in ("affected_accounts", "evidence_ids"):
        got = sorted(str(v).lower() for v in report.get(key, []))
        wanted = sorted(str(v).lower() for v in EXPECTED_REPORT[key])
        missing = [v for v in wanted if v not in got]
        if missing:
            failures.append(f"{key} missing {missing}")

    return not failures, report, failures


def _held(provider: str, stack: str, reason: str, *, model: str = "") -> dict[str, Any]:
    return {
        "provider": provider,
        "provider_stack": stack,
        "model_id": model,
        "status": "held",
        "correctness": False,
        "latency_ms": 0,
        "tool_calls": 0,
        "retries": 0,
        "failure_reason": reason,
        "usage": {},
        "cost_usd": 0.0,
        "teardown": "not started",
        "artifact_path": "",
        "report": {},
    }


def _success(
    provider: str,
    stack: str,
    model: str,
    start: float,
    text: str,
    *,
    emitted: dict[str, Any] | None = None,
    tool_calls: int = 0,
    usage: dict[str, Any] | None = None,
    cost_usd: float | None = None,
    teardown: str = "not applicable",
    artifact_path: str = "",
) -> dict[str, Any]:
    ok, report, failures = score_report(text, emitted)
    normalized_usage = _normalize_usage(provider, model, usage or {})
    if cost_usd is None:
        cost_usd = float(normalized_usage.get("token_api_cost_usd", 0.0) or 0.0)
    return {
        "provider": provider,
        "provider_stack": stack,
        "model_id": model,
        "status": "success" if ok else "failed",
        "correctness": ok,
        "latency_ms": _now_ms(start),
        "tool_calls": tool_calls,
        "retries": 0,
        "failure_reason": "" if ok else "; ".join(failures),
        "usage": normalized_usage,
        "cost_usd": cost_usd,
        "teardown": teardown,
        "artifact_path": artifact_path,
        "report": report,
    }


def _safe(label: str, fn, *args, **kwargs) -> str:
    try:
        fn(*args, **kwargs)
        return f"{label}: ok"
    except Exception as exc:  # noqa: BLE001
        return f"{label}: skipped ({exc.__class__.__name__})"


def _managed_stack(client: Any, tag: str, *, title: str) -> tuple[Any, Any, Any]:
    env = client.beta.environments.create(
        name=tag,
        config={"type": "cloud", "networking": {"type": "unrestricted"}},
    )
    agent = client.beta.agents.create(
        name=tag,
        model=MANAGED_MODEL,
        system="You are a terse ops agent. Use tools when asked and return only the requested JSON.",
        tools=[{"type": "agent_toolset_20260401", "default_config": {"enabled": True}}],
    )
    session = client.beta.sessions.create(
        agent={"type": "agent", "id": agent.id, "version": agent.version},
        environment_id=env.id,
        title=title,
    )
    return env, agent, session


def _teardown_managed(client: Any, session: Any, env: Any, agent: Any) -> list[str]:
    teardown: list[str] = []
    if session is not None:
        teardown.append(_safe("delete session", client.beta.sessions.delete, session_id=session.id))
    if env is not None:
        teardown.append(_safe("delete environment", client.beta.environments.delete, env.id))
    if agent is not None:
        teardown.append(_safe("archive agent", client.beta.agents.archive, agent.id))
    return teardown


def _managed_stream_prompt(
    client: Any,
    session_id: str,
    prompt: str,
    *,
    seen_ids: set[str] | None = None,
    max_events: int = 400,
) -> dict[str, Any]:
    reply: list[str] = []
    tool_output: list[str] = []
    new_event_ids: list[str] = []
    tool_events = 0
    n = 0
    with client.beta.sessions.events.stream(session_id=session_id) as stream:
        client.beta.sessions.events.send(
            session_id=session_id,
            events=[{"type": "user.message", "content": [{"type": "text", "text": prompt}]}],
        )
        for event in stream:
            event_id = getattr(event, "id", None)
            if seen_ids is not None and event_id is not None and event_id in seen_ids:
                continue
            n += 1
            if event_id is not None:
                new_event_ids.append(event_id)
            event_type = getattr(event, "type", "")
            if "tool" in event_type:
                tool_events += 1
            if event_type == "agent.message":
                for block in getattr(event, "content", []) or []:
                    if getattr(block, "type", "") == "text":
                        reply.append(block.text)
            elif event_type == "agent.tool_result":
                tool_output.append(str(getattr(event, "content", "") or ""))
            elif event_type in ("session.status_idle", "session.status_terminated"):
                break
            if n >= max_events:
                break
    return {
        "reply": "".join(reply),
        "tool_output": "\n".join(tool_output),
        "tool_events": tool_events,
        "new_event_ids": new_event_ids,
    }


def managed_prompt() -> str:
    evidence = json.dumps(EVIDENCE, sort_keys=True)
    return (
        "Use bash to create /mnt/session/inputs/ops_evidence.json from the evidence JSON below. "
        "Then inspect that file with shell or Python and produce one incident report. Write the final "
        "report JSON to /mnt/session/outputs/ops_triage.json and print only that JSON. Do not invent "
        "evidence. The report keys must be incident_id, severity, root_cause, action, "
        "affected_accounts, and evidence_ids. The expected incident id is inc-042.\n\n"
        f"Evidence JSON:\n{evidence}"
    )


def run_managed_agent() -> dict[str, Any]:
    if not os.environ.get("ANTHROPIC_API_KEY"):
        return _held("anthropic", "Claude Managed Agents", "ANTHROPIC_API_KEY is not set", model=MANAGED_MODEL)
    start = time.monotonic()
    tag = f"{COMPARE_PREFIX}-{uuid.uuid4().hex[:8]}"
    env = agent = session = None
    teardown: list[str] = []
    usage: dict[str, Any] = {}
    try:
        import anthropic

        client = anthropic.Anthropic()
        env, agent, session = _managed_stack(client, tag, title="managed-agents operations comparison")
        drained = _managed_stream_prompt(client, session.id, managed_prompt())
        usage = _session_usage(client, session.id)
    except Exception as exc:  # noqa: BLE001
        return _held("anthropic", "Claude Managed Agents", str(exc), model=MANAGED_MODEL)
    finally:
        if session is not None or env is not None or agent is not None:
            teardown = _teardown_managed(client, session, env, agent)
    return _success(
        "anthropic",
        "Claude Managed Agents",
        MANAGED_MODEL,
        start,
        "\n".join(part for part in (drained.get("reply", ""), drained.get("tool_output", "")) if part),
        tool_calls=drained["tool_events"],
        usage=usage,
        teardown="; ".join(teardown),
        artifact_path="/mnt/session/outputs/ops_triage.json",
    )


def run_managed_teardown_trials(trials: int) -> dict[str, Any]:
    if trials <= 0:
        return {"ran": False, "reason": "teardown trials disabled", "trials": 0}
    if not os.environ.get("ANTHROPIC_API_KEY"):
        return {"ran": False, "reason": "ANTHROPIC_API_KEY is not set", "trials": trials}
    try:
        import anthropic
    except Exception as exc:  # noqa: BLE001
        return {"ran": False, "reason": f"anthropic import failed: {exc}", "trials": trials}

    client = anthropic.Anthropic()
    results: list[dict[str, Any]] = []
    for idx in range(trials):
        tag = f"{COMPARE_PREFIX}-teardown-{uuid.uuid4().hex[:8]}"
        env = agent = session = None
        started = time.monotonic()
        failure = "forced failure before workload dispatch"
        try:
            env, agent, session = _managed_stack(client, tag, title="managed-agents teardown probe")
            raise RuntimeError(failure)
        except RuntimeError:
            pass
        except Exception as exc:  # noqa: BLE001
            failure = f"{exc.__class__.__name__}: {exc}"
        finally:
            teardown = _teardown_managed(client, session, env, agent)
        ok = bool(teardown) and all(item.endswith(": ok") for item in teardown)
        results.append({
            "trial": idx + 1,
            "forced_failure": failure,
            "success": ok,
            "teardown": teardown,
            "latency_ms": _now_ms(started),
        })
    successes = sum(1 for item in results if item["success"])
    return {
        "ran": True,
        "trials": trials,
        "successful_trials": successes,
        "success_rate": successes / trials if trials else 0.0,
        "results": results,
    }


def run_managed_resume_probe(*, max_events: int = 400) -> dict[str, Any]:
    if not os.environ.get("ANTHROPIC_API_KEY"):
        return {"ran": False, "reason": "ANTHROPIC_API_KEY is not set"}
    start = time.monotonic()
    tag = f"{COMPARE_PREFIX}-resume-{uuid.uuid4().hex[:8]}"
    env = agent = session = None
    teardown: list[str] = []
    result: dict[str, Any] | None = None
    try:
        import anthropic

        client = anthropic.Anthropic()
        env, agent, session = _managed_stack(client, tag, title="managed-agents resume probe")
        write_task = (
            "Use bash to run exactly this script, then stop.\n\n"
            "python3 - <<'PY'\n"
            "import pathlib\n"
            "pathlib.Path('/mnt/session/outputs').mkdir(parents=True, exist_ok=True)\n"
            "pathlib.Path('/mnt/session/outputs/resume_probe.txt').write_text('probe-started\\n')\n"
            "print('probe-started')\n"
            "PY"
        )
        first = _managed_stream_prompt(client, session.id, write_task, max_events=max_events)
        try:
            replayed = list(client.beta.sessions.events.list(session.id, order="asc"))
        except TypeError:
            replayed = list(client.beta.sessions.events.list(session_id=session.id, order="asc"))
        seen_ids = {str(getattr(event, "id", "")) for event in replayed if getattr(event, "id", None)}
        read_task = (
            "Use bash to read /mnt/session/outputs/resume_probe.txt, append probe-resumed, "
            "then print the file. Return only the file contents."
        )
        resume_start = time.monotonic()
        resumed = _managed_stream_prompt(
            client,
            session.id,
            read_task,
            seen_ids=seen_ids,
            max_events=max_events,
        )
        negative_recovered = True
        try:
            client.beta.sessions.retrieve(session_id="sesn_" + "0" * 24)
        except Exception:  # noqa: BLE001
            negative_recovered = False
        combined = "\n".join([resumed.get("reply", ""), resumed.get("tool_output", "")])
        recovered = "probe-started" in combined
        appended = "probe-resumed" in combined
        usage = _session_usage(client, session.id)
        result = {
            "ran": True,
            "recovered": recovered,
            "state_visible_after_interruption": recovered,
            "appended_after_resume": appended,
            "negative_control_recovered": negative_recovered,
            "events_replayed_on_resume": len(seen_ids),
            "resume_latency_ms": int((time.monotonic() - resume_start) * 1000),
            "latency_ms": _now_ms(start),
            "tool_events_first_run": first.get("tool_events", 0),
            "tool_events_resume": resumed.get("tool_events", 0),
            "usage": _normalize_usage("anthropic", MANAGED_MODEL, usage),
        }
    except Exception as exc:  # noqa: BLE001
        result = {
            "ran": True,
            "recovered": False,
            "state_visible_after_interruption": False,
            "appended_after_resume": False,
            "negative_control_recovered": None,
            "failure_reason": str(exc),
            "latency_ms": _now_ms(start),
        }
    finally:
        if session is not None or env is not None or agent is not None:
            teardown = _teardown_managed(client, session, env, agent)
    result = result or {"ran": True, "recovered": False, "failure_reason": "unknown resume probe failure"}
    result["teardown"] = teardown
    result["teardown_success"] = bool(teardown) and all(item.endswith(": ok") for item in teardown)
    return result


def run_self_managed_claude() -> dict[str, Any]:
    if not os.environ.get("ANTHROPIC_API_KEY"):
        return _held("anthropic", "self-managed Messages tool loop", "ANTHROPIC_API_KEY is not set",
                     model=CLAUDE_SELF_MODEL)
    start = time.monotonic()
    try:
        import anthropic
    except Exception as exc:  # noqa: BLE001
        return _held("anthropic", "self-managed Messages tool loop", f"anthropic import failed: {exc}",
                     model=CLAUDE_SELF_MODEL)

    client = anthropic.Anthropic()
    messages: list[dict[str, Any]] = [{"role": "user", "content": PROMPT}]
    emitted: dict[str, Any] | None = None
    tool_calls = 0
    usage_totals: dict[str, int] = {}
    tools = [
        {
            "name": "fetch_ops_slice",
            "description": "Return one deterministic ops evidence slice.",
            "input_schema": {
                "type": "object",
                "properties": {"kind": {"type": "string", "enum": ["logs", "tickets", "deploys"]}},
                "required": ["kind"],
            },
        },
        {
            "name": "emit_incident_report",
            "description": "Emit the final incident report as structured JSON.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "incident_id": {"type": "string"},
                    "severity": {"type": "string"},
                    "root_cause": {"type": "string"},
                    "action": {"type": "string"},
                    "affected_accounts": {"type": "array", "items": {"type": "string"}},
                    "evidence_ids": {"type": "array", "items": {"type": "string"}},
                },
                "required": ["incident_id", "severity", "root_cause", "action", "affected_accounts", "evidence_ids"],
            },
        },
    ]
    final_text = ""
    try:
        for _ in range(8):
            response = client.messages.create(
                model=CLAUDE_SELF_MODEL,
                max_tokens=600,
                tools=tools,
                messages=messages,
            )
            usage = getattr(response, "usage", None)
            if usage:
                for key in ("input_tokens", "output_tokens", "cache_read_input_tokens"):
                    usage_totals[key] = usage_totals.get(key, 0) + int(getattr(usage, key, 0) or 0)
            content = [block.to_dict() if hasattr(block, "to_dict") else block for block in response.content]
            messages.append({"role": "assistant", "content": content})
            tool_results = []
            tool_uses = [block for block in response.content if getattr(block, "type", "") == "tool_use"]
            if not tool_uses:
                final_text = "".join(getattr(block, "text", "") for block in response.content)
                break
            for use in tool_uses:
                tool_calls += 1
                if use.name == "fetch_ops_slice":
                    result = fetch_ops_slice(use.input["kind"])
                elif use.name == "emit_incident_report":
                    emitted = dict(use.input)
                    result = "accepted"
                else:
                    result = f"unknown tool: {use.name}"
                tool_results.append({"type": "tool_result", "tool_use_id": use.id, "content": result})
            messages.append({"role": "user", "content": tool_results})
    except Exception as exc:  # noqa: BLE001
        return _held("anthropic", "self-managed Messages tool loop", str(exc), model=CLAUDE_SELF_MODEL)
    return _success(
        "anthropic",
        "self-managed Messages tool loop",
        CLAUDE_SELF_MODEL,
        start,
        final_text,
        emitted=emitted,
        tool_calls=tool_calls,
        usage=usage_totals,
    )


def run_openai_agents() -> dict[str, Any]:
    if not os.environ.get("OPENAI_API_KEY"):
        return _held("openai", "OpenAI Agents SDK", "OPENAI_API_KEY is not set", model=OPENAI_MODEL)
    start = time.monotonic()
    emitted: dict[str, Any] | None = None
    tool_calls = 0
    usage: dict[str, Any] = {}
    try:
        from agents import Agent, Runner, function_tool
    except Exception as exc:  # noqa: BLE001
        return _held("openai", "OpenAI Agents SDK", f"openai-agents import failed: {exc}", model=OPENAI_MODEL)

    @function_tool
    def fetch_ops_slice_tool(kind: str) -> str:
        """Return one deterministic ops evidence slice."""
        nonlocal tool_calls
        tool_calls += 1
        return fetch_ops_slice(kind)

    @function_tool
    def emit_incident_report_tool(report_json: str) -> str:
        """Record the final incident report JSON."""
        nonlocal emitted, tool_calls
        tool_calls += 1
        emitted = json.loads(report_json)
        return "accepted"

    async def _run() -> str:
        nonlocal usage
        agent = Agent(
            name="ops_triage_agent",
            model=OPENAI_MODEL,
            instructions=(
                "Use fetch_ops_slice_tool for logs, tickets, and deploys. Then call "
                "emit_incident_report_tool with a JSON string. Return only the JSON."
            ),
            tools=[fetch_ops_slice_tool, emit_incident_report_tool],
        )
        result = await Runner.run(agent, PROMPT, max_turns=8)
        usage = _usage_dict(result)
        return str(result.final_output)

    try:
        text = asyncio.run(_run())
    except Exception as exc:  # noqa: BLE001
        return _held("openai", "OpenAI Agents SDK", str(exc), model=OPENAI_MODEL)
    return _success("openai", "OpenAI Agents SDK", OPENAI_MODEL, start, text,
                    emitted=emitted, tool_calls=tool_calls, usage=usage)


def run_google_adk() -> dict[str, Any]:
    if not os.environ.get("GEMINI_API_KEY") and not os.environ.get("GOOGLE_API_KEY"):
        return _held("google", "Google ADK with Gemini", "GEMINI_API_KEY or GOOGLE_API_KEY is not set",
                     model=GEMINI_MODEL)
    os.environ.setdefault("GOOGLE_API_KEY", os.environ.get("GEMINI_API_KEY", ""))
    start = time.monotonic()
    emitted: dict[str, Any] | None = None
    tool_calls = 0
    usage_parts: list[dict[str, Any]] = []
    try:
        from google.adk.agents import Agent
        from google.adk.runners import Runner
        from google.adk.sessions import InMemorySessionService
        from google.genai import types
    except Exception as exc:  # noqa: BLE001
        return _held("google", "Google ADK with Gemini", f"google-adk import failed: {exc}", model=GEMINI_MODEL)

    def fetch_ops_slice_tool(kind: str) -> str:
        """Return one deterministic ops evidence slice."""
        nonlocal tool_calls
        tool_calls += 1
        return fetch_ops_slice(kind)

    def emit_incident_report_tool(report_json: str) -> str:
        """Record the final incident report JSON."""
        nonlocal emitted, tool_calls
        tool_calls += 1
        emitted = json.loads(report_json)
        return "accepted"

    try:
        agent = Agent(
            name="ops_triage_agent",
            model=GEMINI_MODEL,
            instruction=(
                "Use fetch_ops_slice_tool for logs, tickets, and deploys. Then call "
                "emit_incident_report_tool with a JSON string. Return only the JSON."
            ),
            tools=[fetch_ops_slice_tool, emit_incident_report_tool],
        )
        session_service = InMemorySessionService()
        session = asyncio.run(session_service.create_session(
            app_name="managed_agents_compare",
            user_id="local",
            session_id=f"cmp-{uuid.uuid4().hex[:8]}",
        ))
        runner = Runner(app_name="managed_agents_compare", agent=agent, session_service=session_service)
        message = types.Content(role="user", parts=[types.Part.from_text(text=PROMPT)])
        parts: list[str] = []
        for event in runner.run(user_id="local", session_id=session.id, new_message=message):
            event_usage = _usage_dict(event)
            if event_usage:
                usage_parts.append(event_usage)
            content = getattr(event, "content", None)
            for part in getattr(content, "parts", []) or []:
                if getattr(part, "text", None):
                    parts.append(part.text)
        text = "".join(parts)
    except Exception as exc:  # noqa: BLE001
        return _held("google", "Google ADK with Gemini", str(exc), model=GEMINI_MODEL)
    usage = _sum_usage_dicts(usage_parts) if usage_parts else {}
    return _success("google", "Google ADK with Gemini", GEMINI_MODEL, start, text,
                    emitted=emitted, tool_calls=tool_calls, usage=usage)


def _source_loc(*function_names: str) -> int:
    count = 0
    for name in function_names:
        fn = globals().get(name)
        if fn is None:
            continue
        for line in inspect.getsource(fn).splitlines():
            stripped = line.strip()
            if stripped and not stripped.startswith("#"):
                count += 1
    return count


def _orchestration_metrics() -> dict[str, Any]:
    by_stack = {
        STACK_MANAGED: _source_loc(
            "managed_prompt",
            "_managed_stack",
            "_managed_stream_prompt",
            "run_managed_agent",
        ),
        STACK_SELF_MANAGED: _source_loc("run_self_managed_claude"),
        STACK_OPENAI: _source_loc("run_openai_agents"),
        STACK_GEMINI: _source_loc("run_google_adk"),
    }
    self_loc = by_stack.get(STACK_SELF_MANAGED, 0)
    managed_loc = by_stack.get(STACK_MANAGED, 0)
    return {
        "lines_by_stack": by_stack,
        "managed_lines_removed_vs_self_managed": self_loc - managed_loc,
        "counting_basis": "nonblank noncomment source lines in the implemented radar arms",
    }


def _operations_scorecard(
    arms: list[dict[str, Any]],
    *,
    teardown_probe: dict[str, Any] | None = None,
    resume_probe: dict[str, Any] | None = None,
) -> dict[str, Any]:
    orchestration = _orchestration_metrics()
    return build_operations_scorecard(
        arms,
        managed_stack=STACK_MANAGED,
        baseline_stack=STACK_SELF_MANAGED,
        components_inventory=COMPONENT_INVENTORY,
        components_avoided_vs_baseline=MANAGED_COMPONENTS_AVOIDED_VS_SELF_MANAGED,
        orchestration=orchestration,
        teardown_probe=teardown_probe,
        resume_probe=resume_probe,
        managed_label="Managed Agents",
        baseline_label="self-managed",
        cost_worse_label="Managed Agents token/API cost is worse than the self-managed loop",
    )


def _status(arms: list[dict[str, Any]]) -> str:
    if any(arm["status"] == "held" for arm in arms):
        return "held"
    if arms and all(arm["status"] == "success" and arm["correctness"] for arm in arms):
        return "mechanically vetted"
    return "candidate"


def run_compare(
    *,
    providers: list[str],
    live: bool = True,
    teardown_trials: int = TEARDOWN_TRIALS,
    resume_probe: bool = RESUME_PROBE_DEFAULT,
) -> dict[str, Any]:
    _load_env()
    arms: list[dict[str, Any]] = []
    provider_set = {p.strip() for p in providers if p.strip()}
    teardown_result: dict[str, Any] = {"ran": False, "reason": "not requested", "trials": teardown_trials}
    resume_result: dict[str, Any] = {"ran": False, "reason": "not requested"}
    if not live:
        dry_stacks = {
            "managed": ("anthropic", "Claude Managed Agents", MANAGED_MODEL),
            "self-managed": ("anthropic", "self-managed Messages tool loop", CLAUDE_SELF_MODEL),
            "openai": ("openai", "OpenAI Agents SDK", OPENAI_MODEL),
            "gemini": ("google", "Google ADK with Gemini", GEMINI_MODEL),
        }
        for provider in sorted(provider_set):
            vendor, stack, model = dry_stacks.get(provider, (provider, provider, ""))
            arms.append(_held(vendor, stack, "dry run only", model=model))
    else:
        if "managed" in provider_set:
            platform.used("managed_agents", "Claude Managed Agents operations arm")
            arms.append(run_managed_agent())
        if "self-managed" in provider_set:
            arms.append(run_self_managed_claude())
        if "openai" in provider_set:
            arms.append(run_openai_agents())
        if "gemini" in provider_set:
            arms.append(run_google_adk())
        if "managed" in provider_set:
            teardown_result = run_managed_teardown_trials(teardown_trials)
            if resume_probe:
                resume_result = run_managed_resume_probe()
            else:
                resume_result = {"ran": False, "reason": "resume probe disabled"}

    scorecard = _operations_scorecard(
        arms,
        teardown_probe=teardown_result,
        resume_probe=resume_result,
    )

    return {
        "schema_version": 1,
        "status": _status(arms),
        "promotion": "held unless Managed Agents proves a measured operations advantage on the same workload",
        "workload": {
            "id": "ops_triage_tool_loop",
            "description": "stateful ops triage over logs, tickets, and deploys",
            "expected": EXPECTED_REPORT,
        },
        "arms": arms,
        "operations_scorecard": scorecard,
    }


def _arm_to_base(raw: dict[str, Any]) -> Arm:
    report = raw.get("report") or {}
    text = json.dumps(report, sort_keys=True) if report else ""
    usage = raw.get("usage") or {}
    return Arm(
        provider=raw.get("provider", ""),
        model=raw.get("model_id", ""),
        text=text,
        ran=raw.get("status") != "held",
        latency_s=float(raw.get("latency_ms", 0) or 0) / 1000.0,
        output_tokens=int(usage.get("output_tokens", 0) or 0),
        input_tokens=int(usage.get("input_tokens", 0) or 0),
        cache_read_tokens=int(usage.get("cache_read_input_tokens", usage.get("cached_tokens", 0)) or 0),
        cost_usd=float(raw.get("cost_usd", 0.0) or usage.get("token_api_cost_usd", 0.0) or 0.0),
        metric={
            "provider_stack": raw.get("provider_stack", ""),
            "status": raw.get("status", ""),
            "correctness": bool(raw.get("correctness")),
            "latency_ms": int(raw.get("latency_ms", 0) or 0),
            "tool_calls": int(raw.get("tool_calls", 0) or 0),
            "retries": int(raw.get("retries", 0) or 0),
            "failure_reason": raw.get("failure_reason", ""),
            "usage": raw.get("usage") or {},
            "teardown": raw.get("teardown", ""),
            "artifact_path": raw.get("artifact_path", ""),
            "report": report,
        },
        note=raw.get("failure_reason", ""),
    )


def _split_arms(raw: dict[str, Any]) -> tuple[Arm, list[Arm]]:
    arms = [_arm_to_base(arm) for arm in raw.get("arms", [])]
    managed = next((arm for arm in arms if arm.metric.get("provider_stack") == "Claude Managed Agents"), None)
    if managed is None:
        managed = Arm(
            provider="anthropic",
            model=MANAGED_MODEL,
            ran=False,
            metric={"provider_stack": "Claude Managed Agents", "status": "held", "correctness": False},
            note="managed provider arm was not requested",
        )
    competitors = [arm for arm in arms if arm is not managed]
    return managed, competitors


def _comparison_metric(
    claude: Arm,
    competitors: list[Arm],
    raw_status: str,
    raw_compare: dict[str, Any] | None = None,
) -> dict[str, Any]:
    competitor_latencies = [int(a.metric.get("latency_ms", 0)) for a in competitors if a.ran and a.metric.get("correctness")]
    competitor_tools = [int(a.metric.get("tool_calls", 0)) for a in competitors if a.ran and a.metric.get("correctness")]
    managed_latency = int(claude.metric.get("latency_ms", 0))
    managed_tools = int(claude.metric.get("tool_calls", 0))
    scorecard = (raw_compare or {}).get("operations_scorecard") or {}
    if not scorecard and raw_compare and raw_compare.get("arms"):
        scorecard = _operations_scorecard(raw_compare.get("arms", []))
    return {
        "status": raw_status,
        "managed_correct": bool(claude.metric.get("correctness")),
        "all_competitors_ran": bool(competitors) and all(a.ran for a in competitors),
        "all_competitors_correct": bool(competitors) and all(bool(a.metric.get("correctness")) for a in competitors),
        "managed_latency_ms": managed_latency,
        "fastest_correct_competitor_latency_ms": min(competitor_latencies) if competitor_latencies else 0,
        "managed_tool_calls": managed_tools,
        "fewest_correct_competitor_tool_calls": min(competitor_tools) if competitor_tools else 0,
        "operations_advantage": bool(scorecard.get("operations_advantage")),
        "advantage_basis": (
            "operations scorecard satisfied"
            if scorecard.get("operations_advantage")
            else "operations scorecard blocked promotion"
        ),
        "operations_scorecard": scorecard,
    }


def _verdict_for(
    claude: Arm,
    competitors: list[Arm],
    raw_status: str,
    raw_compare: dict[str, Any] | None = None,
) -> Verdict:
    metric = _comparison_metric(claude, competitors, raw_status, raw_compare)
    if not claude.ran or not metric["all_competitors_ran"]:
        return Verdict(
            verdict="never-evaluated",
            passed=False,
            metric=metric,
            note="one or more requested arms were held, so no promotion comparison is complete",
        )
    if not bool(claude.metric.get("correctness")) and any(bool(a.metric.get("correctness")) for a in competitors):
        return Verdict(
            verdict="claude-behind",
            passed=False,
            metric=metric,
            note="Managed Agents did not pass the shared correctness gate while a competitor did",
        )
    if bool(claude.metric.get("correctness")) and not any(bool(a.metric.get("correctness")) for a in competitors):
        metric["operations_advantage"] = True
        metric["advantage_basis"] = "Managed Agents was the only stack to pass the shared correctness gate"
        return Verdict(
            verdict="claude-ahead",
            passed=True,
            metric=metric,
            note="Managed Agents was the only requested stack to return the expected incident report",
        )
    if metric["managed_correct"] and metric["all_competitors_correct"]:
        if metric["operations_advantage"]:
            return Verdict(
                verdict="claude-ahead",
                passed=True,
                metric=metric,
                note="Managed Agents cleared the Operations scorecard on the shared workload",
            )
        return Verdict(
            verdict="parity",
            passed=True,
            metric=metric,
            note="mechanically vetted on the ops-triage workload, but no measured operations advantage",
        )
    return Verdict(
        verdict="never-evaluated",
        passed=False,
        metric=metric,
        note="the shared correctness gate did not produce a clean parity or lead result",
    )


class ManagedAgentsOperationsDemonstrator(BaseDemonstrator):
    demo_kind = "agent_runtime_operations"

    def _raw_compare(self, spec):
        spec = spec if isinstance(spec, dict) else {}
        raw = spec.get("raw_compare")
        if raw is None:
            raw = run_compare(providers=["managed", "self-managed", "openai", "gemini"], live=True)
            spec["raw_compare"] = raw
        return raw

    def estimate(self, edge, spec):
        return CostEstimate(
            usd=0.50,
            wall_clock_s=180.0,
            command="make managed-agents-ops",
            note="live ops-triage comparison across Managed Agents, self-managed Claude, OpenAI Agents SDK, and Google ADK",
        )

    def run_claude_arm(self, edge, spec):
        raw = self._raw_compare(spec)
        claude, _ = _split_arms(raw)
        return claude

    def run_competitor_arms(self, edge, spec):
        raw = self._raw_compare(spec)
        _, competitors = _split_arms(raw)
        return competitors

    def score(self, claude, competitors, spec):
        raw_compare = (spec.get("raw_compare") or {}) if spec else {}
        raw_status = raw_compare.get("status", "unknown")
        return _verdict_for(claude, competitors, raw_status, raw_compare)

    def receipt(self, edge, claude, competitors, verdict, spec):
        spec = spec or {}
        models = {
            "managed_agents": claude.model,
            "competitors": {a.metric.get("provider_stack", a.provider): a.model for a in competitors},
        }
        return self.build_receipt(
            edge, claude, competitors, verdict, spec,
            workload={
                "task_shape": "deterministic ops triage over logs, tickets, and deploys",
                "models": models,
                "features_on": [
                    "Claude Managed Agents hosted loop and cloud environment",
                    "self-managed Claude Messages tool loop",
                    "OpenAI Agents SDK function tools",
                    "Google ADK in-memory session with Gemini",
                ],
                "expected_report": EXPECTED_REPORT,
                "scope": (
                    "measures correctness, latency, tool events, teardown, interruption resume, "
                    "orchestration code lines, state or cleanup components, and token/API usage on "
                    "one ops-triage workload. It does not promote Managed Agents unless the "
                    "Operations scorecard shows same correctness, materially less glue code or fewer "
                    "failure modes, and no worse token/API cost"
                ),
            },
            grounding=[
                {
                    "claim": "Managed Agents is the Anthropic-hosted agent loop and environment surface used by the managed arm.",
                    "source_url": "https://platform.claude.com/docs/en/managed-agents/overview",
                    "date": "2026-06-28",
                },
                {
                    "claim": "Managed Agents sessions and event streams are the session surface exercised by the managed arm.",
                    "source_url": "https://platform.claude.com/docs/en/managed-agents/sessions",
                    "date": "2026-06-28",
                },
                {
                    "claim": "Managed Agents environments provide the cloud environment used by the managed arm.",
                    "source_url": "https://platform.claude.com/docs/en/managed-agents/environments",
                    "date": "2026-06-28",
                },
            ],
            fairness={
                "best_to_best": (
                    "same deterministic evidence and same machine-checked report gate across Managed "
                    "Agents, a self-managed Claude tool loop, OpenAI Agents SDK, and Google ADK"
                ),
                "isolate": (
                    "the workload is intentionally small so the comparison measures hosted loop shape, "
                    "correctness, latency, tool events, and teardown instead of domain difficulty"
                ),
                "lead_basis": "head-to-head",
            },
        )


register(ManagedAgentsOperationsDemonstrator())


def _edge() -> dict[str, Any]:
    return {
        "key": "managed_agents_operations",
        "axis": "reliability",
        "demoKind": "agent_runtime_operations",
        "claim": (
            "Managed Agents removes hosted-loop operations work only when the same workload shows a "
            "measured advantage over self-managed Claude, OpenAI Agents SDK, and Google ADK"
        ),
        "fair_comparison": {
            "lead_basis": "head-to-head",
            "repro": {"command": "make managed-agents-ops", "est_cost_usd": 0.50, "est_time_s": 180},
        },
    }


def write_receipt(receipt) -> None:
    DATA.mkdir(parents=True, exist_ok=True)
    LAST_JSON.write_text(json.dumps(receipt.to_dict(), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    scorecard = receipt.metric.get("operations_scorecard") or {}
    orchestration = scorecard.get("orchestration") or {}
    teardown = scorecard.get("teardown") or {}
    resume = scorecard.get("resume") or {}
    lines = [
        "# Managed Agents operations receipt",
        "",
        f"verdict: {receipt.verdict}",
        f"passed: {receipt.passed}",
        f"workload: {receipt.workload.get('task_shape', '')}",
        f"operations_advantage: {scorecard.get('operations_advantage', False)}",
        f"promotion_rule: {scorecard.get('promotion_rule', '')}",
        "",
        "| provider | stack | model | status | correct | latency_ms | tool_calls | token_api_cost_usd | failure |",
        "| --- | --- | --- | --- | --- | ---: | ---: | ---: | --- |",
    ]
    for arm in receipt.arms:
        metric = arm.get("metric") or {}
        usage = metric.get("usage") or {}
        cost = usage.get("token_api_cost_usd")
        cost_text = "" if cost is None else f"{float(cost):.6f}"
        lines.append(
            f"| {arm.get('provider')} | {metric.get('provider_stack', '')} | {arm.get('model')} | "
            f"{metric.get('status', '')} | {metric.get('correctness', False)} | "
            f"{metric.get('latency_ms', 0)} | {metric.get('tool_calls', 0)} | "
            f"{cost_text} | "
            f"{metric.get('failure_reason', '')} |"
        )
    lines.extend([
        "",
        "## Operations scorecard",
        "",
        f"- Lines removed vs self-managed loop: {orchestration.get('managed_lines_removed_vs_self_managed')}",
        f"- Managed components avoided vs self-managed loop: {(scorecard.get('components') or {}).get('managed_avoided_count')}",
        f"- Failed-run teardown success rate: {teardown.get('effective_success_rate')}",
        f"- Resume state visible after interruption: {resume.get('state_visible_after_interruption')}",
        f"- No-worse token/API cost vs self-managed loop: {scorecard.get('no_worse_token_api_cost_vs_self_managed')}",
    ])
    blockers = scorecard.get("blockers") or []
    if blockers:
        lines.extend(["", "Promotion blockers:"])
        lines.extend(f"- {blocker}" for blocker in blockers)
    LAST_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")


def format_receipt(receipt) -> str:
    scorecard = receipt.metric.get("operations_scorecard") or {}
    lines = [
        "=== managed-agents operations ===",
        f"verdict: {receipt.verdict}",
        f"passed: {receipt.passed}",
        f"operations_advantage: {scorecard.get('operations_advantage', False)}",
        f"receipt: {LAST_JSON}",
    ]
    for arm in receipt.arms:
        metric = arm.get("metric") or {}
        usage = metric.get("usage") or {}
        cost = usage.get("token_api_cost_usd")
        cost_text = "-" if cost is None else f"{float(cost):.6f}"
        lines.append(
            f"- {metric.get('provider_stack', arm.get('provider'))}: {metric.get('status')} "
            f"correct={metric.get('correctness')} latency_ms={metric.get('latency_ms')} "
            f"tools={metric.get('tool_calls')} cost_usd={cost_text} "
            f"failure={metric.get('failure_reason') or '-'}"
        )
    blockers = scorecard.get("blockers") or []
    if blockers:
        lines.append("promotion_blockers:")
        lines.extend(f"- {blocker}" for blocker in blockers)
    return "\n".join(lines)


def build_receipt(*, providers: list[str], live: bool, teardown_trials: int, resume_probe: bool) -> Any:
    raw = run_compare(
        providers=providers,
        live=live,
        teardown_trials=teardown_trials,
        resume_probe=resume_probe,
    )
    demo = ManagedAgentsOperationsDemonstrator()
    edge = _edge()
    est = demo.estimate(edge, {})
    spec = {"raw_compare": raw, "estimate": est.to_dict()}
    claude, competitors = _split_arms(raw)
    verdict = demo.score(claude, competitors, spec)
    return demo.receipt(edge, claude, competitors, verdict, spec)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="Run the canonical Managed Agents operations comparison in radar.",
    )
    parser.add_argument(
        "--providers",
        default="managed,self-managed,openai,gemini",
        help="comma-separated provider arms: managed,self-managed,openai,gemini",
    )
    parser.add_argument(
        "--teardown-trials",
        type=int,
        default=TEARDOWN_TRIALS,
        help="number of forced-failure Managed Agents teardown trials",
    )
    parser.add_argument(
        "--resume-probe",
        dest="resume_probe",
        action="store_true",
        default=RESUME_PROBE_DEFAULT,
        help="run the Managed Agents interruption and resume probe",
    )
    parser.add_argument(
        "--no-resume-probe",
        dest="resume_probe",
        action="store_false",
        help="skip the Managed Agents interruption and resume probe",
    )
    parser.add_argument("--dry-run", action="store_true", help="do not call provider APIs")
    parser.add_argument("--no-write", action="store_true", help="do not write data/last_managed_agents_operations.*")
    parser.add_argument("--check", action="store_true", help="return non-zero unless every requested arm succeeds")
    args = parser.parse_args(argv)

    receipt = build_receipt(
        providers=args.providers.split(","),
        live=not args.dry_run,
        teardown_trials=args.teardown_trials,
        resume_probe=args.resume_probe,
    )
    if not args.no_write:
        write_receipt(receipt)
    print(format_receipt(receipt))
    if args.check and not receipt.passed:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
