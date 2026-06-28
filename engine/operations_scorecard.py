"""Reusable Operations scorecard helpers.

The Operations bar is intentionally stricter than "the feature is convenient".
A candidate promotes only when the same workload stays correct, the managed or
hosted path removes material app-owned operations work or failure modes, and
token/API cost is no worse than the self-managed baseline.
"""

from __future__ import annotations

from typing import Any

PROMOTION_RULE = (
    "same correctness, materially less glue code or fewer failure modes, and no worse token/API cost"
)

REQUIRED_FIELDS = (
    "orchestration_lines_removed",
    "components_avoided",
    "failed_run_teardown",
    "resume_state_under_interruption",
    "time_to_first_working_agent",
    "token_api_cost",
)


def arm_by_stack(arms: list[dict[str, Any]], stack: str) -> dict[str, Any]:
    return next((arm for arm in arms if arm.get("provider_stack") == stack), {})


def token_api_cost(arm: dict[str, Any]) -> float | None:
    usage = arm.get("usage") or {}
    if "token_api_cost_usd" in usage:
        return float(usage["token_api_cost_usd"] or 0.0)
    if "cost_usd" in arm and arm.get("cost_usd"):
        return float(arm["cost_usd"] or 0.0)
    return None


def teardown_success_from_text(teardown: str) -> bool | None:
    if not teardown or teardown == "not applicable" or teardown == "not started":
        return None
    parts = [part.strip() for part in teardown.split(";") if part.strip()]
    if not parts:
        return None
    return all(part.endswith(": ok") for part in parts)


def build_operations_scorecard(
    arms: list[dict[str, Any]],
    *,
    managed_stack: str,
    baseline_stack: str,
    components_inventory: dict[str, Any],
    components_avoided_vs_baseline: list[dict[str, Any]],
    orchestration: dict[str, Any],
    teardown_probe: dict[str, Any] | None = None,
    resume_probe: dict[str, Any] | None = None,
    lines_removed_key: str = "managed_lines_removed_vs_self_managed",
    material_lines_threshold: int = 20,
    material_components_threshold: int = 3,
    managed_label: str | None = None,
    baseline_label: str | None = None,
    cost_worse_label: str | None = None,
) -> dict[str, Any]:
    """Build the shared Operations scorecard used by radar demonstrators."""

    managed = arm_by_stack(arms, managed_stack)
    baseline = arm_by_stack(arms, baseline_stack)
    competitors = [arm for arm in arms if arm.get("provider_stack") != managed_stack]
    teardown_probe = teardown_probe or {"ran": False, "reason": "not requested"}
    resume_probe = resume_probe or {"ran": False, "reason": "not requested"}
    managed_label = managed_label or managed_stack
    baseline_label = baseline_label or baseline_stack

    managed_cost = token_api_cost(managed)
    baseline_cost = token_api_cost(baseline)
    managed_correct = bool(managed.get("correctness"))
    competitors_correct = bool(competitors) and all(bool(arm.get("correctness")) for arm in competitors)

    teardown_success = teardown_success_from_text(str(managed.get("teardown", "")))
    teardown_rate = teardown_probe.get("success_rate")
    if teardown_rate is None and teardown_success is not None:
        teardown_rate = 1.0 if teardown_success else 0.0

    no_worse_cost = (
        managed_cost is not None
        and baseline_cost is not None
        and managed_cost <= baseline_cost
    )
    lines_removed = int(orchestration.get(lines_removed_key, 0) or 0)
    material_loc_reduction = lines_removed >= material_lines_threshold
    material_component_reduction = len(components_avoided_vs_baseline) >= material_components_threshold
    cleaner_failure_modes = (
        bool(teardown_probe.get("ran"))
        and float(teardown_probe.get("success_rate", 0.0) or 0.0) >= 0.95
        and bool(resume_probe.get("ran"))
        and bool(resume_probe.get("state_visible_after_interruption"))
        and resume_probe.get("negative_control_recovered") is False
    )

    operations_advantage = (
        managed_correct
        and competitors_correct
        and no_worse_cost
        and (material_loc_reduction or material_component_reduction or cleaner_failure_modes)
    )

    blockers: list[str] = []
    if not managed_correct or not competitors_correct:
        blockers.append("same-correctness gate not satisfied")
    if managed_cost is None:
        blockers.append(f"{managed_label} token/API cost unavailable from session usage")
    if baseline_cost is None:
        blockers.append(f"{baseline_label} token/API cost unavailable")
    if managed_cost is not None and baseline_cost is not None and not no_worse_cost:
        blockers.append(cost_worse_label or f"{managed_label} token/API cost is worse than {baseline_label}")
    if not (material_loc_reduction or material_component_reduction or cleaner_failure_modes):
        blockers.append("no material glue-code or failure-mode reduction measured")
    if not bool(teardown_probe.get("ran")):
        blockers.append("repeated failed-run teardown probe not run")
    if not bool(resume_probe.get("ran")):
        blockers.append("interruption resume probe not run")

    return {
        "scorecard_schema": "operations_v1",
        "required_fields": list(REQUIRED_FIELDS),
        "same_correctness": managed_correct and competitors_correct,
        "operations_advantage": operations_advantage,
        "promotion_rule": PROMOTION_RULE,
        "orchestration": orchestration,
        "components": {
            "inventory": components_inventory,
            "managed_stack": managed_stack,
            "baseline_stack": baseline_stack,
            "avoided_vs_baseline": components_avoided_vs_baseline,
            "managed_avoided_vs_self_managed": components_avoided_vs_baseline,
            "managed_avoided_count": len(components_avoided_vs_baseline),
        },
        "teardown": {
            "single_run_success": teardown_success,
            "failed_run_probe": teardown_probe,
            "effective_success_rate": teardown_rate,
        },
        "resume": resume_probe,
        "time_to_first_working_agent_ms": {
            arm.get("provider_stack", arm.get("provider", "")): arm.get("latency_ms", 0)
            for arm in arms
            if arm.get("correctness")
        },
        "token_api_cost_usd": {
            arm.get("provider_stack", arm.get("provider", "")): token_api_cost(arm)
            for arm in arms
        },
        "no_worse_token_api_cost_vs_self_managed": no_worse_cost,
        "blockers": blockers,
    }
