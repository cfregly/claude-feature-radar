"""The model registry: one verified source of truth for ids, prices, and the reasoning knobs.

Every value here is checked against the live docs and a real API call. See
docs/VERIFIED_FACTS.md for the citations and the date. Modules import from this file so a price
or a support flag is fixed in exactly one place.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Model:
    key: str            # short handle: "opus", "sonnet", "haiku", "fable"
    id: str             # the API model id string
    label: str          # human label
    tier: str
    input_per_mtok: float
    output_per_mtok: float
    cache_write_5m_per_mtok: float
    cache_write_1h_per_mtok: float
    cache_read_per_mtok: float
    context_window: int
    min_cache_tokens: int
    effort_levels: tuple[str, ...]   # () means the model has no effort knob
    thinking_mode: str               # "adaptive" | "manual" | "none"


# Verified 2026-06-17 against docs.claude.com (pricing, effort, adaptive-thinking) and a live call.
MODELS: dict[str, Model] = {
    "opus": Model(
        key="opus", id="claude-opus-4-8", label="Claude Opus 4.8", tier="frontier",
        input_per_mtok=5.0, output_per_mtok=25.0,
        cache_write_5m_per_mtok=6.25, cache_write_1h_per_mtok=10.0, cache_read_per_mtok=0.50,
        context_window=1_000_000, min_cache_tokens=1024,
        effort_levels=("low", "medium", "high", "xhigh", "max"),
        thinking_mode="adaptive",
    ),
    "sonnet": Model(
        key="sonnet", id="claude-sonnet-4-6", label="Claude Sonnet 4.6", tier="balanced",
        input_per_mtok=3.0, output_per_mtok=15.0,
        cache_write_5m_per_mtok=3.75, cache_write_1h_per_mtok=6.0, cache_read_per_mtok=0.30,
        context_window=1_000_000, min_cache_tokens=1024,
        effort_levels=("low", "medium", "high", "max"),   # no xhigh on Sonnet 4.6
        thinking_mode="adaptive",
    ),
    "haiku": Model(
        key="haiku", id="claude-haiku-4-5-20251001", label="Claude Haiku 4.5", tier="fast",
        input_per_mtok=1.0, output_per_mtok=5.0,
        cache_write_5m_per_mtok=1.25, cache_write_1h_per_mtok=2.0, cache_read_per_mtok=0.10,
        context_window=200_000, min_cache_tokens=4096,
        effort_levels=(),                  # verified: effort returns 400 on Haiku 4.5
        thinking_mode="manual",            # not on the adaptive list; left off by default here
    ),
    "fable": Model(
        key="fable", id="claude-fable-5", label="Claude Fable 5", tier="frontier-plus",
        input_per_mtok=10.0, output_per_mtok=50.0,
        cache_write_5m_per_mtok=12.50, cache_write_1h_per_mtok=20.0, cache_read_per_mtok=1.0,
        context_window=1_000_000, min_cache_tokens=512,
        effort_levels=("low", "medium", "high", "xhigh", "max"),
        thinking_mode="adaptive",          # always on; may be access-gated on a given key
    ),
}


def get(key_or_id: str) -> Model:
    """Resolve a model by short key ("opus") or full id ("claude-opus-4-8")."""
    if key_or_id in MODELS:
        return MODELS[key_or_id]
    for m in MODELS.values():
        if m.id == key_or_id:
            return m
    raise KeyError(f"unknown model: {key_or_id!r} (known: {list(MODELS)})")
