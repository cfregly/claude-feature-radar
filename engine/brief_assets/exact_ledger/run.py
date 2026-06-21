"""exact_ledger: keep an exact running list across a long tool-heavy agent, with Claude context editing.

A long agent reads a stream of bulky records through a tool (incident reports, fraud flags, billing
exceptions, support escalations) and must report the EXACT list of flagged ids at the end. The bulky
record text is disposable after each step, but the running ledger must stay exact. Claude context
editing clears the old tool RESULTS in place once the context crosses a trigger, so the bulky text
leaves the window while the assistant turns that carry the running list stay intact. The carried
context stays flat instead of growing with every record, and the list stays exact.

Usage:
    python -m exact_ledger.run            # run the long-stream ledger agent, print the table
    python -m exact_ledger.run --check    # cheap live self-test that asserts the win invariant ($0.17)

Cost: $0.17 for --check on the 2026-06-19 run (Claude Haiku 4.5).
Docs: https://platform.claude.com/docs/en/build-with-claude/context-editing
"""

from __future__ import annotations

import argparse
import random
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from .common.models import get
from .common.pricing import cost_usd

# Context editing is a beta. The founder must set this header on the request.
BETA_HEADER = "context-management-2025-06-27"
EXEC_MODEL = "haiku"          # Claude Haiku 4.5, the cheap tier; the win holds up the tiers too
URGENT_EVERY = 3              # every third report is URGENT (deterministic ground truth)
CHAIN_SEED = 42              # fixed seed: the chain is identical every run, so the result reproduces

# Default workload: 8 bulky records in a chain, each about 20,000 tokens.
DOCS = 8
DOC_TOKENS = 20000
# Clear the old tool results once the carried context crosses this many input tokens, keeping the most
# recent KEEP tool results. Aggressive clearing (keep=1) holds the window near one record.
TRIGGER = 30000
KEEP = 1
MAX_TURNS = 18
# With clearing OFF this stream accumulates to about 125,000 carried tokens (measured). With clearing
# ON it holds near one record (about 17,000). The bound proves the context stayed flat, not unbounded.
FLAT_CTX_BOUND = 45000

# The comparison gate default. The generator bakes this per surface: the public brief ships it OFF, so
# `make exact_ledger` runs the Claude side alone on one dependency, and `make exact_ledger COMPARE=1`
# (or --compare) reproduces the OpenAI compaction and Gemini full-window head-to-head. A private
# both-directions checkout ships it ON. Either way --compare / --no-compare overrides it.
COMPARE_DEFAULT = {compare_default}


# --------------------------------------------------------------------------------- the workload corpus

def build_chain(n_docs: int, approx_tokens: int):
    """A chain of incident reports. Returns (docs_by_id, start_id).

    Each report ends with the id of the next report, in a fixed shuffled order, so the agent cannot
    batch: it only learns the next id by reading the current report. That makes the long horizon real.
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


def ledger_prompt(start: int) -> str:
    """The exact-list task. The agent keeps the full running list in its own reply each turn, because
    it cannot re-read earlier reports once their tool results are cleared. The precious state lives in
    the reasoning, and context editing preserves exactly that while clearing the bulky tool results."""
    return (
        f"You are auditing a chain of incident reports for URGENT items. Start by reading report "
        f"{start} with the read_document tool. Each report ends with the id of the next report to "
        f"read. Follow that pointer one report at a time until a report says the next one is `done`. "
        f"You must read every report before `done`.\n\n"
        f"A report is URGENT when its header says `Priority: URGENT`. Collect the exact ids of every "
        f"URGENT report.\n\n"
        f"You cannot re-read earlier reports, so maintain your list as you go. After you read each "
        f"report, write a single line `Running URGENT ids: [ ... ]` with your complete sorted list so "
        f"far.\n\n"
        f"When a report says the next id is `done`, reply with a single final line in the form "
        f"`Answer: [id, id, id]`, the complete sorted list of all URGENT report ids (for example "
        f"`Answer: [0, 3, 6]`). Output nothing else on that line."
    )


# --------------------------------------------------------------------------------------- the Claude arm

def _text_of(msg) -> str:
    return "".join(b.text for b in msg.content if getattr(b, "type", None) == "text").strip()


def _ctx_tokens(usage) -> int:
    """True carried context = every input bucket the model processed this turn. On the turn right
    after context editing clears, almost the whole prefix is a fresh cache WRITE, so input_tokens
    drops to about 1 and the write bucket carries it. Summing all three avoids undercounting."""
    _in = getattr(usage, "input_tokens", 0) or 0
    _cr = getattr(usage, "cache_read_input_tokens", 0) or 0
    cc = getattr(usage, "cache_creation", None)
    if cc is not None:
        _cw = (getattr(cc, "ephemeral_5m_input_tokens", 0) or 0) + \
              (getattr(cc, "ephemeral_1h_input_tokens", 0) or 0)
    else:
        _cw = getattr(usage, "cache_creation_input_tokens", 0) or 0
    return _in + _cr + _cw


def _mark_cache(messages):
    """One rolling cache breakpoint on the last block, so the whole prefix caches (best config)."""
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


def run_ledger_agent(docs, start, *, trigger=TRIGGER, keep=KEEP, max_turns=MAX_TURNS):
    """Run the long-stream ledger audit once on Claude, caching on, context editing on.

    Returns (records, final_text). Each record carries the per-turn carried context and cost, read off
    the real usage object. The win is attributable to context editing: it is the only managed feature
    on, and the prompt and corpus are held fixed.
    """
    from .common.client import get_client  # lazy: keep the one-dependency import out of module load

    client = get_client()
    model = get(EXEC_MODEL)
    messages = [{"role": "user", "content": ledger_prompt(start)}]
    kw_extra = {
        "extra_headers": {"anthropic-beta": BETA_HEADER},        # add this: turn context editing on
        "extra_body": {                                          # add this: clear stale tool results
            "context_management": {
                "edits": [{
                    "type": "clear_tool_uses_20250919",
                    "trigger": {"type": "input_tokens", "value": trigger},
                    "keep": {"type": "tool_uses", "value": keep},
                }]
            }
        },
    }

    records, final_text = [], ""
    for turn in range(max_turns):
        _mark_cache(messages)
        t0 = time.perf_counter()
        msg = client.messages.create(
            model=model.id, max_tokens=1024, messages=messages, tools=[READ_TOOL], **kw_extra,
        )
        records.append({
            "turn": turn,
            "ctx": _ctx_tokens(msg.usage),
            "cost": cost_usd(model.key, msg.usage),
            "latency_s": time.perf_counter() - t0,
        })
        if msg.stop_reason != "tool_use":
            final_text = _text_of(msg)
            break
        messages.append({"role": "assistant", "content": msg.content})
        results = []
        for tu in msg.content:
            if getattr(tu, "type", None) != "tool_use":
                continue
            did = tu.input.get("doc_id")
            content = docs[did]["text"] if did in docs else f"Error: no document with id {did}"
            results.append({"type": "tool_result", "tool_use_id": tu.id, "content": content})
        messages.append({"role": "user", "content": results})

    return records, final_text


def parse_list(text):
    if not text:
        return None
    m = re.search(r"Answer:\s*\[([0-9,\s]*)\]", text)
    if not m:
        return None
    return sorted({int(x) for x in m.group(1).split(",") if x.strip()})


# --------------------------------------------------------------------------------------------- commands

def _run_once(docs, start, trigger=TRIGGER, keep=KEEP, max_turns=MAX_TURNS):
    gold = sorted(d["id"] for d in docs.values() if d["urgent"])
    t0 = time.perf_counter()
    recs, text = run_ledger_agent(docs, start, trigger=trigger, keep=keep, max_turns=max_turns)
    elapsed = time.perf_counter() - t0
    answer = parse_list(text)
    cost = sum(r["cost"] for r in recs)
    peak = max((r["ctx"] for r in recs), default=0)
    return gold, answer, cost, elapsed, peak


def _maybe_compare(cost, answer, gold, compare_on: bool) -> None:
    """When the comparison gate is on, run the same ledger agent on OpenAI (compaction) and Gemini (full
    window) over the same chain and print the cost-at-equal-correctness table. Imported lazily, so the
    default Claude-only run never touches the comparison code or its optional SDKs."""
    if not compare_on:
        return
    from .compare import append_comparison  # lazy: the comparison SDKs load only here
    append_comparison(EXEC_MODEL, {"cost": cost, "exact": answer == gold})


def cmd_run(a) -> int:
    docs, start = build_chain(a.docs, a.doc_tokens)
    print(f"\n  Exact-list ledger over a {a.docs}-report chain, each report about {a.doc_tokens:,} "
          f"tokens.\n  Claude {get(EXEC_MODEL).label}, context editing on (clear old tool results, "
          f"keep {KEEP}).\n")
    gold, answer, cost, elapsed, peak = _run_once(docs, start)
    print(f"  {'metric':<22}{'value':>16}")
    print("  " + "-" * 38)
    print(f"  {'gold URGENT ids':<22}{str(gold):>16}")
    print(f"  {'Claude answer':<22}{str(answer):>16}")
    print(f"  {'exact list':<22}{('yes' if answer == gold else 'no'):>16}")
    print(f"  {'peak carried context':<22}{peak:>16,}")
    print(f"  {'cost (USD)':<22}{('$' + format(cost, '.2f')):>16}")
    print(f"  {'wall time (s)':<22}{elapsed:>16.1f}\n")
    _maybe_compare(cost, answer, gold, COMPARE_DEFAULT if a.compare is None else a.compare)
    return 0 if answer == gold else 1


def cmd_check(a) -> int:
    """Cheap live self-test. Asserts the win invariant: the exact list is preserved AND context
    editing held the carried context flat (peak well below the unbounded sum). About $0.17."""
    docs, start = build_chain(DOCS, DOC_TOKENS)
    print(f"\n  self-test: exact list preserved with context held flat (~$0.17, {get(EXEC_MODEL).label})")
    print(f"  beta header: {BETA_HEADER}\n")
    gold, answer, cost, elapsed, peak = _run_once(docs, start)
    print(f"  gold URGENT ids: {gold}")
    print(f"  Claude answer:   {answer}")
    print(f"  exact: {answer == gold}   peak ctx: {peak:,} (flat bound {FLAT_CTX_BOUND:,})")
    print(f"  cost: ${cost:.2f}   wall: {elapsed:.1f}s\n")
    assert answer == gold, f"NOT exact: {answer} != {gold}"
    assert peak < FLAT_CTX_BOUND, f"context not held flat: peak {peak} >= {FLAT_CTX_BOUND}"
    print("  CHECK PASSED: exact list preserved while context editing held the context flat\n")
    _maybe_compare(cost, answer, gold, COMPARE_DEFAULT if a.compare is None else a.compare)
    return 0


def main() -> int:
    p = argparse.ArgumentParser(description="Exact-list ledger over a long stream, with context editing.")
    p.add_argument("--check", action="store_true", help="cheap live self-test that asserts the win")
    p.add_argument("--docs", type=int, default=DOCS)
    p.add_argument("--doc-tokens", type=int, default=DOC_TOKENS)
    p.add_argument("--compare", dest="compare", action="store_true", default=None,
                   help="also run the OpenAI and Gemini ledger arms and print the cost-at-equal-correctness "
                        "table (needs OPENAI_API_KEY, GEMINI_API_KEY, requirements-compare.txt)")
    p.add_argument("--no-compare", dest="compare", action="store_false",
                   help="run only the Claude side (the public-brief default)")
    a = p.parse_args()
    return cmd_check(a) if a.check else cmd_run(a)


if __name__ == "__main__":
    raise SystemExit(main())
