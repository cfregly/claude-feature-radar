"""The Gemini arm: the same long-horizon chain agent on Google Gemini, best config.

Uses the google-genai SDK with Gemini's best long-agent setup:
  - implicit prompt caching (automatic, on by default), so the re-sent prefix is cheap.
  - full context carried. Gemini has no server-side context compaction or in-place clearing on
    the platform (only a client-side ADK toggle), so carrying the full context with caching is its
    best, the same shape as OpenAI's no-compaction config.
  - automatic function calling DISABLED so we control the loop, matching the other arms.

`google-genai` is an optional dependency. Model ids verified live on the key via models.list().

Prices verified 2026-06-17 (paid tier) against the live pricing page. The benchmark reports token
counts from usage_metadata, priced by the verified table below. See docs/VERIFIED_FACTS.md.
"""

from __future__ import annotations

import os
import time

from engine.demo import build_chain, task_prompt  # the exact same task

# per 1M tokens, paid tier, verified 2026-06-17 against ai.google.dev/gemini-api/docs/pricing
GEMINI_PRICES = {
    "gemini-3.5-flash": {"input": 1.50, "cached": 0.15, "output": 9.00},
    "gemini-3.1-flash-lite": {"input": 0.25, "cached": 0.025, "output": 1.50},
    "gemini-3.1-pro-preview": {"input": 2.00, "cached": 0.20, "output": 12.00},
}
DEFAULT_GEMINI_MODEL = "gemini-3.5-flash"

READ_TOOL_GEMINI = {
    "function_declarations": [{
        "name": "read_document",
        "description": "Read one incident report by its integer id.",
        "parameters": {
            "type": "OBJECT",
            "properties": {"doc_id": {"type": "INTEGER", "description": "the report id to read"}},
            "required": ["doc_id"],
        },
    }]
}


def _client():
    try:
        from google import genai  # noqa: F401
    except ImportError:
        raise SystemExit("The Gemini comparison needs the SDK. Run: pip install google-genai")
    if not os.environ.get("GEMINI_API_KEY"):
        raise SystemExit("GEMINI_API_KEY is not set. Add it to .env or export it.")
    from google import genai
    return genai.Client(api_key=os.environ["GEMINI_API_KEY"])


def _cost(model, um):
    p = GEMINI_PRICES.get(model, GEMINI_PRICES[DEFAULT_GEMINI_MODEL])
    prompt = getattr(um, "prompt_token_count", 0) or 0
    cached = getattr(um, "cached_content_token_count", 0) or 0
    out = (getattr(um, "candidates_token_count", 0) or 0) + (getattr(um, "thoughts_token_count", 0) or 0)
    fresh = max(0, prompt - cached)
    cost = (fresh * p["input"] + cached * p["cached"] + out * p["output"]) / 1e6
    return cost, prompt, cached, out


def _generate(client, model, contents, config, retries=6):
    """Call Gemini, backing off on transient 503 (high demand) and 429 (quota), so a long run does
    not die mid-chain. 429 backs off harder, since it is a rate or quota cap."""
    from google.genai import errors
    for i in range(retries):
        try:
            return client.models.generate_content(model=model, contents=contents, config=config)
        except errors.ClientError as e:
            if getattr(e, "code", None) == 429 and i < retries - 1:
                time.sleep(12 * (i + 1))
            else:
                raise
        except errors.ServerError:
            if i == retries - 1:
                raise
            time.sleep(3 * (i + 1))


def run_gemini_agent(docs, start, *, model=DEFAULT_GEMINI_MODEL, max_turns):
    """Run the chain audit on Gemini, implicit caching on. Returns (records, final_text, model)."""
    from google.genai import types
    client = _client()
    config = types.GenerateContentConfig(
        tools=[READ_TOOL_GEMINI],
        automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
    )
    contents = [types.Content(role="user", parts=[types.Part(text=task_prompt(start, memory=False))])]
    records, final_text = [], ""
    for turn in range(max_turns):
        t0 = time.perf_counter()
        resp = _generate(client, model, contents, config)
        dt = time.perf_counter() - t0
        cost, prompt, cached, out = _cost(model, resp.usage_metadata)
        records.append({
            "turn": turn, "input_tokens": prompt, "cache_read": cached,
            "ctx": prompt,  # prompt_token_count already includes cached, so it is the carried context
            "output_tokens": out, "cost": cost, "latency_s": dt, "cleared": 0,
        })
        fcs = resp.function_calls
        if not fcs:
            final_text = (resp.text or "") if hasattr(resp, "text") else ""
            break
        contents.append(resp.candidates[0].content)
        parts = []
        for fc in fcs:
            did = (fc.args or {}).get("doc_id")
            content = docs[did]["text"] if did in docs else f"Error: no document with id {did}"
            parts.append(types.Part.from_function_response(name=fc.name, response={"result": content}))
        contents.append(types.Content(role="user", parts=parts))
    return records, final_text, model
