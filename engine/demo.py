"""The gap demo: a long-running agent that stays cheap and sharp.

It runs the same long task twice on the same model:

  baseline : no context management. The full transcript is re-sent every turn, so per-turn
             input tokens climb as the agent works through the documents.
  managed  : context editing (clear stale tool results) plus the memory tool. The agent drops
             old tool output but writes what matters to memory, so per-turn input tokens
             plateau and the final answer stays correct.

The agent works one step at a time (parallel tool calls are disabled), which is how a real
long-horizon agent behaves: read, reason, read the next thing. That is the regime where a
growing transcript actually costs money.

Every number comes from the usage object the API returns. Nothing is quoted from a blog.

Two Claude features carry the managed run:
  - context editing  (beta header context-management-2025-06-27), clear_tool_uses_20250919
    https://platform.claude.com/docs/en/build-with-claude/context-editing
  - the memory tool  (memory_20250818)
    https://platform.claude.com/docs/en/agents-and-tools/tool-use/memory-tool
"""

from __future__ import annotations

import argparse
import json
import re
import tempfile
import time

from common.client import get_client, repo_root
from common.models import get
from common.pricing import cost_breakdown
from engine.memory_backend import MemoryBackend

BETA_HEADER = "context-management-2025-06-27"
TOOL_CHOICE = {"type": "auto", "disable_parallel_tool_use": True}  # one step per turn
URGENT_EVERY = 3  # every third incident report is URGENT


# ----------------------------------------------------------------------------- corpus + tools

def build_corpus(n_docs: int, approx_tokens: int) -> list[dict]:
    """A deterministic set of incident reports. Every third one is URGENT."""
    unit = "The on-call engineer reviewed the trace and confirmed the rollback completed. "
    repeats = max(1, (approx_tokens * 4) // len(unit))
    docs = []
    for i in range(n_docs):
        urgent = (i % URGENT_EVERY == 0)
        head = (
            f"Incident report #{i}\n"
            f"Priority: {'URGENT' if urgent else 'normal'}\n"
            f"Service: checkout-{i % 5}\n\n"
        )
        docs.append({"id": i, "urgent": urgent, "text": head + unit * repeats})
    return docs


READ_TOOL = {
    "name": "read_document",
    "description": "Read one incident report by its integer id (0-based).",
    "input_schema": {
        "type": "object",
        "properties": {"doc_id": {"type": "integer", "description": "the report id to read"}},
        "required": ["doc_id"],
    },
}
MEMORY_TOOL = {"type": "memory_20250818", "name": "memory"}


def task_prompt(n: int, managed: bool) -> str:
    base = (
        f"You are auditing {n} incident reports, numbered 0 to {n - 1}. Read every report in "
        f"order, one at a time, using the read_document tool. We need the total count of "
        f"reports whose header says `Priority: URGENT`."
    )
    if managed:
        return base + (
            f" Your context window is trimmed automatically as you work, so do not rely on "
            f"remembering earlier reports. The first time you see an URGENT report, create a "
            f"memory file at `/memories/urgent.txt` and add its id on its own line. For each "
            f"later URGENT report, append its id to that file. After reading all {n} reports, "
            f"view `/memories/urgent.txt`, count the ids, and reply with exactly `Answer: K` "
            f"and nothing else."
        )
    return base + (
        f" When you have read all {n} reports, reply with exactly `Answer: K` where K is the "
        f"count, and nothing else."
    )


# ------------------------------------------------------------------------------------- runner

def _text_of(msg) -> str:
    return "".join(b.text for b in msg.content if getattr(b, "type", None) == "text").strip()


def _cleared_tokens(msg) -> int:
    cm = getattr(msg, "context_management", None)
    if cm is None:
        return 0
    edits = getattr(cm, "applied_edits", None) or []
    return sum(getattr(e, "cleared_input_tokens", 0) or 0 for e in edits)


def parse_answer(text: str):
    m = re.search(r"Answer:\s*(-?\d+)", text)
    return int(m.group(1)) if m else None


def run_agent(client, model_key, docs, *, managed, trigger, keep, max_turns):
    """Run the audit task once. Returns (records, final_text)."""
    model = get(model_key)
    n = len(docs)
    messages = [{"role": "user", "content": task_prompt(n, managed)}]
    tools = [READ_TOOL] + ([MEMORY_TOOL] if managed else [])

    kw_extra = {}
    mem = None
    if managed:
        mem = MemoryBackend(tempfile.mkdtemp(prefix="cce_mem_"))
        kw_extra["extra_headers"] = {"anthropic-beta": BETA_HEADER}
        kw_extra["extra_body"] = {
            "context_management": {
                "edits": [
                    {
                        "type": "clear_tool_uses_20250919",
                        "trigger": {"type": "input_tokens", "value": trigger},
                        "keep": {"type": "tool_uses", "value": keep},
                        "exclude_tools": ["memory"],
                    }
                ]
            }
        }

    records, final_text = [], ""
    for turn in range(max_turns):
        msg = client.messages.create(
            model=model.id, max_tokens=1024, messages=messages,
            tools=tools, tool_choice=TOOL_CHOICE, **kw_extra,
        )
        u = msg.usage
        records.append(
            {
                "turn": turn,
                "input_tokens": getattr(u, "input_tokens", 0) or 0,
                "output_tokens": getattr(u, "output_tokens", 0) or 0,
                "cost": cost_breakdown(model.key, u).total,
                "cleared": _cleared_tokens(msg),
            }
        )

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
                content = docs[did]["text"] if isinstance(did, int) and 0 <= did < n \
                    else f"Error: no document with id {did}"
            elif tu.name == "memory":
                content = mem.handle(tu.input)
            else:
                content = f"Error: unknown tool {tu.name}"
            results.append({"type": "tool_result", "tool_use_id": tu.id, "content": content})
        messages.append({"role": "user", "content": results})

    return records, final_text


# -------------------------------------------------------------------------------------- print

def summarize(records):
    drops = [r["turn"] for i, r in enumerate(records)
             if i > 0 and r["input_tokens"] < records[i - 1]["input_tokens"] - 500]
    return {
        "turns": len(records),
        "total_cost": sum(r["cost"] for r in records),
        "total_input": sum(r["input_tokens"] for r in records),
        "peak_input": max((r["input_tokens"] for r in records), default=0),
        "total_cleared": sum(r["cleared"] for r in records),
        "drop_turns": drops,
    }


def print_report(docs, model_key, base_rec, base_ans, man_rec, man_ans):
    gold = sum(1 for d in docs if d["urgent"])
    label = get(model_key).label
    b, m = summarize(base_rec), summarize(man_rec)

    print()
    print(f"  Task: count URGENT reports across {len(docs)} documents on {label}, one step per turn.")
    print(f"  True count: {gold}\n")

    print("  input tokens per turn (this is the whole point)")
    print("  turn | baseline | managed")
    print("  -----+----------+--------")
    for i in range(max(len(base_rec), len(man_rec))):
        bt = f"{base_rec[i]['input_tokens']:>8,}" if i < len(base_rec) else " " * 8
        mt = f"{man_rec[i]['input_tokens']:>7,}" if i < len(man_rec) else " " * 7
        flag = "  <- context cleared" if i < len(man_rec) and (
            man_rec[i]["cleared"] or i in m["drop_turns"]) else ""
        print(f"  {i:>4} | {bt} | {mt}{flag}")

    print()
    print(f"  baseline total: ${b['total_cost']:.5f}      managed total: ${m['total_cost']:.5f}"
          f"      ratio: {(m['total_cost'] / b['total_cost']) if b['total_cost'] else 0:.2f}x")
    print(f"  peak input tokens/turn:   baseline {b['peak_input']:>7,}   managed {m['peak_input']:>7,}")
    print(f"  total input tokens:       baseline {b['total_input']:>7,}   managed {m['total_input']:>7,}")
    if m["total_cleared"]:
        print(f"  context editing reported clearing {m['total_cleared']:,} input tokens")
    if m["drop_turns"]:
        print(f"  managed per-turn input dropped at turns {m['drop_turns']} (clearing engaged)")
    print(f"  answers:  baseline {base_ans}   managed {man_ans}   true {gold}")
    print()


# --------------------------------------------------------------------------------------- main

PRESETS = {
    "quick": dict(docs=10, doc_tokens=900, trigger=3500, keep=2, max_turns=24),
    "default": dict(docs=32, doc_tokens=1300, trigger=6000, keep=2, max_turns=52),
    "full": dict(docs=45, doc_tokens=1500, trigger=6000, keep=2, max_turns=70),
}


def main():
    p = argparse.ArgumentParser(description="Cost-curve demo: a long agent that stays cheap and sharp.")
    p.add_argument("--model", default="haiku", help="model key: haiku | sonnet | opus")
    p.add_argument("--quick", action="store_true", help="tiny cheap run to prove the shape")
    p.add_argument("--full", action="store_true", help="larger run with a dramatic curve")
    p.add_argument("--docs", type=int)
    p.add_argument("--doc-tokens", type=int)
    p.add_argument("--trigger", type=int)
    p.add_argument("--keep", type=int)
    p.add_argument("--max-turns", type=int)
    a = p.parse_args()

    cfg = dict(PRESETS["quick"] if a.quick else PRESETS["full"] if a.full else PRESETS["default"])
    for k in ("docs", "doc_tokens", "trigger", "keep", "max_turns"):
        v = getattr(a, k)
        if v is not None:
            cfg[k] = v

    client = get_client()
    docs = build_corpus(cfg["docs"], cfg["doc_tokens"])
    common = dict(trigger=cfg["trigger"], keep=cfg["keep"], max_turns=cfg["max_turns"])

    t0 = time.perf_counter()
    base_rec, base_text = run_agent(client, a.model, docs, managed=False, **common)
    man_rec, man_text = run_agent(client, a.model, docs, managed=True, **common)
    elapsed = time.perf_counter() - t0

    base_ans, man_ans = parse_answer(base_text), parse_answer(man_text)
    print_report(docs, a.model, base_rec, base_ans, man_rec, man_ans)

    out = {
        "model": get(a.model).id,
        "config": cfg,
        "elapsed_s": round(elapsed, 1),
        "gold": sum(1 for d in docs if d["urgent"]),
        "baseline": {"records": base_rec, "answer": base_ans, **summarize(base_rec)},
        "managed": {"records": man_rec, "answer": man_ans, **summarize(man_rec)},
    }
    data_dir = repo_root() / "data"
    data_dir.mkdir(exist_ok=True)
    (data_dir / "last_demo.json").write_text(json.dumps(out, indent=2))
    print(f"  wrote receipts to data/last_demo.json  ({elapsed:.0f}s wall)\n")


if __name__ == "__main__":
    main()
