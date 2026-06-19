"""Offline tests for the task_budget validation gate.

The live harness spends credits and is run manually. These tests only protect the decision logic:
positive candidate signal is not enough to publish a public edge, and the public-edge gate opens
only after a real multi-tool workload shows a measured value win.
"""

from engine.demonstrators import task_budgets as tb


def _arm(provider, *, correct=True, saw_marker=False, ran=True):
    return tb.ArmResult(
        provider=provider,
        model=f"{provider}-model",
        ran=ran,
        correct_for_arm=correct,
        saw_low_budget_marker=saw_marker,
        graceful_stop=saw_marker,
    )


def _tool_arm(provider, *, tool_calls, handoff=False, saw_marker=False, ran=True):
    return tb.ArmResult(
        provider=provider,
        model=f"{provider}-model",
        ran=ran,
        correct_for_arm=True,
        saw_low_budget_marker=saw_marker,
        graceful_stop=handoff,
        tool_calls=tool_calls,
    )


def _absence():
    return {
        "openai": {"equivalent_found": False, "hits": []},
        "gemini": {"equivalent_found": False, "hits": []},
    }


def test_positive_signal_is_held_without_measured_workload_win():
    claude = _arm("claude", saw_marker=True)
    openai = _arm("openai")
    gemini = _arm("gemini")
    verdict = tb.score(claude, [openai, gemini], _absence())
    assert verdict["positive_signal"] is True
    assert verdict["promotable_edge"] is False
    assert any("measured value win" in r for r in verdict["why_not_promotable"])


def test_promotable_only_when_measured_workload_win_is_present():
    claude = _arm("claude", saw_marker=True)
    openai = _arm("openai")
    gemini = _arm("gemini")
    verdict = tb.score(claude, [openai, gemini], _absence(), measured_workload_win=True)
    assert verdict["positive_signal"] is True
    assert verdict["promotable_edge"] is True
    assert verdict["why_not_promotable"] == []


def test_tool_loop_workload_can_supply_measured_workload_win():
    claude = _arm("claude", saw_marker=True)
    openai = _arm("openai")
    gemini = _arm("gemini")
    workload = tb.summarize_tool_loop_workload(
        _tool_arm("claude", tool_calls=0, handoff=True, saw_marker=True),
        _tool_arm("claude", tool_calls=1),
        [_tool_arm("openai", tool_calls=1), _tool_arm("gemini", tool_calls=1)],
    )
    verdict = tb.score(claude, [openai, gemini], _absence(), tool_loop_workload=workload)
    assert workload["measured_workload_win"] is True
    assert verdict["promotable_edge"] is True


def test_tool_loop_workload_blocks_when_control_does_not_call_tool():
    workload = tb.summarize_tool_loop_workload(
        _tool_arm("claude", tool_calls=0, handoff=True, saw_marker=True),
        _tool_arm("claude", tool_calls=0),
        [_tool_arm("openai", tool_calls=1), _tool_arm("gemini", tool_calls=1)],
    )
    assert workload["measured_workload_win"] is False
    assert any("high-budget control" in r for r in workload["why_not_measured_win"])


def test_competitor_exact_subfeature_blocks_positive_signal():
    claude = _arm("claude", saw_marker=True)
    docs = {"openai": {"equivalent_found": True, "hits": ["task_budget"]}}
    verdict = tb.score(claude, [_arm("openai"), _arm("gemini")], docs, measured_workload_win=True)
    assert verdict["positive_signal"] is False
    assert verdict["promotable_edge"] is False


def test_competitor_marker_observation_blocks_clean_absence_claim():
    claude = _arm("claude", saw_marker=True)
    openai = _arm("openai", saw_marker=True)
    verdict = tb.score(claude, [openai, _arm("gemini")], _absence(), measured_workload_win=True)
    assert verdict["positive_signal"] is False
    assert verdict["promotable_edge"] is False


def test_action_helpers_require_matching_action_and_flag():
    assert tb._is_handoff({"action": "handoff", "graceful_stop": True}) is True
    assert tb._is_handoff({"action": "continue", "graceful_stop": True}) is False
    assert tb._is_continue({"action": "continue", "graceful_stop": False}) is True
    assert tb._is_continue({"action": "handoff", "graceful_stop": False}) is False
