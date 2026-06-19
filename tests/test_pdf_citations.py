"""Offline tests for the direct-PDF citation edge gate."""

from engine.demonstrators import pdf_citations as pc


def _arm(provider, *, answered=5, cited=0, page_correct=0, asked=5):
    return pc.ArmResult(
        name=f"{provider}:model",
        provider=provider,
        model=f"{provider}-model",
        answered=answered,
        cited=cited,
        page_correct=page_correct,
        asked=asked,
    )


def test_direct_pdf_citations_promote_when_claude_pages_resolve_and_competitors_have_no_pointer():
    run = pc.PdfRun(
        arms=[
            _arm("anthropic", answered=5, cited=5, page_correct=5),
            _arm("openai", answered=5, cited=0, page_correct=0),
            _arm("gemini", answered=5, cited=0, page_correct=0),
        ],
        n_questions=5,
        total_cost=0.1,
    )
    verdict = pc.score_run(run)
    assert verdict["positive_signal"] is True
    assert verdict["promotable_edge"] is True


def test_direct_pdf_citations_do_not_promote_if_competitor_has_pointer():
    run = pc.PdfRun(
        arms=[
            _arm("anthropic", answered=5, cited=5, page_correct=5),
            _arm("openai", answered=5, cited=1, page_correct=0),
            _arm("gemini", answered=5, cited=0, page_correct=0),
        ],
        n_questions=5,
        total_cost=0.1,
    )
    verdict = pc.score_run(run)
    assert verdict["positive_signal"] is False
    assert verdict["promotable_edge"] is False
    assert any("competitor" in r for r in verdict["why_not_promotable"])


def test_direct_pdf_citations_require_correct_claude_pages():
    run = pc.PdfRun(
        arms=[
            _arm("anthropic", answered=5, cited=5, page_correct=4),
            _arm("openai", answered=5, cited=0, page_correct=0),
            _arm("gemini", answered=5, cited=0, page_correct=0),
        ],
        n_questions=5,
        total_cost=0.1,
    )
    verdict = pc.score_run(run)
    assert verdict["positive_signal"] is False
    assert verdict["promotable_edge"] is False
