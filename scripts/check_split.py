"""Cross-repo split gate: public wins stay public, misses stay private.

This is an operator-side check. It runs from the private engine checkout and inspects the sibling
public hits repo and private misses repo when they are present locally. CI for a single repo cannot
see all three checkouts, so absent siblings produce an explicit SKIPPED note rather than a false pass.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


HITS_DIRNAME = "claude-feature-" + "hits"
MISSES_DIRNAME = "claude-feature-" + "misses"
COMBINATION_PUBLIC_ARTIFACTS = {
    "combo-1": (
        "ptc_cache_context",
        (
            "ptc_cache_context/README.md",
            "ptc_cache_context/run.py",
            "ptc_cache_context/sample.txt",
            "ptc_cache_context/receipt.json",
        ),
    ),
}


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


def _read_json(root: Path, rel: str) -> dict:
    text = _read(root, rel)
    if not text:
        return {}
    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"{rel} is not valid JSON: {exc}") from exc


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
        "cost": ["misses/cost-model/BRIEF.md", "misses/cost-model/sample.txt", "misses/cost-model/PRODUCT_NOTE.md"],
        "eval_quality": ["misses/eval-quality/BRIEF.md", "misses/eval-quality/sample.txt", "misses/eval-quality/PRODUCT_NOTE.md"],
        "retention_resume": [
            "misses/retention-resume/BRIEF.md",
            "misses/retention-resume/sample.txt",
            "misses/retention-resume/PRODUCT_NOTE.md",
        ],
        "security_posture": ["misses/security-posture/BRIEF.md", "misses/security-posture/FINDING.md"],
        "other": ["misses/parity-gated/BRIEF.md", "misses/parity-gated/sample.txt", "misses/parity-gated/PRODUCT_NOTE.md"],
        "advisor_routing": ["misses/advisor-tool/BRIEF.md", "misses/advisor-tool/FINDING.md"],
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
        f"misses/{edge_key}/PRODUCT_NOTE.md",
        f"misses/{edge_key}/FINDING.md",
        f"misses/{edge_key}/BRIEF.md",
        "misses/parity-gated/PRODUCT_NOTE.md",
        "archive/briefs/2026-06-19-edge-vetting.md",
    ]
    if any((misses / rel).exists() and _contains_any(misses, key_forms, [rel]) for rel in likely_paths):
        return True
    return _contains_any(
        misses,
        key_forms,
        [rel for rel in misses_files if rel.startswith(("misses/", "head_to_head/", "archive/briefs/"))],
    )


def _check_public_plans(hits: Path, misses: Path, fail: list[str]) -> None:
    from engine import adversarial
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
        value_gate = adversarial.adversarial_status(edge_key, root=ROOT)
        if value_gate.ok:
            for rel in required:
                if rel not in hits_files:
                    fail.append(f"public hits missing promoted {edge_key!r} artifact: {rel}")
        else:
            for rel in required:
                if rel in hits_files:
                    fail.append(f"public hits still tracks killed {edge_key!r} artifact: {rel}")
        if not _misses_has_note(misses, misses_files, edge_key, plan.slug):
            fail.append(f"misses has no both-directions/product note for edge {edge_key!r}")


def _check_surviving_combinations(hits: Path, fail: list[str]) -> None:
    combos = _read_json(ROOT, "landscape/combinations.json").get("combinations", [])
    hits_files = set(_git_files(hits))
    for combo in combos:
        combo_id = str(combo.get("id", ""))
        mapped = COMBINATION_PUBLIC_ARTIFACTS.get(combo_id)
        verdict = combo.get("skeptic_verdict")
        if verdict == "SURVIVES":
            if not mapped:
                fail.append(f"surviving combination {combo_id!r} has no public artifact mapping")
                continue
            _, required = mapped
            for rel in required:
                if rel not in hits_files:
                    fail.append(f"public hits missing surviving combination {combo_id!r} artifact: {rel}")
        elif mapped:
            slug, required = mapped
            for rel in required:
                if rel in hits_files:
                    fail.append(f"public hits still tracks killed combination {combo_id!r} artifact: {slug}/")
                    break


def _head(root: Path) -> str | None:
    out = _run(["git", "rev-parse", "HEAD"], root)
    if out.returncode != 0:
        return None
    return out.stdout.strip()


def _check_provenance(radar: Path, hits: Path, misses: Path, warn: list[str], fail: list[str]) -> None:
    text = _read(misses, "PROVENANCE.md")
    if not text:
        fail.append("misses missing committed PROVENANCE.md")
        return
    m = re.search(r"Source commit this snapshot reflects:\*\*\s*`?([0-9a-f]{7,40})`?", text)
    if not m:
        fail.append("misses PROVENANCE.md does not name a source commit")
        return
    stamped = m.group(1)
    head = _head(radar)
    if not head:
        warn.append("could not read radar HEAD for provenance freshness")
    elif not head.startswith(stamped):
        fail.append(f"misses provenance source stamp {stamped} does not match radar HEAD {head[:12]}")

    m = re.search(r"Public artifact commit checked with it:\*\*\s*`?([0-9a-f]{7,40})`?", text)
    if not m:
        fail.append("misses PROVENANCE.md does not name a public artifact commit")
        return
    stamped = m.group(1)
    head = _head(hits)
    if not head:
        warn.append("could not read hits HEAD for provenance freshness")
    elif not head.startswith(stamped):
        fail.append(f"misses provenance public stamp {stamped} does not match hits HEAD {head[:12]}")


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
    _check_public_plans(args.hits_root, args.misses_root, fail)
    _check_surviving_combinations(args.hits_root, fail)
    _check_provenance(ROOT, args.hits_root, args.misses_root, warn, fail)

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
