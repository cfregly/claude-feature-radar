"""Offline tests for the private security_posture demonstrator."""

import json

from engine.demonstrators import security_posture as sp
from engine.demonstrators.security_posture import (
    CAVEATS,
    REQUIRED_SOURCE_KEYS,
    SecurityPostureDemonstrator,
)
from engine.sources_registry import sources


def _write_complete_snapshots(root):
    (root / "sources").mkdir(parents=True, exist_ok=True)
    by_key = {s.key: s for s in sources() if s.vendor == "claude"}
    for key in sp.REQUIRED_KEYS:
        src = by_key[key]
        (root / "sources" / f"{src.vendor}_{src.key}_2026-06-22.txt").write_text(
            f"Source: {src.url}\nSnapshot fetched 2026-06-22.\nOfficial source for {src.key}.\n"
        )


def test_security_sources_are_registered_for_the_sweep():
    entries = [(s.vendor, s.key, s.url) for s in sources()]
    keys = {(vendor, key) for vendor, key, _ in entries}
    for key in sp.REQUIRED_KEYS:
        assert ("claude", key) in keys
    assert sum(1 for vendor, key, _ in entries if vendor == "claude" and key == "mcp_connector") == 1
    assert ("claude", "ip_addresses") in keys
    for vendor, key, url in entries:
        if vendor == "claude" and key in sp.REQUIRED_KEYS:
            assert url.startswith(("https://platform.claude.com/", "https://docs.claude.com/",
                                   "https://code.claude.com/"))


def test_security_posture_holds_when_snapshots_are_missing(tmp_path, monkeypatch):
    monkeypatch.setattr(sp, "repo_root", lambda: tmp_path)
    demo = SecurityPostureDemonstrator()
    edge = {"key": "cmek", "axis": "security", "demoKind": "security_posture"}
    claude = demo.run_claude_arm(edge, {})
    verdict = demo.score(claude, [], {})
    receipt = demo.receipt(edge, claude, [], verdict, {})

    assert verdict.verdict == "never-evaluated"
    assert verdict.passed is False
    assert receipt.verdict == "never-evaluated"
    assert receipt.metric["missing_snapshots"]


def test_complete_synthetic_snapshots_pass_within_claude_only(tmp_path, monkeypatch):
    monkeypatch.setattr(sp, "repo_root", lambda: tmp_path)
    _write_complete_snapshots(tmp_path)
    demo = SecurityPostureDemonstrator()
    edge = {"key": "security-posture", "axis": "security", "demoKind": "security_posture"}
    claude = demo.run_claude_arm(edge, {})
    competitors = demo.run_competitor_arms(edge, {})
    verdict = demo.score(claude, competitors, {})
    receipt = demo.receipt(edge, claude, competitors, verdict, {})

    assert competitors == []
    assert receipt.demo_kind == "security_posture"
    assert receipt.verdict == "within-claude-only"
    assert receipt.passed is True
    assert receipt.metric["cross_vendor_claim"] is False
    assert set(receipt.workload["categories"]) == set(REQUIRED_SOURCE_KEYS)
    assert receipt.fairness["private_only"] is True


def test_receipt_carries_required_caveats(tmp_path, monkeypatch):
    monkeypatch.setattr(sp, "repo_root", lambda: tmp_path)
    _write_complete_snapshots(tmp_path)
    receipt = sp._run()
    caveats = receipt["workload"]["caveats"]

    for key in ("zdr", "hipaa_baa", "access_transparency", "cmek", "mcp_connector",
                "ip_allowlisting"):
        assert key in caveats
        assert caveats[key] == CAVEATS[key]
    assert "ZDR" in receipt["workload"]["not_claimed"]
    assert "HIPAA" in receipt["workload"]["not_claimed"]
    assert "BAA" in receipt["workload"]["not_claimed"]


def test_cli_writes_only_private_security_receipt(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(sp, "repo_root", lambda: tmp_path)
    _write_complete_snapshots(tmp_path)
    assert sp.main(["--json"]) == 0
    out = capsys.readouterr().out
    printed = json.loads(out)

    receipt_path = tmp_path / "data" / "last_security_posture.json"
    assert receipt_path.exists()
    assert not (tmp_path / "data" / "last_receipt.json").exists()
    assert json.loads(receipt_path.read_text())["verdict"] == "within-claude-only"
    assert printed["verdict"] == "within-claude-only"
