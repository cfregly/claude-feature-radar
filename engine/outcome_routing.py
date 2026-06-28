"""Outcome routing rules for radar, hits, and misses."""

from __future__ import annotations

from dataclasses import dataclass

ROUTE_HITS = "hits"
ROUTE_MISSES = "misses"
ROUTE_RADAR = "radar"


@dataclass(frozen=True)
class RouteDecision:
    route: str
    reason: str
    mirror_to_misses: bool = False


def _norm(verdict: str) -> str:
    return (verdict or "").strip().lower().replace("_", "-")


def route_outcome(
    verdict: str,
    *,
    public_value: bool = False,
    measured: bool = False,
    claim_relevant: bool = False,
    public_claim_blocking: bool = False,
    product_owner_ask: bool = False,
    held_candidate: bool = False,
) -> RouteDecision:
    """Return the primary route for a measured or candidate outcome."""

    v = _norm(verdict)
    useful_miss_signal = claim_relevant or public_claim_blocking or product_owner_ask

    if v == "claude-ahead":
        if public_value:
            return RouteDecision(
                ROUTE_HITS,
                "verified Claude-ahead value belongs in hits",
                mirror_to_misses=useful_miss_signal,
            )
        if useful_miss_signal:
            return RouteDecision(ROUTE_MISSES, "Claude-ahead caveat is useful product-owner signal")
        return RouteDecision(ROUTE_RADAR, "Claude-ahead without public value stays internal")

    if v == "parity":
        if measured or claim_relevant:
            return RouteDecision(ROUTE_MISSES, "measured or claim-relevant parity belongs in misses")
        return RouteDecision(ROUTE_RADAR, "unmeasured parity-shaped candidate stays in radar")

    if v == "claude-behind":
        return RouteDecision(ROUTE_MISSES, "Claude-behind findings belong in misses")

    if v == "never-evaluated":
        if public_claim_blocking or product_owner_ask:
            return RouteDecision(ROUTE_MISSES, "never-evaluated item blocks a public claim or product ask")
        return RouteDecision(ROUTE_RADAR, "never-evaluated speculation stays in radar")

    if held_candidate or v in {"held", "held-candidate", "candidate"}:
        if useful_miss_signal:
            return RouteDecision(ROUTE_MISSES, "held candidate is useful roadmap signal")
        return RouteDecision(ROUTE_RADAR, "held candidate stays in radar by default")

    return RouteDecision(ROUTE_RADAR, "unknown verdict stays in radar until classified")
