"""Offline tests for production blocker intake packets."""

from __future__ import annotations

import json

import pytest

from engine import blockers


def _record() -> dict:
    return {
        "schema_version": 1,
        "blocker_id": "blk-test",
        "date": "2026-06-28",
        "segment": "anonymized founder team",
        "category": "deployment",
        "severity": "high",
        "affected_workload": "Tool-heavy support workflow.",
        "consequence": "The deployment path blocks the measured production pattern.",
        "current_workaround": "Use the direct API path or app-owned reducer.",
        "privacy_level": "anonymized",
        "linked_feature_key": "programmatic_tool_calling",
        "misses_slug": "programmatic-tool-calling",
        "owner": "Claude platform deployment surfaces",
        "value_pillar": "cost",
        "recurrence_count": 1,
        "decision_state": "workaround",
        "next_action": "Document the fallback.",
        "learning_update": {
            "target": "quickstart",
            "change": "Add the deployment caveat.",
        },
        "founder_follow_up": {
            "state": "pending",
            "note": "Follow up after the fallback is decided.",
        },
        "source_evidence": [
            {
                "type": "radar receipt",
                "path": "edges/programmatic-tool-calling/sample.txt",
                "note": "Receipt for the measured path.",
            }
        ],
        "replay": {
            "command": "make programmatic-tool-calling",
            "fixture": "edges/programmatic-tool-calling/sample.txt",
            "receipt": "data/last_programmatic_tool_calling.json",
            "expected": "Direct API path proves the cost lever.",
            "actual": "Deployment availability blocks production use.",
        },
    }


def test_packet_generation_carries_required_sections():
    record = blockers.load_records()[0]

    packet = blockers.render_packet(record)

    assert "## Replayable Case" in packet
    assert "## Business Consequence" in packet
    assert "## Priority Argument" in packet
    assert "## Founder Follow-Up" in packet
    assert record["blocker_id"] in packet


def test_required_fields_are_enforced(tmp_path):
    root = tmp_path / "radar"
    (root / "blockers").mkdir(parents=True)
    record = _record()
    record.pop("owner")
    (root / "blockers" / "bad.json").write_text(json.dumps(record))

    with pytest.raises(blockers.BlockerError, match="missing fields: owner"):
        blockers.load_records(root)


def test_packet_check_detects_stale_private_packet(tmp_path):
    root = tmp_path / "radar"
    misses = tmp_path / "misses"
    (root / "blockers").mkdir(parents=True)
    record = _record()
    (root / "blockers" / "blocker.json").write_text(json.dumps(record))
    packet = misses / "misses" / record["misses_slug"] / "GAP_PACKET.md"
    packet.parent.mkdir(parents=True)
    packet.write_text("# stale\n")

    with pytest.raises(blockers.BlockerError, match="stale or missing"):
        blockers.write_packets(root=root, misses_root=misses, check=True)

