"""Offline tests for the dynamic web filtering validation gate.

The live harness spends credits and is run manually. These tests only protect the decision logic:
positive candidate signal is not enough to publish a public edge, and the public-edge gate opens
only when Claude beats every grounded correct competitor on the measured value axis.
"""

from engine.demonstrators import dynamic_web_filtering as dwf


def _arm(provider, *, tokens, correct=True, grounded=True, dynamic=False, ran=True):
    return dwf.ArmResult(
        provider=provider,
        model=f"{provider}-model",
        ran=ran,
        correct=correct,
        grounded=grounded,
        dynamic_filtering_exercised=dynamic,
        input_tokens=tokens,
        output_tokens=0,
    )


def _absence():
    return {
        "openai": {"equivalent_found": False, "hits": []},
        "gemini": {"equivalent_found": False, "hits": []},
    }


def test_positive_signal_is_not_promotable_until_all_competitors_are_grounded_correct():
    claude = _arm("claude", tokens=100, dynamic=True)
    openai = _arm("openai", tokens=200)
    verdict = dwf.score(claude, [openai], {"available": False}, _absence())
    assert verdict["positive_signal"] is True
    assert verdict["promotable_edge"] is False
    assert any("grounded correct" in r for r in verdict["why_not_promotable"])


def test_promotable_requires_token_win_against_grounded_correct_competitors():
    claude = _arm("claude", tokens=300, dynamic=True)
    openai = _arm("openai", tokens=200)
    verdict = dwf.score(claude, [openai], {"available": True}, _absence())
    assert verdict["positive_signal"] is True
    assert verdict["promotable_edge"] is False
    assert any("total tokens" in r for r in verdict["why_not_promotable"])


def test_promotable_when_all_gates_pass():
    claude = _arm("claude", tokens=100, dynamic=True)
    openai = _arm("openai", tokens=200)
    gemini = _arm("gemini", tokens=300)
    verdict = dwf.score(claude, [openai, gemini], {"available": True}, _absence())
    assert verdict["positive_signal"] is True
    assert verdict["promotable_edge"] is True
    assert verdict["why_not_promotable"] == []


def test_competitor_exact_subfeature_blocks_positive_signal():
    claude = _arm("claude", tokens=100, dynamic=True)
    docs = {"openai": {"equivalent_found": True, "hits": ["dynamic filtering"]}}
    verdict = dwf.score(claude, [], {"available": True}, docs)
    assert verdict["positive_signal"] is False
    assert verdict["promotable_edge"] is False


def test_answer_correct_requires_dynamic_filtering_version():
    assert dwf._answer_correct("web_search_20260209", {}) is True
    assert dwf._answer_correct("web_search_20250305", {}) is False


def test_sdk_schema_flags_track_subfeature_versions():
    flags = dwf._sdk_schema_flags_from_text("web_search_20260209 web_fetch_20260309")
    assert flags["has_web_search_20260209"] is True
    assert flags["has_web_fetch_20260309"] is True
    assert flags["has_web_search_20260318"] is False
    assert flags["has_response_inclusion"] is False


def test_discrepancy_summary_holds_response_inclusion_when_raw_api_and_sdk_reject_it():
    sdk_schema = {
        "has_web_search_20260209": True,
        "has_web_fetch_20260309": True,
        "has_web_search_20260318": False,
        "has_web_fetch_20260318": False,
        "has_response_inclusion": False,
    }
    tool_acceptance = {
        "web_search_20260209": {"accepted": True},
        "web_fetch_20260309": {"accepted": True},
        "web_search_20260318": {"accepted": False},
        "web_fetch_20260318": {"accepted": False},
    }
    raw_api = {
        "tools": {
            "web_search_20260318": {"accepted": False},
            "web_fetch_20260318": {"accepted": False},
        }
    }
    summary = dwf.summarize_new_tool_discrepancy(sdk_schema, tool_acceptance, raw_api, {})
    assert summary["sdk_has_dynamic_filtering_tags"] is True
    assert summary["server_accepts_dynamic_filtering_tags"] is True
    assert summary["sdk_has_docs_new_response_inclusion_tags"] is False
    assert summary["raw_api_accepts_docs_new_response_inclusion_tags"] is False
    assert "do not pitch response_inclusion yet" in summary["conclusion"]
