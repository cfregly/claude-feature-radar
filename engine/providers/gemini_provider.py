"""The Gemini provider: a client, one call helper, and an access probe.

Ported from ship-on-claude common/gemini_provider.py. It lets the cross-vendor runner run a Gemini
model through the same call-and-receipt path the Claude side uses, returning text, token counts,
latency, and a truncation flag. Nothing in here is faked: a model the key cannot reach is reported
unavailable, the same way the Claude side reports an access-gated tier instead of pretending the call
succeeded.

The google-genai SDK is imported lazily, inside the functions that use it, so importing this module
costs nothing and the engine's one-dependency core (anthropic only) is never pulled off `google-genai`.
Install it from requirements-compare.txt to run a real Gemini arm.

Key handling. genai.Client() reads the API key from the environment. GEMINI_API_KEY is what this repo
sets. GOOGLE_API_KEY, if also set, takes precedence inside the SDK, so this module reads only
GEMINI_API_KEY and passes it explicitly, never writing GOOGLE_API_KEY.

Token accounting. Gemini bills thinking at the output rate, so the output-token count this module
returns is candidates_token_count + thoughts_token_count. That matches the bill and keeps the receipt
honest. Prices verified 2026-06-17 (paid tier) against ai.google.dev/gemini-api/docs/pricing.
"""

from __future__ import annotations

import os
import time

from common.client import load_env

# The three candidate models, one per tier. Preview ids may 404 on a given key, which is why
# available_models probes each one with a real call instead of trusting this list. The ids match the
# gem-* rows in common/models.py so a probe result keys back to a verified price.
CANDIDATE_MODELS: dict[str, str] = {
    "cheap": "gemini-3.1-flash-lite",
    "balanced": "gemini-3.5-flash",
    "frontier": "gemini-3.1-pro-preview",
}

SYSTEM_INSTRUCTION = "You are a precise coding assistant. Output only what is asked for."
# The valid Gemini 3.x thinking levels. A value outside this set is rejected by the API.
THINKING_LEVELS = ("minimal", "low", "medium", "high")


def get_gemini_client():
    """Return a genai.Client that reads GEMINI_API_KEY, or None if that key is not set.

    Calls load_env first so a forked repo with the key only in .env still works. Returns None rather
    than raising so a demonstrator can skip Gemini cleanly (marking its arm ran=False) when no key is
    present. The SDK is imported here, lazily, so a key-absent run never needs `google-genai`.
    """
    load_env()
    if not os.environ.get("GEMINI_API_KEY"):
        return None
    try:
        from google import genai
    except ImportError as e:  # the optional comparison dep is not installed
        raise SystemExit("The Gemini arm needs the SDK. Run: pip install -r requirements-compare.txt") from e
    # Pass the key explicitly so GOOGLE_API_KEY in the environment cannot override the one this repo
    # sets. The SDK would otherwise prefer GOOGLE_API_KEY.
    return genai.Client(api_key=os.environ["GEMINI_API_KEY"])


def _output_tokens(usage) -> int:
    """Output tokens billed: the answer plus the thinking, both charged at the output rate."""
    answer = getattr(usage, "candidates_token_count", 0) or 0
    thoughts = getattr(usage, "thoughts_token_count", 0) or 0
    return answer + thoughts


def _is_truncated(resp) -> bool:
    """True when the model stopped because it hit max_output_tokens.

    finish_reason can be an enum or a string across SDK versions, so this compares by name and by
    string form rather than assuming one shape.
    """
    candidates = getattr(resp, "candidates", None) or []
    if not candidates:
        return False
    reason = getattr(candidates[0], "finish_reason", None)
    if reason is None:
        return False
    name = getattr(reason, "name", None)
    return "MAX_TOKENS" in (name or "") or "MAX_TOKENS" in str(reason)


def call_gemini(client, prompt: str, effort: str | None, model_id: str, max_tokens: int) -> dict:
    """One timed Gemini call. Returns text, token counts, latency, and a truncation flag.

    effort, when set, is passed as the Gemini 3.x thinking_level ("minimal" | "low" | "medium" |
    "high"). When None, no thinking_config is sent and the model uses its default. max_tokens caps the
    output. Output tokens in the result include thinking, since that is what bills. The SDK types are
    imported lazily.
    """
    from google.genai import types

    thinking = None
    if effort is not None:
        thinking = types.ThinkingConfig(thinking_level=effort)

    config = types.GenerateContentConfig(
        system_instruction=SYSTEM_INSTRUCTION,
        thinking_config=thinking,
        max_output_tokens=max_tokens,
    )

    start = time.perf_counter()
    resp = client.models.generate_content(model=model_id, contents=prompt, config=config)
    latency = time.perf_counter() - start

    usage = getattr(resp, "usage_metadata", None)
    input_tokens = (getattr(usage, "prompt_token_count", 0) or 0) if usage else 0
    output_tokens = _output_tokens(usage) if usage else 0

    # resp.text can be None when the whole budget went to thinking and no answer text came back.
    text = getattr(resp, "text", None) or ""

    return {
        "text": text,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "latency_s": latency,
        "truncated": _is_truncated(resp),
    }


def available_models() -> dict:
    """Probe each candidate model with a tiny call and report which ones the key can reach.

    Returns a dict keyed by tier. Each value carries the model id, an available flag, and, when the
    probe failed, the error type and message. A 404 or a permission error on a preview id is reported,
    not hidden, the same posture the Claude side takes for an access-gated tier. The SDK error classes
    are imported lazily so a no-key run does not need `google-genai`.
    """
    client = get_gemini_client()
    if client is None:
        return {
            tier: {"id": mid, "available": False, "error_type": "NoKey",
                   "error": "GEMINI_API_KEY is not set"}
            for tier, mid in CANDIDATE_MODELS.items()
        }

    from google.genai import errors as genai_errors

    out: dict[str, dict] = {}
    for tier, model_id in CANDIDATE_MODELS.items():
        try:
            # Smallest possible probe: one cheap prompt, a tiny cap, no thinking.
            call_gemini(client, "Reply with the single word: ok", None, model_id, 32)
            out[tier] = {"id": model_id, "available": True, "error": None}
        except genai_errors.APIError as exc:
            # ClientError (4xx, includes 404 and permission) and ServerError both subclass this.
            out[tier] = {
                "id": model_id, "available": False, "error_type": type(exc).__name__,
                "code": getattr(exc, "code", None), "error": str(exc),
            }
        except Exception as exc:  # noqa: BLE001 - report any other failure, never fake a pass
            out[tier] = {"id": model_id, "available": False, "error_type": type(exc).__name__, "error": str(exc)}
    return out
