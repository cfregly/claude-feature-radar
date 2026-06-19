"""The OpenAI arm: the same long-horizon chain agent on OpenAI's LATEST API, best config.

This is the STATEFUL multi-turn chain agent (server-stored conversation, compaction, the tool loop)
that engine/compare.py, engine/sweep.py, and engine/longhorizon_compare.py drive. It is a different
shape from the single-call competitor arm a Demonstrator runs: a Demonstrator's OpenAI arm goes
through the provider-blind layer (common/runner.py call() plus engine/providers/openai_provider.py),
which probes access and never fakes a row. New demonstrators use that layer; this chain agent stays
the backend for the legacy long-horizon comparison so the committed receipts do not move.

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
import time

from common.pricing import cost_from_buckets  # the one verified price table lives in common/models.py
from engine.demo import build_chain, task_prompt  # the exact same task

# why gpt-5.4-mini: the cheapest tier the docs recommend as a capable multi-step tool driver.
# nano is cheaper but a weaker driver. The choice is documented so a founder can swap it. Its price
# (and gpt-5.4-nano's) lives once in common/models.py, re-verified live 2026-06-18, never copied here.
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
    """The OpenAI client for the legacy long-horizon chain, shared with the demonstrator path.

    Delegates to engine.providers.get_openai_client (the single client builder), then preserves this
    arm's contract: raise SystemExit when the key is unset, so compare/sweep/longhorizon stop loudly
    rather than running a half comparison. The provider builder raises its own SystemExit when the SDK
    is missing. Imported lazily so importing this module never pulls `openai`.
    """
    from engine.providers.openai_provider import get_openai_client
    client = get_openai_client()
    if client is None:
        raise SystemExit("OPENAI_API_KEY is not set. Add it to .env or export it.")
    return client


def _cost(model, usage):
    # OpenAI's input_tokens INCLUDES the cached tokens, so fresh = input - cached. Rates come from the
    # one verified table in common/models.py via cost_from_buckets, never a copy in this file.
    inp = getattr(usage, "input_tokens", 0) or 0
    out = getattr(usage, "output_tokens", 0) or 0
    det = getattr(usage, "input_tokens_details", None)
    cached = (getattr(det, "cached_tokens", 0) or 0) if det else 0
    cost = cost_from_buckets(model, fresh_input=max(0, inp - cached), cached=cached, output=out)
    return cost, inp, cached


def run_openai_agent(docs, start, *, model=DEFAULT_OPENAI_MODEL, compact_threshold=None, max_turns):
    """Run the chain audit on OpenAI, caching always on, compaction on if compact_threshold is set.

    compact_threshold=None means no compaction (carry the full context, let caching make the
    re-send cheap), which is OpenAI's other best config. Returns (records, final_text, model).
    """
    client = _client()
    cm = [{"type": "compaction", "compact_threshold": compact_threshold}] if compact_threshold else None
    prev_id = None
    pending = [{"role": "user", "content": task_prompt(start, memory=False)}]
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
            "ctx": inp,  # Responses input_tokens already includes cached, so it is the carried context
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
