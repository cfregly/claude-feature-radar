"""Public-surface gate: feature-hits contains promoted artifacts only."""

from __future__ import annotations

import pathlib
import re
import subprocess
import sys


ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
from artifact_manifest import active_slugs, removed_slugs  # noqa: E402

SELF = {"scripts/public_surface_check.py"}
CURRENT_WIN_DOCS = ("CLAUDE.md", "README.md", "SKILL.md")
REMOVED_ARTIFACTS = set(removed_slugs())
PROMOTED_ARTIFACTS = set(active_slugs())
DIMENSIONS = ("Cost", "Speed", "Accuracy", "Reliability", "Operations", "Security")

FORBIDDEN = [
    ("claude-feature-" + "radar", "private method repo name"),
    ("claude-feature-" + "misses", "private misses repo name"),
    ("engine/" + "providers", "private provider path"),
    ("offer_" + "code=", "starter-credit offer code"),
    ("signup_" + "code=", "starter-credit signup code"),
    ("No other major " + "provider", "absolute competitor-negative phrasing"),
    ("about " + "$", "hedged dollar figure"),
    ("roughly " + "$", "hedged dollar figure"),
    ("very " + "exciting!!", "mail-merge tone"),
    ("From one former " + "founder", "mail-merge bridge line"),
    ("Claude Claude", "duplicated Claude label"),
    ("Status: " + "he" + "ld as a public feature-hit framing", "retired receipt directory still exposed"),
    ("br" + "ief", "old artifact label"),
    ("BR" + "IEF", "old artifact label"),
    ("sur" + "viving " + "co" + "mbo", "retrospective framing"),
    ("deterministic " + "cost", "local-only cost framing"),
    ("No API " + "call", "local-only demo framing"),
    ("no API " + "key required", "local-only demo framing"),
]


def surface_files() -> list[pathlib.Path]:
    out = subprocess.run(
        ["git", "ls-files", "--cached", "--others", "--exclude-standard"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=20,
    )
    if out.returncode != 0:
        raise RuntimeError(out.stderr.strip() or "git ls-files failed")
    return [ROOT / line for line in out.stdout.splitlines() if line]


def check_current_win_language(bad: list[str]) -> None:
    for rel in CURRENT_WIN_DOCS:
        text = (ROOT / rel).read_text(encoding="utf-8")
        if "current" not in text.lower():
            bad.append(f"{rel}: missing current-win framing")

    text = (ROOT / "CLAUDE.md").read_text(encoding="utf-8")
    for needle in [
        "Every artifact README keeps a `What you get` section",
        "Every artifact README keeps a `Dimension matrix` section",
        "If a claim lacks measured value",
    ]:
        if needle not in text:
            bad.append(f"CLAUDE.md: missing current-win rule: {needle!r}")


def check_promoted_artifacts(bad: list[str]) -> None:
    root = (ROOT / "README.md").read_text(encoding="utf-8")
    for slug in sorted(PROMOTED_ARTIFACTS):
        readme = ROOT / slug / "README.md"
        if not readme.exists():
            bad.append(f"{slug}/README.md: promoted artifact missing")
            continue
        text = readme.read_text(encoding="utf-8")
        if "## What you get" not in text:
            bad.append(f"{slug}/README.md: missing `## What you get` value section")
        if "## Best-available comparison" not in text:
            bad.append(f"{slug}/README.md: missing `## Best-available comparison` section")
        if "## Dimension matrix" not in text:
            bad.append(f"{slug}/README.md: missing `## Dimension matrix` section")
        for dimension in DIMENSIONS:
            if f"| {dimension} |" not in text:
                bad.append(f"{slug}/README.md: missing `{dimension}` dimension row")
        if "OpenAI" not in text:
            bad.append(f"{slug}/README.md: missing OpenAI best-available comparison")
        if "Gemini" not in text:
            bad.append(f"{slug}/README.md: missing Gemini best-available comparison")
        if not (ROOT / slug / "sample.txt").exists():
            bad.append(f"{slug}/sample.txt: missing receipt backing public value")
        if f"[**{slug}**]" not in root:
            bad.append(f"README.md: promoted artifact `{slug}` missing from promoted surface")


def check_removed_artifacts(bad: list[str], files: list[pathlib.Path]) -> None:
    tracked = {str(path.relative_to(ROOT)) for path in files}
    for slug in sorted(REMOVED_ARTIFACTS):
        if any(rel == slug or rel.startswith(slug + "/") for rel in tracked):
            bad.append(f"{slug}/: removed receipt must not be tracked in feature-hits")


def main() -> int:
    bad: list[str] = []
    files = surface_files()
    check_current_win_language(bad)
    check_promoted_artifacts(bad)
    check_removed_artifacts(bad, files)

    for path in files:
        rel = str(path.relative_to(ROOT))
        if rel in SELF:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        for needle, why in FORBIDDEN:
            if needle in text:
                bad.append(f"{rel}: {why}: {needle!r}")
        if rel.endswith("PROVENANCE.md"):
            bad.append(f"{rel}: provenance files must stay untracked")
        if re.search(r"\broughly\s+\$[0-9]", text):
            bad.append(f"{rel}: hedged dollar figure")

    if bad:
        print("public surface gate: FAIL")
        print("\n".join(bad))
        return 1
    print(f"public surface gate: clean ({len(files)} tracked or untracked surface files)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
