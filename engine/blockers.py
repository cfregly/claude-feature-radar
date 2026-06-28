"""Production blocker intake and GAP_PACKET renderer.

Radar owns classification. The blocker layer adds the field-signal packet a product or engineering
team needs: replayable case, business consequence, priority argument, owner, workaround or fix state,
founder follow-up state, and the learning update that keeps the same blocker from repeating.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from common.client import repo_root

CATEGORIES = {
    "cost",
    "speed",
    "reliability",
    "accuracy",
    "security",
    "evals",
    "tool design",
    "rate limits",
    "observability",
    "deployment",
    "docs",
    "other",
}
SEVERITIES = {"critical", "high", "medium", "low"}
PRIVACY_LEVELS = {"anonymized", "private", "public-source"}
VALUE_PILLARS = {"cost", "speed", "reliability", "accuracy", "security", "less glue code"}
DECISION_STATES = {"fix", "workaround", "doc", "cookbook", "primitive", "keep collecting evidence"}
FOLLOW_UP_STATES = {"pending", "sent", "not applicable"}
REQUIRED_FIELDS = {
    "schema_version",
    "blocker_id",
    "date",
    "segment",
    "category",
    "severity",
    "affected_workload",
    "consequence",
    "current_workaround",
    "privacy_level",
    "linked_feature_key",
    "misses_slug",
    "owner",
    "value_pillar",
    "recurrence_count",
    "decision_state",
    "next_action",
    "learning_update",
    "founder_follow_up",
    "source_evidence",
    "replay",
}
REPLAY_FIELDS = {"command", "fixture", "receipt", "expected", "actual"}


class BlockerError(ValueError):
    """Raised when a blocker record is malformed."""


@dataclass(frozen=True)
class PacketWrite:
    blocker_id: str
    misses_slug: str
    path: Path
    changed: bool


def blockers_root(root: Path | None = None) -> Path:
    return (root or repo_root()) / "blockers"


def default_misses_root(root: Path | None = None) -> Path:
    return (root or repo_root()).parent / ("claude-feature-" + "misses")


def _require_string(record: dict, field: str) -> None:
    if not isinstance(record.get(field), str) or not record[field].strip():
        raise BlockerError(f"{record.get('blocker_id', '<unknown>')}: {field} must be a non-empty string")


def _require_enum(record: dict, field: str, allowed: set[str]) -> None:
    _require_string(record, field)
    if record[field] not in allowed:
        allowed_text = ", ".join(sorted(allowed))
        raise BlockerError(f"{record['blocker_id']}: {field} must be one of {allowed_text}")


def validate_record(record: dict) -> dict:
    missing = sorted(REQUIRED_FIELDS - set(record))
    if missing:
        raise BlockerError(f"{record.get('blocker_id', '<unknown>')}: missing fields: {', '.join(missing)}")
    if record["schema_version"] != 1:
        raise BlockerError(f"{record['blocker_id']}: schema_version must be 1")
    for field in (
        "blocker_id",
        "date",
        "segment",
        "affected_workload",
        "consequence",
        "current_workaround",
        "linked_feature_key",
        "misses_slug",
        "owner",
        "next_action",
    ):
        _require_string(record, field)
    _require_enum(record, "category", CATEGORIES)
    _require_enum(record, "severity", SEVERITIES)
    _require_enum(record, "privacy_level", PRIVACY_LEVELS)
    _require_enum(record, "value_pillar", VALUE_PILLARS)
    _require_enum(record, "decision_state", DECISION_STATES)
    if not isinstance(record["recurrence_count"], int) or record["recurrence_count"] < 1:
        raise BlockerError(f"{record['blocker_id']}: recurrence_count must be a positive integer")
    _validate_learning_update(record)
    _validate_follow_up(record)
    _validate_evidence(record)
    _validate_replay(record)
    return record


def _validate_learning_update(record: dict) -> None:
    update = record["learning_update"]
    if not isinstance(update, dict):
        raise BlockerError(f"{record['blocker_id']}: learning_update must be an object")
    for field in ("target", "change"):
        if not isinstance(update.get(field), str) or not update[field].strip():
            raise BlockerError(f"{record['blocker_id']}: learning_update.{field} must be a non-empty string")


def _validate_follow_up(record: dict) -> None:
    follow = record["founder_follow_up"]
    if not isinstance(follow, dict):
        raise BlockerError(f"{record['blocker_id']}: founder_follow_up must be an object")
    state = follow.get("state")
    if state not in FOLLOW_UP_STATES:
        allowed_text = ", ".join(sorted(FOLLOW_UP_STATES))
        raise BlockerError(f"{record['blocker_id']}: founder_follow_up.state must be one of {allowed_text}")
    if not isinstance(follow.get("note"), str) or not follow["note"].strip():
        raise BlockerError(f"{record['blocker_id']}: founder_follow_up.note must be a non-empty string")


def _validate_evidence(record: dict) -> None:
    evidence = record["source_evidence"]
    if not isinstance(evidence, list) or not evidence:
        raise BlockerError(f"{record['blocker_id']}: source_evidence must be a non-empty list")
    for i, item in enumerate(evidence, start=1):
        if not isinstance(item, dict):
            raise BlockerError(f"{record['blocker_id']}: source_evidence[{i}] must be an object")
        for field in ("type", "path", "note"):
            if not isinstance(item.get(field), str) or not item[field].strip():
                raise BlockerError(
                    f"{record['blocker_id']}: source_evidence[{i}].{field} must be a non-empty string"
                )


def _validate_replay(record: dict) -> None:
    replay = record["replay"]
    if not isinstance(replay, dict):
        raise BlockerError(f"{record['blocker_id']}: replay must be an object")
    missing = sorted(REPLAY_FIELDS - set(replay))
    if missing:
        raise BlockerError(f"{record['blocker_id']}: replay missing fields: {', '.join(missing)}")
    for field in sorted(REPLAY_FIELDS):
        if not isinstance(replay.get(field), str) or not replay[field].strip():
            raise BlockerError(f"{record['blocker_id']}: replay.{field} must be a non-empty string")


def load_records(root: Path | None = None) -> list[dict]:
    base = blockers_root(root)
    records = []
    for path in sorted(base.glob("*.json")):
        records.append(validate_record(json.loads(path.read_text(encoding="utf-8"))))
    return records


def records_for_miss(misses_slug: str, *, root: Path | None = None) -> list[dict]:
    return [record for record in load_records(root) if record["misses_slug"] == misses_slug]


def records_for_feature(feature_key: str, *, root: Path | None = None) -> list[dict]:
    normalized = feature_key.replace("-", "_")
    return [record for record in load_records(root) if record["linked_feature_key"].replace("-", "_") == normalized]


def packet_path(record: dict, misses_root: Path | None = None) -> Path:
    base = misses_root or default_misses_root()
    return base / "misses" / record["misses_slug"] / "GAP_PACKET.md"


def _bullet_lines(items: Iterable[dict]) -> list[str]:
    lines = []
    for item in items:
        lines.append(f"- {item['type']}: `{item['path']}`. {item['note']}")
    return lines


def render_packet(record: dict) -> str:
    record = validate_record(dict(record))
    replay = record["replay"]
    learning = record["learning_update"]
    follow = record["founder_follow_up"]
    lines = [
        f"# Gap Packet: {record['misses_slug']}",
        "",
        "<!-- generated by engine.blockers from radar blockers/*.json -->",
        "",
        "## Blocker",
        "",
        f"- Blocker id: `{record['blocker_id']}`",
        f"- Date: {record['date']}",
        f"- Segment: {record['segment']}",
        f"- Category: {record['category']}",
        f"- Severity: {record['severity']}",
        f"- Privacy level: {record['privacy_level']}",
        f"- Linked feature key: `{record['linked_feature_key']}`",
        "",
        "## Replayable Case",
        "",
        f"- Command: `{replay['command']}`",
        f"- Fixture: `{replay['fixture']}`",
        f"- Receipt: `{replay['receipt']}`",
        f"- Expected: {replay['expected']}",
        f"- Actual: {replay['actual']}",
        "",
        "## Business Consequence",
        "",
        record["consequence"],
        "",
        "## Priority Argument",
        "",
        f"- Value pillar: {record['value_pillar']}",
        f"- Recurrence count: {record['recurrence_count']}",
        f"- Affected workload: {record['affected_workload']}",
        f"- Why now: {record['next_action']}",
        "",
        "## Owner And State",
        "",
        f"- Receiving owner: {record['owner']}",
        f"- Decision state: {record['decision_state']}",
        f"- Current workaround: {record['current_workaround']}",
        "",
        "## Evidence",
        "",
        *_bullet_lines(record["source_evidence"]),
        "",
        "## Learning Update",
        "",
        f"- Target: {learning['target']}",
        f"- Change: {learning['change']}",
        "",
        "## Founder Follow-Up",
        "",
        f"- State: {follow['state']}",
        f"- Note: {follow['note']}",
        "",
    ]
    return "\n".join(lines)


def render_freshness_context(records: list[dict]) -> str:
    if not records:
        return ""
    lines = ["## Blocker Context", ""]
    for record in records:
        lines.append(
            f"- `{record['blocker_id']}` routes to `GAP_PACKET.md`: {record['consequence']}"
        )
    lines.append("")
    return "\n".join(lines)


def write_packets(
    *,
    misses_root: Path | None = None,
    root: Path | None = None,
    only_slugs: set[str] | None = None,
    check: bool = False,
) -> list[PacketWrite]:
    writes: list[PacketWrite] = []
    for record in load_records(root):
        if only_slugs and record["misses_slug"] not in only_slugs:
            continue
        path = packet_path(record, misses_root)
        rendered = render_packet(record)
        existing = path.read_text(encoding="utf-8") if path.exists() else ""
        changed = existing != rendered
        if check:
            if changed:
                raise BlockerError(f"{path}: stale or missing GAP_PACKET.md for {record['blocker_id']}")
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(rendered, encoding="utf-8")
        writes.append(PacketWrite(record["blocker_id"], record["misses_slug"], path, changed))
    return writes


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Render or check product-owner production blocker packets.")
    parser.add_argument("--misses-root", type=Path, default=default_misses_root())
    parser.add_argument("--check", action="store_true", help="fail if a committed packet is stale")
    args = parser.parse_args(argv)
    try:
        writes = write_packets(misses_root=args.misses_root, check=args.check)
    except BlockerError as exc:
        print(f"blocker packets: FAIL\n  {exc}")
        return 1
    action = "checked" if args.check else "wrote"
    for item in writes:
        state = "changed" if item.changed else "clean"
        print(f"blocker packets: {action} {item.path} ({state})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
