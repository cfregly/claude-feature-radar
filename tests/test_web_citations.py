"""Offline tests for the web citation source-quote edge gate."""

from engine.demonstrators import web_citations as wc


def _arm(provider, *, answered=3, asked=3, web_citations=3, source_quotes=0, ran=True):
    return wc.ArmResult(
        name=f"{provider}:model",
        provider=provider,
        model=f"{provider}-model",
        ran=ran,
        asked=asked,
        answered=answered,
        web_citations=web_citations,
        source_quote_citations=source_quotes,
    )


def test_web_citations_promote_when_claude_quotes_sources_and_competitors_cite_urls_only():
    run = wc.WcRun(
        arms=[
            _arm("anthropic", web_citations=9, source_quotes=9),
            _arm("openai", web_citations=3, source_quotes=0),
            _arm("gemini", web_citations=6, source_quotes=0),
        ],
        n_questions=3,
        total_cost=0.1,
    )
    verdict = wc.score_run(run)
    assert verdict["positive_signal"] is True
    assert verdict["promotable_edge"] is True


def test_web_citations_do_not_promote_if_claude_lacks_source_quotes():
    run = wc.WcRun(
        arms=[
            _arm("anthropic", web_citations=9, source_quotes=8),
            _arm("openai", web_citations=3, source_quotes=0),
            _arm("gemini", web_citations=6, source_quotes=0),
        ],
        n_questions=3,
        total_cost=0.1,
    )
    verdict = wc.score_run(run)
    assert verdict["positive_signal"] is False
    assert verdict["promotable_edge"] is False


def test_web_citations_do_not_promote_if_competitor_returns_source_quote():
    run = wc.WcRun(
        arms=[
            _arm("anthropic", web_citations=9, source_quotes=9),
            _arm("openai", web_citations=3, source_quotes=1),
            _arm("gemini", web_citations=6, source_quotes=0),
        ],
        n_questions=3,
        total_cost=0.1,
    )
    verdict = wc.score_run(run)
    assert verdict["positive_signal"] is False
    assert verdict["promotable_edge"] is False
    assert any("competitor" in reason for reason in verdict["why_not_promotable"])
