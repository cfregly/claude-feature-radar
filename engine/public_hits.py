"""Canonical public-hit bundle publisher.

The public ``claude-feature-hits`` repo is generated from the explicit manifest under
``engine/public_hits_bundle``. The publisher copies only files named in that manifest and removes
tracked target files that are no longer named there. Missing bundle files, a missing target checkout,
or a non-git target are hard failures.
"""

from __future__ import annotations

import json
import pathlib
import shutil
import subprocess
from dataclasses import dataclass


ROOT = pathlib.Path(__file__).resolve().parent.parent
BUNDLE_ROOT = ROOT / "engine" / "public_hits_bundle"
MANIFEST = BUNDLE_ROOT / "manifest.json"


class PublicHitsPublishError(RuntimeError):
    """Raised when the public-hit bundle cannot be published exactly."""


@dataclass(frozen=True)
class PublishResult:
    copied: tuple[str, ...]
    removed: tuple[str, ...]
    target: pathlib.Path


def load_manifest() -> dict:
    try:
        manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise PublicHitsPublishError(f"missing public hits manifest: {MANIFEST}") from exc
    if manifest.get("schema_version") != 1:
        raise PublicHitsPublishError("public hits manifest schema_version must be 1")
    files = manifest.get("files")
    if not isinstance(files, list) or not files:
        raise PublicHitsPublishError("public hits manifest must name at least one file")
    return manifest


def manifest_files() -> tuple[str, ...]:
    files = tuple(load_manifest()["files"])
    bad = [rel for rel in files if rel.startswith("/") or ".." in pathlib.PurePosixPath(rel).parts]
    if bad:
        raise PublicHitsPublishError(f"public hits manifest contains unsafe paths: {bad}")
    return files


def active_artifacts() -> tuple[str, ...]:
    artifacts = load_manifest().get("active_artifacts", [])
    if not isinstance(artifacts, list):
        raise PublicHitsPublishError("public hits manifest active_artifacts must be a list")
    return tuple(str(a) for a in artifacts)


def validate_bundle(files: tuple[str, ...] | None = None) -> None:
    missing = [rel for rel in (files or manifest_files()) if not (BUNDLE_ROOT / rel).is_file()]
    if missing:
        raise PublicHitsPublishError(f"public hits bundle is missing manifest files: {missing}")


def _git_tracked_files(target: pathlib.Path) -> set[str]:
    proc = subprocess.run(
        ["git", "ls-files"],
        cwd=target,
        capture_output=True,
        text=True,
        timeout=30,
    )
    if proc.returncode != 0:
        detail = proc.stderr.strip() or proc.stdout.strip() or "git ls-files failed"
        raise PublicHitsPublishError(f"target is not a readable git checkout: {target}: {detail}")
    return {line for line in proc.stdout.splitlines() if line}


def _remove_empty_dirs(target: pathlib.Path) -> None:
    for path in sorted((p for p in target.rglob("*") if p.is_dir()), key=lambda p: len(p.parts), reverse=True):
        if ".git" in path.parts:
            continue
        try:
            path.rmdir()
        except OSError:
            pass


def publish_all(target: pathlib.Path) -> PublishResult:
    target = pathlib.Path(target).resolve()
    if not target.exists():
        raise PublicHitsPublishError(f"public hits target does not exist: {target}")
    files = manifest_files()
    validate_bundle(files)

    owned = set(files)
    tracked = _git_tracked_files(target)
    removed: list[str] = []
    for rel in sorted(tracked - owned):
        path = target / rel
        if path.exists() or path.is_symlink():
            path.unlink()
            removed.append(rel)

    copied: list[str] = []
    for rel in files:
        src = BUNDLE_ROOT / rel
        dst = target / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
        copied.append(rel)

    _remove_empty_dirs(target)
    return PublishResult(copied=tuple(copied), removed=tuple(removed), target=target)


def copy_artifact(slug: str, target_dir: pathlib.Path) -> tuple[str, ...]:
    """Copy one active artifact directory from the public bundle into ``target_dir``.

    This is used by ``publish_brief`` for the old per-edge command. It still reads the central
    manifest and fails if the artifact is not active or any source file is missing.
    """
    if slug not in active_artifacts():
        raise PublicHitsPublishError(f"{slug!r} is not an active public artifact in the manifest")
    prefix = f"{slug}/"
    files = tuple(rel for rel in manifest_files() if rel.startswith(prefix))
    if not files:
        raise PublicHitsPublishError(f"public hits manifest has no files for artifact {slug!r}")
    validate_bundle(files)
    copied: list[str] = []
    for rel in files:
        src = BUNDLE_ROOT / rel
        dst = target_dir / rel.removeprefix(prefix)
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
        copied.append(str(dst.relative_to(target_dir)))
    return tuple(copied)
