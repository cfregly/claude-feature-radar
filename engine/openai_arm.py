"""The OpenAI arm: the same long-horizon chain agent on OpenAI's LATEST API, best config.

Uses the Responses API (not Chat Completions) with every best-feature ON, so the fight is fair:
  - server-side compaction ON (context_management compaction), so OpenAI trims its carried
    context the same way Claude's context editing does. The threshold is matched to the Claude
    trigger, so neither side is configured to carry more than the other.
  - automatic prompt caching (on by default, nothing to set).
  - parallel tool calls left at the default (the natural mode).
  - server-stored conversation (previous_response_id), so compaction actually bounds the context
    instead of us re-sending the whole transcript each turn.

A fair fight needs both sides at full strength. This is OpenAI at full strength on purpose.

Verified 2026-06-17 against developers.openai.com. `openai` is an optional dependency.
"""

from __future__ import annotations

import json
import os
import time

from engine.demo import build_chain, task_prompt  # the exact same task

# per 1M tokens, verified 2026-06-17 (developers.openai.com/api/docs/pricing)
OPENAI_PRICES = {
    "gpt-5.4-mini": {"input": 0.75, "cached": 0.075, "output": 4.50},
    "gpt-5.4-nano": {"input": 0.20, "cached": 0.02, "output": 1.25},
}
# why gpt-5.4-mini: the cheapest tier the docs recommend as a capable multi-step tool driver.
# nano is cheaper but a weaker driver. The choice is documented so a founder can swap it.
DEFAULT_OPENAI_MODEL = "gpt-5.4-mini"

READ_TOOL_OAI = {
    "type": "function",
    "name": "read_document",
    "description": "Read one incident report by its integer id.",
    "parameters": {
        "type": "object",
        "properties": {"doc_id": {"type": "integer", "description": "the report id to read"}},
        "required": ["doc_id"],
        "additionalProperties": False,
    },
}


def _client():
    try:
        from openai import OpenAI
    except ImportError:
        raise SystemExit("The comparison needs the OpenAI SDK. Run: pip install openai")
    if not os.environ.get("OPENAI_API_KEY"):
        raise SystemExit("OPENAI_API_KEY is not set. Add it to .env or export it.")
    return OpenAI()


def _cost(model, usage):
    p = OPENAI_PRICES.get(model, OPENAI_PRICES[DEFAULT_OPENAI_MODEL])
    inp = getattr(usage, "input_tokens", 0) or 0
    out = getattr(usage, "output_tokens", 0) or 0
    det = getattr(usage, "input_tokens_details", None)
    cached = (getattr(det, "cached_tokens", 0) or 0) if det else 0
    fresh = max(0, inp - cached)
    cost = (fresh * p["input"] + cached * p["cached"] + out * p["output"]) / 1e6
    return cost, inp, cached


def run_openai_agent(docs, start, *, model=DEFAULT_OPENAI_MODEL, compact_threshold=None, max_turns):
    """Run the chain audit on OpenAI, caching always on, compaction on if compact_threshold is set.

    compact_threshold=None means no compaction (carry the full context, let caching make the
    re-send cheap), which is OpenAI's other best config. Returns (records, final_text, model).
    """
    client = _client()
    cm = [{"type": "compaction", "compact_threshold": compact_threshold}] if compact_threshold else None
    prev_id = None
    pending = [{"role": "user", "content": task_prompt(start, managed=False)}]
    records, final_text = [], ""
    for turn in range(max_turns):
        kwargs = dict(model=model, tools=[READ_TOOL_OAI], store=True, input=pending)
        if cm is not None:
            kwargs["context_management"] = cm
        if prev_id is not None:
            # server-stored style: the prior turn's items live server-side (compacted), so we
            # send only the new tool outputs. This is what lets compaction bound the context.
            kwargs["previous_response_id"] = prev_id
        t0 = time.perf_counter()
        resp = client.responses.create(**kwargs)
        dt = time.perf_counter() - t0
        prev_id = resp.id
        cost, inp, cached = _cost(model, resp.usage)
        records.append({
            "turn": turn, "input_tokens": inp, "cache_read": cached,
            "output_tokens": getattr(resp.usage, "output_tokens", 0) or 0,
            "cost": cost, "latency_s": dt, "cleared": 0,
        })
        calls = [it for it in resp.output if getattr(it, "type", None) == "function_call"]
        if not calls:
            final_text = getattr(resp, "output_text", "") or ""
            break
        pending = []
        for c in calls:
            args = json.loads(getattr(c, "arguments", "") or "{}")
            did = args.get("doc_id")
            content = docs[did]["text"] if did in docs else f"Error: no document with id {did}"
            pending.append({"type": "function_call_output", "call_id": c.call_id, "output": content})
    return records, final_text, model
