"""Offline tests for the cache diagnostics promotion gate."""

from engine.demonstrators import cache_diagnostics as cd


def _arm(provider, *, ran=True, root=False, fields=None, cache=True):
    return cd.ArmResult(
        provider=provider,
        model=f"{provider}-model",
        ran=ran,
        root_cause_known=root,
        miss_reason_type="system_changed" if root else "",
        missed_input_tokens=100 if root else 0,
        cache_signal_present=cache,
        diagnostic_fields=fields or [],
    )


def _absence():
    return {
        "openai": {"equivalent_found": False, "hits": []},
        "gemini": {"equivalent_found": False, "hits": []},
    }


def test_promotable_when_claude_has_reason_and_competitors_are_silent():
    verdict = cd.score(_arm("claude", root=True), [_arm("openai"), _arm("gemini")], _absence())
    assert verdict["positive_signal"] is True
    assert verdict["promotable_edge"] is True
    assert verdict["manual_suspects_eliminated"] == 3


def test_claude_needs_concrete_cache_miss_reason():
    verdict = cd.score(_arm("claude", root=False), [_arm("openai"), _arm("gemini")], _absence())
    assert verdict["positive_signal"] is False
    assert verdict["promotable_edge"] is False
    assert any("cache_miss_reason" in reason for reason in verdict["why_not_promotable"])


def test_competitor_diagnostic_field_blocks_edge():
    verdict = cd.score(
        _arm("claude", root=True),
        [_arm("openai", fields=["cache_miss_reason"]), _arm("gemini")],
        _absence(),
    )
    assert verdict["positive_signal"] is False
    assert verdict["promotable_edge"] is False


def test_docs_equivalent_blocks_edge():
    docs = {"openai": {"equivalent_found": True, "hits": ["cache_miss_reason"]}}
    verdict = cd.score(_arm("claude", root=True), [_arm("openai"), _arm("gemini")], docs)
    assert verdict["positive_signal"] is False
    assert verdict["promotable_edge"] is False


def test_diagnostic_key_finder_ignores_regular_cache_counters():
    keys = cd._diagnostic_keys({"usage": {"cached_tokens": 0}, "diagnostics": {"cache_miss_reason": {}}})
    assert keys == ["cache_miss_reason", "diagnostics"]
    assert cd._diagnostic_keys({"usage": {"cached_tokens": 0}}) == []
