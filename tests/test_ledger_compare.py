"""Offline tests for the exact-list ledger promotability gate."""

from engine import ledger_compare as lc


def _row(name, *, exact=True, cost=1.0, elapsed=10.0, crashed=False):
    return {
        "platform": name,
        "crashed": crashed,
        "cost": cost,
        "elapsed_s": elapsed,
        "score": {"exact": exact},
    }


def test_promotable_when_all_exact_and_claude_wins_cost_and_time():
    rows = [
        _row("Claude Haiku 4.5 (context editing)", cost=1.0, elapsed=10.0),
        _row("OpenAI gpt-5.5 (compaction)", cost=2.0, elapsed=20.0),
        _row("Gemini gemini-3.1-pro-preview (full context)", cost=3.0, elapsed=30.0),
    ]
    verdict = lc.verdict(rows)
    assert verdict["positive_signal"] is True
    assert verdict["promotable_edge"] is True
    assert verdict["why_not_promotable"] == []


def test_not_promotable_when_competitor_is_not_exact():
    rows = [
        _row("Claude Haiku 4.5 (context editing)", cost=1.0, elapsed=10.0),
        _row("OpenAI gpt-5.5 (compaction)", exact=False, cost=2.0, elapsed=20.0),
        _row("Gemini gemini-3.1-pro-preview (full context)", cost=3.0, elapsed=30.0),
    ]
    verdict = lc.verdict(rows)
    assert verdict["positive_signal"] is True
    assert verdict["promotable_edge"] is False
    assert any("not every competitor" in r for r in verdict["why_not_promotable"])


def test_not_promotable_when_claude_loses_cost_or_time():
    rows = [
        _row("Claude Haiku 4.5 (context editing)", cost=4.0, elapsed=10.0),
        _row("OpenAI gpt-5.5 (compaction)", cost=2.0, elapsed=20.0),
        _row("Gemini gemini-3.1-pro-preview (full context)", cost=3.0, elapsed=30.0),
    ]
    verdict = lc.verdict(rows)
    assert verdict["positive_signal"] is True
    assert verdict["promotable_edge"] is False
    assert any("cost" in r for r in verdict["why_not_promotable"])


def test_positive_signal_requires_claude_exact():
    rows = [
        _row("Claude Haiku 4.5 (context editing)", exact=False, cost=1.0, elapsed=10.0),
        _row("OpenAI gpt-5.5 (compaction)", cost=2.0, elapsed=20.0),
        _row("Gemini gemini-3.1-pro-preview (full context)", cost=3.0, elapsed=30.0),
    ]
    verdict = lc.verdict(rows)
    assert verdict["positive_signal"] is False
    assert verdict["promotable_edge"] is False
