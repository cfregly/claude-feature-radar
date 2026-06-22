"""Cross-repo split gate: public wins stay public, misses stay private.

This is an operator-side check. It runs from the private engine checkout and inspects the sibling
public hits repo and private misses repo when they are present locally. CI for a single repo cannot
see all three checkouts, so absent siblings produce an explicit SKIPPED note rather than a false pass.
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


HITS_DIRNAME = "claude-feature-" + "hits"
MISSES_DIRNAME = "claude-feature-" + "misses"


def _run(cmd: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=30)


def _git_files(root: Path) -> list[str]:
    out = _run(["git", "ls-files"], root)
    if out.returncode != 0:
        raise RuntimeError(out.stderr.strip() or f"git ls-files failed in {root}")
    return [line for line in out.stdout.splitlines() if line]


def _read(root: Path, rel: str) -> str:
    p = root / rel
    return p.read_text(errors="ignore") if p.exists() else ""


def _contains_any(root: Path, needles: list[str], files: list[str]) -> bool:
    lows = [n.lower() for n in needles]
    for rel in files:
        text = (rel + "\n" + _read(root, rel)).lower()
        if any(n in text for n in lows):
            return True
    return False


def _check_surface_gate(fail: list[str]) -> None:
    out = _run([sys.executable, "scripts/check_surface.py"], ROOT)
    if out.returncode != 0:
        detail = (out.stdout + out.stderr).strip()
        fail.append("surface gate failed during split check:\n" + detail)


def _check_internal_kinds(hits: Path, misses: Path, fail: list[str]) -> None:
    from engine.coverage import _INTERNAL_KINDS

    expected = {
        "cost": ["edges/cost-model/README.md", "edges/cost-model/sample.txt", "edges/cost-model/PRODUCT_EMAIL.md"],
        "eval_quality": ["edges/eval-quality/README.md", "edges/eval-quality/sample.txt", "edges/eval-quality/PRODUCT_EMAIL.md"],
        "retention_resume": ["edges/retention-resume/README.md", "edges/retention-resume/sample.txt", "edges/retention-resume/PRODUCT_EMAIL.md"],
        "security_posture": ["edges/security-posture/FINDING.md"],
        "other": ["edges/parity-gated/README.md", "edges/parity-gated/sample.txt", "edges/parity-gated/PRODUCT_EMAIL.md"],
        "advisor_routing": ["edges/advisor-tool/FINDING.md"],
    }
    forbidden_public_markers = {
        "cost": ["cost-model", "cost_model"],
        "eval_quality": ["eval-quality", "eval_quality"],
        "retention_resume": ["retention-resume", "retention_resume"],
        "security_posture": ["security-posture", "security_posture"],
        "other": ["parity-gated", "parity_gated"],
        "advisor_routing": ["advisor-tool", "advisor_tool", "advisor-routing", "advisor_routing"],
    }
    missing_map = sorted(set(_INTERNAL_KINDS) - set(expected))
    if missing_map:
        fail.append(f"internal kind map missing entries: {missing_map}")

    hits_files = _git_files(hits)
    for kind in sorted(_INTERNAL_KINDS):
        for rel in expected.get(kind, []):
            if not (misses / rel).exists():
                fail.append(f"misses missing internal {kind} artifact: {rel}")
        markers = forbidden_public_markers.get(kind, sorted({kind, kind.replace("_", "-")}))
        if _contains_any(hits, markers, hits_files):
            fail.append(f"public hits contains internal kind marker {kind!r}")


def _misses_has_note(misses: Path, misses_files: list[str], edge_key: str, slug: str) -> bool:
    key_forms = sorted({edge_key, edge_key.replace("-", "_"), edge_key.replace("_", "-"), slug, slug.replace("_", "-")})
    likely_paths = [
        f"head_to_head/{slug}/README.md",
        f"edges/{edge_key}/PRODUCT_EMAIL.md",
        f"edges/{edge_key}/FINDING.md",
        "edges/parity-gated/PRODUCT_EMAIL.md",
        "briefs/2026-06-19-edge-vetting.md",
    ]
    if any((misses / rel).exists() and _contains_any(misses, key_forms, [rel]) for rel in likely_paths):
        return True
    return _contains_any(misses, key_forms, [rel for rel in misses_files if rel.startswith(("edges/", "head_to_head/", "briefs/"))])


def _check_publishable_plans(hits: Path, misses: Path, fail: list[str]) -> None:
    from engine.publish_brief import PLANS

    hits_files = set(_git_files(hits))
    misses_files = _git_files(misses)
    entrypoints = {
        "programmatic_tool_calling": "run_tokens.py",
        "citations": "cite.py",
    }
    for edge_key, plan in sorted(PLANS.items()):
        entrypoint = entrypoints.get(plan.slug, "run.py")
        required = [f"{plan.slug}/README.md", f"{plan.slug}/{entrypoint}", f"{plan.slug}/sample.txt"]
        for rel in required:
            if rel not in hits_files:
                fail.append(f"public hits missing publishable {edge_key!r} artifact: {rel}")
        if not _misses_has_note(misses, misses_files, edge_key, plan.slug):
            fail.append(f"misses has no both-directions/product note for publishable edge {edge_key!r}")


def _check_provenance(radar: Path, misses: Path, warn: list[str], fail: list[str]) -> None:
    text = _read(misses, "PROVENANCE.md")
    if not text:
        fail.append("misses missing committed PROVENANCE.md")
        return
    m = re.search(r"Source commit this snapshot reflects:\*\*\s*`?([0-9a-f]{7,40})`?", text)
    if not m:
        fail.append("misses PROVENANCE.md does not name a source commit")
        return
    stamped = m.group(1)
    out = _run(["git", "rev-parse", "HEAD"], radar)
    if out.returncode != 0:
        warn.append("could not read radar HEAD for provenance freshness")
        return
    head = out.stdout.strip()
    if not head.startswith(stamped):
        warn.append(f"misses provenance is stamped {stamped}, radar HEAD is {head[:12]}")


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Check the local public-wins/private-misses split.")
    p.add_argument("--hits-root", type=Path, default=ROOT.parent / HITS_DIRNAME)
    p.add_argument("--misses-root", type=Path, default=ROOT.parent / MISSES_DIRNAME)
    args = p.parse_args(argv)

    fail: list[str] = []
    warn: list[str] = []
    missing = [str(path) for path in (args.hits_root, args.misses_root) if not path.exists()]
    if missing:
        print("split gate: SKIPPED, sibling checkout absent: " + ", ".join(missing))
        return 0

    _check_surface_gate(fail)
    _check_internal_kinds(args.hits_root, args.misses_root, fail)
    _check_publishable_plans(args.hits_root, args.misses_root, fail)
    _check_provenance(ROOT, args.misses_root, warn, fail)

    for w in warn:
        print(f"split gate: WARN {w}")
    if fail:
        print("split gate: FAIL")
        for item in fail:
            print(f"  - {item}")
        return 1
    print("split gate: clean (public wins, private misses, provenance checked)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
