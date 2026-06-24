"""Offline tests for the deep-loop budget preflight.

No key, no network, no model call. The budget ledger is redirected to a temp repo and fed synthetic
usage objects, so the tests only protect the accounting boundary around verify/combine.
"""

import json

import pytest

from engine.budget import BudgetLedger, estimate_cost_usd, estimate_tokens


class _Usage:
    def __init__(self, **kw):
        for k, v in kw.items():
            setattr(self, k, v)


def test_estimate_tokens_is_padded_and_deterministic():
    assert estimate_tokens("abcd") >= 257
    assert estimate_tokens({"b": 2, "a": 1}) == estimate_tokens({"a": 1, "b": 2})


def test_preflight_blocks_when_estimate_crosses_cap(tmp_path):
    budget = BudgetLedger(0.01, label="test", root=tmp_path)
    with pytest.raises(SystemExit) as e:
        budget.preflight("too-big", "opus", messages=[{"role": "user", "content": "x"}],
                         max_tokens=8000, system="sys")
    assert "Budget preflight blocked" in str(e.value)
    assert not budget.path.exists()


def test_preflight_reserves_and_commit_replaces_estimate_with_actual(tmp_path):
    budget = BudgetLedger(2.0, label="test", root=tmp_path)
    reservation = budget.preflight("verify", "opus", messages=[{"role": "user", "content": "x"}],
                                   max_tokens=8000, system="sys")
    data = json.loads(budget.path.read_text())
    assert data["records"][0]["status"] == "reserved"
    assert data["records"][0]["estimated_usd"] == round(reservation.estimated_usd, 6)

    actual = budget.commit_usage(reservation, _Usage(input_tokens=1000, output_tokens=200))
    data = json.loads(budget.path.read_text())
    assert data["records"][0]["status"] == "actual"
    assert data["records"][0]["actual_usd"] == round(actual, 6)
    assert data["spent_or_reserved_usd"] == round(actual, 6)


def test_openai_xhigh_estimate_uses_gpt_top_price():
    tokens = estimate_tokens("short prompt")
    assert estimate_cost_usd("gpt-top", input_tokens=tokens, max_output_tokens=1000) > 0
