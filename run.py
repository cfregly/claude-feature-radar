#!/usr/bin/env python3
"""One entry point for the engine. Use the Makefile, or:

    python run.py demo [--quick|--full]   the runnable proof for the current gap
    python run.py scan                     the candidate gaps, grounded in both sides' docs
    python run.py verify                   the skeptic pass: keep only what survives
    python run.py draft                    draft the founder email from the measured receipt
    python run.py brief                    print the latest sourced brief
"""

import pathlib
import sys


def _brief():
    briefs = sorted((pathlib.Path(__file__).resolve().parent / "briefs").glob("*.md"))
    print(briefs[-1].read_text() if briefs else "no briefs yet")


def main():
    cmd = sys.argv[1] if len(sys.argv) > 1 else "demo"
    sys.argv = [sys.argv[0]] + sys.argv[2:]  # pass the rest through to the subcommand
    if cmd == "demo":
        from engine.demo import main as m; m()
    elif cmd in ("longhorizon-compare", "lhc"):
        from engine.longhorizon_compare import main as m; m()
    elif cmd == "compare":
        from engine.compare import main as m; m()
    elif cmd == "alert":
        from engine.product_alert import main as m; m()
    elif cmd == "sweep":
        from engine.sweep import main as m; m()
    elif cmd == "scan":
        from engine.scan import main as m; m()
    elif cmd == "verify":
        from engine.verify import main as m; m()
    elif cmd in ("draft", "email", "draft-email"):
        from engine.draft_email import main as m; m()
    elif cmd == "brief":
        _brief()
    else:
        print(__doc__)
        sys.exit(2)


if __name__ == "__main__":
    main()
