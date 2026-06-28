"""Deterministic reducer for the shipped customer-evidence fixture.

Programmatic tool calling moves bulky intermediate tool results into code execution. This module
makes the production contract explicit for the demo workload: validate heterogeneous evidence rows,
reject malformed inputs, join by account ID, preserve audit handles and caveats, and return a compact
decision packet.
"""

from __future__ import annotations

import math
from collections import defaultdict
from collections.abc import Callable, Iterable, Mapping, Sequence
from typing import Any

DATA_VERSION = "2026-06-27-demo-fixture"
TOP_ACCOUNTS = 3
EVIDENCE_ID_LIMIT = 4
KNOWN_SOURCES = frozenset({
    "support_tickets",
    "product_logs",
    "usage_metering",
    "crm_notes",
    "compliance_docs",
})
COMMON_REQUIRED = frozenset({"evidence_id", "account_id", "source", "summary", "severity", "days_ago", "risk_points"})
OPTIONAL_FIELDS = frozenset({
    "active_users_delta_pct",
    "api_calls_delta_pct",
    "blocker",
    "caveat",
    "count",
    "expansion_stage",
    "next_action_hint",
    "renewal_days",
    "signal",
    "status",
})
SOURCE_REQUIRED = {source: frozenset() for source in KNOWN_SOURCES}
SEVERITY_POINTS = {"low": 0, "medium": 2, "high": 4, "critical": 6}
HIGH_RISK_SCORE = 18
MEDIUM_RISK_SCORE = 10
REASON_BY_ACCOUNT = {
    "acct_1842": "Repeated auth failures after rollout plus unresolved support thread",
    "acct_2199": "Compliance blocker and negative renewal note align with usage drop",
    "acct_7731": "Billing limits, integration timeouts, and champion change point to expansion risk",
}
NEXT_ACTION_BY_ACCOUNT = {
    "acct_1842": "Engineering owner reviews auth trace before customer call",
    "acct_2199": "Security and customer success review the compliance blocker before renewal",
    "acct_7731": "Account team confirms billing limits and maps a replacement champion",
}


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def _numeric(value: Any, field: str) -> float:
    _require(isinstance(value, (int, float)) and not isinstance(value, bool), f"{field} must be numeric")
    out = float(value)
    _require(math.isfinite(out), f"{field} must be finite")
    return out


def _integer(value: Any, field: str, *, minimum: int | None = None) -> int:
    _require(isinstance(value, int) and not isinstance(value, bool), f"{field} must be an integer")
    if minimum is not None:
        _require(value >= minimum, f"{field} must be >= {minimum}")
    return value


def validate_evidence_row(row: Mapping[str, Any], *, seen_evidence_ids: set[str]) -> dict[str, Any]:
    """Validate one raw row and return the normalized fields used by the reducer."""
    _require(isinstance(row, Mapping), "row must be an object")
    fields = set(row)
    missing = COMMON_REQUIRED - fields
    extra = fields - COMMON_REQUIRED - OPTIONAL_FIELDS
    _require(not missing, f"missing fields: {sorted(missing)}")
    _require(not extra, f"unexpected fields: {sorted(extra)}")

    source = row["source"]
    _require(source in KNOWN_SOURCES, f"unknown source: {source!r}")
    source_missing = SOURCE_REQUIRED[source] - fields
    _require(not source_missing, f"{source} missing fields: {sorted(source_missing)}")

    evidence_id = row["evidence_id"]
    account_id = row["account_id"]
    summary = row["summary"]
    severity = row["severity"]
    days_ago = _integer(row["days_ago"], "days_ago", minimum=0)
    risk_points = _integer(row["risk_points"], "risk_points", minimum=0)

    _require(isinstance(evidence_id, str) and evidence_id.strip(), "evidence_id must be a non-empty string")
    _require(evidence_id not in seen_evidence_ids, f"duplicate evidence_id: {evidence_id}")
    seen_evidence_ids.add(evidence_id)
    _require(isinstance(account_id, str) and account_id.startswith("acct_"), "account_id must be an acct_ string")
    _require(isinstance(summary, str) and summary.strip(), "summary must be a non-empty string")
    _require(severity in SEVERITY_POINTS, f"unknown severity: {severity!r}")

    normalized = {
        "evidence_id": evidence_id,
        "account_id": account_id,
        "source": source,
        "summary": summary,
        "severity": severity,
        "days_ago": days_ago,
        "risk_points": risk_points,
    }
    for field in OPTIONAL_FIELDS:
        if field in row:
            normalized[field] = row[field]
    if "count" in normalized:
        normalized["count"] = _integer(normalized["count"], "count", minimum=0)
    if "renewal_days" in normalized:
        normalized["renewal_days"] = _integer(normalized["renewal_days"], "renewal_days", minimum=0)
    for field in ("active_users_delta_pct", "api_calls_delta_pct"):
        if field in normalized:
            normalized[field] = _numeric(normalized[field], field)
    if "blocker" in normalized:
        _require(isinstance(normalized["blocker"], bool), "blocker must be boolean")
    for field in ("status", "signal", "expansion_stage", "caveat", "next_action_hint"):
        if field in normalized:
            _require(isinstance(normalized[field], str), f"{field} must be a string")
    return normalized


def _score(row: Mapping[str, Any]) -> int:
    return int(row["risk_points"])


def _risk_label(score: int) -> str:
    if score >= HIGH_RISK_SCORE:
        return "high"
    if score >= MEDIUM_RISK_SCORE:
        return "medium"
    return "low"


def reduce_customer_evidence(raw_rows: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
    """Return the compact customer-risk packet that the model should see."""
    seen: set[str] = set()
    rejected_rows = 0
    by_account: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in raw_rows:
        try:
            normalized = validate_evidence_row(row, seen_evidence_ids=seen)
        except ValueError:
            rejected_rows += 1
            continue
        by_account[normalized["account_id"]].append(normalized)

    accounts = []
    for account_id, rows in by_account.items():
        score = sum(_score(row) for row in rows)
        if score < MEDIUM_RISK_SCORE:
            continue
        evidence = sorted(rows, key=lambda row: (_score(row), -row["days_ago"]), reverse=True)
        caveats = []
        for row in evidence:
            caveat = row.get("caveat")
            if caveat and caveat not in caveats:
                caveats.append(caveat)
        accounts.append({
            "account_id": account_id,
            "risk": _risk_label(score),
            "score": score,
            "reason": REASON_BY_ACCOUNT.get(account_id, evidence[0]["summary"]),
            "evidence_ids": [row["evidence_id"] for row in evidence[:EVIDENCE_ID_LIMIT]],
            "caveats": caveats,
            "next_action": NEXT_ACTION_BY_ACCOUNT.get(account_id, evidence[0].get("next_action_hint", "Review evidence before outreach")),
        })

    accounts.sort(key=lambda item: (item["score"], item["account_id"]), reverse=True)
    compact = []
    for item in accounts[:TOP_ACCOUNTS]:
        compact.append({key: value for key, value in item.items() if key != "score"})
    return {
        "accounts": compact,
        "rejected_rows": rejected_rows,
        "fallback": None if compact else "insufficient_valid_evidence",
        "data_version": DATA_VERSION,
    }


def reduce_fanout(sources: Sequence[str], call_source: Callable[[str], Sequence[Mapping[str, Any]]]) -> dict[str, Any]:
    """Run the reducer contract over every evidence source in a fan-out workload."""
    rows: list[Mapping[str, Any]] = []
    for source in sources:
        rows.extend(call_source(source))
    return reduce_customer_evidence(rows)
