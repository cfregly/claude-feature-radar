import json

from engine.demonstrators.programmatic_tool_calling_cache_context import (
    COMMITTED_OUT_PATH,
    compute_proof,
    programmatic_tool_calling_receipt,
)


def test_programmatic_tool_calling_receipt_parses_committed_sample():
    receipt = programmatic_tool_calling_receipt()
    assert receipt["plain_tool_use_billed_input_tokens"] == 54989
    assert receipt["programmatic_tool_calling_billed_input_tokens"] == 14299
    assert receipt["input_reduction_pct"] == 74.0


def test_programmatic_tool_calling_cache_context_proves_cost_cliff():
    proof = compute_proof()
    scenarios = proof["scenarios"]
    cliff = proof["cliff"]

    assert scenarios["claude_cache_programmatic"]["total_usd"] < scenarios["claude_cache_no_programmatic"]["total_usd"]
    assert scenarios["claude_cache_programmatic"]["total_usd"] < scenarios["openai_best_cache_1m_no_programmatic"]["total_usd"]
    assert scenarios["claude_cache_programmatic"]["total_usd"] < scenarios["gemini_best_cache_1m_no_programmatic"]["total_usd"]
    assert scenarios["claude_cache_programmatic"]["total_usd"] == 26.04
    assert scenarios["openai_best_cache_1m_no_programmatic"]["total_usd"] == 135.55
    assert scenarios["gemini_best_cache_1m_no_programmatic"]["total_usd"] == 40.67
    assert cliff["reduction_vs_claude_cache_no_programmatic_pct"] > 60
    assert cliff["reduction_vs_openai_best_cache_no_programmatic_pct"] > 60
    assert cliff["reduction_vs_gemini_best_cache_no_programmatic_pct"] == 36.0


def test_programmatic_tool_calling_cache_context_requires_the_1m_window_for_the_large_prefix():
    proof = compute_proof()
    fit = proof["context_fit"]
    assert fit["prefix_tokens"] == 700_000
    assert fit["fits_claude_1m_with_programmatic_summary"] is True
    assert fit["fits_400k_context_with_prefix"] is False


def test_programmatic_tool_calling_cache_context_committed_receipt_matches_the_model():
    receipt = json.loads(COMMITTED_OUT_PATH.read_text())
    assert receipt["cliff"] == compute_proof()["cliff"]
