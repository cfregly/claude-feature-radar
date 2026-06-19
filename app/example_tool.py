"""example_tool: the region_sales worked example, the one home for the shipped fixture.

This is the ready-made example the app ships with so `make app` and `make app-check` run out of the
box, and the same fixture the programmatic-tool-calling demo measures. It is a deterministic mock
backend: a region_sales tool that returns about 60 sales rows per region, and a fan-out task that
asks for the highest-revenue region across four regions (240 rows). The seed makes region_sales
return the same rows every run, so the highest-revenue region is a fact you can check by hand, not a
coin flip.

The app copies this example into app/my_tool.py (the edit surface) so a forker has a working starting
point, and edges/programmatic-tool-calling/demo.py imports the same fixture from here, so the app's
number and the demo's number come from one definition, never two.

Nothing here imports anthropic. It is data plus plain Python functions.
"""

from __future__ import annotations

import hashlib
import random
import re

REGIONS = ["north", "south", "east", "pacific"]
PRODUCTS = ["widget", "gadget", "sprocket", "gizmo", "doohickey", "flange", "valve", "bracket"]
ROWS_PER_REGION = 60


def region_sales(region: str):
    """About 60 deterministic sales rows for one region, so the true winner is fixed and reproducible."""
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


# The fan-out task: a prompt that makes the model call the tool once per input, and the list of inputs.
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


def _true_winner() -> str:
    totals = {r: sum(row["revenue"] for row in region_sales(r)) for r in REGIONS}
    return max(totals, key=totals.get)


EXPECTED_ANSWER = _true_winner()  # the example's known answer


def parse_answer(text: str):
    """Pull the final answer out of the model's last text. The example uses 'Winner: <region>'.

    Returns a normalized string to compare against EXPECTED_ANSWER, or None when the model did not
    answer in the expected form.
    """
    m = re.search(r"Winner:\s*([a-zA-Z]+)", text or "")
    if not m:
        return None
    w = m.group(1).lower()
    return w if w in REGIONS else None
