"""cache-diagnostics: wrapper for the cache-miss root-cause edge."""

from __future__ import annotations

import pathlib as _pl
import sys as _sys

_sys.path.insert(0, str(_pl.Path(__file__).resolve().parents[2]))

from engine.demonstrators.cache_diagnostics import main


if __name__ == "__main__":
    main()
