"""yourtool: THE single file you edit to run the bill-cut on your own tool.

HOW TO RUN THIS ON YOUR OWN TOOL (3 steps):
  1. Replace TOOL_SPEC below with your own Messages-API tool dict (the same dict you already pass in
     tools=[...]): name, description, input_schema.
  2. Replace call(...) with the function that actually runs your tool. Its keyword arguments match
     input_schema's properties, and it returns whatever the model would normally get back (a list,
     dict, or string).
  3. Set QUESTION and EXAMPLE_INPUTS to your own fan-out task, the prompt that makes the model call
     your tool many times.
Then run `make app` to see your own before and after token count. The shipped example (region_sales)
runs out of the box, so `make app-check` works before you change anything.

Replace the two things below with your own tool and you are done:

  TOOL_SPEC   a Messages-API tool dict: name, description, input_schema. The exact dict you already
              pass in `tools=[...]`. Copy yours in.
  call(...)   the Python that actually runs your tool. It takes the tool's input arguments as keyword
              arguments (matching input_schema's properties) and returns a JSON-serializable result
              (a list, a dict, a string). This is your real backend: a database query, an API call,
              a file read. Whatever the model would get back.

QUESTION and EXAMPLE_INPUTS describe the fan-out task: a prompt that makes the model call your tool
many times, and the list of inputs it should fan out over. Programmatic tool calling pays off when the
model calls a tool many times and the bulky outputs would otherwise flow through its context, so the
task has to fan out. On a sequential single-call task the doc reports it is flat to about 8% more
expensive, so a one-shot task is the wrong shape and the bill will not drop.

Out of the box this ships a WORKED EXAMPLE: a region_sales tool that returns about 60 sales rows per
region, and a task that asks for the highest-revenue region across four regions (240 rows). That is
the same fan-out the repo's programmatic-tool-calling receipt measures, so `python -m app.billcut
--check` gives you a real before/after number before you change a line. Then swap in your own.

Nothing here imports anthropic. yourtool is data plus a plain Python function. app/billcut.py drives it.
"""

from __future__ import annotations

import hashlib
import random

# --------------------------------------------------------------------------- the worked example
# A deterministic mock backend so the shipped example has a fixed, reproducible true answer. Replace
# this whole block with your own tool. The seed makes region_sales(region) return the same ~60 rows
# every run, so "the highest-revenue region" is a fact a founder can check by hand, not a coin flip.

REGIONS = ["north", "south", "east", "pacific"]
PRODUCTS = ["widget", "gadget", "sprocket", "gizmo", "doohickey", "flange", "valve", "bracket"]
ROWS_PER_REGION = 60


def _region_sales(region: str):
    """About 60 deterministic sales rows for one region. This is the EXAMPLE backend, swap it out."""
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


# --------------------------------------------------------------------------- THE EDIT SURFACE
# Replace TOOL_SPEC and call() with your own tool. Keep the shape: a Messages-API tool dict, and a
# Python function whose keyword arguments match input_schema's properties.

TOOL_SPEC = {
    "name": "query_region_sales",
    "description": (
        "Return the full list of sales order records for one region. Each call returns a JSON array "
        "of objects, each with keys order_id (string), product (string), units (integer), and "
        "revenue (number, USD). About 60 records per region."
    ),
    "input_schema": {
        "type": "object",
        "properties": {"region": {"type": "string", "description": "the region name, lowercase"}},
        "required": ["region"],
    },
}


def call(region: str = ""):
    """Run the tool for one input and return a JSON-serializable result. Your real backend goes here.

    The example reads the deterministic mock above. Replace the body with your database query, API
    call, or file read. The return value is what the model (or the sandbox, under programmatic tool
    calling) receives as the tool result.
    """
    return _region_sales(region)


# The fan-out task: a prompt that makes the model call the tool once per input, and the list of inputs.
# Replace these with your own task and the inputs it fans out over.
EXAMPLE_INPUTS = REGIONS

QUESTION = (
    "You have a tool query_region_sales(region) that returns the sales records for one region. "
    f"For these {len(REGIONS)} regions: {', '.join(REGIONS)}. Find the single region with the highest "
    "TOTAL revenue, the sum of the revenue field across all of that region's records. "
    "Write ONE script that loops over all of the regions in a single code execution, calls the tool "
    "for each region inside that one loop, sums the revenue per region, and returns the winner. Do "
    "NOT call the tool one region at a time across separate steps. Reply with exactly one final line "
    "in the form: Winner: <region>"
)


# --------------------------------------------------------------------------- the example's check
# Only the shipped example needs a machine-checkable true answer, so `billcut --check` can assert the
# model answered correctly. When you swap in your own tool, set EXPECTED_ANSWER to your task's known
# answer (or leave it None and --check will only assert the token invariant, not correctness).

def _true_winner() -> str:
    totals = {r: sum(row["revenue"] for row in _region_sales(r)) for r in REGIONS}
    return max(totals, key=totals.get)


EXPECTED_ANSWER = _true_winner()  # the example's known answer, set to your own (or None) when you swap


def parse_answer(text: str):
    """Pull the final answer out of the model's last text. The example uses 'Winner: <region>'.

    Replace this with however your task states its answer. It returns a normalized string to compare
    against EXPECTED_ANSWER, or None when the model did not answer in the expected form.
    """
    import re
    m = re.search(r"Winner:\s*([a-zA-Z]+)", text or "")
    if not m:
        return None
    w = m.group(1).lower()
    return w if w in REGIONS else None
