"""No-key reducer evals for the promoted programmatic-tool-calling artifact."""

from __future__ import annotations

import hashlib
import json
import pathlib
import sys
from collections.abc import Callable


ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from programmatic_tool_calling import founder_workload  # noqa: E402
from programmatic_tool_calling.tool_result_reducer import (  # noqa: E402
    DATA_VERSION,
    reduce_customer_evidence,
    reduce_fanout,
    validate_evidence_row,
)

EXPECTED_FIXTURE_SHA256 = "e0bd6424352c512e2c8529fe44d69a9aa9924e2ec329dd5c25d8f804291fa7b7"
EXPECTED_ACCOUNTS = ("acct_1842", "acct_2199", "acct_7731")
EXPECTED_REJECTED_ROWS = 17


def _row(**overrides):
    row = {
        "evidence_id": "ticket_eval_1",
        "account_id": "acct_1842",
        "source": "support_tickets",
        "summary": "Unresolved support thread.",
        "severity": "high",
        "days_ago": 1,
        "risk_points": 5,
        "status": "open",
        "signal": "unresolved_support",
    }
    row.update(overrides)
    return row


def _raises(fn: Callable[[], object], contains: str) -> None:
    try:
        fn()
    except ValueError as exc:
        if contains not in str(exc):
            raise AssertionError(f"expected {contains!r} in {exc!r}") from exc
        return
    raise AssertionError(f"expected ValueError containing {contains!r}")


def _fixture() -> dict[str, list[dict]]:
    return {source: founder_workload._customer_evidence(source) for source in founder_workload.EVIDENCE_SOURCES}


def _fixture_sha256(fixture: dict[str, list[dict]]) -> str:
    payload = json.dumps(fixture, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode()).hexdigest()


def test_reference_fixture_accounts_and_counts() -> None:
    fixture = _fixture()
    result = reduce_fanout(founder_workload.EVIDENCE_SOURCES, lambda source: fixture[source])

    assert _fixture_sha256(fixture) == EXPECTED_FIXTURE_SHA256
    assert tuple(account["account_id"] for account in result["accounts"]) == EXPECTED_ACCOUNTS
    assert result["rejected_rows"] == EXPECTED_REJECTED_ROWS
    assert result["fallback"] is None
    assert result["data_version"] == DATA_VERSION
    assert all(len(rows) == founder_workload.ROWS_PER_SOURCE for rows in fixture.values())


def test_compact_evidence_is_auditable() -> None:
    rows = []
    for source in founder_workload.EVIDENCE_SOURCES:
        rows.extend(founder_workload._customer_evidence(source))
    result = reduce_customer_evidence(rows)
    raw_len = len(json.dumps(rows, sort_keys=True))
    summary_len = len(json.dumps(result, sort_keys=True))
    first = result["accounts"][0]

    assert first["account_id"] == "acct_1842"
    assert first["risk"] == "high"
    assert "ticket_8831" in first["evidence_ids"]
    assert "log_52991" in first["evidence_ids"]
    assert first["caveats"] == ["Usage drop may reflect holiday week"]
    assert summary_len < raw_len


def test_empty_input_returns_visible_fallback() -> None:
    result = reduce_customer_evidence([])

    assert result["accounts"] == []
    assert result["rejected_rows"] == 0
    assert result["fallback"] == "insufficient_valid_evidence"


def test_missing_account_id_fails_closed() -> None:
    bad = _row()
    del bad["account_id"]

    _raises(lambda: validate_evidence_row(bad, seen_evidence_ids=set()), "missing fields")


def test_bad_risk_points_fails_closed() -> None:
    _raises(lambda: validate_evidence_row(_row(risk_points="5"), seen_evidence_ids=set()), "risk_points must be an integer")


def test_duplicate_evidence_ids_fail_closed() -> None:
    seen = set()
    validate_evidence_row(_row(evidence_id="dup_1"), seen_evidence_ids=seen)

    _raises(lambda: validate_evidence_row(_row(evidence_id="dup_1"), seen_evidence_ids=seen), "duplicate evidence_id")


def test_unexpected_fields_fail_closed() -> None:
    _raises(lambda: validate_evidence_row(_row(customer_email="secret@example.com"), seen_evidence_ids=set()), "unexpected fields")


def test_unknown_source_fails_closed() -> None:
    _raises(lambda: validate_evidence_row(_row(source="warehouse"), seen_evidence_ids=set()), "unknown source")


def test_bad_account_id_fails_closed() -> None:
    bad = _row(account_id="bad-account")

    _raises(lambda: validate_evidence_row(bad, seen_evidence_ids=set()), "account_id must be an acct_ string")


def test_dropped_decision_data_fails_evidence_gate() -> None:
    result = reduce_fanout(founder_workload.EVIDENCE_SOURCES, founder_workload._customer_evidence)

    assert len(result["accounts"]) == 3
    for account in result["accounts"]:
        assert account["reason"]
        assert account["evidence_ids"]
        assert isinstance(account["caveats"], list)
        assert account["next_action"]


def main() -> int:
    tests = [(name, fn) for name, fn in globals().items() if name.startswith("test_")]
    failures: list[str] = []
    for name, fn in sorted(tests):
        try:
            fn()
        except Exception as exc:  # noqa: BLE001
            failures.append(f"{name}: {type(exc).__name__}: {exc}")
    if failures:
        print("reducer eval gate: FAIL")
        print("\n".join("  " + item for item in failures))
        return 1
    print(f"reducer eval gate: clean ({len(tests)} fixtures)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
