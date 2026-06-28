"""Publish the canonical public ``claude-feature-hits`` code bundle."""

from __future__ import annotations

import argparse
import pathlib

from engine.public_hits import PublicHitsPublishError, publish_all


ROOT = pathlib.Path(__file__).resolve().parent.parent


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--hits-root",
        type=pathlib.Path,
        default=ROOT.parent / "claude-feature-hits",
        help="target claude-feature-hits checkout",
    )
    args = parser.parse_args(argv)
    try:
        result = publish_all(args.hits_root)
    except PublicHitsPublishError as exc:
        print(f"publish-hits REFUSED: {exc}")
        return 1
    print(f"publish-hits: copied {len(result.copied)} files into {result.target}")
    if result.removed:
        print(f"publish-hits: removed {len(result.removed)} tracked files no longer in the manifest")
        for rel in result.removed:
            print(f"  - {rel}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
