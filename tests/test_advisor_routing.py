"""Offline tests for the advisor-routing promotion gate."""

from engine.demonstrators import advisor_routing as ar


def _arm(
    name,
    provider,
    *,
    correct=8,
    graded=8,
    test_correct=4,
    test_graded=4,
    cost=1.0,
    advisor_calls=0,
):
    return ar.ArmResult(
        name=name,
        provider=provider,
        model=f"{provider}-model",
        correct=correct,
        graded=graded,
        test_correct=test_correct,
        test_graded=test_graded,
        cost=cost,
        advisor_calls=advisor_calls,
    )


def test_advisor_routing_promotes_cost_at_quality_win():
    run = ar.AdvisorRun(
        arms=[
            _arm("claude:sonnet+opus-advisor", "anthropic", cost=1.0, advisor_calls=8),
            _arm("claude:opus-solo", "anthropic", cost=2.0),
            _arm("claude:sonnet-solo", "anthropic", correct=6, test_correct=2, cost=0.5),
            _arm("openai:gpt-top", "openai", cost=3.0),
            _arm("gemini:gem-pro", "gemini", cost=2.5),
            _arm("openai:gpt-mini", "openai", correct=5, test_correct=2, cost=0.2),
            _arm("gemini:gem-flash", "gemini", correct=5, test_correct=2, cost=0.2),
        ],
        n_problems=8,
        n_test=4,
        total_cost=9.2,
    )
    verdict = ar.score_run(run)
    assert verdict["positive_signal"] is True
    assert verdict["promotable_edge"] is True


def test_advisor_routing_blocks_if_quality_peer_is_cheaper():
    run = ar.AdvisorRun(
        arms=[
            _arm("claude:sonnet+opus-advisor", "anthropic", cost=1.0, advisor_calls=8),
            _arm("claude:opus-solo", "anthropic", cost=2.0),
            _arm("openai:gpt-top", "openai", cost=0.5),
            _arm("gemini:gem-pro", "gemini", cost=2.5),
        ],
        n_problems=8,
        n_test=4,
        total_cost=6.0,
    )
    verdict = ar.score_run(run)
    assert verdict["positive_signal"] is False
    assert verdict["promotable_edge"] is False
    assert any("competitor" in reason for reason in verdict["why_not_promotable"])


def test_advisor_routing_blocks_if_advisor_not_used_for_every_problem():
    run = ar.AdvisorRun(
        arms=[
            _arm("claude:sonnet+opus-advisor", "anthropic", cost=1.0, advisor_calls=4),
            _arm("claude:opus-solo", "anthropic", cost=2.0),
            _arm("openai:gpt-top", "openai", cost=3.0),
            _arm("gemini:gem-pro", "gemini", cost=2.5),
        ],
        n_problems=8,
        n_test=4,
        total_cost=8.5,
    )
    verdict = ar.score_run(run)
    assert verdict["positive_signal"] is False
    assert verdict["promotable_edge"] is False
    assert any("advisor tool" in reason for reason in verdict["why_not_promotable"])


def test_advisor_routing_blocks_if_frontier_competitor_missing():
    run = ar.AdvisorRun(
        arms=[
            _arm("claude:sonnet+opus-advisor", "anthropic", cost=1.0, advisor_calls=8),
            _arm("claude:opus-solo", "anthropic", cost=2.0),
            _arm("openai:gpt-top", "openai", cost=3.0),
        ],
        n_problems=8,
        n_test=4,
        total_cost=6.0,
    )
    verdict = ar.score_run(run)
    assert verdict["positive_signal"] is False
    assert verdict["promotable_edge"] is False
    assert any("frontier" in reason for reason in verdict["why_not_promotable"])

