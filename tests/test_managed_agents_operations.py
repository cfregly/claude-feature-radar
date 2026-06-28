"""Offline tests for the Managed Agents operations demonstrator."""

from engine.demonstrators import managed_agents_operations as mao
from engine.demonstrators.registry import REGISTRY, dispatch, register_all


def _arm(provider, stack, *, status="success", correct=True, latency=1000, tools=4, model="m"):
    return {
        "provider": provider,
        "provider_stack": stack,
        "model_id": model,
        "status": status,
        "correctness": correct,
        "latency_ms": latency,
        "tool_calls": tools,
        "retries": 0,
        "failure_reason": "" if status == "success" and correct else "failed",
        "usage": {},
        "cost_usd": 0.0,
        "teardown": "ok",
        "artifact_path": "",
        "report": mao.EXPECTED_REPORT if correct else {},
    }


def _raw(*, held=False, managed_correct=True, competitor_correct=True):
    arms = [
        _arm("anthropic", "Claude Managed Agents", correct=managed_correct, latency=8600, tools=2,
             model=mao.MANAGED_MODEL),
        _arm("anthropic", "self-managed Messages tool loop", correct=competitor_correct, latency=6100, tools=4,
             model=mao.CLAUDE_SELF_MODEL),
        _arm("openai", "OpenAI Agents SDK", correct=competitor_correct, latency=7900, tools=4,
             model=mao.OPENAI_MODEL),
        _arm("google", "Google ADK with Gemini", correct=competitor_correct, latency=14200, tools=5,
             model=mao.GEMINI_MODEL),
    ]
    if held:
        arms[2] = _arm("openai", "OpenAI Agents SDK", status="held", correct=False, latency=0, tools=0,
                       model=mao.OPENAI_MODEL)
    return {"status": "held" if held else "mechanically vetted", "arms": arms}


def test_registers_and_dispatches_distinct_from_retention_resume():
    register_all()
    assert REGISTRY["agent_runtime_operations"].demo_kind == "agent_runtime_operations"
    r = dispatch({"key": "managed_agents_operations", "axis": "operations"})
    assert r.demo_kind == "agent_runtime_operations"
    assert r.estimate.command == "make managed-agents-ops"


def test_score_report_accepts_expected_ops_report():
    ok, report, failures = mao.score_report("", mao.EXPECTED_REPORT)
    assert ok is True
    assert report["incident_id"] == "inc-042"
    assert failures == []


def test_managed_prompt_carries_evidence_not_the_expected_answer():
    prompt = mao.managed_prompt()
    assert "log-auth-1" in prompt
    assert "ticket-884" in prompt
    assert "rollback dpl-17 and invalidate auth cache" not in prompt
    assert "auth cache ttl regression" not in prompt


def test_all_correct_same_workload_is_parity_not_ahead():
    raw = _raw()
    claude, competitors = mao._split_arms(raw)
    verdict = mao._verdict_for(claude, competitors, "mechanically vetted", raw)
    assert verdict.verdict == "parity"
    assert verdict.passed is True
    assert verdict.metric["operations_advantage"] is False
    assert "Managed Agents token/API cost unavailable from session usage" in (
        verdict.metric["operations_scorecard"]["blockers"]
    )


def test_held_provider_blocks_promotion():
    raw = _raw(held=True)
    claude, competitors = mao._split_arms(raw)
    verdict = mao._verdict_for(claude, competitors, "held", raw)
    assert verdict.verdict == "never-evaluated"
    assert verdict.passed is False


def test_receipt_uses_standard_shape_and_keeps_candidate_held():
    demo = mao.ManagedAgentsOperationsDemonstrator()
    raw = _raw()
    raw["operations_scorecard"] = mao._operations_scorecard(raw["arms"])
    claude, competitors = mao._split_arms(raw)
    verdict = demo.score(claude, competitors, {"raw_compare": raw})
    receipt = demo.receipt(mao._edge(), claude, competitors, verdict,
                           {"raw_compare": raw, "estimate": demo.estimate({}, {}).to_dict()})
    assert receipt.demo_kind == "agent_runtime_operations"
    assert receipt.edge_key == "managed_agents_operations"
    assert receipt.verdict == "parity"
    assert receipt.workload["expected_report"]["incident_id"] == "inc-042"
    assert len(receipt.arms) == 4
    assert receipt.metric["operations_scorecard"]["promotion_rule"].startswith("same correctness")


def test_operations_scorecard_requires_no_worse_self_managed_cost():
    raw = _raw()
    raw["arms"][0]["usage"] = {"usage_available": False}
    raw["arms"][1]["usage"] = {
        "input_tokens": 100,
        "output_tokens": 50,
        "token_api_cost_usd": 0.00035,
    }
    scorecard = mao._operations_scorecard(raw["arms"])
    assert scorecard["same_correctness"] is True
    assert scorecard["no_worse_token_api_cost_vs_self_managed"] is False
    assert scorecard["operations_advantage"] is False
    assert "Managed Agents token/API cost unavailable from session usage" in scorecard["blockers"]


def test_operations_scorecard_blocks_even_tiny_managed_cost_increase():
    raw = _raw()
    raw["arms"][0]["usage"] = {"token_api_cost_usd": 0.0101}
    raw["arms"][1]["usage"] = {"token_api_cost_usd": 0.0100}
    scorecard = mao._operations_scorecard(raw["arms"])
    assert scorecard["no_worse_token_api_cost_vs_self_managed"] is False
    assert scorecard["operations_advantage"] is False
    assert "Managed Agents token/API cost is worse than the self-managed loop" in scorecard["blockers"]


def test_dry_compare_marks_requested_arms_held_without_sdk_imports():
    receipt = mao.run_compare(providers=["managed", "self-managed", "openai", "gemini"], live=False)
    assert receipt["status"] == "held"
    assert all(arm["status"] == "held" for arm in receipt["arms"])
    assert receipt["operations_scorecard"]["operations_advantage"] is False
    assert receipt["operations_scorecard"]["teardown"]["failed_run_probe"]["ran"] is False
