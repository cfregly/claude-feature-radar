"""exact-list-ledger: wrapper for the long-stream exact-list edge.

The implementation lives in engine/ledger_compare.py so the Makefile target, run.py command, and edge
folder use one code path. Run from the repo root with:

    make ledger
"""

from __future__ import annotations

import pathlib as _pl
import sys as _sys

_sys.path.insert(0, str(_pl.Path(__file__).resolve().parents[2]))

from engine.ledger_compare import main


if __name__ == "__main__":
    main()
