"""No-key reconciliation gate for public artifact drift."""

from __future__ import annotations

import hashlib
import importlib
import pathlib
import subprocess
import sys


ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))
from artifact_manifest import active_slugs  # noqa: E402

GIF_ARTIFACTS = tuple(active_slugs())
COMMON_HELPER_ARTIFACTS = tuple(
    slug for slug in active_slugs()
    if slug in {"pdf_citations", "grounding_stack", "search_results", "task_budgets"}
)
COMMON_FILES = ("client.py", "models.py", "pricing.py", "compare_clients.py")


def _read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def _sha(path: pathlib.Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _is_tracked(rel: str) -> bool:
    out = subprocess.run(
        ["git", "ls-files", "--error-unmatch", rel],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=10,
    )
    return out.returncode == 0


def check_receipt_docs(fail: list[str]) -> None:
    for rel in ("docs/VERIFIED_FACTS.md", "docs/CITED_FACTS.md", "scripts/reconciliation_check.py"):
        path = ROOT / rel
        if not path.exists():
            fail.append(f"{rel}: missing tracked public audit file")
        elif not _is_tracked(rel):
            fail.append(f"{rel}: exists but is not tracked by Git")


def check_common_hashes(fail: list[str]) -> None:
    for filename in COMMON_FILES:
        hashes: dict[str, list[str]] = {}
        for artifact in COMMON_HELPER_ARTIFACTS:
            path = ROOT / artifact / "common" / filename
            if path.exists():
                hashes.setdefault(_sha(path), []).append(str(path.relative_to(ROOT)))
        if len(hashes) > 1:
            fail.append(f"common/{filename}: duplicated copies drifted: {hashes}")


def check_repo_root(fail: list[str]) -> None:
    for artifact in COMMON_HELPER_ARTIFACTS:
        mod_name = ".".join((artifact, "common", "client"))
        mod = importlib.import_module(mod_name)
        got = mod.repo_root()
        if got != ROOT:
            fail.append(f"{mod_name}.repo_root() returned {got}, expected {ROOT}")


def check_gif_contract(fail: list[str]) -> None:
    for artifact in GIF_ARTIFACTS:
        for rel in (f"{artifact}/README.md", f"{artifact}/demo.tape", f"{artifact}/sample.txt", f"{artifact}/demo.gif"):
            if not (ROOT / rel).exists():
                fail.append(f"{rel}: missing GIF contract file")
        readme = ROOT / artifact / "README.md"
        if readme.exists():
            link = f"https://raw.githubusercontent.com/cfregly/claude-feature-hits/main/{artifact}/demo.gif"
            if link not in readme.read_text(encoding="utf-8"):
                fail.append(f"{artifact}/README.md: missing raw GitHub demo.gif embed")


def check_public_copy(fail: list[str]) -> None:
    for path in ROOT.rglob("*.py"):
        rel = str(path.relative_to(ROOT))
        if rel.startswith(".venv/") or "__pycache__" in path.parts:
            continue
        if rel == "scripts/reconciliation_check.py":
            continue
        text = path.read_text(encoding="utf-8")
        if ("generator " + "bakes") in text or ("private both-" + "directions") in text:
            fail.append(f"{rel}: public source contains private generator wording")
        if "check_docs.py" in text:
            fail.append(f"{rel}: references nonexistent check_docs.py")
        if "python run.py" in text:
            fail.append(f"{rel}: direct script command can ImportError from repo root")


def check_registry_values(fail: list[str]) -> None:
    text = _read("programmatic_tool_calling/common/model_catalog.py")
    required = [
        'verified: str = "2026-06-24"',
        'id="gemini-3.5-flash"',
        'effort_levels=("none", "low", "medium", "high", "xhigh")',
        "input_per_mtok=1.50, output_per_mtok=9.0",
        "cache_read_per_mtok=0.15",
    ]
    for needle in required:
        if needle not in text:
            fail.append(f"programmatic_tool_calling/common/model_catalog.py: missing registry value {needle!r}")


def main() -> int:
    fail: list[str] = []
    check_receipt_docs(fail)
    check_gif_contract(fail)
    check_common_hashes(fail)
    check_repo_root(fail)
    check_public_copy(fail)
    check_registry_values(fail)
    if fail:
        print("reconciliation gate: FAIL")
        print("\n".join("  " + item for item in fail))
        return 1
    print("reconciliation gate: clean (public artifact contracts, receipts, and common helpers)")


if __name__ == "__main__":
    raise SystemExit(main())
