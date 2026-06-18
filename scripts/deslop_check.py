"""A small deslop gate: the prose states facts in plain language.

No em-dashes, no en-dashes, no semicolons, no emoji in the prose docs (code blocks are exempt).
Self-contained, no dependency, so CI runs it offline. Exits non-zero on a hit.
"""

import pathlib
import re
import sys

BANNED = {"—": "em-dash", "–": "en-dash", ";": "semicolon"}
EMOJI = re.compile(
    "[\U0001F300-\U0001FAFF\U00002600-\U000027BF\U0001F1E6-\U0001F1FF\U00002B00-\U00002BFF]"
)
ROOT = pathlib.Path(__file__).resolve().parent.parent
DOCS = ["README.md", "CLAUDE.md", "SKILL.md", "FOUNDER_EMAIL.md",
        "docs/VERIFIED_FACTS.md", "docs/FINDINGS.md"]


def _targets():
    docs = [ROOT / d for d in DOCS]
    docs += sorted((ROOT / "briefs").glob("*.md"))
    docs += sorted((ROOT / "edges").glob("*/*.md"))   # per-edge FOUNDER_EMAIL, PRODUCT_EMAIL, README
    docs += sorted((ROOT / "emails").glob("*.md"))    # the founder outreach emails
    return docs


def main():
    bad = []
    for path in _targets():
        if not path.exists():
            continue
        in_code = False
        for i, line in enumerate(path.read_text().splitlines(), 1):
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
    if bad:
        print("deslop gate: FAIL")
        print("\n".join(bad))
        sys.exit(1)
    print(f"deslop gate: clean ({len([p for p in _targets() if p.exists()])} files)")


if __name__ == "__main__":
    main()
