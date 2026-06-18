"""A cost-claim gate: the citations costs in the prose and the README table match the receipt.

The `make citations` run cost is a sum of four arms and is dominated by the Gemini arm's token
count, so it moves whenever the benchmark is re-run. The figure is quoted in two layers, both of
which can silently rot the way the stale "about thirty cents" did:

  1. the total, in three prose spots: EMAIL.md, README.md, and the Makefile `citations:` target.
  2. the per-arm cost and output-token columns of the README "measured proof" table.

This gate re-sums the committed receipt and checks both layers against it.

Source of truth is the COMMITTED receipt, sample_citations.txt, because that is what the README
table and the prose ship from. data/last_citations.json is gitignored scratch from the last local
run (possibly a quick smoke or a run not yet promoted to the committed snapshot), so it never
decides pass or fail. When it diverges from the committed receipt the gate prints a non-fatal note,
which is the heads-up to refresh the snapshot, the table, and the claim sites together.

Stdlib only, runs offline, exits non-zero on drift.
"""

import json
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
TOLERANCE_CENTS = 1       # the total is stated as "about", so a one-cent rounding choice is fine
TABLE_COST_TOL = 0.001    # the README table shows costs to three decimals

ONES = ["zero", "one", "two", "three", "four", "five", "six", "seven", "eight",
        "nine", "ten", "eleven", "twelve", "thirteen", "fourteen", "fifteen",
        "sixteen", "seventeen", "eighteen", "nineteen"]
TENS = {20: "twenty", 30: "thirty", 40: "forty", 50: "fifty", 60: "sixty",
        70: "seventy", 80: "eighty", 90: "ninety"}
ONES_IDX = {w: i for i, w in enumerate(ONES)}
TENS_IDX = {w: n for n, w in TENS.items()}

# (file, regex with one capturing group for the total, kind). Each pattern is anchored tightly
# enough to match only the citations cost claim, not the other "about $X" comments in the Makefile
# or the "about 37x" ratios in the prose.
CLAIMS = [
    {"file": "edges/citations/FOUNDER_EMAIL.md", "pattern": r"[Aa]bout ([a-z][a-z-]*) cents", "kind": "words"},
    {"file": "edges/citations/README.md", "pattern": r"about ([a-z][a-z-]*) cents", "kind": "words"},
    {"file": "Makefile", "pattern": r"^citations:.*about \$(\d+\.\d{2})", "kind": "dollars"},
]


def words_to_cents(s):
    s = s.strip().lower()
    if s in ONES_IDX:
        return ONES_IDX[s]
    if s in TENS_IDX:
        return TENS_IDX[s]
    if "-" in s:
        tens, ones = s.split("-", 1)
        if tens in TENS_IDX and ones in ONES_IDX and 1 <= ONES_IDX[ones] <= 9:
            return TENS_IDX[tens] + ONES_IDX[ones]
    raise ValueError(f"cannot parse spelled-out cents: {s!r}")


def cents_to_words(n):
    if n < 20:
        return ONES[n]
    tens, ones = divmod(n, 10)
    base = TENS[tens * 10]
    return base if ones == 0 else f"{base}-{ONES[ones]}"


def snapshot_arms(path):
    """Per-arm (output_tokens, cost) from the committed receipt, in table order."""
    arms = []
    for line in path.read_text().splitlines():
        # an arm row carries a resolved/total fraction and ends with output-tokens then cost
        if re.search(r"\d/8", line):
            m = re.search(r"([\d,]+)\s+(\d+\.\d+)\s*$", line)
            if m:
                arms.append((int(m.group(1).replace(",", "")), float(m.group(2))))
    return arms


def readme_table_arms(path):
    """Per-arm (output_tokens, cost) from the README measured-proof table, in row order.

    Located by its header (the only table with both 'resolves' and 'output tokens'), so the
    cost/time credibility table further down the README is not picked up by mistake.
    """
    lines = path.read_text().splitlines()
    for i, line in enumerate(lines):
        head = line.strip().lower()
        if head.startswith("|") and "resolves" in head and "output tokens" in head:
            arms, j = [], i + 2  # skip the header and the |---| separator
            while j < len(lines) and lines[j].strip().startswith("|"):
                cells = [c.strip() for c in lines[j].strip().strip("|").split("|") if c.strip()]
                tok = cells[-2].replace(",", "").replace("*", "").strip()
                cost = cells[-1].replace("$", "").replace("*", "").strip()
                arms.append((int(tok), float(cost)))
                j += 1
            return arms
    return None


def main():
    snapshot = ROOT / "edges" / "citations" / "sample.txt"
    if not snapshot.exists():
        print("cost-claim gate: SKIP (no committed receipt edges/citations/sample.txt found)")
        return
    arms = snapshot_arms(snapshot)
    cents = round(sum(cost for _, cost in arms) * 100)
    if cents >= 100:
        print("cost-claim gate: FAIL")
        print(f"  committed receipt now sums to ${cents / 100:.2f}, which no longer fits the 'about N cents' phrasing")
        print("  reword the three claim sites (EMAIL.md, README.md, Makefile) and this gate")
        sys.exit(1)

    want_words = cents_to_words(cents)
    want_dollars = f"${cents / 100:.2f}"

    failures = []

    # Layer 1: the total, in the three prose claim sites.
    for claim in CLAIMS:
        path = ROOT / claim["file"]
        if not path.exists():
            continue
        for lineno, line in enumerate(path.read_text().splitlines(), 1):
            match = re.search(claim["pattern"], line)
            if match:
                raw = match.group(1)
                break
        else:
            failures.append(f"{claim['file']}: no citations cost claim found")
            continue
        if claim["kind"] == "words":
            claimed, shown, want_shown = words_to_cents(raw), f"{raw} cents", want_words
        else:
            claimed, shown, want_shown = round(float(raw) * 100), f"${raw}", want_dollars
        if abs(claimed - cents) > TOLERANCE_CENTS:
            failures.append(f"{claim['file']}:{lineno} total claims {shown}  STALE -> {want_shown}")

    # Layer 2: the per-arm cost and output-token columns of the edge README proof table.
    table = readme_table_arms(ROOT / "edges" / "citations" / "README.md")
    if table is None:
        failures.append("edges/citations/README.md: could not locate the measured-proof table to check per-arm costs")
    elif len(table) != len(arms):
        failures.append(f"README.md table has {len(table)} arms, the receipt has {len(arms)}")
    else:
        for idx, ((r_tok, r_cost), (t_tok, t_cost)) in enumerate(zip(arms, table), 1):
            if abs(r_cost - t_cost) > TABLE_COST_TOL:
                failures.append(f"README.md table arm {idx} cost ${t_cost:.3f}  STALE -> ${r_cost:.3f}")
            if r_tok != t_tok:
                failures.append(f"README.md table arm {idx} output tokens {t_tok}  STALE -> {r_tok}")

    if failures:
        print("cost-claim gate: FAIL")
        print(f"  committed receipt sample_citations.txt: total {want_dollars}, {len(arms)} arms")
        for f in failures:
            print(f"  {f}")
    else:
        print(f"cost-claim gate: clean (committed receipt {want_dollars}, "
              f"3 prose claims and {len(arms)} table arms agree)")

    # Non-fatal: the last local run is scratch, but flag when it has drifted from the committed
    # snapshot so a stale committed receipt does not slip by unnoticed.
    scratch = ROOT / "data" / "last_citations.json"
    if scratch.exists():
        live = round(sum(a["cost"] for a in json.loads(scratch.read_text())["summaries"]) * 100)
        if abs(live - cents) > TOLERANCE_CENTS:
            print(f"  note: data/last_citations.json (last local run) sums to ${live / 100:.2f}, "
                  f"the committed receipt is {want_dollars}.")
            print("  if the newer run is the one to ship, refresh sample_citations.txt, the README "
                  "table, and the three claim sites together, then re-run this gate.")

    if failures:
        sys.exit(1)


if __name__ == "__main__":
    main()
