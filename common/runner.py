"""The provider-blind call helper every demonstrator shares.

Ported from ship-on-claude common/runner.py. call() makes a request, times it, pulls the token
usage, and computes the exact cost, so a demonstrator gets back one Result with everything it needs
to print a receipt, no matter which vendor ran it. It dispatches on the model's provider (set in
common/models.py): Claude through the Anthropic SDK, OpenAI and Gemini through the engine.providers
callers. Every provider returns the same Result, so a grader, a grid, or a table never branches on
the vendor.

to_arm() converts a Result into the engine's standard Arm (engine/demonstrators/base.py), with the
correct carried-context bucket per vendor: on Claude input + cache_read + cache_write, on OpenAI and
Gemini the inclusive field. That is the one number that makes a long-horizon claim apples to apples
(see CLAUDE.md "Carried context is every input bucket").

The Anthropic SDK is imported lazily inside the Claude path, and the OpenAI and Gemini SDKs even more
lazily (inside engine.providers), so importing this module pulls no SDK and the one-dependency core
runs with anthropic alone. A competitor arm whose key is absent returns None from its get_*_client(),
and the demonstrator marks that arm ran=False, never faked.
"""

from __future__ import annotations

import os
import time
from dataclasses import dataclass

from common.client import load_env
from common.models import get
from common.pricing import CostBreakdown, cost_breakdown


def get_openai_client():
    """An OpenAI client, or None when OPENAI_API_KEY is unset, so the default run stays Claude only."""
    load_env()
    if not os.environ.get("OPENAI_API_KEY"):
        return None
    from engine.providers.openai_provider import get_openai_client as _impl
    return _impl()


def get_gemini_client():
    """A Gemini client, or None when GEMINI_API_KEY is unset."""
    load_env()
    if not os.environ.get("GEMINI_API_KEY"):
        return None
    from engine.providers.gemini_provider import get_gemini_client as _impl
    return _impl()


@dataclass
class Result:
    model: str
    text: str
    latency_s: float
    input_tokens: int
    output_tokens: int
    cache_read_tokens: int
    cache_write_tokens: int
    thinking_tokens: int
    cost: CostBreakdown
    raw: object  # the provider's native response object (or the provider receipt dict)
    truncated: bool = False  # True if it hit the token budget before finishing

    @property
    def cost_usd(self) -> float:
        return self.cost.total


def _text_of(message) -> str:
    parts = [b.text for b in message.content if getattr(b, "type", None) == "text"]
    return "".join(parts).strip()


@dataclass
class _Usage:
    """A minimal usage object for OpenAI and Gemini, so pricing.cost_breakdown stays provider blind."""

    input_tokens: int = 0
    output_tokens: int = 0


def call(client, model: str, messages, *, max_tokens: int = 1024, effort: str | None = None) -> Result:
    """One timed, costed request, dispatched to the model's provider. model is a key or id.

    Every provider returns the same Result, so the grader, the grid, and the tables stay provider
    blind. effort is the harness label and each provider translates it: Claude sends
    output_config.effort, OpenAI sends reasoning_effort, Gemini sends thinking_level.
    """
    m = get(model)
    if m.provider == "openai":
        return _call_openai(client, m, messages, max_tokens, effort)
    if m.provider == "gemini":
        return _call_gemini(client, m, messages, max_tokens, effort)
    return _call_anthropic(client, m, messages, max_tokens, effort)


def _call_anthropic(client, m, messages, max_tokens, effort) -> Result:
    kwargs: dict = {}
    if effort is not None and effort in m.effort_levels:
        kwargs["output_config"] = {"effort": effort}
    if m.thinking_mode == "adaptive":
        kwargs["thinking"] = {"type": "adaptive"}
    start = time.perf_counter()
    msg = client.messages.create(model=m.id, max_tokens=max_tokens, messages=messages, **kwargs)
    latency = time.perf_counter() - start
    u = msg.usage
    details = getattr(u, "output_tokens_details", None)
    thinking = getattr(details, "thinking_tokens", 0) if details else 0
    return Result(
        model=m.id,
        text=_text_of(msg),
        latency_s=latency,
        input_tokens=getattr(u, "input_tokens", 0) or 0,
        output_tokens=getattr(u, "output_tokens", 0) or 0,
        cache_read_tokens=getattr(u, "cache_read_input_tokens", 0) or 0,
        cache_write_tokens=getattr(u, "cache_creation_input_tokens", 0) or 0,
        thinking_tokens=thinking or 0,
        cost=cost_breakdown(m.key, u),
        raw=msg,
        truncated=getattr(msg, "stop_reason", None) == "max_tokens",
    )


def _result_from_provider(m, r) -> Result:
    usage = _Usage(input_tokens=r["input_tokens"], output_tokens=r["output_tokens"])
    return Result(
        model=m.id,
        text=r["text"],
        latency_s=r["latency_s"],
        input_tokens=r["input_tokens"],
        output_tokens=r["output_tokens"],
        cache_read_tokens=0,
        cache_write_tokens=0,
        thinking_tokens=0,
        cost=cost_breakdown(m.key, usage),
        raw=r,
        truncated=r["truncated"],
    )


def _call_openai(client, m, messages, max_tokens, effort) -> Result:
    from engine.providers.openai_provider import call_openai
    eff = effort if (effort is None or effort in m.effort_levels) else None
    # Forward the FULL messages list, not just the last turn. A multi-turn agentic loop must hand
    # every provider the same accumulated history Claude gets, or it measures a one-shot OpenAI against
    # a multi-turn Claude (a confound). A single-turn caller passes a one-element list, unchanged.
    return _result_from_provider(m, call_openai(client, messages, eff, m.id, max_tokens))


def _call_gemini(client, m, messages, max_tokens, effort) -> Result:
    from engine.providers.gemini_provider import call_gemini
    eff = effort if (effort is None or effort in m.effort_levels) else None
    # Forward the FULL messages list (the symmetric-loop fix), the same as the OpenAI path above.
    return _result_from_provider(m, call_gemini(client, messages, eff, m.id, max_tokens))


def to_arm(result: Result, *, provider: str | None = None, metric: dict | None = None, note: str = ""):
    """Convert a provider-blind Result into the engine's standard Arm.

    The carried-context bucket is summed per vendor: a Claude Result carries cache_read and
    cache_write separately, so ctx is input + cache_read + cache_write; an OpenAI or Gemini Result
    has those at 0 because the inclusive field already lives in input_tokens, so ctx is input_tokens.
    That keeps a long-horizon comparison apples to apples. The Arm dataclass is imported here, not at
    module top, so this module stays import-light for the offline core.
    """
    from engine.demonstrators.base import Arm

    prov = provider or get(result.model).provider
    ctx = result.input_tokens + result.cache_read_tokens + result.cache_write_tokens
    return Arm(
        provider=prov,
        model=result.model,
        text=result.text,
        ran=True,
        latency_s=result.latency_s,
        input_tokens=result.input_tokens,
        output_tokens=result.output_tokens,
        cache_read_tokens=result.cache_read_tokens,
        cache_write_tokens=result.cache_write_tokens,
        thinking_tokens=result.thinking_tokens,
        cost_usd=result.cost_usd,
        ctx=ctx,
        truncated=result.truncated,
        metric=metric or {},
        note=note,
    )

