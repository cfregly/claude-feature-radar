"""The OpenAI provider: a client, one call helper, and an access probe.

Ported from ship-on-claude common/openai_provider.py. It gives the cross-vendor runner an OpenAI
client and one call that returns the same shape of receipt the Claude side does: the text, the token
counts the API actually returned, the wall-clock latency, and whether the response was cut off at the
token cap. available_models() probes each candidate with a tiny real call and reports which ones the
key can reach, so an access-gated tier is reported unavailable instead of faking a row, the same
posture the Claude side takes for an access-gated tier.

The OpenAI SDK is imported lazily, inside the functions that use it, so importing this module costs
nothing and the engine's one-dependency core (anthropic only) is never pulled off `openai`. Install
`openai` from requirements-compare.txt to run a real OpenAI arm.

Uses the Responses API. Text comes back on resp.output_text. Token usage is read straight off
resp.usage so every count traces to the call, never to memory. Verified 2026-06-17 against
developers.openai.com.
"""

from __future__ import annotations

import os
import time

from common.client import load_env

# Candidate models by tier. Whether the key can call each one is decided by available_models(), never
# assumed here. The ids match the gpt-* rows in common/models.py so a probe result keys back to a price.
CANDIDATE_MODELS: dict[str, str] = {
    "cheap": "gpt-5.4-nano",
    "balanced": "gpt-5.4",
    "frontier": "gpt-5.5",
}


def get_openai_client():
    """Return an OpenAI client, or None if no key is set.

    Loads the repo's .env first, the same way the Claude client does, so a fork that pasted its key
    into .env works with no export. Returns None rather than raising so a demonstrator can skip the
    OpenAI arm cleanly (marking it ran=False) when the key is absent. The SDK is imported here, lazily,
    so a key-absent run never needs `openai` installed.
    """
    load_env()
    if not os.environ.get("OPENAI_API_KEY"):
        return None
    try:
        from openai import OpenAI
    except ImportError as e:  # the optional comparison dep is not installed
        raise SystemExit("The OpenAI arm needs the SDK. Run: pip install -r requirements-compare.txt") from e
    return OpenAI()


def _to_input(prompt) -> list:
    """Normalize the prompt argument into the Responses-API ``input`` list.

    Accepts either a plain string (one user turn) or a full multi-turn ``messages`` list
    ([{"role": "user"|"assistant", "content": "..."}, ...]). The list form is what a symmetric
    agentic loop forwards, so OpenAI sees the SAME accumulated history Claude does, never just the
    last turn. The Responses API takes role/content items directly, so a Claude-shaped messages list
    maps across with no translation.
    """
    if isinstance(prompt, str):
        return [{"role": "user", "content": prompt}]
    return [{"role": m["role"], "content": m["content"]} for m in prompt]


def call_openai(client, prompt, effort: str | None, model_id: str, max_tokens: int) -> dict:
    """One timed call. Returns the harness receipt for this response.

    ``prompt`` is either a string (one user turn) or a full multi-turn messages list, so the same
    helper serves a one-shot call and a symmetric agentic loop that forwards the whole history.

    The returned dict is exactly: text, input_tokens, output_tokens, latency_s, truncated.
    output_tokens already includes any reasoning tokens, the way the API reports it. When the response
    hits max_tokens the API marks it incomplete, which is what sets truncated. Effort is sent only when
    it is not None, so a default-effort run omits the knob.
    """
    request: dict = {
        "model": model_id,
        "input": _to_input(prompt),
        "max_output_tokens": max_tokens,
    }
    if effort is not None:
        request["reasoning"] = {"effort": effort}

    start = time.perf_counter()
    resp = client.responses.create(**request)
    latency = time.perf_counter() - start

    usage = resp.usage
    input_tokens = getattr(usage, "input_tokens", 0) or 0
    output_tokens = getattr(usage, "output_tokens", 0) or 0

    incomplete = getattr(resp, "incomplete_details", None)
    reason = getattr(incomplete, "reason", None) if incomplete else None
    truncated = getattr(resp, "status", None) == "incomplete" and reason == "max_output_tokens"

    return {
        "text": resp.output_text or "",
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "latency_s": latency,
        "truncated": truncated,
    }


def available_models() -> dict:
    """Probe each candidate model with a tiny call and report which ones the key can reach.

    Returns a dict keyed by model id, each value either {"available": True} or
    {"available": False, "error": <ExceptionTypeName>}. A 404 (NotFoundError), a 403
    (PermissionDeniedError), or an auth or bad-request error is reported as unavailable, never faked,
    matching how the Claude side handles an access-gated tier. The SDK error classes are imported
    lazily so a no-key run does not need `openai`.
    """
    client = get_openai_client()
    if client is None:
        return {mid: {"available": False, "error": "OPENAI_API_KEY unset"} for mid in CANDIDATE_MODELS.values()}

    from openai import (
        APIError,
        AuthenticationError,
        BadRequestError,
        NotFoundError,
        PermissionDeniedError,
    )

    out: dict = {}
    for model_id in CANDIDATE_MODELS.values():
        try:
            # A minimal probe. Effort "low" exercises the reasoning knob too.
            client.responses.create(
                model=model_id,
                input=[{"role": "user", "content": "ping"}],
                max_output_tokens=16,
                reasoning={"effort": "low"},
            )
            out[model_id] = {"available": True}
        except (NotFoundError, PermissionDeniedError, AuthenticationError, BadRequestError) as e:
            out[model_id] = {"available": False, "error": type(e).__name__}
        except APIError as e:
            out[model_id] = {"available": False, "error": type(e).__name__}
    return out
