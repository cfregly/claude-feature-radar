import json

from engine.demonstrators.ptc_cache_context import COMMITTED_OUT_PATH, compute_proof, ptc_receipt


def test_ptc_receipt_parses_committed_sample():
    receipt = ptc_receipt()
    assert receipt["plain_tool_use_billed_input_tokens"] == 9494
    assert receipt["programmatic_tool_calling_billed_input_tokens"] == 6910
    assert receipt["input_reduction_pct"] == 27.2


def test_ptc_cache_context_proves_cache_plus_ptc_cliff():
    proof = compute_proof()
    scenarios = proof["scenarios"]
    cliff = proof["cliff"]

    assert scenarios["claude_cache_ptc"]["total_usd"] < scenarios["claude_cache_no_ptc"]["total_usd"]
    assert scenarios["claude_cache_ptc"]["total_usd"] < scenarios["openai_best_cache_1m_no_ptc"]["total_usd"]
    assert scenarios["claude_cache_ptc"]["total_usd"] < scenarios["gemini_best_cache_1m_no_ptc"]["total_usd"]
    assert scenarios["claude_cache_ptc"]["total_usd"] == 26.04
    assert scenarios["openai_best_cache_1m_no_ptc"]["total_usd"] == 135.55
    assert scenarios["gemini_best_cache_1m_no_ptc"]["total_usd"] == 40.67
    assert cliff["reduction_vs_claude_cache_no_ptc_pct"] > 60
    assert cliff["reduction_vs_openai_best_cache_no_ptc_pct"] > 60
    assert cliff["reduction_vs_gemini_best_cache_no_ptc_pct"] == 36.0


def test_ptc_cache_context_requires_the_1m_window_for_the_large_prefix():
    proof = compute_proof()
    fit = proof["context_fit"]
    assert fit["prefix_tokens"] == 700_000
    assert fit["fits_claude_1m_with_ptc_summary"] is True
    assert fit["fits_400k_context_with_prefix"] is False


def test_ptc_cache_context_committed_receipt_matches_the_model():
    receipt = json.loads(COMMITTED_OUT_PATH.read_text())
    assert receipt["cliff"] == compute_proof()["cliff"]
