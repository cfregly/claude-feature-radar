"""The Claude arm: a genuinely long-horizon agent, in Claude's best configuration.

The task is a CHAIN. Each incident report names the next report to read, so the agent must follow
it one step at a time. That makes the long horizon real, not an artifact of disabling parallel
tool calls. Parallel tool use is left ON (the natural mode), because the chain enforces the order
on its own.

It runs the task twice on the same model, both with prompt caching ON (the best config on both
sides), so the only difference is the two managed features:

  baseline : caching on. No context management, no memory.
  managed  : caching on, plus context editing (clear stale tool results) and the memory tool.

So the delta is the NET effect of context editing + memory on top of caching, which is the honest
question (caching is table stakes both vendors have). Every number, including wall-clock time,
comes from real calls.

Features used (all current, all on for best-to-best):
  - prompt caching      https://platform.claude.com/docs/en/build-with-claude/prompt-caching
  - context editing     https://platform.claude.com/docs/en/build-with-claude/context-editing
  - the memory tool     https://platform.claude.com/docs/en/agents-and-tools/tool-use/memory-tool
"""

from __future__ import annotations

import argparse
import json
import random
import re
import tempfile
import time

import anthropic

from common.client import get_client, repo_root
from common.models import get
from common.pricing import cost_breakdown
from engine.memory_backend import MemoryBackend

BETA_HEADER = "context-management-2025-06-27"
URGENT_EVERY = 3          # every third report is URGENT (deterministic)
CHAIN_SEED = 42           # fixed seed so the chain is identical every run (reproducible)


# ----------------------------------------------------------------------------- corpus + tools

def build_chain(n_docs: int, approx_tokens: int):
    """A chain of incident reports. Returns (docs_by_id, start_id).

    Each report ends with the id of the next report, in a fixed shuffled order, so the agent
    cannot batch: it only learns the next id by reading the current report.
    """
    rng = random.Random(CHAIN_SEED)
    order = list(range(n_docs))
    rng.shuffle(order)
    unit = "The on-call engineer reviewed the trace and confirmed the rollback completed. "
    repeats = max(1, (approx_tokens * 4) // len(unit))
    docs = {}
    for idx, doc_id in enumerate(order):
        urgent = (doc_id % URGENT_EVERY == 0)
        nxt = order[idx + 1] if idx + 1 < len(order) else "done"
        head = (
            f"Incident report #{doc_id}\n"
            f"Priority: {'URGENT' if urgent else 'normal'}\n"
            f"Service: checkout-{doc_id % 5}\n"
        )
        docs[doc_id] = {
            "id": doc_id, "urgent": urgent, "next": nxt,
            "text": head + unit * repeats + f"\nNext report to read: {nxt}\n",
        }
    return docs, order[0]


READ_TOOL = {
    "name": "read_document",
    "description": "Read one incident report by its integer id.",
    "input_schema": {
        "type": "object",
        "properties": {"doc_id": {"type": "integer", "description": "the report id to read"}},
        "required": ["doc_id"],
    },
}
MEMORY_TOOL = {"type": "memory_20250818", "name": "memory"}


def task_prompt(start: int, managed: bool) -> str:
    base = (
        f"You are auditing a chain of incident reports. Start by reading report {start} with the "
        f"read_document tool. Each report ends with the id of the next report to read. Follow that "
        f"pointer one report at a time until a report says the next one is `done`. Count the "
        f"reports whose header says `Priority: URGENT`."
    )
    # Unambiguous answer format. An earlier version said "Answer: K", and some models echoed the
    # literal K instead of substituting the count, which contaminated the correctness measurement.
    answer = (
        " Then reply with a single line in the form `Answer: N`, where you replace N with the "
        "integer count of URGENT reports (for example `Answer: 7`). Output nothing else."
    )
    if managed:
        return base + (
            " Your context window is trimmed automatically as you work, so do not rely on "
            "remembering earlier reports. The first time you see an URGENT report, create a memory "
            "file at `/memories/urgent.txt` and add its id. For each later URGENT report, append "
            "its id. When you reach `done`, view `/memories/urgent.txt` and count the ids."
        ) + answer
    return base + " When you reach `done`," + answer


# ------------------------------------------------------------------------------------- runner

def _text_of(msg) -> str:
    return "".join(b.text for b in msg.content if getattr(b, "type", None) == "text").strip()


def _cleared_tokens(msg) -> int:
    cm = getattr(msg, "context_management", None)
    edits = getattr(cm, "applied_edits", None) or [] if cm else []
    return sum(getattr(e, "cleared_input_tokens", 0) or 0 for e in edits)


def parse_answer(text: str):
    m = re.search(r"Answer:\s*(-?\d+)", text)
    return int(m.group(1)) if m else None


def _overflow_info(err) -> tuple[bool, int | None]:
    """Classify a 400 as a context-window overflow, and pull the attempted token count if present.

    The API rejects a request whose input exceeds the model's context window with a message like
    `prompt is too long: 207123 tokens > 200000 maximum`. Returns (is_overflow, attempted_tokens).
    A non-overflow 400 returns (False, None) so the caller re-raises it.
    """
    msg = str(err).lower()
    is_overflow = any(k in msg for k in ("too long", "maximum", "context window", "exceed"))
    if not is_overflow:
        return False, None
    m = re.search(r"(\d[\d,]*)\s*tokens", msg)
    return True, (int(m.group(1).replace(",", "")) if m else None)


def _mark_cache(messages):
    """Keep exactly one rolling cache breakpoint on the last block, so the whole prefix caches.

    Caching is automatic on OpenAI; on Claude it is opt-in, so we turn it on here to stay
    best-to-best. One breakpoint avoids exceeding the four-breakpoint limit.
    """
    for m in messages:
        c = m.get("content")
        if isinstance(c, list):
            for b in c:
                if isinstance(b, dict):
                    b.pop("cache_control", None)
    last = messages[-1]
    c = last["content"]
    if isinstance(c, str):
        last["content"] = [{"type": "text", "text": c, "cache_control": {"type": "ephemeral"}}]
    elif isinstance(c, list) and c and isinstance(c[-1], dict):
        c[-1]["cache_control"] = {"type": "ephemeral"}


def run_agent(client, model_key, docs, start, *, managed, caching=True, trigger, keep, max_turns,
              stop_on_overflow=False):
    """Run the chain audit once on Claude, caching ON. Returns (records, final_text).

    ``stop_on_overflow`` makes the context-window error a measured event instead of a crash: when
    the carried context grows past the model's window and the API rejects the request, the run
    records a ``crashed`` turn (with the attempted token count the API reported) and stops. That
    lets a caller compare an unbounded agent that dies at the wall against a bounded one that
    finishes. Off by default, so existing callers are unaffected.
    """
    model = get(model_key)
    messages = [{"role": "user", "content": task_prompt(start, managed)}]
    tools = [READ_TOOL] + ([MEMORY_TOOL] if managed else [])

    kw_extra = {}
    mem = None
    if managed:
        mem = MemoryBackend(tempfile.mkdtemp(prefix="cce_mem_"))
        kw_extra["extra_headers"] = {"anthropic-beta": BETA_HEADER}
        # context editing: clear stale tool results in place once the context crosses the trigger,
        # keep the most recent `keep` tool uses, and never clear the memory calls.
        kw_extra["extra_body"] = {
            "context_management": {
                "edits": [{
                    "type": "clear_tool_uses_20250919",
                    "trigger": {"type": "input_tokens", "value": trigger},
                    "keep": {"type": "tool_uses", "value": keep},
                    "exclude_tools": ["memory"],
                }]
            }
        }

    records, final_text = [], ""
    for turn in range(max_turns):
        if caching:
            _mark_cache(messages)  # best-config: cache the growing prefix
        t0 = time.perf_counter()
        try:
            msg = client.messages.create(
                model=model.id, max_tokens=1024, messages=messages, tools=tools, **kw_extra,
            )
        except anthropic.BadRequestError as e:
            is_overflow, attempted = _overflow_info(e)
            if stop_on_overflow and is_overflow:
                records.append({
                    "turn": turn, "crashed": True, "error": str(e)[:200],
                    "attempted_tokens": attempted,
                    "input_tokens": 0, "cache_read": 0, "cache_write": 0, "ctx": attempted or 0,
                    "output_tokens": 0, "cost": 0.0,
                    "latency_s": round(time.perf_counter() - t0, 3), "cleared": 0,
                })
                break
            raise
        dt = time.perf_counter() - t0
        u = msg.usage
        _in = getattr(u, "input_tokens", 0) or 0
        _cr = getattr(u, "cache_read_input_tokens", 0) or 0
        # cache_creation is a THIRD, disjoint input bucket (tokens written to cache this turn). On a
        # cold turn or the turn right after context editing clears, almost the whole prefix is a
        # write, so input_tokens drops to ~1 and cache_read is 0. Carried context is all three input
        # buckets summed, not input + cache_read. Omitting the write bucket undercounts the context
        # exactly when it matters most (cold and post-clear). See docs/VERIFIED_FACTS.md.
        cc = getattr(u, "cache_creation", None)
        if cc is not None:
            _cw = (getattr(cc, "ephemeral_5m_input_tokens", 0) or 0) + \
                  (getattr(cc, "ephemeral_1h_input_tokens", 0) or 0)
        else:
            _cw = getattr(u, "cache_creation_input_tokens", 0) or 0
        records.append({
            "turn": turn,
            "input_tokens": _in,
            "cache_read": _cr,
            "cache_write": _cw,
            "ctx": _in + _cr + _cw,  # true carried context = every input bucket the model processed
            "output_tokens": getattr(u, "output_tokens", 0) or 0,
            "cost": cost_breakdown(model.key, u).total,
            "latency_s": dt,
            "cleared": _cleared_tokens(msg),
        })

        if msg.stop_reason != "tool_use":
            final_text = _text_of(msg)
            break

        messages.append({"role": "assistant", "content": msg.content})
        results = []
        for tu in msg.content:
            if getattr(tu, "type", None) != "tool_use":
                continue
            if tu.name == "read_document":
                did = tu.input.get("doc_id")
                content = docs[did]["text"] if did in docs else f"Error: no document with id {did}"
            elif tu.name == "memory":
                content = mem.handle(tu.input)
            else:
                content = f"Error: unknown tool {tu.name}"
            results.append({"type": "tool_result", "tool_use_id": tu.id, "content": content})
        messages.append({"role": "user", "content": results})

    return records, final_text


# -------------------------------------------------------------------------------------- print

def summarize(records):
    return {
        "turns": len(records),
        "total_cost": sum(r["cost"] for r in records),
        "total_time": sum(r["latency_s"] for r in records),
        "total_input": sum(r["input_tokens"] for r in records),
        "peak_input": max((r["input_tokens"] for r in records), default=0),
        "cache_read": sum(r["cache_read"] for r in records),
    }


def print_report(docs, model_key, base_rec, base_ans, man_rec, man_ans):
    gold = sum(1 for d in docs.values() if d["urgent"])
    label = get(model_key).label
    b, m = summarize(base_rec), summarize(man_rec)

    print(f"\n  Chain audit of {len(docs)} reports on {label}, caching ON in both runs.")
    print(f"  True URGENT count: {gold}\n")

    print("  input tokens per turn (carried context)")
    print("  turn | baseline | managed")
    print("  -----+----------+--------")
    for i in range(max(len(base_rec), len(man_rec))):
        bt = f"{base_rec[i]['input_tokens']:>8,}" if i < len(base_rec) else " " * 8
        mt = f"{man_rec[i]['input_tokens']:>7,}" if i < len(man_rec) else " " * 7
        print(f"  {i:>4} | {bt} | {mt}")

    print()
    print(f"  {'':<20}{'baseline':>12}{'managed':>12}")
    print(f"  {'total cost (USD)':<20}{b['total_cost']:>12.5f}{m['total_cost']:>12.5f}")
    print(f"  {'total time (s)':<20}{b['total_time']:>12.1f}{m['total_time']:>12.1f}")
    print(f"  {'peak context tok':<20}{b['peak_input']:>12,}{m['peak_input']:>12,}")
    print(f"  {'cache-read tok':<20}{b['cache_read']:>12,}{m['cache_read']:>12,}")
    print(f"  {'answer':<20}{str(base_ans):>12}{str(man_ans):>12}")
    print(f"  (true URGENT count: {gold})\n")


# --------------------------------------------------------------------------------------- main

PRESETS = {
    "quick": dict(docs=10, doc_tokens=900, trigger=3500, keep=2, max_turns=24),
    "default": dict(docs=32, doc_tokens=1300, trigger=20000, keep=3, max_turns=52),
    "full": dict(docs=45, doc_tokens=1500, trigger=20000, keep=3, max_turns=70),
}


def main():
    p = argparse.ArgumentParser(description="Claude long-horizon chain agent, baseline vs managed.")
    p.add_argument("--model", default="haiku", help="model key: haiku | sonnet | opus")
    p.add_argument("--quick", action="store_true")
    p.add_argument("--full", action="store_true")
    p.add_argument("--docs", type=int)
    p.add_argument("--doc-tokens", type=int)
    p.add_argument("--trigger", type=int)
    p.add_argument("--keep", type=int)
    p.add_argument("--max-turns", type=int)
    a = p.parse_args()

    cfg = dict(PRESETS["quick"] if a.quick else PRESETS["full"] if a.full else PRESETS["default"])
    for k in ("docs", "doc_tokens", "trigger", "keep", "max_turns"):
        if getattr(a, k) is not None:
            cfg[k] = getattr(a, k)

    client = get_client()
    docs, start = build_chain(cfg["docs"], cfg["doc_tokens"])
    common = dict(trigger=cfg["trigger"], keep=cfg["keep"], max_turns=cfg["max_turns"])

    t0 = time.perf_counter()
    base_rec, base_text = run_agent(client, a.model, docs, start, managed=False, **common)
    man_rec, man_text = run_agent(client, a.model, docs, start, managed=True, **common)
    elapsed = time.perf_counter() - t0

    base_ans, man_ans = parse_answer(base_text), parse_answer(man_text)
    print_report(docs, a.model, base_rec, base_ans, man_rec, man_ans)

    out = {
        "model": get(a.model).id, "config": cfg, "elapsed_s": round(elapsed, 1),
        "gold": sum(1 for d in docs.values() if d["urgent"]),
        "baseline": {"records": base_rec, "answer": base_ans, **summarize(base_rec)},
        "managed": {"records": man_rec, "answer": man_ans, **summarize(man_rec)},
    }
    (repo_root() / "data").mkdir(exist_ok=True)
    (repo_root() / "data" / "last_demo.json").write_text(json.dumps(out, indent=2))
    print(f"  wrote receipts to data/last_demo.json  ({elapsed:.0f}s wall)\n")


if __name__ == "__main__":
    main()
