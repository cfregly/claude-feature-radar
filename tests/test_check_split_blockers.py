"""Offline split-gate tests for blocker packets and provenance."""

from __future__ import annotations

import importlib.util
from pathlib import Path

from engine import blockers

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("check_split", ROOT / "scripts" / "check_split.py")
check_split = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(check_split)


def test_split_gate_rejects_product_owner_blocker_marker_in_public_hits(monkeypatch, tmp_path):
    hits = tmp_path / "hits"
    misses = tmp_path / "misses"
    hits.mkdir()
    (hits / "README.md").write_text("blk-2026-06-28-ptc-deployment\n")
    record = blockers.load_records(ROOT)[0]
    packet = blockers.packet_path(record, misses)
    packet.parent.mkdir(parents=True)
    packet.write_text(blockers.render_packet(record))
    monkeypatch.setattr(check_split, "_git_files", lambda root: ["README.md"] if root == hits else [])

    fail: list[str] = []
    check_split._check_blocker_packets(hits, misses, fail)

    assert any("product-owner blocker marker" in item for item in fail)


def test_split_gate_rejects_stale_provenance(monkeypatch, tmp_path):
    radar = tmp_path / "radar"
    hits = tmp_path / "hits"
    misses = tmp_path / "misses"
    misses.mkdir()
    (misses / "PROVENANCE.md").write_text(
        "- **Source commit this snapshot reflects:** `aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa`\n"
        "- **Public artifact commit checked with it:** `bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb`\n"
    )

    def fake_head(root: Path) -> str:
        if root == radar:
            return "cccccccccccccccccccccccccccccccccccccccc"
        if root == hits:
            return "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"
        return "unknown"

    monkeypatch.setattr(check_split, "_head", fake_head)
    warn: list[str] = []
    fail: list[str] = []

    check_split._check_provenance(radar, hits, misses, warn, fail)

    assert not warn
    assert any("does not match radar HEAD" in item for item in fail)
