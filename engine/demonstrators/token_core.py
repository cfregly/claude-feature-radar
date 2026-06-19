"""token_core: the ONE audited input-token counter and the PTC run loop, shared by the
programmatic-tool-calling demo and the forkable app, so the receipt is counted in exactly one place.

The whole repo's promise is "every number traces to a real usage object." If the demo counted billed
input one way and the founder-facing app counted it another, a reader could not trust either. So both
import `billed_input` and `run_mode` from here. There is one counter, audited once.

What `billed_input` counts and why. Claude reports input across three disjoint buckets, and PTC's win
is a reduction in the SUM of all three, not just the uncached `input_tokens` field:

  input_tokens                 the uncached prompt the model processed this turn
  cache_read_input_tokens      the cached prefix re-read this turn (billed at the cheaper read rate)
  cache_creation_input_tokens  the prefix written into the cache this turn (one bucket, or split into
                               ephemeral_5m_input_tokens + ephemeral_1h_input_tokens when the API
                               reports the two TTL tiers)

Counting only `input_tokens` would read a cold turn as almost free (the whole prefix lands in the
write bucket then) and would understate exactly the data PTC keeps out of context. So the counter sums
every input bucket, apples to apples across both modes. See the repo CLAUDE.md, "Carried context is
every input bucket."

The mechanism. Programmatic tool calling lets Claude write one script in a code-execution sandbox that
calls the developer's OWN tools in a loop and filters the results before they ever reach the model's
context window. Add `allowed_callers: ["code_execution_20260120"]` to a tool and Claude is strongly guided to
invoke it from code rather than make one round trip per call (it is guidance, not a hard API block,
so a client still handles a direct tool_use). The bulky tool OUTPUTS go to the sandbox, not the model, so
the developer is not billed input tokens for data the model never needs to read. GA, no beta header.
Models (per the docs): Fable 5, Mythos 5, Opus 4.5 to 4.8, Sonnet 4.5 to 4.6 (not Haiku). The runnable demos use Sonnet and Opus. Source, re-fetched 2026-06-18:
https://platform.claude.com/docs/en/agents-and-tools/tool-use/programmatic-tool-calling

The win is workload-shaped. It needs a FAN-OUT task: the model has to call the tool many times for the
bulky outputs to pile up, so keeping them in the sandbox is what saves the input tokens. The demo and
the app both run the genuine fan-out example, and the app says so plainly, so the claim stays scoped to
where it holds: fewer billed input tokens on a fan-out workload. Keep your own task fan-out shaped.

Nothing here imports anthropic. The caller passes in a client, so this module stays import-light and
the one-dependency core is untouched.
"""

from __future__ import annotations

import json
import time

# The code execution tool block, and the toggle that turns a plain tool into a programmatic one.
# These are the exact strings the live doc names. check_docs.py asserts the demo still ships them.
CODE_EXEC_TOOL = {"type": "code_execution_20260120", "name": "code_execution"}
PTC_CALLER = "code_execution_20260120"


def billed_input(usage) -> int:
    """Every input bucket the model was billed for, summed apples to apples. The one audited counter.

    Sums input_tokens + cache_read_input_tokens + cache_creation (both TTL tiers when the API splits
    them). This is the number PTC reduces, and the only input-token figure this repo ships.
    """
    inp = getattr(usage, "input_tokens", 0) or 0
    cr = getattr(usage, "cache_read_input_tokens", 0) or 0
    cc = getattr(usage, "cache_creation", None)
    if cc is not None:
        cw = (getattr(cc, "ephemeral_5m_input_tokens", 0) or 0) + (getattr(cc, "ephemeral_1h_input_tokens", 0) or 0)
    else:
        cw = getattr(usage, "cache_creation_input_tokens", 0) or 0
    return inp + cr + cw


def run_mode(client, model_id, tool_spec, call_fn, question, *, programmatic,
             cost_fn=None, max_turns=8, label=None, progress=True):
    """Run the SAME fan-out task one way, and return the audited receipt for it.

    The single A/B engine. The demo and the app both call this so Mode A and Mode B are produced by
    identical code, the only difference being the `programmatic` toggle. No second copy of the loop.

      client       an Anthropic client (passed in, never imported here)
      model_id     the exact model id string (a PTC-capable model, e.g. Sonnet 4.6 or Opus 4.8)
      tool_spec    the developer's own tool, a Messages-API tool dict with name/description/input_schema
      call_fn      the Python implementation of that tool: call_fn(**tool_input) -> JSON-serializable
      question     the task prompt that fans the tool out over many inputs
      programmatic when True, add allowed_callers + the code execution tool (Mode B). When False the
                   model calls the tool directly, one round trip per call (Mode A)
      cost_fn      optional cost_fn(usage) -> float, summed across turns. None leaves cost at 0.0

    Returns a dict: billed_input, output_tokens, cost, turns, tool_calls, answer (the final text),
    and time. `billed_input` is summed with the one audited counter above.
    """
    tool = dict(tool_spec)
    if programmatic:
        tool["allowed_callers"] = [PTC_CALLER]
        tools = [CODE_EXEC_TOOL, tool]
    else:
        tools = [tool]

    tag = label or ("B" if programmatic else "A")
    messages = [{"role": "user", "content": question}]
    container = None
    total_billed_input = output_tokens = turns = tool_calls = 0
    cost = 0.0
    final_text = ""
    t0 = time.perf_counter()
    for _ in range(max_turns):
        # A generous per-request timeout: a code-execution turn can legitimately take a minute, but if
        # the container expires mid-run the call can hang, so we fail fast instead of grinding.
        kwargs = dict(model=model_id, max_tokens=4096, tools=tools, messages=messages, timeout=180.0)
        if container:
            kwargs["container"] = container
        resp = client.messages.create(**kwargs)
        turns += 1
        total_billed_input += billed_input(resp.usage)
        output_tokens += getattr(resp.usage, "output_tokens", 0) or 0
        if cost_fn is not None:
            cost += cost_fn(resp.usage)
        if getattr(resp, "container", None):
            container = resp.container.id
        if progress:
            _ntu = sum(1 for b in resp.content if getattr(b, "type", None) == "tool_use")
            _ncode = sum(1 for b in resp.content if getattr(b, "type", None) == "server_tool_use")
            print(f"      [{tag}] turn {turns}: stop={resp.stop_reason} tool_use={_ntu} "
                  f"code={_ncode} billed={total_billed_input:,} {time.perf_counter() - t0:.0f}s",
                  flush=True)
        text = "".join(b.text for b in resp.content if getattr(b, "type", None) == "text")
        if text.strip():
            final_text = text
        if resp.stop_reason != "tool_use":
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
                results.append({"type": "tool_result", "tool_use_id": block.id,
                                "content": out if isinstance(out, str) else json.dumps(out)})
        if not results:
            break
        messages.append({"role": "user", "content": results})
    return {
        "billed_input": total_billed_input, "output_tokens": output_tokens, "cost": cost,
        "turns": turns, "tool_calls": tool_calls, "answer": final_text,
        "time": time.perf_counter() - t0,
    }
