"""No-committed-secret gate: no API key shape, no request id, anywhere in the tracked tree.

A public repo a founder clones must never carry a secret or a leaked request id. This gate scans every
git-tracked text file for:

  - an Anthropic key shape (`sk-ant-...`) or a generic provider key shape (`sk-...`, `sk-proj-...`,
    `sk-svcacct-...`, `AIza...`),
  - a request id shape (`req_...`), which is residue from a captured failure and never belongs in the
    committed surface.

`.env` is gitignored, so a real key on disk is never scanned (only tracked files are). Stdlib only, no
key, no network. Exits non-zero on a hit.
"""

import pathlib
import re
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent

SECRET = [
    (re.compile(r"sk-ant-[A-Za-z0-9_\-]{8,}"), "an Anthropic API key shape (sk-ant-...)"),
    (re.compile(r"\bsk-(?:proj|svcacct)-[A-Za-z0-9_\-]{16,}"),
     "an OpenAI API key shape (sk-proj-... or sk-svcacct-...)"),
    (re.compile(r"\bsk-[A-Za-z0-9_\-]{16,}"), "a generic API key shape (sk-...)"),
    (re.compile(r"\bAIza[A-Za-z0-9_\-]{20,}"), "a Google API key shape (AIza...)"),
    (re.compile(r"\breq_[0-9A-Za-z]{8,}"), "a request id (req_...), failure residue"),
]

# This file names the patterns it looks for, so it would match itself. Skip it (and its compiled form).
SELF = {"scripts/secret_check.py"}


def tracked_files():
    """Every git-tracked file, so a gitignored .env is never scanned. Falls back to a tree walk if git
    is unavailable (a fresh export), skipping the venv, git, and cache dirs."""
    try:
        out = subprocess.run(["git", "ls-files"], cwd=ROOT, capture_output=True, text=True, timeout=20)
        if out.returncode == 0 and out.stdout.strip():
            return [ROOT / line for line in out.stdout.splitlines() if line]
    except Exception:  # noqa: BLE001
        pass
    skip = {".venv", ".git", "__pycache__", "data"}
    return [p for p in ROOT.rglob("*") if p.is_file() and not (skip & set(p.relative_to(ROOT).parts))]


def main() -> int:
    bad = []
    for path in tracked_files():
        rel = str(path.relative_to(ROOT)) if path.is_absolute() else str(path)
        if rel in SELF or not path.exists():
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue  # a binary or unreadable file carries no greppable secret
        for rx, why in SECRET:
            m = rx.search(text)
            if m:
                bad.append(f"{rel}: {why}: {m.group(0)[:16]}...")
    if bad:
        print("secret gate: FAIL (a key shape or request id is committed)")
        print("\n".join(bad))
        return 1
    print(f"secret gate: clean ({len(tracked_files())} tracked files, no key shape, no request id)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
