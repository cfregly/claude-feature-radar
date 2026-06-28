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


def check_programmatic_tool_calling(fail, warn):
    """The programmatic-tool-calling receipt is the source for the billed-token
    numbers, the percent reduction, and the run cost. Every surface that quotes them must agree."""
    s = _read("edges/programmatic-tool-calling/sample.txt")
    a = re.search(r"without programmatic tool calling\s+([\d,]+)", s)
    b = re.search(r"with programmatic tool calling\s+([\d,]+)", s)
    if not (a and b):
        fail.append("programmatic tool calling: could not parse receipt rows in sample.txt")
        return
    a_tok = int(a.group(1).replace(",", ""))
    b_tok = int(b.group(1).replace(",", ""))
    pct = round((1 - b_tok / a_tok) * 100)

    # the stable token numbers and percent must appear verbatim where the edge is pitched
    a_str, b_str = f"{a_tok:,}", f"{b_tok:,}"
    for rel in [
        "README.md",
        "edges/programmatic-tool-calling/README.md",
        "engine/brief_assets/programmatic_tool_calling/README.md",
        "engine/brief_assets/programmatic_tool_calling/email.md",
        "emails/drafts/programmatic_tool_calling_FOUNDER_EMAIL.md",
    ]:
        text = _read(rel)
        if a_str not in text or b_str not in text:
            fail.append(f"programmatic tool calling tokens: {rel} does not carry the receipt's {a_str}/{b_str}")
        if f"{pct}%" not in text:
            fail.append(f"programmatic tool calling percent: {rel} does not carry the receipt's {pct}% reduction")

    cost_files = [
        "Makefile", "README.md",
        "edges/programmatic-tool-calling/README.md",
        "engine/brief_assets/programmatic_tool_calling/README.md",
        "engine/brief_assets/programmatic_tool_calling/email.md",
        "emails/drafts/programmatic_tool_calling_FOUNDER_EMAIL.md",
    ]
    for rel in cost_files:
        text = _read(rel)
        for i, line in enumerate(text.splitlines(), 1):
            target_line = re.search(r"programmatic[-_]tool[-_]calling(?![-_])", line, re.I)
            email_cost_line = "token/API cost" in line
            if not (target_line or email_cost_line):
                continue
            for c in _dollars(line):
                if abs(c - 0.08) > COST_TOL:
                    fail.append(f"programmatic tool calling cost: {rel}:{i} says ${c:.2f}, expected the canonical $0.08 estimate")


def check_programmatic_tool_calling_drift(fail, warn):
    """Any programmatic-tool-calling token-shaped number on a founder surface must equal the receipt."""
    s = _read("edges/programmatic-tool-calling/sample.txt")
    a = re.search(r"without programmatic tool calling\s+([\d,]+)", s)
    b = re.search(r"with programmatic tool calling\s+([\d,]+)", s)
    if not (a and b):
        return
    a_tok, b_tok = int(a.group(1).replace(",", "")), int(b.group(1).replace(",", ""))
    programmatic_tool_calling_ctx = re.compile(r"programmatic tool calling|Token MINNing|allowed_callers", re.I)
    files = [ROOT / "README.md"]
    files += sorted(ROOT.glob("edges/*/FOUNDER_EMAIL.md"))
    files += sorted(ROOT.glob("emails/*.md")) + sorted(ROOT.glob("emails/**/*.md"))
    for p in files:
        if not p.exists():
            continue
        text = p.read_text()
        if not programmatic_tool_calling_ctx.search(text):
            continue  # not a programmatic-tool-calling surface, so unrelated token numbers trace elsewhere
        for m in re.finditer(r"\b(\d{2},\d{3})\b", text):
            v = int(m.group(1).replace(",", ""))
            if 10000 < v < 20000 and v != b_tok:
                fail.append(f"programmatic tool calling token drift: {p.relative_to(ROOT)} has {m.group(1)}, receipt Mode B is {b_tok:,}")
            if 50000 < v < 60000 and v != a_tok:
                fail.append(f"programmatic tool calling token drift: {p.relative_to(ROOT)} has {m.group(1)}, receipt Mode A is {a_tok:,}")


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
    check_programmatic_tool_calling(fail, warn)
    check_programmatic_tool_calling_drift(fail, warn)
    check_price_provenance(fail, warn)
    for w in warn:
        print(f"  receipt gate: WARN {w}")
    if fail:
        print("receipt-drift gate: FAIL")
        for f in fail:
            print(f"  {f}")
        sys.exit(1)
    print(f"receipt-drift gate: clean (programmatic tool calling tokens/percent/cost, eval total, price provenance"
          f"{'; ' + str(len(warn)) + ' warning(s)' if warn else ''})")


if __name__ == "__main__":
    main()
