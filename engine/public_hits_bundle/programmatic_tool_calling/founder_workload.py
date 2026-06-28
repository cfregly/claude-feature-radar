"""founder_workload: THE single file you edit to run the token-bill comparison on your own tool.

This is the edit surface. Out of the box it ships a worked example: a customer-evidence tool that
returns this week's support tickets, product logs, CRM notes, usage metering, and compliance docs.
The task asks for the three customer accounts most likely to churn or block expansion. That is the
same fan-out the artifact's token-bill comparison measures, so `make programmatic_tool_calling`
gives you a real before-and-after number before you change a line. Then swap in your own tool:

  1. Replace TOOL_SPEC with your own Messages-API tool dict (name, description, input_schema).
  2. Replace call(...) with the function that runs your real backend (a database query, an API call,
     a file read). Its keyword arguments match input_schema's properties, and it returns whatever the
     model normally gets back.
  3. Set QUESTION to your own fan-out task, the prompt that makes the model call your tool many times.

Keep the task fan-out shaped: the win lands when the model calls your tool many times, so the bulky
outputs run in code instead of filling its context. A fan-out task is where the input-token savings
show up, so pick one that fans out over many inputs.

Nothing here imports anthropic. founder_workload is data plus a plain Python function;
compare_direct_vs_programmatic.py drives it.
"""

from __future__ import annotations

import hashlib
import json
import random
import re

from .tool_result_reducer import DATA_VERSION, reduce_fanout

# --------------------------------------------------------------------------- the worked example
# A fixed mock backend so the shipped example has a known, reproducible true answer. Replace this
# whole block with your own tool. The seed makes query_customer_evidence(source) return the same raw
# rows every run, so "the three at-risk accounts" is a fact you can check by hand, not a coin flip.

EVIDENCE_SOURCES = ["support_tickets", "product_logs", "usage_metering", "crm_notes", "compliance_docs"]
NOISE_ACCOUNTS = ["acct_3001", "acct_3002", "acct_3003", "acct_3004", "acct_3005", "acct_3006"]
NOISE_SIGNALS = ["password_reset", "feature_question", "minor_latency", "onboarding", "billing_question"]
ROWS_PER_SOURCE = 120
EXPECTED_REJECTED_ROWS = 17

_KEY_ROWS = {
    "support_tickets": [
        {
            "evidence_id": "ticket_8831",
            "account_id": "acct_1842",
            "source": "support_tickets",
            "summary": "Unresolved auth rollout thread after enterprise SSO change.",
            "severity": "critical",
            "days_ago": 1,
            "risk_points": 10,
            "status": "open",
            "signal": "auth_failure",
            "next_action_hint": "Review auth trace before the customer call.",
        },
        {
            "evidence_id": "ticket_9050",
            "account_id": "acct_2199",
            "source": "support_tickets",
            "summary": "Security questionnaire blocked by missing audit export answer.",
            "severity": "high",
            "days_ago": 2,
            "risk_points": 6,
            "status": "unresolved",
            "signal": "unresolved_support",
        },
        {
            "evidence_id": "ticket_9002",
            "account_id": "acct_7731",
            "source": "support_tickets",
            "summary": "Billing limit question is blocking the implementation team.",
            "severity": "high",
            "days_ago": 2,
            "risk_points": 7,
            "status": "open",
            "signal": "billing_limit",
        },
    ],
    "product_logs": [
        {
            "evidence_id": "log_52991",
            "account_id": "acct_1842",
            "source": "product_logs",
            "summary": "Auth failures spiked after rollout and affected production users.",
            "severity": "critical",
            "days_ago": 0,
            "risk_points": 10,
            "signal": "auth_failure",
            "count": 187,
        },
        {
            "evidence_id": "log_62004",
            "account_id": "acct_2199",
            "source": "product_logs",
            "summary": "Scheduled data export jobs are failing during vendor review.",
            "severity": "high",
            "days_ago": 1,
            "risk_points": 4,
            "signal": "data_export_error",
            "count": 64,
        },
        {
            "evidence_id": "log_67300",
            "account_id": "acct_7731",
            "source": "product_logs",
            "summary": "Integration timeouts increased after the customer changed middleware.",
            "severity": "high",
            "days_ago": 1,
            "risk_points": 7,
            "signal": "integration_timeout",
            "count": 96,
        },
    ],
    "usage_metering": [
        {
            "evidence_id": "usage_771",
            "account_id": "acct_1842",
            "source": "usage_metering",
            "summary": "Weekly active users and API calls dropped after auth failures.",
            "severity": "high",
            "days_ago": 0,
            "risk_points": 8,
            "active_users_delta_pct": -42.0,
            "api_calls_delta_pct": -51.0,
            "caveat": "Usage drop may reflect holiday week",
        },
        {
            "evidence_id": "usage_889",
            "account_id": "acct_2199",
            "source": "usage_metering",
            "summary": "Usage dropped while renewal and security review are open.",
            "severity": "high",
            "days_ago": 1,
            "risk_points": 7,
            "active_users_delta_pct": -35.0,
            "api_calls_delta_pct": -28.0,
        },
        {
            "evidence_id": "usage_512",
            "account_id": "acct_7731",
            "source": "usage_metering",
            "summary": "Activity fell after billing limits started blocking batch jobs.",
            "severity": "medium",
            "days_ago": 1,
            "risk_points": 4,
            "active_users_delta_pct": -24.0,
            "api_calls_delta_pct": -19.0,
        },
    ],
    "crm_notes": [
        {
            "evidence_id": "crm_194",
            "account_id": "acct_1842",
            "source": "crm_notes",
            "summary": "Expansion call delayed until engineering can explain auth failures.",
            "severity": "high",
            "days_ago": 1,
            "risk_points": 6,
            "expansion_stage": "blocked",
            "renewal_days": 45,
        },
        {
            "evidence_id": "crm_211",
            "account_id": "acct_2199",
            "source": "crm_notes",
            "summary": "Renewal sponsor wrote that vendor review is now the blocker.",
            "severity": "high",
            "days_ago": 2,
            "risk_points": 5,
            "expansion_stage": "at_risk",
            "renewal_days": 16,
        },
        {
            "evidence_id": "crm_305",
            "account_id": "acct_7731",
            "source": "crm_notes",
            "summary": "Champion left and procurement asked for a smaller plan.",
            "severity": "medium",
            "days_ago": 3,
            "risk_points": 3,
            "expansion_stage": "champion_left",
            "renewal_days": 37,
        },
    ],
    "compliance_docs": [
        {
            "evidence_id": "comp_044",
            "account_id": "acct_1842",
            "source": "compliance_docs",
            "summary": "Data residency question is blocking security approval for rollout.",
            "severity": "high",
            "days_ago": 2,
            "risk_points": 5,
            "blocker": True,
            "status": "blocked",
        },
        {
            "evidence_id": "comp_075",
            "account_id": "acct_2199",
            "source": "compliance_docs",
            "summary": "Security review is blocked until audit export scope is answered.",
            "severity": "critical",
            "days_ago": 1,
            "risk_points": 10,
            "blocker": True,
            "status": "blocked",
        },
        {
            "evidence_id": "comp_103",
            "account_id": "acct_7731",
            "source": "compliance_docs",
            "summary": "Vendor-risk review remains open for a new integration path.",
            "severity": "medium",
            "days_ago": 2,
            "risk_points": 5,
            "blocker": True,
            "status": "open",
        },
    ],
}


def _noise_row(source: str, index: int) -> dict:
    rng = random.Random(int(hashlib.sha256(f"{source}:{index}".encode()).hexdigest()[:8], 16))
    account_id = rng.choice(NOISE_ACCOUNTS)
    base = {
        "evidence_id": f"{source.split('_')[0]}_noise_{index:03d}",
        "account_id": account_id,
        "source": source,
        "summary": f"Low-risk {source.replace('_', ' ')} signal for {account_id}.",
        "severity": "low",
        "days_ago": rng.randint(3, 6),
        "risk_points": 0,
    }
    signal = rng.choice(NOISE_SIGNALS)
    if source == "support_tickets":
        base.update({"status": "closed", "signal": signal})
    elif source == "product_logs":
        base.update({"signal": signal, "count": rng.randint(1, 8)})
    elif source == "usage_metering":
        base.update({"active_users_delta_pct": rng.randint(1, 12), "api_calls_delta_pct": rng.randint(1, 16)})
    elif source == "crm_notes":
        base.update({"expansion_stage": rng.choice(["healthy", "monitor"]), "renewal_days": rng.randint(80, 220)})
    elif source == "compliance_docs":
        base.update({"blocker": False, "status": rng.choice(["closed", "waiting"])})
    return base


def _bad_rows(source: str) -> list[dict]:
    rows = [
        {"evidence_id": f"bad_{source}_missing_account", "source": source, "summary": "missing account", "severity": "low", "days_ago": 1},
        {"evidence_id": f"bad_{source}_extra", "account_id": "bad-account", "source": source, "summary": "extra field", "severity": "low", "days_ago": 1, "private_note": "do not ship"},
        {"evidence_id": f"bad_{source}_severity", "account_id": "bad-account", "source": source, "summary": "bad severity", "severity": "urgent", "days_ago": 1},
    ]
    if source in {"support_tickets", "product_logs"}:
        rows.append({"evidence_id": f"bad_{source}_source_fields", "account_id": "bad-account", "source": source, "summary": "missing source field", "severity": "low", "days_ago": 1})
    return rows


def _customer_evidence(source: str):
    """Fixed raw evidence rows for one source. This is the EXAMPLE backend, swap it out."""
    if source not in EVIDENCE_SOURCES:
        raise ValueError(f"source must be one of {EVIDENCE_SOURCES}")
    rows = list(_KEY_ROWS[source])
    while len(rows) < ROWS_PER_SOURCE - len(_bad_rows(source)):
        rows.append(_noise_row(source, len(rows)))
    rows.extend(_bad_rows(source))
    return rows


def _fixture() -> dict[str, list[dict]]:
    return {source: _customer_evidence(source) for source in EVIDENCE_SOURCES}


def _fixture_sha256() -> str:
    payload = json.dumps(_fixture(), sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode()).hexdigest()


# --------------------------------------------------------------------------- THE EDIT SURFACE
# Replace TOOL_SPEC and call() with your own tool. Keep the shape: a Messages-API tool dict, plus
# optional `_trace_metadata` that the runner records and strips before the API call. The Python
# function's keyword arguments match input_schema's properties.

TOOL_SPEC = {
    "name": "query_customer_evidence",
    "description": (
        "Return raw customer evidence rows for one source from this week. Sources are support tickets, "
        "product logs, usage metering, CRM notes, and compliance docs. Rows are intentionally noisy. "
        "Valid rows include risk_points. Code should reject malformed input, join by account_id, sum "
        "risk_points, preserve evidence_id and caveats, then return a compact customer-risk decision "
        "packet."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "source": {
                "type": "string",
                "enum": EVIDENCE_SOURCES,
                "description": "the evidence source to fetch",
            }
        },
        "required": ["source"],
    },
    "_trace_metadata": {
        "tool_schema_version": "query_customer_evidence-v1",
        "reducer_version": "customer-evidence-reducer-v1",
        "snapshot_id": f"customer-evidence-fixture:{_fixture_sha256()}",
        "source_freshness": "static-seeded-fixture",
    },
}


def call(source: str = ""):
    """Run the tool for one input and return a JSON-serializable result. Your real backend goes here.

    The example reads the fixed mock above. Replace the body with your database query, API call,
    or file read. The return value is what the model, or the sandbox under programmatic tool calling,
    receives as the tool result.
    """
    return _customer_evidence(source)


# The fan-out task: a prompt that makes the model call the tool once per input. Replace with your own.
EXAMPLE_INPUTS = EVIDENCE_SOURCES

QUESTION = (
    "From this week's support tickets, product logs, CRM notes, usage metering, and compliance docs, "
    "identify the three customer accounts most likely to churn or block expansion. Use the tool "
    "query_customer_evidence(source) once for each source: support_tickets, product_logs, "
    "usage_metering, crm_notes, and compliance_docs. If code execution is available, write one script "
    "that loops over those sources, calls the tool inside the loop, keeps only rows with evidence_id, "
    "account_id starting with acct_, source, summary, and numeric risk_points, sums risk_points by "
    "account_id, ranks the top three accounts, and returns only a compact decision packet. If code "
    "execution is not available, call query_customer_evidence for each source directly. Give the "
    "reason, evidence_ids, caveats, and next_action for each account. Reply with "
    "compact JSON only in this shape: {\"accounts\":[{\"account_id\":\"acct_...\",\"risk\":\"high\","
    "\"reason\":\"...\",\"evidence_ids\":[\"...\"],\"caveats\":[\"...\"],\"next_action\":\"...\"}],"
    "\"fallback\":null}."
)


# --------------------------------------------------------------------------- the example's check
# Only the shipped example needs a machine-checkable true answer, so `make programmatic_tool_calling`
# can assert fewer input tokens, the expected answer, and the clean caller-path trace. When you swap
# in your own tool, set EXPECTED_ANSWER to your task's known answer, or leave it None and --check will
# skip only the correctness assertion.

def _true_risk_packet() -> dict:
    return reduce_fanout(EVIDENCE_SOURCES, _customer_evidence)


EXPECTED_ANSWER = tuple(account["account_id"] for account in _true_risk_packet()["accounts"])


def parse_answer(text: str):
    """Pull the ordered customer IDs out of the model's last text.

    The example asks for JSON, but the checker is intentionally tolerant about markdown fences and
    short prose around the packet. Returns the first three unique acct_ IDs in order.
    """
    account_ids = []
    for match in re.finditer(r"\bacct_\d+\b", text or ""):
        account_id = match.group(0)
        if account_id not in account_ids:
            account_ids.append(account_id)
    return tuple(account_ids[:3]) if len(account_ids) >= 3 else None
