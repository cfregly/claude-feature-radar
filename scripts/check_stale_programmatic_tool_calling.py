"""Fail when the old programmatic-tool-calling fixture returns to live surfaces."""

from __future__ import annotations

import pathlib
import re
import sys


ROOT = pathlib.Path(__file__).resolve().parent.parent
SELF = pathlib.Path(__file__).resolve()

FORBIDDEN = [
    "query_" + "region_sales",
    "region_" + "sales",
    "highest-" + "revenue",
    "highest " + "revenue",
    "240-" + "row",
    "240 " + "rows",
    "9," + "494",
    "6," + "910",
    "27" + "%",
    "my_" + "tool.py",
    "run_" + "tokens.py",
    "token_" + "core.py",
    "".join(("p", "tc_", "cache_context")),
    "".join(("p", "tc-", "cache-context")),
]

SCAN_ROOTS = [
    "Makefile",
    "README.md",
    "run.py",
    "docs",
    "edges",
    "emails",
    "engine",
    "scripts",
    "tests",
]

SKIP_PARTS = {
    ".git",
    ".venv",
    "__pycache__",
    "sources",
    "state",
}


def _files() -> list[pathlib.Path]:
    out: list[pathlib.Path] = []
    for rel in SCAN_ROOTS:
        path = ROOT / rel
        if not path.exists():
            continue
        if path.is_file():
            out.append(path)
            continue
        for child in path.rglob("*"):
            if not child.is_file() or child == SELF:
                continue
            if any(part in SKIP_PARTS for part in child.relative_to(ROOT).parts):
                continue
            if child.suffix.lower() not in {".py", ".md", ".txt", ".json", ".tape"} and child.name != "Makefile":
                continue
            out.append(child)
    return out


def main() -> int:
    pattern = re.compile("|".join(re.escape(s) for s in FORBIDDEN), re.IGNORECASE)
    hits: list[str] = []
    for path in _files():
        text = path.read_text(encoding="utf-8", errors="ignore")
        for match in pattern.finditer(text):
            rel = path.relative_to(ROOT)
            line = text.count("\n", 0, match.start()) + 1
            hits.append(f"{rel}:{line}: {match.group(0)}")
            break
    if hits:
        print("stale programmatic-tool-calling guard: FAIL")
        for hit in hits:
            print(f"  - {hit}")
        return 1
    print("stale programmatic-tool-calling guard: clean")
    return 0


if __name__ == "__main__":
    sys.exit(main())
