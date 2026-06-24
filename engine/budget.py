"""Budget preflights for paid deep-research calls.

The daily deep loop is allowed to spend a small, explicit amount. This module makes that boundary
concrete: before a model call, estimate the worst-case cost from the prompt size and max output cap,
record a reservation in data/budget/, and refuse the call when the reservation would cross the cap.
After the call, replace the reservation with the exact cost from the provider usage object.
"""

from __future__ import annotations

import datetime as _dt
import json
import math
import os
import uuid
from dataclasses import dataclass
from typing import Any

from common.client import repo_root
from common.models import get
from common.pricing import cost_breakdown, cost_from_buckets

DEFAULT_BUDGET_USD = 2.0
ENV_BUDGET = "RADAR_BUDGET_USD"
ENV_LABEL = "RADAR_BUDGET_LABEL"


def _jsonable(obj: Any) -> str:
    if isinstance(obj, str):
        return obj
    return json.dumps(obj, sort_keys=True, default=str)


def estimate_tokens(*parts: Any) -> int:
    """Conservative-enough token estimate for preflight gating.

    The exact tokenizer is intentionally not a dependency of this repo's core path. The estimate is
    deliberately simple and slightly padded so a preflight blocks before a plainly oversized call.
    Actual spend is still recorded from the API usage object after the call.
    """
    chars = sum(len(_jsonable(p)) for p in parts if p is not None)
    return max(1, math.ceil(chars / 4) + 256)


def estimate_cost_usd(model_key: str, *, input_tokens: int, max_output_tokens: int) -> float:
    """Estimated upper-bound-ish cost for a single request."""
    m = get(model_key)
    if m.provider == "anthropic":
        return cost_from_buckets(model_key, fresh_input=input_tokens, cached=0, output=max_output_tokens)
    return cost_from_buckets(model_key, fresh_input=input_tokens, cached=0, output=max_output_tokens)


@dataclass(frozen=True)
class Reservation:
    id: str
    label: str
    model_key: str
    estimated_usd: float
    input_tokens_est: int
    max_output_tokens: int


class BudgetLedger:
    """One per-day, per-label budget ledger stored under gitignored data/."""

    def __init__(self, cap_usd: float | None, *, label: str = "grind-deep", root=None):
        self.cap_usd = cap_usd
        self.label = label
        self.root = root or repo_root()
        today = _dt.date.today().isoformat()
        safe_label = "".join(ch if ch.isalnum() or ch in "-_" else "-" for ch in label)
        self.path = self.root / "data" / "budget" / f"{today}-{safe_label}.json"

    @classmethod
    def from_env(cls, *, cap_usd: float | None = None, label: str | None = None, root=None):
        if cap_usd is None:
            raw = os.environ.get(ENV_BUDGET)
            cap_usd = float(raw) if raw not in (None, "") else DEFAULT_BUDGET_USD
        if cap_usd <= 0:
            raise SystemExit(f"{ENV_BUDGET} must be positive, got {cap_usd!r}")
        return cls(cap_usd, label=label or os.environ.get(ENV_LABEL, "grind-deep"), root=root)

    def _load(self) -> dict:
        if not self.path.exists():
            return {"cap_usd": self.cap_usd, "label": self.label, "records": []}
        data = json.loads(self.path.read_text())
        data.setdefault("records", [])
        data["cap_usd"] = self.cap_usd
        data["label"] = self.label
        return data

    def _save(self, data: dict) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        data["cap_usd"] = self.cap_usd
        data["label"] = self.label
        data["spent_or_reserved_usd"] = round(self.spent_or_reserved(data), 6)
        self.path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n")

    @staticmethod
    def spent_or_reserved(data: dict) -> float:
        total = 0.0
        for row in data.get("records", []):
            if row.get("status") == "released":
                continue
            total += float(row.get("actual_usd", row.get("estimated_usd", 0.0)) or 0.0)
        return total

    def remaining(self) -> float:
        return max(0.0, float(self.cap_usd or 0.0) - self.spent_or_reserved(self._load()))

    def preflight(self, label: str, model_key: str, *, messages, max_tokens: int,
                  system: str | None = None) -> Reservation:
        data = self._load()
        input_est = estimate_tokens(system, messages)
        estimated = estimate_cost_usd(model_key, input_tokens=input_est, max_output_tokens=max_tokens)
        used = self.spent_or_reserved(data)
        cap = float(self.cap_usd or 0.0)
        if used + estimated > cap:
            raise SystemExit(
                f"Budget preflight blocked {label}: estimated ${estimated:.4f}, "
                f"already spent/reserved ${used:.4f}, cap ${cap:.2f}. "
                f"Raise {ENV_BUDGET} only after approval."
            )
        rid = str(uuid.uuid4())
        row = {
            "id": rid,
            "label": label,
            "model_key": model_key,
            "model_id": get(model_key).id,
            "input_tokens_est": input_est,
            "max_output_tokens": max_tokens,
            "estimated_usd": round(estimated, 6),
            "status": "reserved",
            "created_at": _dt.datetime.now(_dt.timezone.utc).isoformat(),
        }
        data["records"].append(row)
        self._save(data)
        print(
            f"  budget preflight ok: {label} reserves ${estimated:.4f}; "
            f"${cap - used - estimated:.4f} remains of ${cap:.2f} ({self.path.relative_to(self.root)})"
        )
        return Reservation(rid, label, model_key, estimated, input_est, max_tokens)

    def commit_usage(self, reservation: Reservation, usage) -> float:
        actual = cost_breakdown(reservation.model_key, usage).total
        data = self._load()
        for row in data["records"]:
            if row.get("id") == reservation.id:
                row["status"] = "actual"
                row["actual_usd"] = round(actual, 6)
                row["usage"] = {
                    "input_tokens": getattr(usage, "input_tokens", 0) or 0,
                    "output_tokens": getattr(usage, "output_tokens", 0) or 0,
                    "cache_read_input_tokens": getattr(usage, "cache_read_input_tokens", 0) or 0,
                    "cache_creation_input_tokens": getattr(usage, "cache_creation_input_tokens", 0) or 0,
                }
                row["completed_at"] = _dt.datetime.now(_dt.timezone.utc).isoformat()
                break
        else:
            raise KeyError(f"unknown budget reservation {reservation.id}")
        self._save(data)
        print(f"  budget actual: {reservation.label} spent ${actual:.4f}; ${self.remaining():.4f} remains")
        return actual

    def commit_result_cost(self, reservation: Reservation, actual_usd: float, *, usage: dict | None = None) -> float:
        data = self._load()
        for row in data["records"]:
            if row.get("id") == reservation.id:
                row["status"] = "actual"
                row["actual_usd"] = round(actual_usd, 6)
                if usage is not None:
                    row["usage"] = usage
                row["completed_at"] = _dt.datetime.now(_dt.timezone.utc).isoformat()
                break
        else:
            raise KeyError(f"unknown budget reservation {reservation.id}")
        self._save(data)
        print(f"  budget actual: {reservation.label} spent ${actual_usd:.4f}; ${self.remaining():.4f} remains")
        return actual_usd

    def mark_failed(self, reservation: Reservation, error: Exception) -> None:
        """Keep the estimate reserved when a call fails without returning usage.

        Some API failures may still have consumed tokens. Holding the reservation is the conservative
        choice for a daily budget. The next run can delete data/budget/ after manual inspection.
        """
        data = self._load()
        for row in data["records"]:
            if row.get("id") == reservation.id:
                row["status"] = "failed_estimate_held"
                row["error"] = f"{type(error).__name__}: {str(error)[:200]}"
                row["completed_at"] = _dt.datetime.now(_dt.timezone.utc).isoformat()
                break
        self._save(data)
