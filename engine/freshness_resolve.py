"""Resolve freshness drift into promote, hold, or miss decisions.

Freshness detects that source hashes moved. This follow-up is the guarded action lane: rerun a mapped
workload, inspect its receipt, then prepare repo changes for review. It may open PRs when explicitly
requested, but it never merges, sends mail, or publishes directly.
"""

from __future__ import annotations

import argparse
import datetime
import json
import os
import re
import shlex
import shutil
import subprocess
from dataclasses import asdict, dataclass, field
from pathlib import Path

from common.client import repo_root
from engine import adversarial, freshness, scan

DECISIONS = {"promote", "hold", "miss"}
INFRA_MARKERS = (
    "api key",
    "authentication",
    "auth",
    "quota",
    "rate limit",
    "429",
    "timeout",
    "timed out",
    "overloaded",
    "connection",
    "network",
    "temporarily unavailable",
)


@dataclass(frozen=True)
class Artifact:
    key: str
    hits_slug: str
    misses_slug: str
    rerun_command: str
    source_keys: tuple[str, ...]
    receipt_paths: tuple[str, ...]
    edge_dir: str = ""
    active_public: bool = False
    public_adapter: bool = False
    estimate_usd: float = 0.10
    required_env: tuple[str, ...] = ("ANTHROPIC_API_KEY", "OPENAI_API_KEY", "GEMINI_API_KEY")


@dataclass
class Job:
    artifact: Artifact | None
    rows: list[dict]
    command: str
    decision: str = "hold"
    reason: str = ""
    receipt_path: str = ""
    receipt_summary: dict = field(default_factory=dict)
    command_status: int | None = None
    stdout_tail: str = ""
    stderr_tail: str = ""
    applied: list[str] = field(default_factory=list)

    @property
    def key(self) -> str:
        if self.artifact:
            return self.artifact.key
        first = self.rows[0] if self.rows else {}
        return first.get("source_id") or first.get("key") or "unknown"


ACTIVE_ENV = ("ANTHROPIC_API_KEY", "OPENAI_API_KEY", "GEMINI_API_KEY")

REGISTRY: dict[str, Artifact] = {
    "programmatic_tool_calling": Artifact(
        key="programmatic_tool_calling",
        hits_slug="programmatic_tool_calling",
        misses_slug="programmatic-tool-calling",
        rerun_command="make programmatic-tool-calling",
        source_keys=("programmatic_tool_calling", "code_execution"),
        receipt_paths=("data/last_programmatic_tool_calling.json",),
        edge_dir="edges/programmatic-tool-calling",
        active_public=True,
        public_adapter=True,
        estimate_usd=0.08,
        required_env=("ANTHROPIC_API_KEY",),
    ),
    "ptc_cache_context": Artifact(
        key="ptc_cache_context",
        hits_slug="ptc_cache_context",
        misses_slug="programmatic-tool-calling",
        rerun_command="make ptc-cache-context",
        source_keys=("prompt_caching", "context_windows", "programmatic_tool_calling"),
        receipt_paths=("data/last_ptc_cache_context.json", "edges/programmatic-tool-calling/ptc-cache-context.json"),
        edge_dir="edges/programmatic-tool-calling",
        active_public=True,
        public_adapter=True,
        estimate_usd=0.08,
        required_env=("ANTHROPIC_API_KEY",),
    ),
    "pdf_citations": Artifact(
        key="pdf_citations",
        hits_slug="pdf_citations",
        misses_slug="citations",
        rerun_command="make pdf-citations",
        source_keys=("pdf_support", "citations"),
        receipt_paths=("data/last_pdf_citations.json", "edges/pdf-citations/receipt.json"),
        edge_dir="edges/pdf-citations",
        active_public=True,
        public_adapter=True,
        estimate_usd=0.05,
        required_env=ACTIVE_ENV,
    ),
    "grounding_stack": Artifact(
        key="grounding_stack",
        hits_slug="grounding_stack",
        misses_slug="grounding-stack",
        rerun_command="make grounding-stack",
        source_keys=("search_results", "pdf_support", "citations"),
        receipt_paths=("data/last_grounding_stack.json", "edges/grounding-stack/receipt.json"),
        edge_dir="edges/grounding-stack",
        active_public=True,
        public_adapter=True,
        estimate_usd=0.01,
        required_env=ACTIVE_ENV,
    ),
    "search_results": Artifact(
        key="search_results",
        hits_slug="search_results",
        misses_slug="search-results",
        rerun_command="make search-results",
        source_keys=("search_results",),
        receipt_paths=("data/last_search_results.json", "edges/search-results/receipt.json"),
        edge_dir="edges/search-results",
        active_public=True,
        public_adapter=True,
        estimate_usd=0.02,
        required_env=ACTIVE_ENV,
    ),
    "task_budgets": Artifact(
        key="task_budgets",
        hits_slug="task_budgets",
        misses_slug="task-budgets",
        rerun_command="make task-budget",
        source_keys=("task_budgets",),
        receipt_paths=("data/last_task_budgets.json", "edges/task-budgets/receipt.json"),
        edge_dir="edges/task-budgets",
        active_public=True,
        public_adapter=True,
        estimate_usd=0.01,
        required_env=ACTIVE_ENV,
    ),
    "cache_diagnostics": Artifact(
        key="cache_diagnostics",
        hits_slug="cache_diagnostics",
        misses_slug="cache-diagnostics",
        rerun_command="make cache-diagnostics",
        source_keys=("cache_diagnostics",),
        receipt_paths=("data/last_cache_diagnostics.json", "edges/cache-diagnostics/receipt.json"),
        edge_dir="edges/cache-diagnostics",
        active_public=False,
        public_adapter=False,
        estimate_usd=0.08,
        required_env=ACTIVE_ENV,
    ),
}


def today() -> str:
    return datetime.date.today().isoformat()


def _norm_key(key: str) -> str:
    return (key or "").strip().lower().replace("-", "_")


def _slug(key: str) -> str:
    return _norm_key(key).replace("_", "-")


def registry_by_source() -> dict[str, Artifact]:
    out: dict[str, Artifact] = {}
    for artifact in REGISTRY.values():
        for key in artifact.source_keys:
            out[_norm_key(key)] = artifact
    return out


def load_or_create_report(path: Path | None, *, write_report: bool = False) -> tuple[dict, list[Path]]:
    if path:
        return json.loads(path.read_text(encoding="utf-8")), []
    report = freshness.evaluate()
    written: list[Path] = []
    if write_report:
        written = list(freshness.write_report(report))
    return report, written


def build_jobs(report: dict, *, limit: int | None = None) -> list[Job]:
    by_source = registry_by_source()
    jobs: dict[str, Job] = {}
    holds: list[Job] = []
    for row in report.get("stale") or []:
        key = _norm_key(row.get("key", ""))
        artifact = by_source.get(key)
        command = row.get("rerun_command") or ""
        generic = command.strip() == "make edges && make verify"
        if row.get("status") == "unknown":
            holds.append(Job(artifact, [row], command, reason="source fetch was unknown, so no claim can move"))
            continue
        if not artifact:
            holds.append(Job(None, [row], command, reason="no promotion registry entry for source"))
            continue
        if generic:
            holds.append(Job(artifact, [row], command, reason="generic discovery command is not a workload receipt"))
            continue
        job = jobs.setdefault(artifact.key, Job(artifact, [], artifact.rerun_command))
        job.rows.append(row)
    ordered = list(jobs.values()) + holds
    return ordered[:limit] if limit else ordered


def _tail(text: str, limit: int = 1600) -> str:
    text = text or ""
    return text[-limit:]


def _infra_failure(text: str) -> bool:
    low = (text or "").lower()
    return any(marker in low for marker in INFRA_MARKERS)


def run_command(command: str, *, cwd: Path, timeout_s: int = 1800) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        shlex.split(command),
        cwd=cwd,
        capture_output=True,
        text=True,
        timeout=timeout_s,
    )


def locate_receipt(artifact: Artifact, *, root: Path | None = None) -> tuple[Path | None, dict | None]:
    base = root or repo_root()
    for rel in artifact.receipt_paths:
        path = base / rel
        if not path.exists():
            continue
        if path.suffix == ".json":
            try:
                return path, json.loads(path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        low = text.lower()
        if "promotable_edge: true" in low or "check passed" in low or "gate passed: true" in low:
            return path, {"verdict": {"promotable_edge": True}, "sample_text": text[:2000]}
        if "promotable_edge: false" in low or "gate passed: false" in low:
            return path, {"verdict": {"promotable_edge": False}, "sample_text": text[:2000]}
    return None, None


def _receipt_promotable(receipt: dict | None) -> bool:
    if not receipt:
        return False
    if adversarial.receipt_value_positive(receipt):
        return True
    verdict = receipt.get("verdict")
    return isinstance(verdict, dict) and bool(verdict.get("promotable_edge"))


def _receipt_negative(receipt: dict | None) -> bool:
    if not receipt:
        return False
    verdict = receipt.get("verdict")
    if isinstance(verdict, dict) and verdict.get("promotable_edge") is False:
        return True
    if isinstance(verdict, str) and verdict in {"parity", "claude-behind", "never-evaluated"}:
        return True
    if receipt.get("passed") is False:
        return True
    return False


def _receipt_summary(receipt: dict | None) -> dict:
    if not receipt:
        return {}
    summary = {}
    for key in ("verdict", "passed", "edge_key", "demo_kind", "claim_under_test", "claim"):
        if key in receipt:
            summary[key] = receipt[key]
    return summary


def _landscape_edge(artifact: Artifact) -> dict | None:
    keys = {artifact.key, artifact.key.replace("_", "-")}
    for src in artifact.source_keys:
        keys.add(src)
        keys.add(src.replace("_", "-"))
    for edge in scan.current_edges():
        if edge.get("key") in keys:
            return edge
    return None


def classify_job(job: Job, *, rerun: bool = True, spend_remaining: float = 0.0) -> Job:
    artifact = job.artifact
    if not artifact:
        job.decision = "hold"
        job.reason = job.reason or "unmapped source"
        return job
    if job.reason:
        job.decision = "hold"
        return job
    missing_env = [name for name in artifact.required_env if not os.environ.get(name)]
    if missing_env and rerun:
        job.decision = "hold"
        job.reason = "missing required environment: " + ", ".join(missing_env)
        return job
    if rerun and artifact.estimate_usd > spend_remaining:
        job.decision = "hold"
        job.reason = f"spend cap would be exceeded by {artifact.rerun_command}"
        return job
    if rerun:
        try:
            proc = run_command(artifact.rerun_command, cwd=repo_root())
        except subprocess.TimeoutExpired as exc:
            job.decision = "hold"
            job.reason = f"rerun timed out: {exc}"
            return job
        job.command_status = proc.returncode
        job.stdout_tail = _tail(proc.stdout)
        job.stderr_tail = _tail(proc.stderr)
        if proc.returncode != 0:
            text = proc.stdout + "\n" + proc.stderr
            job.decision = "hold"
            job.reason = "infrastructure failure during rerun" if _infra_failure(text) else "rerun command failed"
            return job

    receipt_path, receipt = locate_receipt(artifact)
    if not receipt_path or not receipt:
        job.decision = "hold"
        job.reason = "missing machine receipt after rerun"
        return job
    job.receipt_path = str(receipt_path.relative_to(repo_root()))
    job.receipt_summary = _receipt_summary(receipt)

    if _receipt_negative(receipt):
        job.decision = "miss"
        job.reason = "receipt no longer proves a promotable edge"
        return job
    if not _receipt_promotable(receipt):
        job.decision = "hold"
        job.reason = "receipt is inconclusive"
        return job

    edge = _landscape_edge(artifact)
    if not edge:
        job.decision = "hold"
        job.reason = "no landscape edge for adversarial gate"
        return job
    gate = adversarial.value_confirmed(edge, receipt=receipt, require_receipt=True)
    if gate.ok:
        if not artifact.public_adapter:
            job.decision = "hold"
            job.reason = "positive receipt has no public adapter"
        else:
            job.decision = "promote"
            job.reason = gate.reason
        return job
    if gate.adversarial_verdict == "KILLED":
        job.decision = "miss"
        job.reason = gate.reason
        return job
    job.decision = "hold"
    job.reason = gate.reason
    return job


def classify_jobs(jobs: list[Job], *, rerun: bool, max_spend_usd: float) -> list[Job]:
    spent_estimate = 0.0
    out = []
    for job in jobs:
        remaining = max(0.0, max_spend_usd - spent_estimate)
        classified = classify_job(job, rerun=rerun, spend_remaining=remaining)
        if rerun and classified.command_status == 0 and classified.artifact:
            spent_estimate += classified.artifact.estimate_usd
        out.append(classified)
    return out


def _load_hits_manifest(hits_dir: Path) -> dict:
    path = hits_dir / "artifacts.json"
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return {"schema_version": 1, "artifacts": {}}


def _write_hits_manifest(hits_dir: Path, manifest: dict) -> None:
    (hits_dir / "artifacts.json").write_text(json.dumps(manifest, indent=2) + "\n")


def _copy_public_artifact(artifact: Artifact, hits_dir: Path) -> list[str]:
    src_dir = repo_root() / artifact.edge_dir
    dst_dir = hits_dir / artifact.hits_slug
    copied: list[str] = []
    if not src_dir.exists():
        return copied
    dst_dir.mkdir(parents=True, exist_ok=True)
    mapping = {
        "README.md": "README.md",
        "sample.txt": "sample.txt",
        "receipt.json": "receipt.json",
        "demo.py": "run.py",
    }
    for src_name, dst_name in mapping.items():
        src = src_dir / src_name
        if src.exists():
            shutil.copy2(src, dst_dir / dst_name)
            copied.append(str((dst_dir / dst_name).relative_to(hits_dir)))
    init = dst_dir / "__init__.py"
    if not init.exists():
        init.write_text("")
        copied.append(str(init.relative_to(hits_dir)))
    return copied


def _remove_markdown_bullet(text: str, slug: str) -> str:
    pattern = re.compile(rf"\n- \[\*\*{re.escape(slug)}\*\*\].*?(?=\n- \[\*\*|\n\n\*\*|\n## |\Z)", re.S)
    return pattern.sub("", text)


def _append_archive_note(path: Path, date: str, slug: str, reason: str) -> None:
    text = path.read_text(encoding="utf-8") if path.exists() else ""
    heading = "## Auto Resolve Archive"
    note = f"- {date}: `{slug}` moved out of the active promoted surface. Reason: {reason}\n"
    if heading not in text:
        text = text.rstrip() + f"\n\n{heading}\n\n{note}"
    elif note not in text:
        text = text.rstrip() + "\n" + note
    path.write_text(text)


def apply_hits(job: Job, hits_dir: Path, date: str) -> None:
    artifact = job.artifact
    if not artifact:
        return
    manifest = _load_hits_manifest(hits_dir)
    artifacts = manifest.setdefault("artifacts", {})
    row = artifacts.setdefault(artifact.hits_slug, {})
    if job.decision == "promote":
        copied = _copy_public_artifact(artifact, hits_dir) if not (hits_dir / artifact.hits_slug).exists() else []
        row.update({
            "status": "active",
            "make_target": artifact.hits_slug,
            "run_module": f"{artifact.hits_slug}.run",
            "check_args": ["--check"],
            "cost_usd": f"{artifact.estimate_usd:.2f}",
        })
        job.applied.append(f"hits manifest active {artifact.hits_slug}")
        job.applied.extend(f"hits copied {rel}" for rel in copied)
    elif job.decision == "miss" and artifact.active_public:
        src = hits_dir / artifact.hits_slug
        if src.exists():
            archive = hits_dir / "archive" / "demoted" / date / artifact.hits_slug
            archive.parent.mkdir(parents=True, exist_ok=True)
            if archive.exists():
                shutil.rmtree(archive)
            shutil.move(str(src), str(archive))
            job.applied.append(f"hits archived {artifact.hits_slug}")
        row["status"] = "demoted"
        row["demoted_at"] = date
        row["reason"] = job.reason
        for rel in ("README.md", "docs/confirmed-improvements.md"):
            path = hits_dir / rel
            if path.exists():
                path.write_text(_remove_markdown_bullet(path.read_text(encoding="utf-8"), artifact.hits_slug))
                _append_archive_note(path, date, artifact.hits_slug, job.reason)
        job.applied.append(f"hits manifest demoted {artifact.hits_slug}")
    _write_hits_manifest(hits_dir, manifest)


def _miss_finding(job: Job, date: str) -> str:
    row = job.rows[0] if job.rows else {}
    artifact = job.artifact
    title = artifact.misses_slug if artifact else _slug(row.get("key", "unknown"))
    return "\n".join([
        f"# Freshness Decision: {title}",
        "",
        f"Decision: `{job.decision}`",
        f"Date: {date}",
        f"Reason: {job.reason}",
        "",
        "## Source",
        "",
        f"- Source URL: {row.get('source_url', '')}",
        f"- Old hash: {row.get('baseline_hash') or 'none'}",
        f"- New hash: {row.get('new_source_hash') or 'unknown'}",
        f"- Rerun command: `{job.command}`",
        f"- Receipt: `{job.receipt_path or 'none'}`",
        "",
        "A release does not update the claim. A rerun updates the claim.",
        "",
    ])


def _upsert_section(path: Path, marker: str, body: str) -> None:
    text = path.read_text(encoding="utf-8") if path.exists() else ""
    start = f"<!-- {marker}:start -->"
    end = f"<!-- {marker}:end -->"
    block = f"{start}\n{body.rstrip()}\n{end}\n"
    if start in text and end in text:
        text = re.sub(rf"{re.escape(start)}.*?{re.escape(end)}\n?", block, text, flags=re.S)
    else:
        text = text.rstrip() + "\n\n" + block
    path.write_text(text)


def apply_misses(job: Job, misses_dir: Path, date: str) -> None:
    artifact = job.artifact
    slug = artifact.misses_slug if artifact else _slug(job.key)
    target = misses_dir / "misses" / slug
    target.mkdir(parents=True, exist_ok=True)
    finding = target / "FINDING.md"
    _upsert_section(finding, "freshness-auto-resolve", _miss_finding(job, date))
    job.applied.append(f"misses updated {finding.relative_to(misses_dir)}")
    index = misses_dir / "misses" / "README.md"
    if index.exists():
        text = index.read_text(encoding="utf-8")
        link = f"[`{slug}`]({slug}/FINDING.md)"
        if link not in text:
            row = f"| {link} | Freshness | Medium | Review `{job.decision}` decision from auto resolve. | `{job.command}` |\n"
            text = text.rstrip() + "\n" + row
            index.write_text(text)
            job.applied.append("misses index updated")


def _git_head(root: Path) -> str:
    out = subprocess.run(["git", "rev-parse", "HEAD"], cwd=root, capture_output=True, text=True, timeout=20)
    return out.stdout.strip() if out.returncode == 0 else "unknown"


def update_misses_provenance(misses_dir: Path, hits_dir: Path, date: str) -> None:
    path = misses_dir / "PROVENANCE.md"
    if not path.exists():
        return
    body = "\n".join([
        f"## Freshness Auto Resolve, {date}",
        "",
        f"- Radar commit at resolve time: `{_git_head(repo_root())}`",
        f"- Public artifact commit at resolve time: `{_git_head(hits_dir)}`",
        "- Resolver output is reviewable PR state, not a merge or publish action.",
        "",
    ])
    _upsert_section(path, "freshness-auto-resolve-provenance", body)


def apply_decisions(jobs: list[Job], *, hits_dir: Path, misses_dir: Path, date: str) -> None:
    for job in jobs:
        if job.decision in {"promote", "miss"}:
            apply_hits(job, hits_dir, date)
        if job.artifact and job.decision in DECISIONS:
            apply_misses(job, misses_dir, date)
    update_misses_provenance(misses_dir, hits_dir, date)


def report_dir(root: Path | None = None) -> Path:
    return (root or repo_root()) / "state" / "outbox" / "freshness-resolve"


def write_report(jobs: list[Job], *, date: str, root: Path | None = None) -> tuple[Path, Path]:
    out = report_dir(root)
    out.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema_version": 1,
        "date": date,
        "guardrail": freshness.GUARDRAIL,
        "summary": {decision: sum(1 for job in jobs if job.decision == decision) for decision in sorted(DECISIONS)},
        "jobs": [job_to_dict(job) for job in jobs],
    }
    json_path = out / f"{date}.json"
    md_path = out / f"{date}.md"
    json_path.write_text(json.dumps(payload, indent=2) + "\n")
    md_path.write_text(markdown_report(payload))
    return json_path, md_path


def job_to_dict(job: Job) -> dict:
    out = asdict(job)
    out["artifact"] = asdict(job.artifact) if job.artifact else None
    return out


def markdown_report(payload: dict) -> str:
    lines = [
        f"# Feature Radar Freshness Resolve, {payload['date']}",
        "",
        payload["guardrail"],
        "",
        "| Job | Decision | Reason | Command | Receipt |",
        "| --- | --- | --- | --- | --- |",
    ]
    for job in payload["jobs"]:
        artifact = job.get("artifact") or {}
        name = artifact.get("key") or job.get("key") or "unknown"
        lines.append(
            f"| {name} | {job['decision']} | {job['reason']} | `{job['command']}` | "
            f"`{job.get('receipt_path') or 'none'}` |"
        )
    lines += ["", "No merge, send, or direct publish is performed by this resolver.", ""]
    return "\n".join(lines)


def _changed(root: Path) -> bool:
    out = subprocess.run(["git", "status", "--porcelain"], cwd=root, capture_output=True, text=True, timeout=20)
    return bool(out.stdout.strip())


def open_pr(root: Path, *, branch: str, title: str, body: str) -> bool:
    if not _changed(root):
        return False
    subprocess.run(["git", "checkout", "-B", branch], cwd=root, check=True)
    subprocess.run(["git", "add", "-A"], cwd=root, check=True)
    subprocess.run(["git", "commit", "-m", title], cwd=root, check=True)
    subprocess.run(["git", "push", "--force-with-lease", "-u", "origin", branch], cwd=root, check=True)
    existing = subprocess.run(
        ["gh", "pr", "view", branch, "--json", "url", "-q", ".url"],
        cwd=root,
        capture_output=True,
        text=True,
    )
    if existing.returncode == 0 and existing.stdout.strip():
        subprocess.run(["gh", "pr", "edit", branch, "--title", title, "--body", body], cwd=root, check=True)
    else:
        subprocess.run(["gh", "pr", "create", "--title", title, "--body", body], cwd=root, check=True)
    return True


def maybe_open_prs(jobs: list[Job], *, hits_dir: Path, misses_dir: Path, date: str) -> None:
    body = markdown_report({
        "date": date,
        "guardrail": freshness.GUARDRAIL,
        "jobs": [job_to_dict(job) for job in jobs],
    })
    branch = f"freshness-resolve/{date}"
    title = f"Resolve freshness drift for {date}"
    for root in (repo_root(), hits_dir, misses_dir):
        open_pr(root, branch=branch, title=title, body=body)


def run(args: argparse.Namespace) -> tuple[list[Job], list[Path]]:
    run_date = args.date or today()
    report, written = load_or_create_report(args.report, write_report=args.write_report)
    jobs = build_jobs(report, limit=args.limit)
    jobs = classify_jobs(jobs, rerun=not args.no_rerun, max_spend_usd=args.max_spend_usd)
    if args.apply:
        apply_decisions(jobs, hits_dir=args.hits_dir, misses_dir=args.misses_dir, date=run_date)
    if args.write_report:
        written.extend(write_report(jobs, date=run_date))
    if args.open_pr:
        maybe_open_prs(jobs, hits_dir=args.hits_dir, misses_dir=args.misses_dir, date=run_date)
    return jobs, written


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Rerun and classify freshness drift.")
    parser.add_argument("--report", type=Path, help="existing freshness JSON report")
    parser.add_argument("--write-report", action="store_true")
    parser.add_argument("--dry-run", action="store_true", help="do not apply repo edits or open PRs")
    parser.add_argument("--apply", action="store_true", help="apply local hits/misses/radar edits")
    parser.add_argument("--open-pr", action="store_true", help="commit, push, and open PRs for changed repos")
    parser.add_argument("--hits-dir", type=Path, default=repo_root().parent / "claude-feature-hits")
    parser.add_argument("--misses-dir", type=Path, default=repo_root().parent / ("claude-feature-" + "misses"))
    parser.add_argument("--max-spend-usd", type=float, default=float(os.environ.get("FRESHNESS_MAX_SPEND_USD", "5.00")))
    parser.add_argument("--limit", type=int)
    parser.add_argument("--date", default="")
    parser.add_argument("--no-rerun", action="store_true", help="classify from existing receipts only")
    args = parser.parse_args(argv)
    if args.dry_run:
        args.apply = False
        args.open_pr = False
    if args.open_pr and not args.apply:
        raise SystemExit("--open-pr requires --apply")
    jobs, written = run(args)
    for path in written:
        try:
            rel = path.relative_to(repo_root())
        except ValueError:
            rel = path
        print(f"freshness resolve report: {rel}")
    for job in jobs:
        print(f"resolve {job.key}: {job.decision} - {job.reason}")
    return 1 if any(job.decision == "hold" for job in jobs) else 0


if __name__ == "__main__":
    raise SystemExit(main())
