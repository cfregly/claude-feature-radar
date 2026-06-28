"""Freshness gate for the recurring radar.

The radar discovers candidates from moving docs, but a changed source does not update a public
claim. This module compares the live watched sources against the committed source hashes in
landscape/landscape.json and fails when any source moved, lacks a baseline, or could not be fetched.

A release does not update the claim. A rerun updates the claim.
"""

from __future__ import annotations

import argparse
import datetime
import json
from pathlib import Path

from common.client import repo_root
from engine import sweep_edges
from engine.sources_registry import Source, sources

GUARDRAIL = "A release does not update the claim. A rerun updates the claim."

CONTROL_PLANE = {
    "mode": "report_only",
    "review_pr_only": True,
    "auto_merge": False,
    "auto_publish": False,
    "auto_send": False,
}

STALE_STATUSES = {"changed", "missing_baseline", "unknown"}

RERUN_COMMANDS = {
    "programmatic_tool_calling": "make programmatic-tool-calling",
    "prompt_caching": "make programmatic_tool_calling_cache_context",
    "context_windows": "make programmatic_tool_calling_cache_context",
    "code_execution": "make programmatic-tool-calling",
    "citations": "make citations-paraphrase",
    "pdf_support": "make pdf-citations",
    "search_results": "make search-results",
    "web_search_tool": "make web-citations",
    "task_budgets": "make task-budget",
    "cache_diagnostics": "make cache-diagnostics",
    "batch_processing": "make bulk-output",
    "advisor_tool": "make advisor",
    "fast_mode": "make fast-mode",
    "pricing": "make verify-live",
}

MODEL_KEYS = (
    "model",
    "opus",
    "fable",
    "mythos",
    "claude_4",
    "gpt_",
    "context_windows",
    "fast_mode",
    "rate_limits",
)


def today() -> str:
    return datetime.date.today().isoformat()


def impact_group(src: Source) -> str:
    key = src.key.lower()
    if src.kind == "pricing" or "pricing" in key:
        return "pricing"
    if any(token in key for token in MODEL_KEYS):
        return "model_availability"
    if src.vendor in {"openai", "gemini"}:
        return "competitor_docs"
    return "anthropic_release_or_docs"


def rerun_command(src: Source) -> str:
    if src.kind == "pricing":
        return "make verify-live"
    return RERUN_COMMANDS.get(src.key, "make edges && make verify")


def _source_id(src: Source) -> str:
    return f"{src.vendor}:{src.key}"


def _prior_capability(src: Source, landscape: dict) -> dict:
    return (landscape.get("capabilities") or {}).get(_source_id(src), {})


def _row(src: Source, status: str, *, landscape: dict, prior: dict | None,
         result: dict, date: str) -> dict:
    current_hash = result.get("hash")
    old_claim = _prior_capability(src, landscape).get("evidence_quote", "")
    return {
        "source_id": _source_id(src),
        "vendor": src.vendor,
        "key": src.key,
        "kind": src.kind,
        "impact_group": impact_group(src),
        "status": status,
        "source_url": src.url,
        "fetch_url": src.feed or src.url,
        "baseline_hash": (prior or {}).get("hash"),
        "new_source_hash": current_hash,
        "etag": result.get("etag") or (prior or {}).get("etag"),
        "last_modified": result.get("last_modified") or (prior or {}).get("last_modified"),
        "fetch_status": result.get("status"),
        "error": result.get("error", ""),
        "fetched_date": date,
        "old_claim": old_claim,
        "rerun_command": rerun_command(src),
        "result": "",
        "decision": "",
        "decision_options": ["promote", "hold", "miss"],
    }


def evaluate_source(src: Source, landscape: dict, date: str) -> dict:
    """Fetch one source and compare it to the committed hash baseline."""
    prior_hashes = landscape.get("content_hashes") or {}
    prior = prior_hashes.get(src.url)
    result = sweep_edges.fetch_one(src, prior)

    if result.get("status") == "unknown":
        return _row(src, "unknown", landscape=landscape, prior=prior, result=result, date=date)
    if not prior:
        return _row(src, "missing_baseline", landscape=landscape, prior=prior, result=result, date=date)
    if result.get("status") == "unchanged":
        return _row(src, "fresh", landscape=landscape, prior=prior, result=result, date=date)
    if result.get("hash") == prior.get("hash"):
        return _row(src, "fresh", landscape=landscape, prior=prior, result=result, date=date)
    return _row(src, "changed", landscape=landscape, prior=prior, result=result, date=date)


def evaluate(*, watched_sources: list[Source] | None = None, date: str | None = None,
             landscape: dict | None = None) -> dict:
    """Return the freshness report shape without writing files."""
    run_date = date or today()
    landscape = landscape if landscape is not None else sweep_edges.load_landscape()
    rows = [evaluate_source(src, landscape, run_date) for src in (watched_sources or sources())]
    stale = [r for r in rows if r["status"] in STALE_STATUSES]
    by_status: dict[str, int] = {}
    by_impact: dict[str, int] = {}
    for row in rows:
        by_status[row["status"]] = by_status.get(row["status"], 0) + 1
        by_impact[row["impact_group"]] = by_impact.get(row["impact_group"], 0) + 1
    return {
        "schema_version": 1,
        "as_of_date": run_date,
        "landscape_as_of_date": landscape.get("as_of_date"),
        "guardrail": GUARDRAIL,
        "control_plane": CONTROL_PLANE,
        "summary": {
            "total_sources": len(rows),
            "fresh_sources": by_status.get("fresh", 0),
            "stale_sources": len(stale),
            "by_status": by_status,
            "by_impact_group": by_impact,
        },
        "stale": stale,
        "rows": rows,
    }


def has_stale(report: dict) -> bool:
    return bool(report.get("stale"))


def report_dir(root: Path | None = None) -> Path:
    return (root or repo_root()) / "state" / "outbox" / "freshness"


def write_report(report: dict, *, root: Path | None = None) -> tuple[Path, Path]:
    out_dir = report_dir(root)
    out_dir.mkdir(parents=True, exist_ok=True)
    date = report["as_of_date"]
    json_path = out_dir / f"{date}.json"
    md_path = out_dir / f"{date}.md"
    json_path.write_text(json.dumps(report, indent=2) + "\n")
    md_path.write_text(markdown_report(report))
    return json_path, md_path


def markdown_report(report: dict) -> str:
    summary = report["summary"]
    lines = [
        f"# Feature Radar Freshness Report, {report['as_of_date']}",
        "",
        report["guardrail"],
        "",
        "Control plane: PR-only control plane, no auto-merge, no auto-publish, no auto-send.",
        "",
        "This report is inert. It does not update public claims, send mail, post publicly, or push a branch.",
        "",
        "## Summary",
        "",
        f"- Total watched sources: {summary['total_sources']}",
        f"- Fresh sources: {summary['fresh_sources']}",
        f"- Sources needing a receipt update: {summary['stale_sources']}",
        f"- Landscape baseline date: {report.get('landscape_as_of_date') or 'unknown'}",
        "",
        "## Receipt Update Queue",
        "",
    ]
    stale = report.get("stale") or []
    if not stale:
        lines.append("No freshness drift found.")
    else:
        lines += [
            "| Source | Impact | Status | Old hash | New hash | Rerun command | Result | Decision |",
            "| --- | --- | --- | --- | --- | --- | --- | --- |",
        ]
        for row in stale:
            old_hash = (row.get("baseline_hash") or "")[:12] or "none"
            new_hash = (row.get("new_source_hash") or "")[:12] or "unknown"
            lines.append(
                f"| {row['source_id']} | {row['impact_group']} | {row['status']} | "
                f"{old_hash} | {new_hash} | `{row['rerun_command']}` |  | promote / hold / miss |"
            )
    lines += [
        "",
        "## Update Rule",
        "",
        "Search broad, prove narrow, republish only with receipts.",
        "`feature-radar` watches the surface. `feature-hits` only contains reproducible wins.",
        "`feature-misses` keeps parity, caveats, losses, and stale findings so stale claims do not disappear.",
        "Founder-kit pins companion commits or tags so recipes stay reproducible when a companion repo moves.",
        "",
    ]
    return "\n".join(lines)


def print_summary(report: dict) -> None:
    summary = report["summary"]
    print(f"freshness: {summary['fresh_sources']}/{summary['total_sources']} sources fresh")
    if not report.get("stale"):
        print("freshness: clean")
        return
    print("freshness: stale sources require receipt updates")
    for row in report["stale"]:
        print(
            f"  - {row['source_id']} {row['status']} "
            f"old={(row.get('baseline_hash') or 'none')[:12]} "
            f"new={(row.get('new_source_hash') or 'unknown')[:12]} "
            f"rerun={row['rerun_command']}"
        )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Check source freshness against landscape hashes.")
    parser.add_argument("--write-report", action="store_true",
                        help="write state/outbox/freshness/YYYY-MM-DD.{json,md}")
    parser.add_argument("--no-fail", action="store_true",
                        help="return 0 even when sources are stale")
    args = parser.parse_args(argv)

    report = evaluate()
    if args.write_report:
        json_path, md_path = write_report(report)
        print(f"freshness report: {json_path.relative_to(repo_root())}")
        print(f"freshness report: {md_path.relative_to(repo_root())}")
    print_summary(report)
    if has_stale(report) and not args.no_fail:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
