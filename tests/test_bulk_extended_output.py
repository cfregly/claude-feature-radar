"""Offline tests for the bulk extended-output edge gate."""

from engine.demonstrators import bulk_extended_output as bulk


def _arm(provider, *, output_tokens, truncated=False, ran=True, stop_reason="end_turn"):
    return bulk.ArmResult(
        name=f"{provider}:model",
        provider=provider,
        model=f"{provider}-model",
        ran=ran,
        output_tokens=output_tokens,
        truncated=truncated,
        stop_reason=stop_reason,
    )


def test_bulk_extended_output_promotes_when_claude_exceeds_competitor_caps_untruncated():
    run = bulk.BulkRun(
        arms=[
            _arm("openai", output_tokens=764, stop_reason="completed"),
            _arm("gemini", output_tokens=32263, stop_reason="STOP"),
            _arm("anthropic", output_tokens=230607, stop_reason="end_turn"),
        ],
        n_entries=3000,
        total_cost=3.77,
    )
    verdict = bulk.score_run(run)
    assert verdict["positive_signal"] is True
    assert verdict["promotable_edge"] is True
    assert verdict["max_documented_competitor_cap"] == 128000


def test_bulk_extended_output_requires_claude_to_exceed_documented_caps():
    run = bulk.BulkRun(
        arms=[
            _arm("openai", output_tokens=764, stop_reason="completed"),
            _arm("gemini", output_tokens=32263, stop_reason="STOP"),
            _arm("anthropic", output_tokens=100000, stop_reason="end_turn"),
        ],
        n_entries=3000,
        total_cost=2.0,
    )
    verdict = bulk.score_run(run)
    assert verdict["positive_signal"] is False
    assert verdict["promotable_edge"] is False


def test_bulk_extended_output_requires_both_competitor_arms():
    run = bulk.BulkRun(
        arms=[
            _arm("openai", output_tokens=764, stop_reason="completed"),
            _arm("anthropic", output_tokens=230607, stop_reason="end_turn"),
        ],
        n_entries=3000,
        total_cost=3.0,
    )
    verdict = bulk.score_run(run)
    assert verdict["positive_signal"] is True
    assert verdict["promotable_edge"] is False
    assert any("both OpenAI and Gemini" in reason for reason in verdict["why_not_promotable"])
