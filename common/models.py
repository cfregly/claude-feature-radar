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
    provider: str = "anthropic"      # "anthropic" | "openai" | "gemini"


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
    # OpenAI and Gemini comparison models. This is the ONE verified competitor price table: the OpenAI
    # and Gemini arms (engine/openai_arm.py, engine/gemini_arm.py) and the citations DIY arms all read
    # cost from these rows, never a local copy. Input, cached-input, and output prices re-verified live
    # 2026-06-18 against the providers' pricing pages (developers.openai.com/api/docs/pricing,
    # ai.google.dev/gemini-api/docs/pricing), Standard tier, every id present and matching. cache_read
    # is the providers' discounted cached-input tier (the cached column on those pages). The cache_write
    # fields stay 0 on purpose: OpenAI automatic caching and Gemini implicit caching charge no separate
    # cache-WRITE fee, only the cheaper read on a hit, so there is nothing to bill there. These rows run
    # only when the matching key is set, and the cross-vendor runner pulls the SDK lazily, so the
    # one-dependency core is untouched. effort is the harness label sent straight through (OpenAI
    # reasoning_effort, Gemini thinking_level, both take low/medium/high). "minimal" is excluded: OpenAI
    # rejects it with a 400. Gemini's long-context (>200k) and audio rate tiers are not modeled here; the
    # benchmark workloads are text under 200k, so the Standard text rate is the one that bills.
    "gpt-nano": Model(
        key="gpt-nano", id="gpt-5.4-nano", label="GPT-5.4 nano", tier="fast", provider="openai",
        input_per_mtok=0.20, output_per_mtok=1.25,
        cache_write_5m_per_mtok=0.0, cache_write_1h_per_mtok=0.0, cache_read_per_mtok=0.02,
        context_window=400_000, min_cache_tokens=0,
        effort_levels=("low", "medium", "high"), thinking_mode="none",
    ),
    "gpt-mini": Model(
        # The citations DIY arm's default OpenAI model and the legacy long-horizon arm's default: the
        # cheapest tier the docs recommend as a capable multi-step tool driver (nano is cheaper but a
        # weaker driver). It produced the committed edges/citations receipt, so it is a first-class row.
        key="gpt-mini", id="gpt-5.4-mini", label="GPT-5.4 mini", tier="fast-mid", provider="openai",
        input_per_mtok=0.75, output_per_mtok=4.50,
        cache_write_5m_per_mtok=0.0, cache_write_1h_per_mtok=0.0, cache_read_per_mtok=0.075,
        context_window=400_000, min_cache_tokens=0,
        effort_levels=("low", "medium", "high"), thinking_mode="none",
    ),
    "gpt-mid": Model(
        key="gpt-mid", id="gpt-5.4", label="GPT-5.4", tier="balanced", provider="openai",
        input_per_mtok=2.50, output_per_mtok=15.0,
        cache_write_5m_per_mtok=0.0, cache_write_1h_per_mtok=0.0, cache_read_per_mtok=0.25,
        context_window=1_050_000, min_cache_tokens=0,
        effort_levels=("low", "medium", "high"), thinking_mode="none",
    ),
    "gpt-top": Model(
        key="gpt-top", id="gpt-5.5", label="GPT-5.5", tier="frontier", provider="openai",
        input_per_mtok=5.0, output_per_mtok=30.0,
        cache_write_5m_per_mtok=0.0, cache_write_1h_per_mtok=0.0, cache_read_per_mtok=0.50,
        context_window=1_050_000, min_cache_tokens=0,
        effort_levels=("low", "medium", "high"), thinking_mode="none",
    ),
    "gem-lite": Model(
        key="gem-lite", id="gemini-3.1-flash-lite", label="Gemini 3.1 Flash-Lite", tier="fast",
        provider="gemini",
        input_per_mtok=0.25, output_per_mtok=1.50,
        cache_write_5m_per_mtok=0.0, cache_write_1h_per_mtok=0.0, cache_read_per_mtok=0.025,
        context_window=1_000_000, min_cache_tokens=0,
        effort_levels=("low", "medium", "high"), thinking_mode="none",
    ),
    "gem-flash": Model(
        key="gem-flash", id="gemini-3.5-flash", label="Gemini 3.5 Flash", tier="balanced",
        provider="gemini",
        input_per_mtok=1.50, output_per_mtok=9.0,
        cache_write_5m_per_mtok=0.0, cache_write_1h_per_mtok=0.0, cache_read_per_mtok=0.15,
        context_window=1_000_000, min_cache_tokens=0,
        effort_levels=("low", "medium", "high"), thinking_mode="none",
    ),
    "gem-pro": Model(
        key="gem-pro", id="gemini-3.1-pro-preview", label="Gemini 3.1 Pro", tier="frontier",
        provider="gemini",
        input_per_mtok=2.0, output_per_mtok=12.0,
        cache_write_5m_per_mtok=0.0, cache_write_1h_per_mtok=0.0, cache_read_per_mtok=0.20,
        context_window=1_000_000, min_cache_tokens=0,
        effort_levels=("low", "medium", "high"), thinking_mode="none",
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


def supports_effort(key_or_id: str) -> bool:
    return bool(get(key_or_id).effort_levels)


def supports_effort_level(key_or_id: str, level: str) -> bool:
    return level in get(key_or_id).effort_levels


def thinking_param(key_or_id: str):
    """The thinking config to send for this model, or None to omit it."""
    return {"type": "adaptive"} if get(key_or_id).thinking_mode == "adaptive" else None


def request_kwargs(key_or_id: str, effort: str | None = None, adaptive_thinking: bool = False) -> dict:
    """Build valid messages.create() kwargs for a Claude model, dropping knobs the model rejects.

    The function that keeps a request from 400ing: it omits effort on models without it (Haiku), and
    only sends adaptive thinking where it is supported. Merged from ship-on-claude common/models.py so
    every demonstrator's Claude arm builds its request the same way.
    """
    m = get(key_or_id)
    kw: dict = {"model": m.id}
    if effort is not None and supports_effort_level(m.key, effort):
        kw["output_config"] = {"effort": effort}
    if adaptive_thinking and m.thinking_mode == "adaptive":
        kw["thinking"] = {"type": "adaptive"}
    return kw
