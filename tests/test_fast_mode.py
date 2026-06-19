"""Offline tests for the fast_mode validation gate."""

from engine.demonstrators import fast_mode as fm


def _arm(mode, *, ran=True, blocked=False, speed_field=None, otps=0.0, correct=True):
    return fm.ArmResult(
        provider="claude",
        model="claude-opus-4-8",
        mode=mode,
        ran=ran,
        correct=correct,
        access_blocked=blocked,
        speed_field=speed_field,
        output_tokens_per_s=otps,
    )


def _docs(*, equivalent=True):
    return {
        "openai_priority_processing": {"equivalent_found": equivalent, "hits": ["priority processing"] if equivalent else []},
        "gemini_priority_inference": {"equivalent_found": equivalent, "hits": ["priority inference"] if equivalent else []},
    }


def test_access_blocked_fast_mode_is_not_positive_signal():
    verdict = fm.score(
        _arm("standard", otps=50),
        _arm("fast", ran=False, blocked=True, speed_field=None),
        _docs(),
    )
    assert verdict["access_blocked"] is True
    assert verdict["positive_signal"] is False
    assert verdict["promotable_edge"] is False
    assert any("not enabled" in r for r in verdict["why_not_promotable"])


def test_same_model_speedup_is_positive_but_held_when_priority_competitors_are_documented():
    verdict = fm.score(
        _arm("standard", otps=50),
        _arm("fast", speed_field="fast", otps=100),
        _docs(equivalent=True),
    )
    assert verdict["positive_signal"] is True
    assert verdict["promotable_edge"] is False
    assert verdict["competitor_priority_documented"] is True
    assert any("competitor priority paths" in r for r in verdict["why_not_promotable"])


def test_speedup_requires_usage_speed_field():
    verdict = fm.score(
        _arm("standard", otps=50),
        _arm("fast", speed_field=None, otps=100),
        _docs(equivalent=False),
    )
    assert verdict["positive_signal"] is False
    assert verdict["promotable_edge"] is False
