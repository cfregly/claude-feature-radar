"""Offline tests for the reusable Operations scorecard."""

from engine.operations_scorecard import REQUIRED_FIELDS, build_operations_scorecard


MANAGED = "Hosted runtime"
BASELINE = "self-managed loop"


def _arm(stack, cost, *, correct=True, latency=1000):
    return {
        "provider_stack": stack,
        "correctness": correct,
        "latency_ms": latency,
        "usage": {"token_api_cost_usd": cost},
        "teardown": "delete session: ok; delete environment: ok",
    }


def _scorecard(*, managed_cost=0.01, baseline_cost=0.01, components=3, cleaner_failure_modes=True):
    teardown_probe = (
        {"ran": True, "success_rate": 1.0}
        if cleaner_failure_modes
        else {"ran": True, "success_rate": 0.0}
    )
    resume_probe = (
        {"ran": True, "state_visible_after_interruption": True, "negative_control_recovered": False}
        if cleaner_failure_modes
        else {"ran": True, "state_visible_after_interruption": False, "negative_control_recovered": True}
    )
    return build_operations_scorecard(
        [
            _arm(MANAGED, managed_cost, latency=900),
            _arm(BASELINE, baseline_cost, latency=1200),
            _arm("Competitor agent", 0.02, latency=1300),
        ],
        managed_stack=MANAGED,
        baseline_stack=BASELINE,
        components_inventory={MANAGED: {}, BASELINE: {}},
        components_avoided_vs_baseline=[{"component": f"c{i}"} for i in range(components)],
        orchestration={"managed_lines_removed_vs_self_managed": 0},
        teardown_probe=teardown_probe,
        resume_probe=resume_probe,
        managed_label="Hosted runtime",
        baseline_label="self-managed",
    )


def test_scorecard_exposes_required_operations_fields():
    scorecard = _scorecard()
    assert tuple(scorecard["required_fields"]) == REQUIRED_FIELDS
    assert scorecard["scorecard_schema"] == "operations_v1"
    assert "orchestration_lines_removed" in scorecard["required_fields"]
    assert "token_api_cost" in scorecard["required_fields"]
    assert scorecard["components"]["baseline_stack"] == BASELINE
    assert len(scorecard["components"]["avoided_vs_baseline"]) == 3


def test_operations_scorecard_promotes_only_with_same_correctness_material_reduction_and_no_worse_cost():
    scorecard = _scorecard(managed_cost=0.01, baseline_cost=0.01, components=3)
    assert scorecard["same_correctness"] is True
    assert scorecard["no_worse_token_api_cost_vs_self_managed"] is True
    assert scorecard["operations_advantage"] is True


def test_operations_scorecard_cannot_promote_when_cost_is_worse_than_baseline():
    scorecard = _scorecard(managed_cost=0.0101, baseline_cost=0.01, components=5)
    assert scorecard["no_worse_token_api_cost_vs_self_managed"] is False
    assert scorecard["operations_advantage"] is False
    assert "token/API cost is worse" in " ".join(scorecard["blockers"])


def test_operations_scorecard_cannot_promote_without_material_operations_reduction():
    scorecard = _scorecard(managed_cost=0.01, baseline_cost=0.01, components=0, cleaner_failure_modes=False)
    assert scorecard["operations_advantage"] is False
    assert "no material glue-code or failure-mode reduction measured" in scorecard["blockers"]
