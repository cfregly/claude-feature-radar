"""A cost-claim gate: the citations cost in the prose and the README table matches the receipt.

The `make citations` edge runs one Claude Citations arm, so its cost moves a little whenever the
benchmark is re-run. The figure is quoted in two layers, both of which can rot:

  1. the total dollar figure, in two prose spots: README.md and the Makefile.
  2. the per-arm cost and output-token columns of the README measured-proof table.

This gate re-sums the committed receipt (edges/citations/sample.txt) and checks both layers at
cents-level precision. Stdlib only, runs offline, exits non-zero on meaningful drift.
"""

import json
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
TOLERANCE_CENTS = 2
TABLE_COST_TOL = 0.015

# (file, regex with one capturing group for the dollar total). Each is anchored tightly enough to
# match only the citations cost claim, not another "$X" figure in the same file.
# NOTE: the citations founder email draft (emails/drafts/citations_FOUNDER_EMAIL.md) is NOT listed here on purpose.
# That email tells the reader to clone claude-feature-hits and run the BRIEF's `make citations`, gated
# by the hits repo's own number gate. Both that brief and this engine edge run a single Claude
# Citations arm (~$0.01).
CLAIMS = [
    {"file": "edges/citations/README.md", "pattern": r"using your own API keys?, (?:about )?\$(\d+\.\d{2})"},
    {"file": "Makefile", "pattern": r"^citations:.*\$(\d+\.\d{2})"},
]


def snapshot_arms(path):
    """Per-arm (output_tokens, cost) from the committed receipt, in table order."""
    arms = []
    for line in path.read_text().splitlines():
        if re.search(r"\d/8", line):
            m = re.search(r"([\d,]+)\s+\$?(\d+\.\d+)\s*$", line)
            if m:
                arms.append((int(m.group(1).replace(",", "")), float(m.group(2))))
    return arms


def readme_table_arms(path):
    """Per-arm (output_tokens, cost) from the README measured-proof table, in row order."""
    lines = path.read_text().splitlines()
    for i, line in enumerate(lines):
        head = line.strip().lower()
        if head.startswith("|") and "resolves" in head and "output tokens" in head:
            arms, j = [], i + 2
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
    want_dollars = f"${cents / 100:.2f}"
    failures = []

    # Layer 1: the total dollar figure in the three prose claim sites.
    for claim in CLAIMS:
        path = ROOT / claim["file"]
        if not path.exists():
            continue
        for lineno, line in enumerate(path.read_text().splitlines(), 1):
            match = re.search(claim["pattern"], line)
            if match:
                claimed = round(float(match.group(1)) * 100)
                if abs(claimed - cents) > TOLERANCE_CENTS:
                    failures.append(f"{claim['file']}:{lineno} claims ${match.group(1)}  STALE -> {want_dollars}")
                break
        else:
            failures.append(f"{claim['file']}: no citations cost claim found")

    # Layer 2: the per-arm columns of the edge README proof table.
    table = readme_table_arms(ROOT / "edges" / "citations" / "README.md")
    if table is None:
        failures.append("edges/citations/README.md: could not locate the measured-proof table")
    elif len(table) != len(arms):
        failures.append(f"README.md table has {len(table)} arms, the receipt has {len(arms)}")
    else:
        for idx, ((r_tok, r_cost), (t_tok, t_cost)) in enumerate(zip(arms, table), 1):
            if abs(r_cost - t_cost) > TABLE_COST_TOL:
                failures.append(f"README.md table arm {idx} cost ${t_cost:.2f}  STALE -> ${r_cost:.2f}")
            if r_tok != t_tok:
                failures.append(f"README.md table arm {idx} output tokens {t_tok}  STALE -> {r_tok}")

    if failures:
        print("cost-claim gate: FAIL")
        print(f"  committed receipt edges/citations/sample.txt: total {want_dollars}, {len(arms)} arms")
        for f in failures:
            print(f"  {f}")
    else:
        print(f"cost-claim gate: clean (committed receipt {want_dollars}, "
              f"{len(CLAIMS)} prose claims and {len(arms)} table arms agree)")

    scratch = ROOT / "data" / "last_citations.json"
    if scratch.exists():
        live = round(sum(a["cost"] for a in json.loads(scratch.read_text())["summaries"]) * 100)
        if abs(live - cents) > TOLERANCE_CENTS:
            print(f"  note: data/last_citations.json (last local run) sums to ${live / 100:.2f}, "
                  f"the committed receipt is {want_dollars}.")

    if failures:
        sys.exit(1)


if __name__ == "__main__":
    main()
