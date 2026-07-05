"""Deslop gate: the prose states facts in plain language.

No em-dashes, no en-dashes, no semicolons, no emoji, and no stock launch buzzwords in the prose docs
(fenced code blocks are exempt, since a semicolon is legal in code). Self-contained, stdlib only, no key,
no network. Exits non-zero on a hit.

This is the same discipline the publication workflow enforces on prose, mirrored here so a regenerated or hand-edited artifact can never ship a slop tell.
"""

import pathlib
import re
import sys

BANNED = {"—": "em-dash", "–": "en-dash", ";": "semicolon"}
BUZZWORDS = [
    "cutting-edge",
    "game-changing",
    "innovative",
    "leverage",
    "next-gen",
    "revolutionary",
    "robust",
    "seamless",
    "synergy",
    "world-class",
]
EMOJI = re.compile(
    "[\U0001F300-\U0001FAFF\U00002600-\U000027BF\U0001F1E6-\U0001F1FF\U00002B00-\U00002BFF]"
)
ROOT = pathlib.Path(__file__).resolve().parent.parent


def targets():
    """Every prose surface a reader sees: the root README, the repo-level docs (CLAUDE.md,
    SKILL.md), and each artifact's README. Artifact code modules are not deslopped (a semicolon is valid
    Python), only the rendered prose is."""
    docs = [
        ROOT / "README.md",
        ROOT / "CLAUDE.md",
        ROOT / "SKILL.md",
        ROOT / "docs" / "confirmed-improvements.md",
    ]
    docs += sorted(ROOT.glob("*/README.md"))
    return [d for d in docs if d.exists()]


def main() -> int:
    bad = []
    for path in targets():
        in_code = False
        for i, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if line.lstrip().startswith("```"):
                in_code = not in_code
                continue
            if in_code:
                continue
            for ch, label in BANNED.items():
                if ch in line:
                    bad.append(f"{path.relative_to(ROOT)}:{i}: {label}")
            if EMOJI.search(line):
                bad.append(f"{path.relative_to(ROOT)}:{i}: emoji")
            lower = line.lower()
            for word in BUZZWORDS:
                if re.search(rf"\b{re.escape(word)}\b", lower):
                    bad.append(f"{path.relative_to(ROOT)}:{i}: buzzword `{word}`")
    if bad:
        print("deslop gate: FAIL")
        print("\n".join(bad))
        return 1
    print(f"deslop gate: clean ({len(targets())} prose files)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
