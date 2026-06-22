"""Doc-correctness gate: the README, CLAUDE.md, SKILL.md, and the edge READMEs must not drift from the
code. Exits nonzero on any mismatch. Stdlib only, runs offline with no key.

The rule it enforces: a doc must not advertise a command, a model, or a runnable receipt the code
does not actually produce. It checks five kinds of drift:

  1. Every `make <target>` named in a doc is a real Makefile target.
  2. Every `run.py <cmd>` named in a doc is a real run.py subcommand.
  3. Every Claude model id named in a doc is one common/models.py defines.
  4. A demonstrator's edge README names the beta header or tool id its demo.py actually sends, so a
     doc cannot promise a programmatic-tool-calling or code-execution receipt the code does not run.
  5. Generator brief assets do not contain stale copy-paste commands or SDK call shapes that would be
     republished into the public repo.

This is the offline docs-vs-code half. The live-claim re-prover that re-checks a price or a 400
against a real API call is scripts/verify_live.py (a paid pre-flight, not a CI step), so the
load-bearing facts get re-proven against a real call.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

errors: list[str] = []


def _read(rel: str) -> str:
    p = ROOT / rel
    return p.read_text() if p.exists() else ""


# The real surfaces, read off the code.
make_targets = set(re.findall(r"^([a-z][a-z0-9-]*):", _read("Makefile"), re.MULTILINE))
# run.py dispatches on `cmd == "x"` and `cmd in ("x", "y")`. Read the literals out of main()'s body so
# both forms are captured and a stray string elsewhere in the file is not.
_run_src = _read("run.py")
_main = re.search(r"def main\(\).*", _run_src, re.DOTALL)
run_commands = set(re.findall(r'cmd (?:==|in) [(\s"a-z0-9,)-]*', _main.group(0))) if _main else set()
run_commands = set(re.findall(r'"([a-z][a-z0-9-]*)"', " ".join(run_commands)))
model_ids = set(re.findall(r"claude-[a-z0-9.-]+", _read("common/models.py")))

DOCS = ["README.md", "CLAUDE.md", "SKILL.md"]
DOCS += [str(p.relative_to(ROOT)) for p in sorted((ROOT / "edges").glob("*/README.md"))]
BRIEF_ASSET_FILES = [
    str(p.relative_to(ROOT))
    for p in sorted((ROOT / "engine" / "brief_assets").glob("*/*"))
    if p.suffix in {".md", ".py", ".txt"}
]

for name in DOCS:
    doc = _read(name)
    if not doc:
        continue
    # 1. Every make target named as a command (inside a `backtick` code span) is real. Bare prose
    # like "make the workload explicit" is not a command, so only backticked forms are checked.
    for m in re.finditer(r"`make ([a-z][a-z0-9-]*)`", doc):
        target = m.group(1)
        if target not in make_targets:
            errors.append(f"{name} references an unknown Makefile target: make {target}")
    # 2. Every run.py command named in prose is real.
    for m in re.finditer(r"\brun\.py ([a-z][a-z0-9-]*)\b", doc):
        if m.group(1) not in run_commands:
            errors.append(f"{name} references an unknown command: run.py {m.group(1)}")
    # 3. Every Claude model id named in prose is one models.py defines.
    for mid in set(re.findall(r"claude-[a-z0-9]+-[0-9]+(?:-[0-9]+)?", doc)):
        # Match against the registry on the id stem, so a doc may name "claude-opus-4-8" or the dated
        # "claude-haiku-4-5-20251001" form and both resolve to a real row.
        if not any(mid == known or known.startswith(mid) for known in model_ids):
            errors.append(f"{name} names a Claude model id not in common/models.py: {mid}")

# 4. A built demonstrator's edge README must name the beta header or tool id its demo.py sends, so the
# doc cannot advertise a receipt the code does not run. Each tuple is (edge dir, marker the demo sends).
DEMO_MARKERS = [
    ("programmatic-tool-calling", "code_execution_20260120"),
    ("programmatic-tool-calling", "allowed_callers"),
    ("citations", "citations"),
    ("context-editing", "context_management"),
]
for edge_dir, marker in DEMO_MARKERS:
    demo = _read(f"edges/{edge_dir}/demo.py")
    readme = _read(f"edges/{edge_dir}/README.md")
    if not demo:
        continue
    if marker not in demo:
        errors.append(f"edges/{edge_dir}/demo.py no longer sends '{marker}', the README advertises it")
    if readme and marker not in readme:
        errors.append(f"edges/{edge_dir}/README.md does not name '{marker}', which its demo.py sends")

# 5. Published-brief generator assets must not carry stale copy-paste code that the public repo would
# inherit on the next publish-brief run. These checks are intentionally asset-specific: public brief
# commands use underscore Make targets in claude-feature-hits, while this private radar repo uses
# hyphenated internal targets.
for name in BRIEF_ASSET_FILES:
    text = _read(name)
    if "python cache_diagnostics/run.py --check" in text:
        errors.append(f"{name} uses direct script execution for cache_diagnostics; use `.venv/bin/python -m cache_diagnostics.run --check`")

exact_assets = [
    "engine/brief_assets/exact_ledger/README.md",
    "engine/brief_assets/exact_ledger/email.md",
    "engine/brief_assets/exact_ledger/run.py",
    "engine/brief_assets/exact_ledger/sample.txt",
]
for name in exact_assets:
    text = _read(name)
    if "client.beta.messages.create" not in text:
        errors.append(f"{name} does not use the context-editing beta helper call")
    if "betas=[" not in text:
        errors.append(f"{name} does not set the context-management beta flag in the copyable path")
    if "context_management=" not in text:
        errors.append(f"{name} does not pass context_management in the copyable path")
    if name.endswith(("run.py", "sample.txt")) and ("extra_body" in text or "extra_headers" in text):
        errors.append(f"{name} still uses raw extra_body/extra_headers for context editing")
    if name.endswith((".md", ".txt")) and "resp = client.messages.create" in text:
        errors.append(f"{name} uses client.messages.create instead of client.beta.messages.create")

search_asset = _read("engine/brief_assets/search_results/run.py")
if "est cost $0.05" in search_asset:
    errors.append("engine/brief_assets/search_results/run.py still prints the three-vendor estimate for the Claude-only run")
if "est cost $0.01" not in search_asset:
    errors.append("engine/brief_assets/search_results/run.py is missing the Claude-only $0.01 estimate")

if errors:
    print("check_docs FAIL")
    for e in errors:
        print("  -", e)
    sys.exit(1)
print(f"check_docs OK ({len([d for d in DOCS if _read(d)])} docs and {len(BRIEF_ASSET_FILES)} brief assets checked against the code)")
