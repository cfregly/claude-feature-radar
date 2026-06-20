"""Lazy OpenAI and Gemini clients plus cost helpers for a brief's optional comparison arm.

A brief runs the Claude side by default, on one dependency (anthropic). When a reader wants to
reproduce the whole Claude vs OpenAI vs Gemini table and not just the Claude side, this module gives
the brief's compare.py an OpenAI client and a Gemini client, plus the per-vendor cost math, so the
competitor arms run on the SAME workload as the Claude arm.

Every SDK import is lazy, inside the function that needs it, so importing this module (or the brief's
compare.py that builds on it) pulls no SDK and the default Claude-only run stays one dependency. A
client whose key is unset returns None, so the brief skips that arm with a clear note and never fakes
a row. Prices come from the one verified table in common/models.py, never a copy here.

This mirrors the engine's own provider callers (engine/providers/), flattened into the brief's
common/ package so the brief is self-contained on a fork. The competitor SDKs live in
requirements-compare.txt. Token accounting matches the engine: OpenAI input_tokens and Gemini
prompt_token_count both INCLUDE the cached tokens, so fresh input is the reported field minus cached,
and Gemini bills thinking at the output rate, so output is candidates plus thoughts.
"""

from __future__ import annotations

import os

from .client import load_env
from .pricing import cost_from_buckets

# What to tell a reader who has the key but not the optional SDK installed.
COMPARE_DEPS_HINT = (
    "the comparison SDKs are optional. Install them with: pip install -r requirements-compare.txt"
)


def get_openai_client():
    """An OpenAI client, or None when OPENAI_API_KEY is unset so the default run stays Claude only.

    Loads the repo's .env first, the same way the Claude client does, so a fork that pasted its key
    into .env works with no export. The SDK is imported here, lazily, so a key-absent run never needs
    `openai` installed.
    """
    load_env()
    if not os.environ.get("OPENAI_API_KEY"):
        return None
    try:
        from openai import OpenAI
    except ImportError as e:  # the optional comparison dep is not installed
        raise SystemExit("The OpenAI comparison arm needs the SDK. " + COMPARE_DEPS_HINT) from e
    return OpenAI()


def get_gemini_client():
    """A Gemini client that reads GEMINI_API_KEY, or None when that key is unset.

    The key is passed explicitly so a GOOGLE_API_KEY also present in the environment cannot override
    the one this repo sets. The SDK is imported here, lazily, so a key-absent run never needs
    `google-genai` installed.
    """
    load_env()
    if not os.environ.get("GEMINI_API_KEY"):
        return None
    try:
        from google import genai
    except ImportError as e:  # the optional comparison dep is not installed
        raise SystemExit("The Gemini comparison arm needs the SDK. " + COMPARE_DEPS_HINT) from e
    return genai.Client(api_key=os.environ["GEMINI_API_KEY"])


def openai_cost(model_key: str, usage) -> float:
    """Dollar cost of one OpenAI response from its usage object, priced by common/models.py.

    OpenAI's input_tokens INCLUDES the cached tokens, so fresh input is input minus cached. output
    already includes any reasoning tokens, the way the API reports it.
    """
    inp = getattr(usage, "input_tokens", 0) or 0
    out = getattr(usage, "output_tokens", 0) or 0
    det = getattr(usage, "input_tokens_details", None)
    cached = (getattr(det, "cached_tokens", 0) or 0) if det else 0
    return cost_from_buckets(model_key, fresh_input=max(0, inp - cached), cached=cached, output=out)


def gemini_cost(model_key: str, usage) -> float:
    """Dollar cost of one Gemini response from its usage_metadata, priced by common/models.py.

    Gemini's prompt_token_count INCLUDES the cached tokens, so fresh input is prompt minus cached, and
    thinking bills at the output rate, so output is candidates plus thoughts.
    """
    prompt = getattr(usage, "prompt_token_count", 0) or 0
    cached = getattr(usage, "cached_content_token_count", 0) or 0
    out = (getattr(usage, "candidates_token_count", 0) or 0) + (getattr(usage, "thoughts_token_count", 0) or 0)
    return cost_from_buckets(model_key, fresh_input=max(0, prompt - cached), cached=cached, output=out)
