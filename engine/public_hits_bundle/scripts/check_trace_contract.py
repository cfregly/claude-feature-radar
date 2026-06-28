"""No-key trace-contract eval for the programmatic-tool-calling runner."""

from __future__ import annotations

import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from programmatic_tool_calling.run_engine import PROGRAMMATIC_CALLER, run_mode  # noqa: E402
from programmatic_tool_calling.compare_direct_vs_programmatic import programmatic_trace_problems  # noqa: E402


class Obj:
    def __init__(self, **fields):
        self.__dict__.update(fields)

    def model_dump(self, exclude_none: bool = True, exclude_unset: bool = True):
        out = dict(self.__dict__)
        if exclude_none:
            out = {k: v for k, v in out.items() if v is not None}
        return out


class FakeMessages:
    def __init__(self, *, include_programmatic_caller: bool = True):
        self.calls = 0
        self.kwargs = []
        self.include_programmatic_caller = include_programmatic_caller

    def create(self, **kwargs):
        self.calls += 1
        self.kwargs.append(kwargs)
        tools = kwargs.get("tools", [])
        programmatic = any(isinstance(tool, dict) and tool.get("type") == PROGRAMMATIC_CALLER for tool in tools)
        usage = Obj(
            input_tokens=100,
            output_tokens=25,
            cache_read_input_tokens=7,
            cache_creation=Obj(ephemeral_5m_input_tokens=3, ephemeral_1h_input_tokens=2),
            server_tool_use=Obj(code_execution_requests=1 if programmatic else 0),
        )
        container = Obj(id="cnt_eval") if programmatic else None
        if self.calls == 1:
            content = []
            if programmatic:
                content.append(Obj(type="server_tool_use", id="srvtoolu_eval", name="code_execution", input={"code": "pass"}))
                caller = Obj(type=PROGRAMMATIC_CALLER, tool_id="srvtoolu_eval") if self.include_programmatic_caller else None
            else:
                caller = None
            tool_use = {
                "type": "tool_use",
                "id": "toolu_eval",
                "name": "query_customer_evidence",
                "input": {"source": "support_tickets"},
            }
            if caller is not None:
                tool_use["caller"] = caller
            content.append(Obj(**tool_use))
            return Obj(
                usage=usage,
                container=container,
                stop_reason="tool_use",
                content=content,
            )
        return Obj(
            usage=usage,
            container=container,
            stop_reason="end_turn",
            content=[Obj(type="text", text='{"accounts":[{"account_id":"acct_1842"},{"account_id":"acct_2199"},{"account_id":"acct_7731"}],"fallback":null}')],
        )


class FakeClient:
    def __init__(self, *, include_programmatic_caller: bool = True):
        self.messages = FakeMessages(include_programmatic_caller=include_programmatic_caller)


def call_source(source: str):
    return [{
        "evidence_id": f"{source}-1",
        "account_id": "acct_1842",
        "source": source,
        "summary": "Unresolved support thread.",
        "severity": "high",
        "days_ago": 1,
        "risk_points": 5,
        "status": "open",
        "signal": "unresolved_support",
    }]


def main() -> int:
    tool_spec = {
        "name": "query_customer_evidence",
        "description": "Return rows.",
        "input_schema": {"type": "object", "properties": {"source": {"type": "string"}}},
        "_trace_metadata": {
            "tool_schema_version": "customer-evidence-tool-v2",
            "reducer_version": "customer-evidence-reducer-v3",
            "snapshot_id": "fixture-customer-evidence-v1",
            "source_freshness": "static-fixture",
        },
    }
    client = FakeClient()
    result = run_mode(
        client,
        "claude-sonnet-4-6",
        tool_spec,
        call_source,
        "Find the account list.",
        programmatic=True,
        cost_fn=lambda usage: 0.01,
        label="B",
        progress=False,
    )
    trace = result["trace"]
    api_tool = client.messages.kwargs[0]["tools"][1]

    checks = {
        "run_id": trace["run_id"].startswith("b-"),
        "trace schema": trace["trace_schema_version"] == "programmatic-tool-calling-trace-v1",
        "mode": trace["mode"] == "programmatic",
        "model": trace["model"] == "claude-sonnet-4-6",
        "tool_name": trace["tool_name"] == "query_customer_evidence",
        "tool schema version": trace["tool_schema_version"] == "customer-evidence-tool-v2",
        "reducer version": trace["reducer_version"] == "customer-evidence-reducer-v3",
        "metadata stripped from api tool": all(
            key not in api_tool
            for key in ["_trace_metadata", "tool_schema_version", "reducer_version", "snapshot_id", "source_freshness"]
        ),
        "allowed_callers": trace["allowed_callers"] == [PROGRAMMATIC_CALLER],
        "prompt_hash": len(trace["prompt_hash"]) == 12,
        "snapshot": trace["snapshot_id"] == "fixture-customer-evidence-v1" and trace["source_freshness"] == "static-fixture",
        "container_ids": trace["container_ids"] == ["cnt_eval"],
        "turns": trace["turns"] == 2,
        "tool_calls": trace["tool_calls"] == 1,
        "budget": trace["budget_limits"] == {"max_turns": 8} and trace["budget_exceeded"] is False,
        "retries": trace["retry_count"] == 0 and trace["rate_limit_events"] == 0,
        "usage buckets": trace["input_tokens"] == 200 and trace["cache_read_input_tokens"] == 14,
        "cache creation buckets": trace["cache_creation_5m_input_tokens"] == 6 and trace["cache_creation_1h_input_tokens"] == 4,
        "server tool use": trace["server_tool_use"]["code_execution_requests"] == 2,
        "observed server tool blocks": trace["server_tool_blocks"] == 1,
        "caller path clean": trace["caller_path_drift"] is False,
        "raw bytes": trace["raw_tool_bytes"] > 0,
        "final bytes": trace["final_bytes"] > 0,
        "cost": trace["cost_usd"] == 0.02,
        "result state": trace["incomplete_result"] is False and trace["partial_result"] is False,
        "abstain": trace["abstain_reason"] is None,
        "fallback": trace["fallback_reason"] is None,
        "policy": trace["policy_denial"] is False,
        "tool call record caller": trace["tool_call_records"][0]["caller_type"] == PROGRAMMATIC_CALLER,
        "tool call record": trace["tool_call_records"][0]["caller_tool_id"] == "srvtoolu_eval",
        "row count": trace["tool_call_records"][0]["row_count"] == 1,
    }
    checks["trace gate accepts clean programmatic tool calling"] = programmatic_trace_problems({"mode_b": result}) == []

    budget_result = run_mode(
        FakeClient(),
        "claude-sonnet-4-6",
        tool_spec,
        call_source,
        "Find the account list.",
        programmatic=True,
        max_turns=1,
        label="B",
        progress=False,
    )
    budget_trace = budget_result["trace"]
    checks.update({
        "budget stop reason": budget_trace["fallback_reason"] == "max_turns_exhausted",
        "budget exceeded": budget_trace["budget_exceeded"] is True,
        "budget incomplete": budget_trace["incomplete_result"] is True and budget_trace["partial_result"] is False,
    })

    direct_spec = dict(tool_spec)
    direct_spec["allowed_callers"] = [PROGRAMMATIC_CALLER]
    direct_client = FakeClient()
    direct_result = run_mode(
        direct_client,
        "claude-sonnet-4-6",
        direct_spec,
        call_source,
        "Find the account list.",
        programmatic=False,
        label="A",
        progress=False,
    )
    direct_tool = direct_client.messages.kwargs[0]["tools"][0]
    checks.update({
        "direct strips caller guidance": "allowed_callers" not in direct_tool,
        "direct trace caller default": direct_result["trace"]["allowed_callers"] == ["direct"],
        "direct caller record": direct_result["trace"]["tool_call_records"][0]["caller_type"] == "direct",
        "direct caller tool id absent": direct_result["trace"]["tool_call_records"][0]["caller_tool_id"] is None,
        "direct container absent": direct_result["trace"]["container_ids"] == [],
        "direct no code execution": direct_result["trace"]["server_tool_use"].get("code_execution_requests", 0) == 0,
        "direct no server tool blocks": direct_result["trace"]["server_tool_blocks"] == 0,
        "direct no caller path drift": direct_result["trace"]["caller_path_drift"] is False,
    })

    drift_result = run_mode(
        FakeClient(include_programmatic_caller=False),
        "claude-sonnet-4-6",
        tool_spec,
        call_source,
        "Find the account list.",
        programmatic=True,
        label="B",
        progress=False,
    )
    drift_trace = drift_result["trace"]
    checks.update({
        "drift caller marked missing": drift_trace["tool_call_records"][0]["caller_type"] == "missing",
        "drift flag": drift_trace["caller_path_drift"] is True,
        "drift fallback reason": drift_trace["fallback_reason"] == "caller_path_drift",
        "trace gate rejects drift": any("caller_path_drift" in item for item in programmatic_trace_problems({"mode_b": drift_result})),
    })
    failures = [name for name, ok in checks.items() if not ok]
    if failures:
        print("trace eval gate: FAIL")
        print("\n".join("  " + item for item in failures))
        return 1
    print(f"trace eval gate: clean ({len(checks)} checks)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
