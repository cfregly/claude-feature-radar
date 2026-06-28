"""Offline tests for the source freshness gate."""

import json

from engine import freshness
from engine.sources_registry import Source


def _src(vendor="claude", key="programmatic_tool_calling", kind="doc"):
    return Source(vendor, key, f"https://example.test/{vendor}/{key}", kind)


def _landscape(src, h="oldhash"):
    return {
        "as_of_date": "2026-06-25",
        "content_hashes": {src.url: {"hash": h, "etag": "e0", "last_modified": "lm0"}},
        "capabilities": {
            f"{src.vendor}:{src.key}": {
                "evidence_quote": "old sourced claim",
                "content_hash": h,
            }
        },
    }


def test_changed_hash_is_reported_with_rerun_command(monkeypatch):
    src = _src()

    def fake_fetch(source, prior):
        assert prior["hash"] == "oldhash"
        return {"src": source, "status": "fetched", "hash": "newhash", "etag": "e1"}

    monkeypatch.setattr(freshness.sweep_edges, "fetch_one", fake_fetch)
    report = freshness.evaluate(watched_sources=[src], landscape=_landscape(src), date="2026-06-27")

    row = report["rows"][0]
    assert row["status"] == "changed"
    assert row["baseline_hash"] == "oldhash"
    assert row["new_source_hash"] == "newhash"
    assert row["rerun_command"] == "make programmatic-tool-calling"
    assert report["summary"]["stale_sources"] == 1
    assert freshness.has_stale(report)


def test_missing_baseline_is_not_treated_as_fresh(monkeypatch):
    src = _src("gemini", "new_docs")

    monkeypatch.setattr(
        freshness.sweep_edges,
        "fetch_one",
        lambda source, prior: {"src": source, "status": "fetched", "hash": "newhash"},
    )
    report = freshness.evaluate(watched_sources=[src], landscape={"content_hashes": {}}, date="2026-06-27")

    assert report["rows"][0]["status"] == "missing_baseline"
    assert report["rows"][0]["impact_group"] == "competitor_docs"
    assert report["summary"]["stale_sources"] == 1


def test_unknown_fetch_is_unknown_not_absence_or_fresh(monkeypatch):
    src = _src("openai", "pricing", "pricing")

    monkeypatch.setattr(
        freshness.sweep_edges,
        "fetch_one",
        lambda source, prior: {"src": source, "status": "unknown", "error": "HTTP 403", "hash": None},
    )
    report = freshness.evaluate(watched_sources=[src], landscape=_landscape(src), date="2026-06-27")

    row = report["rows"][0]
    assert row["status"] == "unknown"
    assert row["impact_group"] == "pricing"
    assert row["error"] == "HTTP 403"
    assert row["new_source_hash"] is None


def test_unchanged_fetch_is_fresh(monkeypatch):
    src = _src()

    monkeypatch.setattr(
        freshness.sweep_edges,
        "fetch_one",
        lambda source, prior: {"src": source, "status": "unchanged", "hash": "oldhash"},
    )
    report = freshness.evaluate(watched_sources=[src], landscape=_landscape(src), date="2026-06-27")

    assert report["rows"][0]["status"] == "fresh"
    assert report["summary"]["stale_sources"] == 0
    assert not freshness.has_stale(report)


def test_report_schema_and_guardrail(monkeypatch, tmp_path):
    src = _src("anthropic", "news", "blog")

    monkeypatch.setattr(
        freshness.sweep_edges,
        "fetch_one",
        lambda source, prior: {"src": source, "status": "fetched", "hash": "newhash"},
    )
    report = freshness.evaluate(watched_sources=[src], landscape={"content_hashes": {}}, date="2026-06-27")
    json_path, md_path = freshness.write_report(report, root=tmp_path)

    saved = json.loads(json_path.read_text())
    assert saved["schema_version"] == 1
    assert saved["guardrail"] == "A release does not update the claim. A rerun updates the claim."
    assert saved["control_plane"] == {
        "mode": "report_only",
        "review_pr_only": True,
        "auto_merge": False,
        "auto_publish": False,
        "auto_send": False,
    }
    assert saved["stale"][0]["decision_options"] == ["promote", "hold", "miss"]
    assert saved["stale"][0]["result"] == ""
    assert saved["stale"][0]["decision"] == ""
    md = md_path.read_text()
    assert "Search broad, prove narrow, republish only with receipts." in md
    assert "Control plane: PR-only control plane" in md
    assert "promote / hold / miss" in md


def test_freshness_report_does_not_mutate_landscape(monkeypatch, tmp_path):
    src = _src()
    landscape_dir = tmp_path / "landscape"
    landscape_dir.mkdir()
    landscape_path = landscape_dir / "landscape.json"
    original = json.dumps(_landscape(src), indent=2) + "\n"
    landscape_path.write_text(original)

    monkeypatch.setattr(
        freshness.sweep_edges,
        "fetch_one",
        lambda source, prior: {"src": source, "status": "fetched", "hash": "newhash"},
    )
    report = freshness.evaluate(watched_sources=[src], landscape=json.loads(original), date="2026-06-27")
    freshness.write_report(report, root=tmp_path)

    assert landscape_path.read_text() == original
    assert (tmp_path / "state" / "outbox" / "freshness" / "2026-06-27.json").exists()


def test_cli_write_report_uses_same_stale_report_and_fails(monkeypatch, tmp_path, capsys):
    report = {
        "schema_version": 1,
        "as_of_date": "2026-06-27",
        "landscape_as_of_date": "2026-06-25",
        "guardrail": freshness.GUARDRAIL,
        "summary": {
            "total_sources": 1,
            "fresh_sources": 0,
            "stale_sources": 1,
            "by_status": {"changed": 1},
            "by_impact_group": {"anthropic_release_or_docs": 1},
        },
        "stale": [{
            "source_id": "claude:programmatic_tool_calling",
            "vendor": "claude",
            "key": "programmatic_tool_calling",
            "kind": "doc",
            "impact_group": "anthropic_release_or_docs",
            "status": "changed",
            "source_url": "https://example.test/programmatic-tool-calling",
            "fetch_url": "https://example.test/programmatic-tool-calling",
            "baseline_hash": "oldhash",
            "new_source_hash": "newhash",
            "etag": None,
            "last_modified": None,
            "fetch_status": "fetched",
            "error": "",
            "fetched_date": "2026-06-27",
            "old_claim": "old sourced claim",
            "rerun_command": "make programmatic-tool-calling",
            "result": "",
            "decision": "",
            "decision_options": ["promote", "hold", "miss"],
        }],
        "rows": [],
    }
    calls = []

    def fake_evaluate():
        calls.append("evaluate")
        return report

    monkeypatch.setattr(freshness, "evaluate", fake_evaluate)
    monkeypatch.setattr(freshness, "repo_root", lambda: tmp_path)

    assert freshness.main(["--write-report"]) == 1
    assert calls == ["evaluate"]

    json_path = tmp_path / "state" / "outbox" / "freshness" / "2026-06-27.json"
    md_path = tmp_path / "state" / "outbox" / "freshness" / "2026-06-27.md"
    assert json_path.exists()
    assert md_path.exists()
    saved = json.loads(json_path.read_text())
    assert saved["stale"][0]["new_source_hash"] == "newhash"
    assert "promote / hold / miss" in md_path.read_text()
    out = capsys.readouterr().out
    assert "freshness report: state/outbox/freshness/2026-06-27.json" in out
    assert "freshness: stale sources require receipt updates" in out
