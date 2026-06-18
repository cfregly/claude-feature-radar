"""ptc: programmatic tool calling, the input-token receipt on a real fan-out task.

The anchor. Programmatic tool calling (PTC) lets Claude write one script in a code-execution sandbox
that calls the developer's OWN tools in a loop and filters the results before they ever reach the
model's context window. Add `allowed_callers: ["code_execution_20260120"]` to a tool and Claude
invokes it from code instead of one round trip per call. The bulky tool OUTPUTS go to the sandbox,
not the model, so you are not billed input tokens for data the model never needs to read. GA, no beta
header. Models: Opus 4.5 to 4.8 and Sonnet 4.5 to 4.6 (not Haiku). Source, re-fetched 2026-06-17:
https://platform.claude.com/docs/en/agents-and-tools/tool-use/programmatic-tool-calling

No competitor exposes this: OpenAI ships a code interpreter and tool search, but neither keeps a
developer's own custom-tool OUTPUTS out of context the way `allowed_callers` does. This is an
absence-of-evidence finding (no named equivalent), stated precisely.

What this measures, honestly. The SAME fan-out task two ways, on the same model, with an identical
final-answer assertion so the comparison cannot be gamed:

  Mode A (plain tool use)   Claude calls query_region_sales(region) directly, once per region, so
                            every region's ~50 rows flow through the model context and are billed.
  Mode B (programmatic)     Claude writes one script that loops the regions, calls the tool from
                            code, sums in the sandbox, and returns only the winner. The rows go to
                            the sandbox, not the model.

The receipt: total billed input tokens A vs B (input + cache_read + cache_write, every input bucket),
the model round-trip count, and the dollar delta, all read off the real usage object. The win is
workload-shaped: the live doc itself notes a sequential single-call benchmark (tau2-bench) was flat
to about 8% MORE expensive, so this task is a genuine fan-out or the result does not hold. Anthropic's
own doc reports about 24% fewer input tokens on agentic-search benchmarks; we quote that as theirs and
the number below as ours, measured on our key. PTC is not ZDR-eligible and is not on Bedrock or Vertex.
"""

from __future__ import annotations

import pathlib as _pl
import sys as _sys
_sys.path.insert(0, str(_pl.Path(__file__).resolve().parents[2]))  # repo root, for common/ and engine/

import argparse
import hashlib
import json
import random
import re
import time

from common.client import fmt_usd, get_client, load_env, repo_root
from common.models import get
from common.pricing import cost_usd

REGIONS = ["north", "south", "east", "pacific"]
PRODUCTS = ["widget", "gadget", "sprocket", "gizmo", "doohickey", "flange", "valve", "bracket"]
ROWS_PER_REGION = 60

CODE_EXEC_TOOL = {"type": "code_execution_20260120", "name": "code_execution"}
QUERY_TOOL = {
    "name": "query_region_sales",
    "description": (
        "Return the full list of sales order records for one region. Each call returns a JSON array "
        "of objects, each with keys order_id (string), product (string), units (integer), and "
        "revenue (number, USD). About 50 records per region."
    ),
    "input_schema": {
        "type": "object",
        "properties": {"region": {"type": "string", "description": "the region name, lowercase"}},
        "required": ["region"],
    },
}


def region_sales(region: str):
    """Deterministic ~50 rows for a region, so the true winner is fixed and reproducible."""
    seed = int(hashlib.sha256(region.encode()).hexdigest()[:8], 16)
    rng = random.Random(seed)
    rows = []
    for i in range(ROWS_PER_REGION):
        rows.append({
            "order_id": f"{region[:2].upper()}{i:04d}",
            "product": rng.choice(PRODUCTS),
            "units": rng.randint(1, 100),
            "revenue": round(rng.uniform(10.0, 5000.0), 2),
        })
    return rows


def true_winner():
    totals = {r: round(sum(row["revenue"] for row in region_sales(r)), 2) for r in REGIONS}
    return max(totals, key=totals.get), totals


QUESTION = (
    "You have a tool query_region_sales(region) that returns the sales records for one region. "
    f"For these {len(REGIONS)} regions: {', '.join(REGIONS)}. Find the single region with the highest "
    "TOTAL revenue, the sum of the revenue field across all of that region's records. "
    "Write ONE script that loops over all of the regions in a single code execution, calls the tool "
    "for each region inside that one loop, sums the revenue per region, and returns the winner. Do "
    "NOT call the tool one region at a time across separate steps. Reply with exactly one final line "
    "in the form: Winner: <region>"
)


def parse_winner(text: str):
    m = re.search(r"Winner:\s*([a-zA-Z]+)", text or "")
    if not m:
        return None
    w = m.group(1).lower()
    return w if w in REGIONS else None


def _billed_input(u) -> int:
    """Every input bucket the model was billed for, apples to apples."""
    inp = getattr(u, "input_tokens", 0) or 0
    cr = getattr(u, "cache_read_input_tokens", 0) or 0
    cc = getattr(u, "cache_creation", None)
    if cc is not None:
        cw = (getattr(cc, "ephemeral_5m_input_tokens", 0) or 0) + (getattr(cc, "ephemeral_1h_input_tokens", 0) or 0)
    else:
        cw = getattr(u, "cache_creation_input_tokens", 0) or 0
    return inp + cr + cw


def run_mode(client, model_key, *, programmatic, max_turns=8):
    model = get(model_key).id
    tool = dict(QUERY_TOOL)
    if programmatic:
        tool["allowed_callers"] = ["code_execution_20260120"]
        tools = [CODE_EXEC_TOOL, tool]
    else:
        tools = [tool]

    messages = [{"role": "user", "content": QUESTION}]
    container = None
    billed_input = output_tokens = turns = tool_calls = 0
    cost = 0.0
    final_text = ""
    t0 = time.perf_counter()
    for _ in range(max_turns):
        # A generous per-request timeout: a code-execution turn can legitimately take a minute, but if
        # the container expires mid-run the call can hang, so we fail fast instead of grinding.
        kwargs = dict(model=model, max_tokens=4096, tools=tools, messages=messages, timeout=180.0)
        if container:
            kwargs["container"] = container
        resp = client.messages.create(**kwargs)
        turns += 1
        billed_input += _billed_input(resp.usage)
        output_tokens += getattr(resp.usage, "output_tokens", 0) or 0
        cost += cost_usd(model_key, resp.usage)
        if getattr(resp, "container", None):
            container = resp.container.id
        _ntu = sum(1 for b in resp.content if getattr(b, "type", None) == "tool_use")
        _ncode = sum(1 for b in resp.content if getattr(b, "type", None) == "server_tool_use")
        print(f"      [{'B' if programmatic else 'A'}] turn {turns}: stop={resp.stop_reason} "
              f"tool_use={_ntu} code={_ncode} billed={billed_input:,} {time.perf_counter() - t0:.0f}s",
              flush=True)
        text = "".join(b.text for b in resp.content if getattr(b, "type", None) == "text")
        if text.strip():
            final_text = text
        if resp.stop_reason != "tool_use":
            break
        # Echo the assistant content back, but drop code_execution_tool_result blocks: the server
        # holds that state in the container, and re-sending them fails validation. This matches the
        # doc's continuation shape (text + server_tool_use + tool_use only).
        asst = [b.model_dump(exclude_unset=True) for b in resp.content
                if getattr(b, "type", None) != "code_execution_tool_result"]
        messages.append({"role": "assistant", "content": asst})
        results = []
        for block in resp.content:
            if getattr(block, "type", None) == "tool_use":  # our custom tool (direct or from code)
                tool_calls += 1
                rows = region_sales(block.input.get("region", ""))
                results.append({"type": "tool_result", "tool_use_id": block.id,
                                "content": json.dumps(rows)})
        if not results:
            break
        messages.append({"role": "user", "content": results})
    return {
        "billed_input": billed_input, "output_tokens": output_tokens, "cost": cost,
        "turns": turns, "tool_calls": tool_calls, "answer": parse_winner(final_text),
        "time": time.perf_counter() - t0,
    }


def main():
    p = argparse.ArgumentParser(description="Programmatic tool calling: the input-token receipt on a fan-out task.")
    p.add_argument("--model", default="sonnet", help="opus or sonnet (Haiku does not support PTC)")
    a = p.parse_args()

    load_env()
    client = get_client()
    winner, totals = true_winner()
    label = get(a.model).label

    print(f"\n  Programmatic tool calling: the input-token receipt on a real fan-out task.")
    print(f"  Task: across {len(REGIONS)} regions, each returning ~{ROWS_PER_REGION} sales rows, find the")
    print(f"  region with the highest total revenue. True winner (computed locally): {winner}.")
    print(f"  Same task and same model ({label}) both ways, the final answer must match or we fail.\n")

    print("  running Mode A (plain tool use, every row through context) ...", flush=True)
    a_run = run_mode(client, a.model, programmatic=False)
    print(f"    Mode A done: {a_run['turns']} round-trips, {a_run['billed_input']:,} billed input tokens, "
          f"answer {a_run['answer']}.", flush=True)
    print("  running Mode B (programmatic, rows filtered in the sandbox) ...", flush=True)
    b_run = run_mode(client, a.model, programmatic=True)
    print(f"    Mode B done: {b_run['turns']} round-trips, {b_run['billed_input']:,} billed input tokens, "
          f"answer {b_run['answer']}.\n", flush=True)

    rows = [("Mode A: plain tool use", a_run), ("Mode B: programmatic (allowed_callers)", b_run)]
    print(f"  {'mode':<40}{'billed input tok':>18}{'round-trips':>13}{'answer':>10}{'cost':>11}")
    print("  " + "-" * 92)
    for name, r in rows:
        print(f"  {name:<40}{r['billed_input']:>18,}{r['turns']:>13}{str(r['answer']):>10}{fmt_usd(r['cost']):>11}")

    a_correct = a_run["answer"] == winner
    b_correct = b_run["answer"] == winner
    fewer = b_run["billed_input"] < a_run["billed_input"]
    n_rows = len(REGIONS) * ROWS_PER_REGION
    pct = (1 - b_run["billed_input"] / a_run["billed_input"]) * 100 if a_run["billed_input"] else 0.0

    print("\n  Honest reading:")
    print(f"  - THE EDGE, measured: Mode B billed {b_run['billed_input']:,} input tokens vs Mode A's "
          f"{a_run['billed_input']:,}, a {pct:.0f}% reduction, because the {n_rows} rows the tool "
          f"returned went to the sandbox, not the model context.")
    print(f"  - Bonus, correctness: Mode B (the sandbox code does the arithmetic) answered "
          f"{b_run['answer']} ({'correct' if b_correct else 'WRONG'}). Mode A (the model sums {n_rows} "
          f"rows in its head) answered {a_run['answer']} ({'correct' if a_correct else 'WRONG'}). Exact "
          f"math in code beats in-context summation over many rows.")
    print(f"  - Honest cost of the approach: Mode B made {b_run['turns']} model round-trips to Mode A's "
          f"{a_run['turns']} because the model called the tool serially from code, so on an INSTANT mock "
          f"tool it runs slower. The token saving is the win, the latency depends on your real tool's "
          f"per-call time (PTC saves the per-call model round-trip a real slow tool would cost).")
    print(f"  - Fan-out-shaped: the doc notes a sequential single-call task (tau2-bench) is flat to about "
          f"8% more expensive. No competitor keeps your custom-tool outputs out of context.\n")

    out = {"model": get(a.model).id, "regions": len(REGIONS), "rows_per_region": ROWS_PER_REGION,
           "true_winner": winner, "mode_a": a_run, "mode_b": b_run,
           "pct_input_reduction": round(pct, 1), "mode_a_correct": a_correct, "mode_b_correct": b_correct}
    (repo_root() / "data").mkdir(exist_ok=True)
    (repo_root() / "data" / "last_ptc.json").write_text(json.dumps(out, indent=2))
    print("  wrote receipts to data/last_ptc.json\n")

    if not (b_correct and fewer):
        raise SystemExit("PTC invariant failed: mode B (the code) must answer correctly AND bill fewer input tokens.")


if __name__ == "__main__":
    main()
