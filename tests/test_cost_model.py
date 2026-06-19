"""Offline tests for the cost_model demonstrator.

No key, no network, no SDK, no model call: the cost demonstrator is a pure pricing-model computation, so
every test drives the deterministic calculators and the demonstrator interface against the dated price
constants and the verified registry. These tests protect the load-bearing facts of a cost edge: that the
Claude prices reconcile against common/models.py, that BOTH a win regime and a lose regime resolve (the
no-cherry-pick gate), that the crossover is named, and that the verdict is a conditional, all-arms-ran
claude-ahead, never an unconditional one.

What these tests protect:
  - the demonstrator registers under "cost" and dispatch routes pricing/caching/long_context to it as a
    $0 ALWAYS demonstrator (no spend, like the discovery loop).
  - the Claude cache and input prices used in the model match common/models.py exactly (no drift).
  - edge 1 (cache TTL): the win regime beats Gemini's storage meter, and the lose regimes (high QPS,
    long hold) genuinely lose, so both sides of the crossover resolve.
  - edge 2 (long context): the win regime beats the above-200k surcharge on the cheaper tier and loses
    below the threshold, and the win is tier-honest (Opus does NOT win the band).
  - the both-regimes gate passes only when a win AND a lose regime are present and the crossover named,
    and the verdict is claude-ahead off that gate (every competitor arm, a deterministic computation, ran).
  - every grounding fact carries a dated source url.
"""

from engine.demonstrators import cost_model as cm
from engine.demonstrators.base import Arm
from engine.demonstrators.registry import REGISTRY, dispatch, register_all
from common.models import get


# ----- registration + dispatch -----

def test_cost_model_registers():
    register_all()
    demo = REGISTRY.get("cost")
    assert demo is not None
    assert demo.demo_kind == "cost"


def test_dispatch_routes_pricing_to_cost_as_a_zero_cost_always():
    register_all()
    r = dispatch({"key": "pricing", "axis": "cost"})
    assert r.covered is True
    assert r.demo_kind == "cost"
    # a pure pricing model spends nothing, so it runs in the ALWAYS lane, like the discovery loop.
    assert r.estimate is not None and r.estimate.usd == 0.0
    assert r.gate == "always"
    assert r.estimate.command == "make cost"


def test_dispatch_routes_caching_and_long_context_to_cost():
    register_all()
    for key in ("caching", "prompt_caching", "long_context"):
        r = dispatch({"key": key, "axis": "cost"})
        assert r.demo_kind == "cost", key
        assert r.covered is True, key


# ----- the Claude prices reconcile against common/models.py (no drift) -----

def test_claude_cache_bill_uses_registry_prices():
    # the 1h write must be the registry's cache_write_1h_per_mtok and the read its cache_read_per_mtok.
    m = get("sonnet")
    prefix_mtok = 50_000 / 1e6
    reads = 10
    bill = cm._claude_cache_bill("sonnet", prefix_mtok, reads)
    assert bill["write"] == prefix_mtok * m.cache_write_1h_per_mtok
    assert bill["reads"] == reads * prefix_mtok * m.cache_read_per_mtok
    assert bill["storage"] == 0.0                       # the edge: no per-hour storage fee
    assert bill["total"] == bill["write"] + bill["reads"]


def test_claude_input_bill_is_flat_at_registry_price():
    m = get("sonnet")
    big = cm._claude_input_bill("sonnet", 300_000)
    small = cm._claude_input_bill("sonnet", 50_000)
    # flat band: the per-token rate is identical above and below 200k (no surcharge).
    assert big / 300_000 == small / 50_000 == m.input_per_mtok / 1e6


def test_one_hour_write_is_two_times_base_input_in_the_registry():
    # the demonstrator's "no storage fee, flat 2x write" claim rests on this registry invariant.
    for key in ("opus", "sonnet", "haiku"):
        m = get(key)
        assert abs(m.cache_write_1h_per_mtok - 2 * m.input_per_mtok) < 1e-9
        assert abs(m.cache_read_per_mtok - 0.1 * m.input_per_mtok) < 1e-9


# ----- edge 1: cache TTL, both regimes resolve -----

def test_cache_ttl_win_regime_beats_gemini_storage_meter():
    ttl = cm.cache_ttl_regimes("sonnet")
    w = ttl["win_regime"]
    # the no-storage-fee flat cache beats Gemini's per-hour storage meter on sparse bursty reuse.
    assert w["claude_wins_vs_gemini_storage"] is True
    assert w["gemini"]["storage"] > 0                   # Gemini meters storage, Claude does not
    assert w["claude"]["storage"] == 0.0
    assert w["claude"]["total"] < w["gemini"]["total"]


def test_cache_ttl_high_qps_lose_regime_claude_is_most_expensive():
    ttl = cm.cache_ttl_regimes("sonnet")
    q = ttl["lose_regime_high_qps"]
    # at high QPS the 0.1x read multiplier is identical, so the bill is base-price-bound, Claude highest.
    assert q["claude_loses"] is True
    assert q["claude_readline"] > min(q["gemini_readline"], q["openai_readline"])


def test_cache_ttl_long_hold_lose_regime_loses_to_24h_retention():
    ttl = cm.cache_ttl_regimes("sonnet")
    h = ttl["lose_regime_long_hold"]
    # a 3h hold expires Claude's 1h cache (reprocess) and hits OpenAI's 24h extended retention.
    assert h["claude_loses"] is True
    assert h["claude_miss"]["total"] > h["openai_extended_hit"]["total"]


def test_cache_ttl_crossover_is_named():
    ttl = cm.cache_ttl_regimes("sonnet")
    assert ttl["crossover"]
    assert "1 hour" in ttl["crossover"] or "1h" in ttl["crossover"] or "60 min" in ttl["crossover"]


# ----- edge 2: long context, tier-honest win -----

def test_long_context_win_on_sonnet_beats_above_200k_surcharge():
    lc = cm.long_context_regimes("sonnet")
    w = lc["win_regime"]
    # Sonnet flat $3/MTok beats Gemini 3.1 Pro's surcharged $4/MTok above 200k.
    assert w["claude_wins"] is True
    assert w["claude_input_usd"] < w["gemini_pro_input_usd"]


def test_long_context_win_is_tier_honest_opus_does_not_win_the_band():
    # the honesty check: Opus at a flat $5/MTok is ABOVE Gemini's surcharged $4, so it does NOT win the
    # band. The demonstrator must compute the win flag, never assume it.
    lc = cm.long_context_regimes("opus")
    assert lc["win_regime"]["claude_wins"] is False


def test_long_context_lose_regime_below_threshold():
    lc = cm.long_context_regimes("sonnet")
    l = lc["lose_regime"]
    # below 200k there is no surcharge edge, and Gemini's raw sub-200k price is lower than Sonnet's flat.
    assert l["claude_loses"] is True
    assert l["claude_input_usd"] > l["gemini_pro_input_usd"]


# ----- the both-regimes honesty gate + the verdict -----

def test_both_regimes_gate_passes_with_a_win_and_a_lose_and_a_crossover():
    report = cm.cost_report("sonnet", "sonnet")
    passed, checks = cm.both_regimes_shown(report)
    assert passed is True
    assert checks["claude_wins_in_a_regime"] is True
    assert checks["claude_loses_in_a_regime"] is True
    assert checks["crossover_named_both_edges"] is True


def test_both_regimes_gate_fails_a_cherry_picked_win_only_report():
    # synthesize a report with no lose regime resolving: the gate must refuse it (a cherry-pick).
    report = cm.cost_report("sonnet", "sonnet")
    report["cache_ttl"]["lose_regime_high_qps"]["claude_loses"] = False
    report["cache_ttl"]["lose_regime_long_hold"]["claude_loses"] = False
    report["long_context"]["lose_regime"]["claude_loses"] = False
    passed, checks = cm.both_regimes_shown(report)
    assert passed is False
    assert checks["claude_loses_in_a_regime"] is False


def test_score_returns_conditional_claude_ahead_off_the_gate():
    d = cm.CostModelDemonstrator()
    claude = d.run_claude_arm({}, {})
    comps = d.run_competitor_arms({}, {})
    v = d.score(claude, comps, {})
    assert v.verdict == "claude-ahead"          # a conditional, regime-bounded, all-arms-ran lead
    assert v.passed is True
    assert "regime-bounded" in v.note


def test_competitor_arms_all_ran_so_the_lead_is_not_an_unrun_arm():
    # the competitor "arms" are deterministic price computations, so every arm always ran. This is what
    # lets the base honesty contract accept a claude-ahead verdict (it requires every competitor arm to run).
    d = cm.CostModelDemonstrator()
    comps = d.run_competitor_arms({}, {})
    assert len(comps) == 2
    assert all(a.ran for a in comps)
    providers = {a.provider for a in comps}
    assert providers == {"gemini", "openai"}


def test_receipt_is_claude_ahead_with_both_crossovers_and_dated_grounding():
    d = cm.CostModelDemonstrator()
    claude = d.run_claude_arm({}, {})
    comps = d.run_competitor_arms({}, {})
    v = d.score(claude, comps, {})
    edge = {"key": "pricing", "axis": "cost", "demoKind": "cost",
            "fair_comparison": {"lead_basis": "head-to-head"}, "claim": "conditional cost edge"}
    receipt = d.receipt(edge, claude, comps, v, {"estimate": {"usd": 0.0, "command": "make cost"}})
    assert receipt.verdict == "claude-ahead"
    assert receipt.demo_kind == "cost"
    assert receipt.cost_usd == 0.0                          # pure pricing model, no spend
    # every grounding row carries a source url and a fetch date (the OpenAI >272k row is dated later).
    assert len(receipt.grounding) == 6
    assert all(g.get("date", "").startswith("2026-") for g in receipt.grounding)
    assert all(g.get("source_url", "").startswith("http") for g in receipt.grounding)
    # both crossovers are carried into the receipt metric.
    assert receipt.metric["cache_ttl_crossover"]
    assert receipt.metric["long_context_crossover"]


def test_receipt_downgrades_when_the_gate_does_not_pass():
    # if the gate fails (a cherry-picked single-regime result), score returns never-evaluated, and the
    # receipt must carry that, never an unconditional cost win.
    from engine.demonstrators.base import Verdict
    d = cm.CostModelDemonstrator()
    claude = d.run_claude_arm({}, {})
    comps = d.run_competitor_arms({}, {})
    failed = Verdict(verdict="never-evaluated", passed=False, metric={}, note="gate did not pass")
    edge = {"key": "pricing", "axis": "cost", "demoKind": "cost",
            "fair_comparison": {"lead_basis": "head-to-head"}, "claim": "x"}
    receipt = d.receipt(edge, claude, comps, failed, {"estimate": {}})
    assert receipt.verdict == "never-evaluated"
    assert receipt.passed is False


# ----- the dated price facts -----

def test_price_facts_are_all_dated_and_sourced():
    assert len(cm.PRICE_FACTS) == 6
    for fact in cm.PRICE_FACTS:
        assert fact["date"].startswith("2026-")
        assert fact["source_url"].startswith("http")
        assert fact["claim"]


def test_estimate_is_zero_and_runs_make_cost():
    d = cm.CostModelDemonstrator()
    est = d.estimate({}, {})
    assert est.usd == 0.0                                   # no API call, $0
    assert est.command == "make cost"
