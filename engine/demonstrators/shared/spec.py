"""Parse a budgeted demonstrator's program.md into the run's config: the model tiers in the search
space, the decoding bounds, and the budget.

Ported from claude-overnight overnight/spec.py. The budgeted demonstrator kinds (eval_quality and
agentic_grading) take a program.md the user edits instead of code they change, so the spend cap, the
iteration count, and the model search space stay a file, not a flag buried in a script. Deterministic
and stdlib only. Missing or unparseable fields fall back to defaults, so a half-written program.md
still runs.

Unlike B's single-repo version, load() takes an explicit path, because each budgeted demonstrator in
this engine carries its own program.md under edges/<key>/. The default template ships at
engine/demonstrators/shared/program.md so a new budgeted kind can copy it.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]   # the repo root
DEFAULT_PROGRAM = Path(__file__).resolve().parent / "program.md"

DEFAULT_MODELS = ["claude-haiku-4-5", "claude-sonnet-4-6"]
DEFAULT_BUDGET = {"dollars": 3.0, "iterations": 12, "minutes": 60.0}


@dataclass
class Spec:
    models: list
    temperature: tuple
    max_tokens: tuple
    budget: dict


def _range(text: str, key: str, default: tuple) -> tuple:
    m = re.search(key + r"\s+in\s+\[\s*([\d.]+)\s*,\s*([\d.]+)\s*\]", text)
    return (float(m.group(1)), float(m.group(2))) if m else default


def load(path: Path | str | None = None) -> Spec:
    """Parse a program.md into a Spec. path is the budgeted demonstrator's own program.md; with no
    path the shipped default template is read, so a caller always gets a usable Spec."""
    p = Path(path) if path is not None else DEFAULT_PROGRAM
    text = p.read_text() if p.exists() else ""

    # The models named in the search space, de-duplicated in first-seen order.
    models = list(dict.fromkeys(re.findall(r"claude-[a-z0-9.-]+", text))) or list(DEFAULT_MODELS)

    temperature = _range(text, "temperature", (0.0, 0.7))
    lo, hi = _range(text, "max_tokens", (128.0, 1024.0))
    max_tokens = (int(lo), int(hi))

    budget = dict(DEFAULT_BUDGET)
    for field_name, pattern, cast in (("dollars", r"spend:\s*([\d.]+)", float),
                                      ("iterations", r"iterations:\s*(\d+)", int),
                                      ("minutes", r"wall clock:\s*([\d.]+)", float)):
        m = re.search(pattern, text)
        if m:
            budget[field_name] = cast(m.group(1))

    return Spec(models=models, temperature=temperature, max_tokens=max_tokens, budget=budget)
