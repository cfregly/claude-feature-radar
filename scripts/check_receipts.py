"""Receipt-drift gate: every measured number in the prose traces to a committed receipt.

The repo's thesis is "numbers are receipts." This gate makes it mechanical for the numbers that
otherwise drift: a measured value lives once in a committed receipt (an edge's sample.txt, or the
model table), and any prose that quotes it must agree. A re-run that refreshes the receipt forces
the prose to follow, or the build goes red. It is the generalization of the citations cost-claim
gate to the rest of the repo. Costs vary run to run, so the gate checks internal CONSISTENCY (prose
matches the committed receipt), not live accuracy, which is the sweep's job. Stdlib only, offline.
"""

from __future__ import annotations

import datetime
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
COST_TOL = 0.03          # dollars: prose cost may round, but not wander far from the receipt total
STALE_DAYS = 45          # warn (do not fail) when a verified price is older than this


def _read(rel: str) -> str:
    p = ROOT / rel
    return p.read_text() if p.exists() else ""


def _dollars(text: str) -> list[float]:
    return [float(x) for x in re.findall(r"\$(\d+\.\d{2,4})", text)]


def check_ptc(fail, warn):
    """The PTC receipt (edges/programmatic-tool-calling/sample.txt) is the source for the billed-token
    numbers, the percent reduction, and the run cost. Every surface that quotes them must agree."""
    s = _read("edges/programmatic-tool-calling/sample.txt")
    a = re.search(r"Mode A:.*?([\d,]+)\s+\d+\s+\S+\s+\$([\d.]+)", s)
    b = re.search(r"Mode B:.*?([\d,]+)\s+\d+\s+\S+\s+\$([\d.]+)", s)
    if not (a and b):
        fail.append("PTC: could not parse the Mode A/Mode B receipt rows in sample.txt")
        return
    a_tok, a_cost = int(a.group(1).replace(",", "")), float(a.group(2))
    b_tok, b_cost = int(b.group(1).replace(",", "")), float(b.group(2))
    pct = round((1 - b_tok / a_tok) * 100)
    total = round(a_cost + b_cost, 2)

    # the stable token numbers and percent must appear verbatim where the edge is pitched
    a_str, b_str = f"{a_tok:,}", f"{b_tok:,}"
    for rel in ["README.md", "edges/programmatic-tool-calling/FOUNDER_EMAIL.md"]:
        text = _read(rel)
        if a_str not in text or b_str not in text:
            fail.append(f"PTC tokens: {rel} does not carry the receipt's {a_str}/{b_str}")
        if f"{pct}%" not in text:
            fail.append(f"PTC percent: {rel} does not carry the receipt's {pct}% reduction")

    # the run-cost claims must all agree with the receipt total (within a rounding tolerance)
    cost_files = [
        "Makefile", "README.md", "FOUNDER_EMAIL.md", "app/run_tokens.py",
        "edges/programmatic-tool-calling/README.md",
        "edges/programmatic-tool-calling/FOUNDER_EMAIL.md",
        "edges/programmatic-tool-calling/PRODUCT_EMAIL.md", "emails/ptc_FOUNDER_EMAIL.md",
    ]
    want = f"${total:.2f}"
    for rel in cost_files:
        text = _read(rel)
        # only inspect lines that mention the PTC run cost (make ptc / make app / "on Sonnet ... reproduce")
        for i, line in enumerate(text.splitlines(), 1):
            if not re.search(r"make (ptc|app)|on Sonnet|reproduce|token bill", line, re.I):
                continue
            for c in _dollars(line):
                if abs(c - total) > COST_TOL:
                    fail.append(f"PTC cost: {rel}:{i} says ${c:.2f}, receipt total is {want} "
                                f"(${a_cost:.4f}+${b_cost:.4f}); update both together")

    # the $ figure that immediately follows a 'make ptc'/'make app' claim must be the receipt total,
    # scanning across line breaks up to the next make-command (so 'make citations $0.06' is not misread)
    for rel in cost_files:
        text = _read(rel)
        for mm in re.finditer(r"make (?:ptc|app)\b", text):
            tail = re.split(r"\bmake \w", text[mm.end():mm.end() + 140])[0]
            d = _dollars(tail)
            if d and abs(d[0] - total) > COST_TOL:
                fail.append(f"PTC cost: {rel} 'make ptc/app' is followed by ${d[0]:.2f}, receipt total is {want}")


def check_ptc_drift(fail, warn):
    """Any PTC-token-shaped number (9,4xx / 6,8xx) on a founder surface must equal the receipt, so a
    stray hand-typed 6,819 cannot drift away from the 6,828 the run actually billed."""
    s = _read("edges/programmatic-tool-calling/sample.txt")
    a = re.search(r"Mode A:.*?([\d,]+)\s+\d+\s+\S+\s+\$", s)
    b = re.search(r"Mode B:.*?([\d,]+)\s+\d+\s+\S+\s+\$", s)
    if not (a and b):
        return
    a_tok, b_tok = int(a.group(1).replace(",", "")), int(b.group(1).replace(",", ""))
    files = [ROOT / "README.md", ROOT / "FOUNDER_EMAIL.md"]
    files += sorted(ROOT.glob("edges/*/FOUNDER_EMAIL.md")) + sorted(ROOT.glob("emails/*.md"))
    for p in files:
        if not p.exists():
            continue
        for m in re.finditer(r"\b([69],\d{3})\b", p.read_text()):
            v = int(m.group(1).replace(",", ""))
            if 6000 < v < 7000 and v != b_tok:
                fail.append(f"PTC token drift: {p.relative_to(ROOT)} has {m.group(1)}, receipt Mode B is {b_tok:,}")
            if 9000 < v < 10000 and v != a_tok:
                fail.append(f"PTC token drift: {p.relative_to(ROOT)} has {m.group(1)}, receipt Mode A is {a_tok:,}")


def check_eval(fail, warn):
    """The eval-quality receipt total must match the internal product note that quotes it."""
    s = _read("edges/eval-quality/sample.txt")
    m = re.search(r"RUN 1.*?total spend this run: \$(\d+\.\d{2,4})", s, re.S)
    if not m:
        warn.append("eval: could not parse the RUN 1 total from sample.txt")
        return
    total = float(m.group(1))
    note = _read("edges/eval-quality/PRODUCT_EMAIL.md")
    for i, line in enumerate(note.splitlines(), 1):
        if "total" not in line.lower():
            continue
        for c in _dollars(line):
            if 0.30 < c < 0.60 and abs(c - total) > 0.005:
                fail.append(f"eval cost: PRODUCT_EMAIL.md:{i} says ${c:.4f}, receipt total is "
                            f"${total:.4f}; reconcile them")


def check_price_provenance(fail, warn):
    """Every model price carries a verified date so the table self-documents, and the gate warns when
    a price is older than the staleness window (a re-verify reminder, never a hard failure offline)."""
    models = _read("common/models.py")
    if not re.search(r'verified[^"\n]*"\d{4}-\d{2}-\d{2}"', models):
        fail.append("price provenance: common/models.py carries no `verified` date on the model table")
        return
    today = datetime.date.today()
    for m in re.finditer(r'verified[^"\n]*"(\d{4}-\d{2}-\d{2})"', models):
        d = datetime.date.fromisoformat(m.group(1))
        if (today - d).days > STALE_DAYS:
            warn.append(f"price provenance: a model price was verified {m.group(1)} "
                        f"({(today - d).days}d ago, > {STALE_DAYS}d). Re-verify against the live page.")


def main():
    fail, warn = [], []
    check_ptc(fail, warn)
    check_ptc_drift(fail, warn)
    check_eval(fail, warn)
    check_price_provenance(fail, warn)
    for w in warn:
        print(f"  receipt gate: WARN {w}")
    if fail:
        print("receipt-drift gate: FAIL")
        for f in fail:
            print(f"  {f}")
        sys.exit(1)
    print(f"receipt-drift gate: clean (PTC tokens/percent/cost, eval total, price provenance"
          f"{'; ' + str(len(warn)) + ' warning(s)' if warn else ''})")


if __name__ == "__main__":
    main()
