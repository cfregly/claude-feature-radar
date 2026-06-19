"""Offline tests for the mixed-inline-source grounding stack edge gate."""

from engine.demonstrators import grounding_stack as gs


def _arm(provider, *, answered=3, sources_cited=0, pointer_kinds=None, persisted_objects=0, ran=True):
    return gs.ArmResult(
        name=f"{provider}:model",
        provider=provider,
        model=f"{provider}-model",
        ran=ran,
        answered=answered,
        sources_cited=sources_cited,
        pointer_kinds=pointer_kinds or [],
        persisted_objects=persisted_objects,
    )


def test_grounding_stack_promotes_when_claude_cites_all_three_inline_types():
    run = gs.GsRun(
        arms=[
            _arm(
                "anthropic",
                sources_cited=3,
                pointer_kinds=["char_location", "page_location", "search_result_location"],
            ),
            _arm("openai", sources_cited=0),
            _arm("gemini", sources_cited=0),
        ],
        total_cost=0.1,
    )
    verdict = gs.score_run(run)
    assert verdict["positive_signal"] is True
    assert verdict["promotable_edge"] is True


def test_grounding_stack_blocks_if_claude_misses_one_source_type():
    run = gs.GsRun(
        arms=[
            _arm("anthropic", sources_cited=2, pointer_kinds=["char_location", "page_location"]),
            _arm("openai", sources_cited=0),
            _arm("gemini", sources_cited=0),
        ],
        total_cost=0.1,
    )
    verdict = gs.score_run(run)
    assert verdict["positive_signal"] is False
    assert verdict["promotable_edge"] is False


def test_grounding_stack_blocks_if_competitor_returns_inline_pointer():
    run = gs.GsRun(
        arms=[
            _arm(
                "anthropic",
                sources_cited=3,
                pointer_kinds=["char_location", "page_location", "search_result_location"],
            ),
            _arm("openai", sources_cited=1, pointer_kinds=["file_citation"]),
            _arm("gemini", sources_cited=0),
        ],
        total_cost=0.1,
    )
    verdict = gs.score_run(run)
    assert verdict["positive_signal"] is False
    assert verdict["promotable_edge"] is False
    assert any("competitor" in reason for reason in verdict["why_not_promotable"])

