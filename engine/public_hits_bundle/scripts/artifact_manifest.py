"""Read the public artifact manifest for Makefile and CI gates."""

from __future__ import annotations

import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
MANIFEST = ROOT / "artifacts.json"


def load() -> dict:
    return json.loads(MANIFEST.read_text(encoding="utf-8"))


def artifacts(status: str = "active") -> dict[str, dict]:
    data = load().get("artifacts", {})
    return {name: row for name, row in data.items() if row.get("status") == status}


def active_slugs() -> list[str]:
    return sorted(artifacts("active"))


def removed_slugs() -> list[str]:
    return sorted(artifacts("removed"))


def main(argv: list[str] | None = None) -> int:
    argv = argv or sys.argv[1:]
    cmd = argv[0] if argv else "active"
    if cmd == "active":
        print(" ".join(active_slugs()))
        return 0
    if cmd == "removed":
        print(" ".join(removed_slugs()))
        return 0
    if cmd == "check":
        data = artifacts("active")
        for slug in active_slugs():
            row = data[slug]
            args = " ".join(row.get("check_args", []))
            print(f".venv/bin/python -m {row['run_module']} {args}".rstrip())
        return 0
    raise SystemExit(f"unknown artifact manifest command: {cmd}")


if __name__ == "__main__":
    raise SystemExit(main())
