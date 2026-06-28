"""Tests for the public hits, product-owner misses, and radar routing rules."""

from engine.outcome_routing import ROUTE_HITS, ROUTE_MISSES, ROUTE_RADAR, route_outcome


def test_claude_ahead_with_public_value_routes_to_hits():
    decision = route_outcome("claude-ahead", public_value=True)
    assert decision.route == ROUTE_HITS
    assert decision.mirror_to_misses is False


def test_claude_ahead_can_mirror_product_owner_caveat_to_misses():
    decision = route_outcome("claude-ahead", public_value=True, claim_relevant=True)
    assert decision.route == ROUTE_HITS
    assert decision.mirror_to_misses is True


def test_measured_parity_routes_to_misses():
    decision = route_outcome("parity", measured=True)
    assert decision.route == ROUTE_MISSES


def test_claim_relevant_parity_routes_to_misses():
    decision = route_outcome("parity", claim_relevant=True)
    assert decision.route == ROUTE_MISSES


def test_claude_behind_routes_to_misses():
    decision = route_outcome("claude-behind")
    assert decision.route == ROUTE_MISSES


def test_never_evaluated_stays_radar_by_default():
    decision = route_outcome("never-evaluated")
    assert decision.route == ROUTE_RADAR


def test_never_evaluated_routes_to_misses_when_it_blocks_public_claim():
    decision = route_outcome("never-evaluated", public_claim_blocking=True)
    assert decision.route == ROUTE_MISSES


def test_held_candidate_stays_radar_unless_useful_roadmap_signal():
    assert route_outcome("held-candidate").route == ROUTE_RADAR
    assert route_outcome("held-candidate", product_owner_ask=True).route == ROUTE_MISSES
