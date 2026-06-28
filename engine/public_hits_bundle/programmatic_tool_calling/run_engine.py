"""run_engine: the ONE audited input-token counter and the programmatic tool calling run loop, shared by the
programmatic-tool-calling demo and the forkable app, so the receipt is counted in exactly one place.

The whole repo's promise is "every number traces to a real usage object." If the demo counted billed
input one way and the founder-facing app counted it another, a reader could not trust either. So both
import `billed_input` and `run_mode` from here. There is one counter, audited once.

What `billed_input` counts and why. Claude reports input across three disjoint buckets, and the programmatic path's win
is a reduction in the SUM of all three, not just the uncached `input_tokens` field:

  input_tokens                 the uncached prompt the model processed this turn
  cache_read_input_tokens      the cached prefix re-read this turn (billed at the cheaper read rate)
  cache_creation_input_tokens  the prefix written into the cache this turn (one bucket, or split into
                               ephemeral_5m_input_tokens + ephemeral_1h_input_tokens when the API
                               reports the two TTL tiers)

Counting only `input_tokens` would read a cold turn as almost free (the whole prefix lands in the
write bucket then) and would understate exactly the data the programmatic path keeps out of context. So the counter sums
every input bucket, apples to apples across both modes. See the repo CLAUDE.md, "Carried context is
every input bucket."

The mechanism. Programmatic tool calling lets Claude write one script in a code-execution sandbox that
calls the developer's OWN tools in a loop and filters the results before they ever reach the model's
context window. Add `allowed_callers: ["code_execution_20260120"]` to a tool and Claude is strongly guided to
invoke it from code rather than make one round trip per call (it is guidance, not a hard API block,
so a client still handles a direct tool_use). The bulky tool OUTPUTS go to the sandbox, not the model, so
the developer is not billed input tokens for data the model never needs to read. This receipt path uses
no beta header. Programmatic tool calling requires `code_execution_20260120` or later. Models (per the
docs): Fable 5, Mythos 5, Opus 4.5 to 4.8, Sonnet 4.5 to 4.6 (not Haiku). The runnable demos use
Sonnet and Opus. Source, re-fetched 2026-06-26:
https://platform.claude.com/docs/en/agents-and-tools/tool-use/programmatic-tool-calling

Cost scope. This module measures input tokens from the Messages API usage object. The pricing module
turns the same usage object into token/API dollars, including cache reads and cache writes when
present. Code execution runtime can bill separately after the monthly free allowance, so production
COGS must add that line item before claiming all-in savings.

The win is workload-shaped. It needs a FAN-OUT task: the model has to call the tool many times for the
bulky outputs to pile up, so keeping them in the sandbox is what saves the input tokens. The demo and
the app both run the genuine fan-out example, and the app says so plainly, so the claim stays scoped to
where it holds: fewer billed input tokens on a fan-out workload. Keep your own task fan-out shaped.

Nothing here imports anthropic. The caller passes in a client, so this module stays import-light and
the one-dependency core is untouched.
"""

from __future__ import annotations

import hashlib
import json
import time
import uuid

# The code execution tool block, and the toggle that turns a plain tool into a programmatic one.
# These are the exact strings the live doc names. The docs-vs-code gate asserts the demo still ships them.
CODE_EXEC_TOOL = {"type": "code_execution_20260120", "name": "code_execution"}
PROGRAMMATIC_CALLER = "code_execution_20260120"
TRACE_METADATA_KEY = "_trace_metadata"
TRACE_METADATA_FIELDS = ("tool_schema_version", "reducer_version", "snapshot_id", "source_freshness")


def billed_input(usage) -> int:
    """Every input bucket the model was billed for, summed apples to apples. The one audited counter.

    Sums input_tokens + cache_read_input_tokens + cache_creation (both TTL tiers when the API splits
    them). This is the number the programmatic path reduces, and the only input-token figure this repo ships.
    """
    inp = getattr(usage, "input_tokens", 0) or 0
    cr = getattr(usage, "cache_read_input_tokens", 0) or 0
    cc = getattr(usage, "cache_creation", None)
    if cc is not None:
        cw = (getattr(cc, "ephemeral_5m_input_tokens", 0) or 0) + (getattr(cc, "ephemeral_1h_input_tokens", 0) or 0)
    else:
        cw = getattr(usage, "cache_creation_input_tokens", 0) or 0
    return inp + cr + cw


def _cache_creation_buckets(usage) -> tuple[int, int]:
    cc = getattr(usage, "cache_creation", None)
    if cc is not None:
        return (
            getattr(cc, "ephemeral_5m_input_tokens", 0) or 0,
            getattr(cc, "ephemeral_1h_input_tokens", 0) or 0,
        )
    return getattr(usage, "cache_creation_input_tokens", 0) or 0, 0


def _public_fields(obj) -> dict:
    if obj is None:
        return {}
    if isinstance(obj, dict):
        return dict(obj)
    if hasattr(obj, "model_dump"):
        return obj.model_dump(exclude_none=True)
    return {
        name: getattr(obj, name)
        for name in dir(obj)
        if not name.startswith("_")
        and isinstance(getattr(obj, name), (str, int, float, bool, type(None)))
    }


def _caller_fields(block, *, programmatic: bool) -> dict:
    caller = _public_fields(getattr(block, "caller", None))
    if caller.get("type"):
        return {
            "caller_type": caller["type"],
            "caller_tool_id": caller.get("tool_id"),
        }
    return {
        "caller_type": "missing" if programmatic else "direct",
        "caller_tool_id": None,
    }


def _json_content(value) -> str:
    return value if isinstance(value, str) else json.dumps(value)


def _byte_len(value: str) -> int:
    return len(value.encode("utf-8"))


def _row_count(value) -> int | None:
    if isinstance(value, list):
        return len(value)
    if isinstance(value, dict) and isinstance(value.get("row_count"), int):
        return value["row_count"]
    return None


def _add_usage_to_trace(trace: dict, usage) -> None:
    cache_creation_5m, cache_creation_1h = _cache_creation_buckets(usage)
    usage_fields = {
        "input_tokens": getattr(usage, "input_tokens", 0) or 0,
        "cache_read_input_tokens": getattr(usage, "cache_read_input_tokens", 0) or 0,
        "cache_creation_5m_input_tokens": cache_creation_5m,
        "cache_creation_1h_input_tokens": cache_creation_1h,
        "output_tokens": getattr(usage, "output_tokens", 0) or 0,
        "billed_input": billed_input(usage),
    }
    for key, value in usage_fields.items():
        trace[key] += value

    for key, value in _public_fields(getattr(usage, "server_tool_use", None)).items():
        if isinstance(value, int):
            trace["server_tool_use"][key] = trace["server_tool_use"].get(key, 0) + value


def _split_tool_spec(tool_spec: dict) -> tuple[dict, dict]:
    """Keep trace-only metadata out of the API tool schema."""
    tool = dict(tool_spec)
    metadata = dict(tool.pop(TRACE_METADATA_KEY, {}) or {})
    for key in TRACE_METADATA_FIELDS:
        if key in tool:
            metadata.setdefault(key, tool.pop(key))
    return tool, metadata


def _new_trace(*, tag: str, model_id: str, tool: dict, trace_metadata: dict, question: str, programmatic: bool) -> dict:
    mode = "programmatic" if programmatic else "direct"
    return {
        "run_id": f"{tag.lower()}-{uuid.uuid4().hex[:12]}",
        "trace_schema_version": "programmatic-tool-calling-trace-v1",
        "mode": mode,
        "model": model_id,
        "tool_name": tool.get("name"),
        "tool_schema_version": trace_metadata.get("tool_schema_version", "demo-tool-v1"),
        "reducer_version": trace_metadata.get("reducer_version", "demo-reducer-v1"),
        "allowed_callers": list(tool.get("allowed_callers", ["direct"])),
        "prompt_hash": hashlib.sha256(question.encode("utf-8")).hexdigest()[:12],
        "snapshot_id": trace_metadata.get("snapshot_id"),
        "source_freshness": trace_metadata.get("source_freshness"),
        "container_ids": [],
        "turns": 0,
        "tool_calls": 0,
        "latency_ms": 0,
        "budget_limits": {},
        "budget_exceeded": False,
        "retry_count": 0,
        "rate_limit_events": 0,
        "input_tokens": 0,
        "cache_read_input_tokens": 0,
        "cache_creation_5m_input_tokens": 0,
        "cache_creation_1h_input_tokens": 0,
        "output_tokens": 0,
        "billed_input": 0,
        "server_tool_use": {},
        "server_tool_blocks": 0,
        "caller_path_drift": False,
        "tool_call_records": [],
        "raw_tool_bytes": 0,
        "final_bytes": 0,
        "cost_usd": 0.0,
        "incomplete_result": False,
        "partial_result": False,
        "abstain_reason": None,
        "fallback_reason": None,
        "policy_denial": False,
        "correctness": None,
    }


def run_mode(client, model_id, tool_spec, call_fn, question, *, programmatic,
             cost_fn=None, max_turns=8, label=None, progress=True):
    """Run the SAME fan-out task one way, and return the audited receipt for it.

    The single A/B engine. The demo and the app both call this so Mode A and Mode B are produced by
    identical code, the only difference being the `programmatic` toggle. No second copy of the loop.

      client       an Anthropic client (passed in, never imported here)
      model_id     the exact model id string (a model that supports programmatic tool calling, e.g. Sonnet 4.6 or Opus 4.8)
      tool_spec    the developer's own tool, a Messages-API tool dict with name/description/input_schema
      call_fn      the Python implementation of that tool: call_fn(**tool_input) -> JSON-serializable
      question     the task prompt that fans the tool out over many inputs
      programmatic when True, add allowed_callers + the code execution tool (Mode B). When False the
                   model calls the tool directly, one round trip per call (Mode A)
      cost_fn      optional cost_fn(usage) -> float, summed across turns. None leaves cost at 0.0

    Returns a dict: billed_input, output_tokens, cost, turns, tool_calls, answer (the final text),
    and time. `billed_input` is summed with the one audited counter above.
    """
    tool, trace_metadata = _split_tool_spec(tool_spec)
    tool.pop("allowed_callers", None)
    if programmatic:
        tool["allowed_callers"] = [PROGRAMMATIC_CALLER]
        tools = [CODE_EXEC_TOOL, tool]
    else:
        tools = [tool]

    tag = label or ("B" if programmatic else "A")
    trace = _new_trace(
        tag=tag,
        model_id=model_id,
        tool=tool,
        trace_metadata=trace_metadata,
        question=question,
        programmatic=programmatic,
    )
    trace["budget_limits"] = {"max_turns": max_turns}
    messages = [{"role": "user", "content": question}]
    container = None
    total_billed_input = output_tokens = turns = tool_calls = 0
    cost = 0.0
    final_text = ""
    ended = False
    t0 = time.perf_counter()
    for _ in range(max_turns):
        # A generous per-request timeout: a code-execution turn can legitimately take a minute, but if
        # the container expires mid-run the call can hang, so we fail fast instead of grinding.
        kwargs = dict(model=model_id, max_tokens=4096, tools=tools, messages=messages, timeout=180.0)
        if container:
            kwargs["container"] = container
        resp = client.messages.create(**kwargs)
        turns += 1
        turn_billed_input = billed_input(resp.usage)
        turn_output_tokens = getattr(resp.usage, "output_tokens", 0) or 0
        total_billed_input += turn_billed_input
        output_tokens += turn_output_tokens
        trace["turns"] = turns
        _add_usage_to_trace(trace, resp.usage)
        server_tool_blocks = sum(1 for b in resp.content if getattr(b, "type", None) == "server_tool_use")
        trace["server_tool_blocks"] += server_tool_blocks
        if cost_fn is not None:
            cost += cost_fn(resp.usage)
        if getattr(resp, "container", None):
            container = resp.container.id
            if container not in trace["container_ids"]:
                trace["container_ids"].append(container)
        if progress:
            _ntu = sum(1 for b in resp.content if getattr(b, "type", None) == "tool_use")
            print(f"      [{tag}] turn {turns}: stop={resp.stop_reason} tool_use={_ntu} "
                  f"code={server_tool_blocks} billed={total_billed_input:,} {time.perf_counter() - t0:.0f}s",
                  flush=True)
        text = "".join(b.text for b in resp.content if getattr(b, "type", None) == "text")
        if text.strip():
            final_text = text
        if resp.stop_reason != "tool_use":
            ended = True
            break
        # Echo the assistant content back, but drop code_execution_tool_result blocks: the server holds
        # that state in the container, and re-sending them fails validation. This matches the doc's
        # continuation shape (text + server_tool_use + tool_use only).
        asst = [b.model_dump(exclude_unset=True) for b in resp.content
                if getattr(b, "type", None) != "code_execution_tool_result"]
        messages.append({"role": "assistant", "content": asst})
        results = []
        for block in resp.content:
            if getattr(block, "type", None) == "tool_use":  # the developer's custom tool (direct or from code)
                tool_calls += 1
                out = call_fn(**(block.input or {}))
                content = _json_content(out)
                caller = _caller_fields(block, programmatic=programmatic)
                if programmatic and caller["caller_type"] != PROGRAMMATIC_CALLER:
                    trace["caller_path_drift"] = True
                    trace["fallback_reason"] = trace["fallback_reason"] or "caller_path_drift"
                raw_bytes = _byte_len(content)
                trace["raw_tool_bytes"] += raw_bytes
                trace["tool_calls"] = tool_calls
                trace["tool_call_records"].append({
                    "tool_use_id": block.id,
                    "tool_name": getattr(block, "name", tool.get("name")),
                    "caller_type": caller["caller_type"],
                    "caller_tool_id": caller["caller_tool_id"],
                    "input": block.input or {},
                    "row_count": _row_count(out),
                    "output_bytes": raw_bytes,
                })
                results.append({"type": "tool_result", "tool_use_id": block.id, "content": content})
        if not results:
            trace["fallback_reason"] = "tool_use_without_client_results"
            break
        messages.append({"role": "user", "content": results})
    if not ended and trace["fallback_reason"] is None and turns >= max_turns:
        trace["fallback_reason"] = "max_turns_exhausted"
        trace["budget_exceeded"] = True
        trace["incomplete_result"] = True
        trace["partial_result"] = bool(final_text.strip())
    trace["latency_ms"] = int((time.perf_counter() - t0) * 1000)
    trace["final_bytes"] = _byte_len(final_text)
    trace["cost_usd"] = cost
    return {
        "billed_input": total_billed_input, "output_tokens": output_tokens, "cost": cost,
        "turns": turns, "tool_calls": tool_calls, "answer": final_text,
        "time": time.perf_counter() - t0, "trace": trace,
    }
