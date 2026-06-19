"""Offline tests for the BYO RAG search_results citation edge gate."""

from engine.demonstrators import search_results_grounding as sr


def _arm(
    provider,
    *,
    answered=5,
    cited=5,
    asked=5,
    pointer_kind="file-level",
    setup_calls=6,
    persisted_objects=6,
):
    return sr.ArmResult(
        name=f"{provider}:model",
        provider=provider,
        model=f"{provider}-model",
        answered=answered,
        cited=cited,
        asked=asked,
        pointer_kind=pointer_kind,
        setup_calls=setup_calls,
        persisted_objects=persisted_objects,
    )


def test_search_results_promotes_when_claude_inline_and_competitors_need_hosted_stores():
    run = sr.SrRun(
        arms=[
            _arm("anthropic", pointer_kind="block-span", setup_calls=0, persisted_objects=0),
            _arm("openai", pointer_kind="file-level", setup_calls=11, persisted_objects=6),
            _arm("gemini", pointer_kind="chunk-level", setup_calls=6, persisted_objects=6),
        ],
        n_questions=5,
        total_cost=0.1,
    )
    verdict = sr.score_run(run)
    assert verdict["positive_signal"] is True
    assert verdict["promotable_edge"] is True


def test_search_results_do_not_promote_if_claude_does_not_resolve_every_chunk():
    run = sr.SrRun(
        arms=[
            _arm("anthropic", cited=4, pointer_kind="block-span", setup_calls=0, persisted_objects=0),
            _arm("openai", pointer_kind="file-level", setup_calls=11, persisted_objects=6),
            _arm("gemini", pointer_kind="chunk-level", setup_calls=6, persisted_objects=6),
        ],
        n_questions=5,
        total_cost=0.1,
    )
    verdict = sr.score_run(run)
    assert verdict["positive_signal"] is False
    assert verdict["promotable_edge"] is False


def test_search_results_do_not_promote_if_competitor_has_inline_block_span():
    run = sr.SrRun(
        arms=[
            _arm("anthropic", pointer_kind="block-span", setup_calls=0, persisted_objects=0),
            _arm("openai", pointer_kind="block-span", setup_calls=0, persisted_objects=0),
            _arm("gemini", pointer_kind="chunk-level", setup_calls=6, persisted_objects=6),
        ],
        n_questions=5,
        total_cost=0.1,
    )
    verdict = sr.score_run(run)
    assert verdict["positive_signal"] is False
    assert verdict["promotable_edge"] is False
    assert any("competitor" in r for r in verdict["why_not_promotable"])

