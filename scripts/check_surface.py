"""Surface gate: the repo stays self-contained, and every founder surface stays wins-only.

Two rules the codebase previously enforced by discipline (and so they drifted): the engine must
read as a generic, self-contained project with no reference to anything outside it, and a
founder-facing surface must show only verified Claude wins. This gate makes both mechanical, so a
re-introduced private-repo name, build-phase label, machine path, or a Claude negative on a founder
email turns the build red instead of slipping in. Stdlib only, offline, exits non-zero on a hit.
"""

import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
SELF = "check_surface.py"

# Rule 1: no internal build-process or external-repo leakage in committed source. The repo must read
# as self-contained (CLAUDE.md "keep it forkable: no references to anything outside this repo").
FORBIDDEN = [
    (r"ship-on-claude", "names a private sibling repo"),
    (r"claude-overnight", "names a private sibling repo"),
    (r"\bported from\b", "internal port provenance"),
    (r"\bPhase [2-5]\b", "internal build-phase label"),
    (r"the A and B harness", "internal consolidation letter-code"),
    (r"the deck'?s pitch", "references a private deck"),
    (r"/Users/", "machine-specific absolute path"),
]

# Rule 2: a founder-facing surface shows only Claude wins, never a negative or a both-directions tell.
FOUNDER_GLOBS = ["FOUNDER_EMAIL.md", "emails/*.md", "edges/*/FOUNDER_EMAIL.md"]
NEGATIVES = [
    "more expensive", "not on bedrock", "not on vertex", "not zdr", "zdr-eligible",
    "table stakes", "parity on", "is parity", "claude loses", "loses on", "where that flips",
    "lose regime", "got it wrong", "failed to produce", "is not a cheaper bill",
    "not a claude-only", "measured it honestly", "the honest part", "the honest one",
]

# Raw fetched vendor docs and gitignored scratch are not authored surfaces, so they are out of scope.
SKIP = ("/.venv/", "/__pycache__/", "/sources/", "/data/", "/.git/", "/.benchmarks/", "/node_modules/")


def _source_files():
    out = []
    for ext in ("*.py", "*.md"):
        out += ROOT.rglob(ext)
    mk = ROOT / "Makefile"
    if mk.exists():
        out.append(mk)
    return [p for p in out
            if p.is_file() and p.name != SELF and not any(s in str(p) for s in SKIP)]


def _founder_files():
    out = []
    for g in FOUNDER_GLOBS:
        out += sorted(ROOT.glob(g))
    seen, files = set(), []
    for p in out:
        if p.is_file() and p not in seen:
            seen.add(p)
            files.append(p)
    return files


def main():
    bad = []
    for p in _source_files():
        text = p.read_text(errors="ignore")
        for pat, why in FORBIDDEN:
            for m in re.finditer(pat, text, re.IGNORECASE):
                line = text[: m.start()].count("\n") + 1
                bad.append(f"{p.relative_to(ROOT)}:{line}: leakage ({why}): {m.group(0)!r}")
    for p in _founder_files():
        for i, line in enumerate(p.read_text(errors="ignore").splitlines(), 1):
            low = line.lower()
            for neg in NEGATIVES:
                if neg in low:
                    bad.append(f"{p.relative_to(ROOT)}:{i}: founder-surface negative: {neg!r}")
    if bad:
        print("surface gate: FAIL")
        print("\n".join(bad))
        sys.exit(1)
    print(f"surface gate: clean ({len(_source_files())} source files, "
          f"{len(_founder_files())} founder surfaces)")


if __name__ == "__main__":
    main()
