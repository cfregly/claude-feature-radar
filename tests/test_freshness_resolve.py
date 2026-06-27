"""Offline tests for freshness auto-resolve."""

from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path

from engine import freshness_resolve as resolve
from engine.adversarial import ValueGate


def _row(key="search_results", status="changed", command="make search-results"):
    return {
        "source_id": f"claude:{key}",
        "vendor": "claude",
        "key": key,
        "kind": "doc",
        "impact_group": "anthropic_release_or_docs",
        "status": status,
        "source_url": f"https://example.test/{key}",
        "fetch_url": f"https://example.test/{key}",
        "baseline_hash": "oldhash",
        "new_source_hash": "newhash",
        "rerun_command": command,
        "old_claim": "old claim",
    }


def test_stale_rows_dedupe_into_workload_jobs():
    report = {"stale": [
        _row("prompt_caching", command="make ptc-cache-context"),
        _row("context_windows", command="make ptc-cache-context"),
    ]}

    jobs = resolve.build_jobs(report)

    assert len(jobs) == 1
    assert jobs[0].key == "ptc_cache_context"
    assert len(jobs[0].rows) == 2


def test_unknown_unmapped_and_generic_rows_hold():
    report = {"stale": [
        _row("search_results", status="unknown"),
        _row("new_surface", command="make new-surface"),
        _row("overview", command="make edges && make verify"),
    ]}

    jobs = resolve.build_jobs(report)

    assert [job.decision for job in jobs] == ["hold", "hold", "hold"]
    assert "unknown" in jobs[0].reason
    assert "no promotion registry" in jobs[1].reason
    assert "no promotion registry" in jobs[2].reason


def test_promotable_receipt_becomes_promote(monkeypatch, tmp_path):
    data = tmp_path / "data"
    data.mkdir()
    (data / "last_pdf_citations.json").write_text(json.dumps({
        "verdict": {"promotable_edge": True, "positive_signal": True},
        "passed": True,
    }))
    artifact = resolve.REGISTRY["pdf_citations"]
    job = resolve.Job(artifact=artifact, rows=[_row("pdf_support", command=artifact.rerun_command)],
                      command=artifact.rerun_command)

    monkeypatch.setattr(resolve, "repo_root", lambda: tmp_path)
    monkeypatch.setattr(resolve, "run_command", lambda *a, **k: subprocess.CompletedProcess(a, 0, "", ""))
    monkeypatch.setattr(resolve.scan, "current_edges", lambda: [{
        "key": "pdf_support",
        "verdict": "claude-ahead",
        "lead_score": 2,
        "axis": "accuracy",
        "fair_comparison": {"lead_basis": "head-to-head", "task_shape": "pdf qa", "score_gate": "5/5"},
    }])
    monkeypatch.setattr(resolve.adversarial, "value_confirmed",
                        lambda *a, **k: ValueGate(True, "adversarially-confirmed to add value"))
    for env in artifact.required_env:
        monkeypatch.setenv(env, "test-key")

    out = resolve.classify_job(job, rerun=True, spend_remaining=1.0)

    assert out.decision == "promote"
    assert out.receipt_path == "data/last_pdf_citations.json"


def test_missing_env_holds_instead_of_demoting(monkeypatch):
    artifact = resolve.REGISTRY["search_results"]
    job = resolve.Job(artifact=artifact, rows=[_row("search_results")], command=artifact.rerun_command)
    for env in artifact.required_env:
        monkeypatch.delenv(env, raising=False)

    out = resolve.classify_job(job, rerun=True, spend_remaining=1.0)

    assert out.decision == "hold"
    assert "missing required environment" in out.reason


def test_measured_negative_archives_hit_and_creates_miss(tmp_path):
    hits = tmp_path / "hits"
    misses = tmp_path / "misses"
    (hits / "search_results").mkdir(parents=True)
    (hits / "search_results" / "README.md").write_text("# Search Results\n")
    (hits / "docs").mkdir()
    (hits / "README.md").write_text("\n- [**search_results**](search_results/README.md): old claim.\n\n**Speed**:\n")
    (hits / "docs" / "confirmed-improvements.md").write_text(
        "| Artifact | Workload | Current receipt | Gate |\n"
        "| --- | --- | --- | --- |\n"
        "| `search_results` | old | old | old |\n"
    )
    (hits / "artifacts.json").write_text(json.dumps({
        "schema_version": 1,
        "artifacts": {"search_results": {"status": "active"}},
    }))
    (misses / "misses").mkdir(parents=True)
    (misses / "misses" / "README.md").write_text("| Miss | Area | Severity | Product ask | Reproduce |\n")
    job = resolve.Job(
        artifact=resolve.REGISTRY["search_results"],
        rows=[_row("search_results")],
        command="make search-results",
        decision="miss",
        reason="receipt no longer proves a promotable edge",
        receipt_path="data/last_search_results.json",
    )

    resolve.apply_decisions([job], hits_dir=hits, misses_dir=misses, date="2026-06-27")

    assert not (hits / "search_results").exists()
    assert (hits / "archive" / "demoted" / "2026-06-27" / "search_results").exists()
    manifest = json.loads((hits / "artifacts.json").read_text())
    assert manifest["artifacts"]["search_results"]["status"] == "demoted"
    readme = (hits / "README.md").read_text()
    assert "[**search_results**]" not in readme
    assert "Auto Resolve Archive" in readme
    finding = misses / "misses" / "search-results" / "FINDING.md"
    assert finding.exists()
    assert "Decision: `miss`" in finding.read_text()


def test_scaffolded_new_artifact_requires_public_adapter(monkeypatch, tmp_path):
    radar = tmp_path / "radar"
    hits = tmp_path / "hits"
    edge = radar / "edges" / "new-edge"
    edge.mkdir(parents=True)
    (edge / "README.md").write_text("# New Edge\n")
    (edge / "sample.txt").write_text("sample\n")
    (edge / "receipt.json").write_text("{}\n")
    hits.mkdir()
    (hits / "artifacts.json").write_text(json.dumps({"schema_version": 1, "artifacts": {}}))
    artifact = resolve.Artifact(
        key="new_edge",
        hits_slug="new_edge",
        misses_slug="new-edge",
        rerun_command="make new-edge",
        source_keys=("new_edge",),
        receipt_paths=("edges/new-edge/receipt.json",),
        edge_dir="edges/new-edge",
        public_adapter=True,
    )
    job = resolve.Job(artifact=artifact, rows=[_row("new_edge")], command="make new-edge",
                      decision="promote", reason="ok")
    monkeypatch.setattr(resolve, "repo_root", lambda: radar)

    resolve.apply_hits(job, hits, "2026-06-27")

    assert (hits / "new_edge" / "README.md").exists()
    assert (hits / "new_edge" / "sample.txt").exists()
    manifest = json.loads((hits / "artifacts.json").read_text())
    assert manifest["artifacts"]["new_edge"]["status"] == "active"


def test_run_dry_path_does_not_write_sibling_repos(monkeypatch, tmp_path):
    report = tmp_path / "freshness.json"
    report.write_text(json.dumps({"stale": [_row("search_results")]}))
    hits = tmp_path / "hits"
    misses = tmp_path / "misses"
    hits.mkdir()
    misses.mkdir()
    args = argparse.Namespace(
        report=report,
        write_report=False,
        apply=False,
        open_pr=False,
        hits_dir=hits,
        misses_dir=misses,
        max_spend_usd=1.0,
        limit=None,
        date="2026-06-27",
        no_rerun=True,
    )
    monkeypatch.setattr(resolve, "repo_root", lambda: tmp_path)

    jobs, written = resolve.run(args)

    assert written == []
    assert jobs[0].decision == "hold"
    assert list(hits.iterdir()) == []
    assert list(misses.iterdir()) == []


def test_resolve_report_carries_review_only_control_plane(tmp_path):
    job = resolve.Job(
        artifact=resolve.REGISTRY["search_results"],
        rows=[_row("search_results")],
        command="make search-results",
        decision="hold",
        reason="missing required environment: OPENAI_API_KEY",
    )

    json_path, md_path = resolve.write_report([job], date="2026-06-27", root=tmp_path)

    payload = json.loads(json_path.read_text())
    assert payload["control_plane"] == {
        "mode": "report_only",
        "review_pr_only": True,
        "auto_merge": False,
        "auto_publish": False,
        "auto_send": False,
    }
    md = md_path.read_text()
    assert "review PR only" in md
    assert "no auto-merge" in md
    assert "no auto-publish" in md


def test_unmapped_hold_apply_stays_report_only(tmp_path):
    hits = tmp_path / "hits"
    misses = tmp_path / "misses"
    hits.mkdir()
    (misses / "misses").mkdir(parents=True)
    (misses / "misses" / "README.md").write_text("| Miss | Area | Severity | Product ask | Reproduce |\n")
    job = resolve.Job(
        artifact=None,
        rows=[_row("unmapped_surface", command="make edges && make verify")],
        command="make edges && make verify",
        decision="hold",
        reason="no promotion registry entry for source",
    )

    resolve.apply_decisions([job], hits_dir=hits, misses_dir=misses, date="2026-06-27")

    assert sorted(p.name for p in (misses / "misses").iterdir()) == ["README.md"]
