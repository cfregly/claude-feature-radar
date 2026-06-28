"""No-key import gate for every public artifact module."""

from __future__ import annotations

import importlib
import os
import pathlib
import re
import sys


ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))
from artifact_manifest import active_slugs  # noqa: E402

ARTIFACTS = tuple(active_slugs())

DANGLING = [
    (re.compile(r"^\s*from\s+engine\.", re.MULTILINE), "dangling `from engine.`"),
    (re.compile(r"^\s*import\s+engine\b", re.MULTILINE), "dangling `import engine`"),
    (re.compile(r"^\s*from\s+common\.", re.MULTILINE), "non-dot `from common.`"),
    (re.compile(r"^\s*import\s+common\b", re.MULTILINE), "non-dot `import common`"),
    (re.compile(r"^import\s+(?:openai|google)\b", re.MULTILINE), "competitor SDK at module load"),
    (re.compile(r"^from\s+(?:openai|google)\b", re.MULTILINE), "competitor SDK at module load"),
]

BLOCKED = ("openai", "google", "google.genai")


class _Blocker:
    def find_spec(self, name, path=None, target=None):
        if any(name == b or name.startswith(b + ".") for b in BLOCKED):
            raise ImportError(f"blocked optional SDK at import: {name}")
        return None


def _static_scan() -> list[str]:
    bad = []
    for artifact in ARTIFACTS:
        for path in sorted((ROOT / artifact).rglob("*.py")):
            text = path.read_text(encoding="utf-8")
            for rx, why in DANGLING:
                if rx.search(text):
                    bad.append(f"{path.relative_to(ROOT)}: {why}")
    return bad


def _dynamic_imports() -> list[str]:
    sys.meta_path.insert(0, _Blocker())
    for mod in [m for m in list(sys.modules) if m.startswith(BLOCKED)]:
        del sys.modules[mod]
    os.environ.pop("ANTHROPIC_API_KEY", None)

    failed = []
    for artifact in ARTIFACTS:
        for path in sorted((ROOT / artifact).rglob("*.py")):
            rel = path.relative_to(ROOT).with_suffix("")
            mod = ".".join(rel.parts).removesuffix(".__init__")
            try:
                importlib.import_module(mod)
            except Exception as exc:  # noqa: BLE001
                failed.append(f"{mod}: {type(exc).__name__}: {exc}")
    return failed


def main() -> int:
    static = _static_scan()
    if static:
        print("no-key import gate: FAIL")
        print("\n".join("  - " + s for s in static))
        return 1
    failed = _dynamic_imports()
    if failed:
        print("no-key import gate: FAIL")
        print("\n".join("  - " + f for f in failed))
        return 1
    print("no-key import gate: clean (public artifact modules import without optional SDKs)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
