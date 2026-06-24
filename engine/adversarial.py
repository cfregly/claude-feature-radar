"""adversarial: the central "adversarially-confirmed to add value" gate.

The engine used to have the rule in prose and several local gates. This module makes it mechanical:
a candidate is pitchable only when it has a founder-value shape AND the current adversarial report
does not contain a kill for the framing. A measured receipt can prove a mechanism, but a hard skeptic
kill still holds the edge until the claim is narrowed and re-verified.
"""

from __future__ import annotations

import json
import pathlib
from dataclasses import dataclass
from datetime import date

from common.client import repo_root

VALUE_AXES = {"cost", "speed", "reliability", "accuracy", "security"}
VALUE_LEAD_BASES = {"head-to-head", "absence-of-evidence", "within-claude-only"}

KEY_ALIASES: dict[str, set[str]] = {
    "programmatic-tool-calling": {"programmatic_tool_calling"},
    "programmatic_tool_calling": {"programmatic-tool-calling"},
    "task-budgets": {"task_budgets"},
    "task_budgets": {"task-budgets"},
    "cache-diagnostics": {"cache_diagnostics"},
    "cache_diagnostics": {"cache-diagnostics"},
    "search-results": {"search_results"},
    "search_results": {"search-results"},
    "web-citations": {"web_search_tool", "web_citations"},
    "web_search_tool": {"web-citations", "web_citations"},
    "pdf-citations": {"pdf_support", "pdf_citations"},
    "pdf_support": {"pdf-citations", "pdf_citations"},
}


@dataclass(frozen=True)
class ValueGate:
    ok: bool
    reason: str
    key: str = ""
    adversarial_verdict: str = "unknown"
    judges: tuple[str, ...] = ()


def equivalent_keys(key: str) -> set[str]:
    key = (key or "").strip()
    if not key:
        return set()
    out = {key, key.replace("-", "_"), key.replace("_", "-")}
    for k in list(out):
        out.update(KEY_ALIASES.get(k, set()))
    return out


def report_path(root: pathlib.Path | None = None) -> pathlib.Path:
    base = pathlib.Path(root) if root else repo_root()
    return base / "landscape" / "adversarial.json"


def load_report(root: pathlib.Path | None = None) -> dict:
    path = report_path(root)
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text())
    except (json.JSONDecodeError, OSError):
        return {}


def write_report(reports: list[dict], *, root: pathlib.Path | None = None) -> pathlib.Path:
    path = report_path(root)
    path.parent.mkdir(parents=True, exist_ok=True)
    out = {
        "as_of_date": date.today().isoformat(),
        "bar": "adversarially-confirmed to add value",
        "rule": (
            "Any KILLED verdict by a current adversarial judge holds the edge. SURVIVES means the "
            "judge could not construct a stronger competitor stack or reduce the value to DX, native "
            "packaging, or a mechanism with no measured founder outcome."
        ),
        "reports": reports,
    }
    path.write_text(json.dumps(out, indent=2) + "\n")
    return path


def _matching_rows(report: dict, key: str) -> list[dict]:
    keys = equivalent_keys(key)
    rows: list[dict] = []
    for judge in report.get("reports", []):
        judge_name = judge.get("judge", "unknown")
        model = judge.get("model")
        for row in judge.get("verdicts", []):
            if row.get("key") in keys:
                rows.append({**row, "judge": judge_name, "model": model})
    return rows


def adversarial_status(key: str, *, root: pathlib.Path | None = None, report: dict | None = None) -> ValueGate:
    report = report if report is not None else load_report(root)
    rows = _matching_rows(report, key)
    if not report:
        return ValueGate(False, "no adversarial report is present", key=key)
    if not rows:
        return ValueGate(False, "no adversarial verdict for this edge key", key=key)
    judges = tuple(str(r.get("judge", "unknown")) for r in rows)
    kills = [r for r in rows if r.get("verdict") == "KILLED"]
    if kills:
        why = kills[0].get("why", "adversarial judge killed the claim")
        return ValueGate(False, why, key=key, adversarial_verdict="KILLED", judges=judges)
    if all(r.get("verdict") == "SURVIVES" for r in rows):
        return ValueGate(True, "survived every recorded adversarial judge", key=key,
                         adversarial_verdict="SURVIVES", judges=judges)
    return ValueGate(False, "adversarial verdict is malformed or incomplete", key=key,
                     adversarial_verdict="unknown", judges=judges)


def receipt_value_positive(receipt: dict | None) -> bool:
    """Return True only when a receipt carries a positive measured value signal."""
    if not receipt:
        return False
    verdict = receipt.get("verdict")
    if isinstance(verdict, dict):
        if "promotable_edge" in verdict:
            return bool(verdict.get("promotable_edge"))
        if "positive_signal" in verdict:
            return bool(verdict.get("positive_signal"))
    if isinstance(verdict, str):
        return verdict == "claude-ahead" and bool(receipt.get("passed", True))
    if "passed" in receipt:
        return bool(receipt.get("passed"))
    if "mode_b_correct" in receipt:
        return bool(receipt.get("mode_b_correct")) and float(receipt.get("pct_input_reduction") or 0) > 0
    if "pct_input_reduction" in receipt:
        return float(receipt.get("pct_input_reduction") or 0) > 0
    return False


def value_confirmed(edge: dict, receipt: dict | None = None, *, root: pathlib.Path | None = None,
                    report: dict | None = None, require_receipt: bool = False,
                    require_adversarial: bool = True) -> ValueGate:
    """The single promotion predicate used by publish, MCP listings, cadence, and draft.

    This is deliberately stricter than "lead_score > 0": it requires a value axis, an honest
    comparison shape, and a clean adversarial overlay. When require_receipt is true, a measured receipt
    must also carry a positive value signal.
    """
    key = edge.get("key", "")
    if edge.get("verdict") != "claude-ahead":
        return ValueGate(False, f"verdict is {edge.get('verdict')!r}, not claude-ahead", key=key)
    if (edge.get("lead_score") or 0) <= 0:
        return ValueGate(False, "lead_score is not positive", key=key)
    axis = edge.get("axis", "unknown")
    if axis not in VALUE_AXES:
        return ValueGate(False, f"axis {axis!r} is not a founder-value axis", key=key)
    fc = edge.get("fair_comparison") or {}
    lead_basis = fc.get("lead_basis")
    if lead_basis not in VALUE_LEAD_BASES:
        return ValueGate(False, f"lead_basis {lead_basis!r} is not publishable", key=key)
    for field in ("task_shape", "score_gate"):
        if not fc.get(field):
            return ValueGate(False, f"missing fair_comparison.{field}", key=key)
    if require_receipt and not receipt_value_positive(receipt):
        return ValueGate(False, "no positive measured receipt", key=key)
    if require_adversarial:
        adv = adversarial_status(key, root=root, report=report)
        if not adv.ok:
            return adv
    return ValueGate(True, "adversarially-confirmed to add value", key=key,
                     adversarial_verdict="SURVIVES" if require_adversarial else "not-required")


def confirmed_edges(edges: list[dict], *, root: pathlib.Path | None = None,
                    report: dict | None = None) -> list[dict]:
    return [e for e in edges if value_confirmed(e, root=root, report=report,
                                                require_receipt=False).ok]
