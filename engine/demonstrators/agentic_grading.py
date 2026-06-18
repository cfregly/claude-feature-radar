"""agentic_grading: does the model resolve a real repo-repair slice when it can iterate against the
real tests? The edge is the agentic loop, not the single shot.

Ported from ship-on-claude edges/agentic-coding (swebench_grade.py + swebench_solve.py +
swebench_tasks.py) and refactored behind the engine's Demonstrator interface. The claim, grounded in
the public SWE-bench Verified leaderboard and reproduced here on a curated pure-Python slice: when a
model can propose a patch, see the real test failure, and try again, Claude separates from the field
that ties single-shot.

WHAT IT MEASURES, honestly. A small curated SWE-bench Verified slice (flask, pylint), each instance
graded LOCALLY with NO Docker. The official harness runs each instance in a Docker image, but that
image is just a per-instance recipe the `swebench` package exposes as plain data: a Python version, a
pinned package set, an editable repo install, a test patch, and a test command. We reproduce that
recipe in a local `uv` virtualenv, apply the model's patch and the gold test patch, run the same
tests, and score with the harness's OWN parser, so the resolved verdict is the same code the public
leaderboard uses, run on your machine for free. `validate()` first proves the grader by resolving every
human GOLD patch, so a fork never gets a false negative from an env we reproduced wrong.

THE SYMMETRIC LOOP (the fix). The agentic loop is IDENTICAL for every provider: plain multi-turn text
completions, no provider-specific tool API, the SAME accumulated history forwarded to Claude, OpenAI,
AND Gemini on every round (the original ship-on-claude loop sent the full history only to Claude, a
confound this port removes by routing every arm through common.runner.call() with the whole messages
list). Each model gets the issue, the source, and on a miss the exact salient test failure, and each
gets the same number of rounds and the same effort label. So a difference in K/N is a difference in the
model's ability to use feedback, not an artifact of who saw more context.

GROUNDING. The leaderboard claim and the model ids trace to the live docs and a real call, the same as
every number in this repo. The K/N below is measured on your key, never quoted from memory. The slice
is small and pure-Python by design, so this is a within-slice receipt that corroborates the public
leaderboard, not a full 500-instance reproduction. Adaptive thinking is on for Claude and disclosed.

DEPENDENCIES. `datasets` and `swebench` are OPTIONAL comparison deps (requirements-compare.txt), pulled
in lazily inside this demonstrator so the one-dependency core never imports them. `uv` must be on PATH
for the local grader. The competitor arms run only when their keys are set.

SECURITY. The grader runs the model's patch against real tests in a local uv venv (no Docker, the same
posture as the official LiveCodeBench runner). Run it on a machine you do not mind exposing to the
patched repo's test suite.
"""

from __future__ import annotations

import os
import pathlib
import re
import shutil
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass
from functools import lru_cache

# repo root on the path, for common/ and engine/ when run as a script.
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))

from engine.demonstrators.base import Arm, BaseDemonstrator, CostEstimate, Verdict
from engine.demonstrators.registry import register
from engine.demonstrators.shared import platform

# --------------------------------------------------------------------------- the curated slice
#
# Pure-Python repos whose tests run offline and deterministically. CURATED_REPOS is the candidate pool
# validate() scans; VALIDATED is the shipped slice whose GOLD patch resolves locally, proven by
# `make validate`. Two of the four are the hardest pylint issues (rated 1-4 hours to fix by hand),
# which is where models actually separate. Requests is excluded: its suite makes live HTTP calls
# (httpbin) a local offline grader cannot reproduce, exactly the long tail Docker isolates.

CURATED_REPOS = {"pallets/flask", "pylint-dev/pylint"}

VALIDATED: list[str] = [
    "pallets__flask-5014",       # <15 min
    "pylint-dev__pylint-4970",   # <15 min
    "pylint-dev__pylint-4551",   # 1-4 hours
    "pylint-dev__pylint-8898",   # 1-4 hours
]

CACHE = pathlib.Path(os.environ.get("SWEBENCH_CACHE", tempfile.gettempdir())) / "swebench_repos"

# The provider-blind model set for the agentic head-to-head. The competitor keys gate which actually
# run; an absent key yields ran=False, never a faked row. Claude opus is the anchor (the slice is where
# the agentic loop separates it), sonnet is the balanced Claude tier, and the OpenAI/Gemini frontier
# and balanced tiers are the competitor arms.
CLAUDE_MODELS = ("opus", "sonnet")
COMPETITOR_MODELS = ("gpt-top", "gpt-mid", "gem-pro", "gem-flash")
DEFAULT_MODELS = CLAUDE_MODELS + COMPETITOR_MODELS

ROUNDS = int(os.environ.get("SOLVE_ROUNDS", "3"))
EFFORT = os.environ.get("SOLVE_EFFORT", "medium")
MAX_TOKENS = int(os.environ.get("SOLVE_MAX_TOKENS", "16000"))
TEST_TIMEOUT = int(os.environ.get("SOLVE_TEST_TIMEOUT", "300"))

PROMPT = (
    "You are fixing a real GitHub issue. Read the issue and the current source of the files that "
    "need changing, then return a fix.\n\n## Issue\n{issue}\n\n## Current source\n{ctx}\n\n"
    "Return ONLY a git unified diff that applies cleanly from the repository root, inside one ```diff "
    "code block. Use the exact paths shown (a/<path> and b/<path>) and edit only those files. The "
    "hunk headers must be correct. No prose before or after the code block."
)

_DIFF = re.compile(r"```(?:diff|patch)?\s*\n(.*?)```", re.DOTALL)


# --------------------------------------------------------------------------- dataset + oracle context

@dataclass
class Instance:
    instance_id: str
    repo: str
    base_commit: str
    problem_statement: str
    files: list  # the files the gold patch touches, the oracle context


def _gold_files(patch: str) -> list:
    return sorted(set(re.findall(r"^\+\+\+ b/(.+)$", patch, re.M)))


@lru_cache(maxsize=1)
def _load_dataset():
    """Pull SWE-bench Verified from HuggingFace at run time. datasets is an OPTIONAL comparison dep,
    imported here lazily so the one-dependency core never needs it (we never vendor the dataset)."""
    from datasets import load_dataset  # optional dep, lazy
    return load_dataset("princeton-nlp/SWE-bench_Verified", split="test")


def load_instances(limit: int | None = None, *, candidates: bool = False) -> list:
    """The shipped VALIDATED slice as Instance objects. candidates=True returns the whole curated pool
    (what validate() scans before the slice is pinned)."""
    ds = _load_dataset()
    keep = (lambda r: r["repo"] in CURATED_REPOS) if candidates else (lambda r: r["instance_id"] in VALIDATED)
    out = [
        Instance(r["instance_id"], r["repo"], r["base_commit"], r["problem_statement"], _gold_files(r["patch"]))
        for r in ds if keep(r)
    ]
    out.sort(key=lambda i: i.instance_id)
    return out[:limit] if limit else out


def _records(limit: int | None = None) -> dict:
    """The raw dataset rows (with patch + test_patch + version), keyed by instance id, for the grader."""
    ids = {i.instance_id for i in load_instances(limit)}
    return {r["instance_id"]: r for r in _load_dataset() if r["instance_id"] in ids}


def _repo_dir(repo: str) -> pathlib.Path:
    d = CACHE / repo.replace("/", "__")
    if not (d / ".git").exists():
        CACHE.mkdir(parents=True, exist_ok=True)
        subprocess.run(["git", "clone", "--quiet", f"https://github.com/{repo}", str(d)], check=True)
    return d


def base_file_lines(inst: Instance, path: str):
    """The lines of one file at the base commit, read from the on-disk clone with `git show`. No
    checkout, no Docker."""
    d = _repo_dir(inst.repo)
    r = subprocess.run(["git", "-C", str(d), "show", f"{inst.base_commit}:{path}"],
                       capture_output=True, text=True)
    return r.stdout.splitlines() if r.returncode == 0 else None


def oracle_context(inst: Instance, max_chars: int = 40000) -> str:
    """The content of the files the fix touches, read at the base commit. The same oracle context for
    every provider, so the comparison is fair."""
    parts = []
    for path in inst.files:
        lines = base_file_lines(inst, path)
        if lines is not None:
            parts.append(f"=== {path} ===\n" + "\n".join(lines))
    return "\n\n".join(parts)[:max_chars]


# --------------------------------------------------------------------------- diff hygiene (repair_patch)

def extract_patch(text: str) -> str:
    for block in _DIFF.findall(text or ""):
        if "diff --git" in block or block.lstrip().startswith("--- "):
            return block.strip() + "\n"
    i = (text or "").find("diff --git")
    return (text[i:].strip() + "\n") if i >= 0 else ""


def _split_hunk(body: list):
    before, after = [], []
    for b in body:
        if not b:
            before.append(""), after.append("")
        elif b[0] == "-":
            before.append(b[1:])
        elif b[0] == "+":
            after.append(b[1:])
        elif b[0] == " ":
            before.append(b[1:]), after.append(b[1:])
        else:
            before.append(b), after.append(b)
    return before, after


def _locate(target: list, before: list) -> int:
    n = len(before)
    if not n or n > len(target):
        return -1
    for s in range(len(target) - n + 1):
        if target[s:s + n] == before:
            return s
    stripped = [x.strip() for x in before]
    for s in range(len(target) - n + 1):
        if [x.strip() for x in target[s:s + n]] == stripped:
            return s
    return -1


def repair_patch(patch: str, get_lines) -> str:
    """Recompute each hunk's `@@ -a,b +c,d @@` header from the target file. Models reliably produce the
    right context and added/removed lines but often botch the hunk arithmetic, so a correctly-reasoned
    edit is relocated against the base file and given a correct header instead of being thrown out.
    Provider-agnostic diff hygiene applied identically to every arm."""
    lines = patch.splitlines()
    out, target, i = [], None, 0
    while i < len(lines):
        ln = lines[i]
        if ln.startswith("--- ") and i + 1 < len(lines) and lines[i + 1].startswith("+++ "):
            path = re.sub(r"^[ab]/", "", lines[i + 1][4:].strip())
            target = get_lines(path)
            out.append(ln), out.append(lines[i + 1])
            i += 2
            continue
        if ln.startswith("@@"):
            j = i + 1
            body = []
            while j < len(lines) and not (
                lines[j].startswith("@@") or lines[j].startswith("--- ") or lines[j].startswith("diff --git")
            ):
                body.append(lines[j])
                j += 1
            before, after = _split_hunk(body)
            start = _locate(target, before) if target is not None else -1
            if start < 0:
                out.append(ln), out.extend(body)
            else:
                out.append(f"@@ -{start + 1},{len(before)} +{start + 1},{len(after)} @@")
                out.extend(body)
            i = j
            continue
        out.append(ln)
        i += 1
    text = "\n".join(out)
    return text if text.endswith("\n") else text + "\n"


# --------------------------------------------------------------------------- the no-Docker grader

def _run(cmd, cwd=None, env=None, text_input=None, timeout=1800):
    return subprocess.run(cmd, cwd=cwd, env=env, input=text_input,
                          capture_output=True, text=True, timeout=timeout)


def _apply_patch(work: pathlib.Path, patch: str) -> bool:
    if not patch.strip():
        return False
    for cmd in (["git", "apply", "-v"], ["patch", "--batch", "--fuzz=5", "-p1"]):
        if _run(cmd, cwd=work, text_input=patch).returncode == 0:
            return True
    return False


def _build_env(instance, work: pathlib.Path, venv: pathlib.Path) -> str:
    """Reproduce the instance's pinned env in a uv venv. uv supplies the exact interpreter; the installs
    run through the venv's own pip in the harness's order (pinned requirements, then spec overrides,
    then the repo), because pip changes an already-installed dependency only when it must, the behavior
    the official harness relies on (uv's resolver would re-derive and break a pin)."""
    from swebench.harness.constants import MAP_REPO_VERSION_TO_SPECS  # optional dep, lazy
    from swebench.harness.test_spec.python import get_requirements

    spec = MAP_REPO_VERSION_TO_SPECS[instance["repo"]][instance["version"]]
    r = _run(["uv", "venv", "--seed", "--python", spec["python"], str(venv)])
    if r.returncode != 0:
        raise RuntimeError(f"uv venv failed:\n{r.stderr}")
    bindir = venv / "bin"
    py = bindir / "python"

    def pip(*args):
        return _run([str(py), "-m", "pip", "install", *args], cwd=work)

    def must(res, what):
        if res.returncode != 0:
            raise RuntimeError(f"{what} failed:\n{res.stdout[-1500:]}\n{res.stderr[-1500:]}")

    packages = spec.get("packages", "")
    if packages == "requirements.txt":
        lockfile = work.parent / "requirements.txt"
        lockfile.write_text(get_requirements(instance))
        must(pip("-r", str(lockfile)), "pip install -r requirements")
    elif packages == "environment.yml":
        raise RuntimeError("environment.yml instances need conda; not in this pure-Python slice")
    elif packages:
        must(pip(*packages.split()), "pip install packages")

    if spec.get("pip_packages"):
        must(pip(*spec["pip_packages"]), "pip install pinned overrides")
    install_args = ["-e", "."] if "-e" in spec.get("install", "") else ["."]
    must(pip(*install_args), f"pip install {' '.join(install_args)}")
    return str(bindir)


def prepare_instance(instance, tmp: pathlib.Path):
    """Clone the repo at the base commit and build its pinned env ONCE. The expensive env build happens
    here so an iterating solver pays it a single time and then scores many candidate patches against the
    same prepared checkout (the prepare-once / score-many split)."""
    from swebench.harness.constants import MAP_REPO_VERSION_TO_SPECS
    from swebench.harness.test_spec.python import get_test_directives
    from swebench.harness.test_spec.test_spec import make_test_spec

    work = tmp / "testbed"
    src = _repo_dir(instance["repo"])
    if _run(["git", "clone", "--quiet", "--no-hardlinks", str(src), str(work)]).returncode != 0:
        raise RuntimeError("git clone from cache failed")
    _run(["git", "-C", str(work), "checkout", "--quiet", instance["base_commit"]])
    bindir = _build_env(instance, work, tmp / "venv")
    test_spec = make_test_spec(instance)
    directives = get_test_directives(instance)
    test_cmd = MAP_REPO_VERSION_TO_SPECS[instance["repo"]][instance["version"]]["test_cmd"]
    if isinstance(test_cmd, list):
        test_cmd = test_cmd[-1]
    return work, bindir, test_spec, directives, test_cmd


def apply_and_score(instance, work, bindir, test_spec, directives, test_cmd, model_patch,
                    test_timeout: int = 600) -> dict:
    """Score one candidate patch against an already-prepared checkout. Reverts any prior attempt first,
    so it is safe to call repeatedly in a solve loop. Returns the verdict plus the raw test output (so
    the loop can feed the failures back to the model)."""
    from swebench.harness.constants import (
        APPLY_PATCH_FAIL, END_TEST_OUTPUT, FAIL_TO_PASS, PASS_TO_PASS,
        START_TEST_OUTPUT, TESTS_TIMEOUT, ResolvedStatus,
    )
    from swebench.harness.grading import (
        get_eval_tests_report, get_logs_eval, get_resolution_status,
    )

    _run(["git", "-C", str(work), "checkout", "--quiet", "--", "."])
    applied = _apply_patch(work, model_patch)
    log_fp = work.parent / "test.log"
    raw = ""
    if not applied:
        log_fp.write_text(APPLY_PATCH_FAIL + "\n")
    else:
        _run(["git", "-C", str(work), "checkout", instance["base_commit"], *directives])
        _apply_patch(work, instance["test_patch"])
        parts = test_cmd.split()
        pytest_bin = pathlib.Path(bindir) / parts[0]
        cmd = [str(pytest_bin), *parts[1:], *directives]
        env = {**os.environ, "PATH": f"{bindir}:{os.environ['PATH']}"}
        try:
            run = _run(cmd, cwd=work, env=env, timeout=test_timeout)
            raw = f"{run.stdout}\n{run.stderr}"
        except subprocess.TimeoutExpired:
            raw = TESTS_TIMEOUT
        log_fp.write_text(f"{START_TEST_OUTPUT}\n{raw}\n{END_TEST_OUTPUT}\n")

    status_map, _ = get_logs_eval(test_spec, str(log_fp))
    gold = {FAIL_TO_PASS: test_spec.FAIL_TO_PASS, PASS_TO_PASS: test_spec.PASS_TO_PASS}
    report = get_eval_tests_report(status_map, gold)
    resolved = get_resolution_status(report) == ResolvedStatus.FULL.value
    f2p, p2p = report[FAIL_TO_PASS], report[PASS_TO_PASS]
    return {
        "applied": applied, "resolved": resolved,
        "f2p_pass": len(f2p["success"]), "f2p_total": len(f2p["success"]) + len(f2p["failure"]),
        "p2p_pass": len(p2p["success"]), "p2p_total": len(p2p["success"]) + len(p2p["failure"]),
        "raw_output": raw,
    }


def grade_one(instance, model_patch: str, test_timeout: int = 600) -> dict:
    """Build the env, apply the patch, run the tests, score with the official parser. The one-shot
    convenience that prepares and scores in one call."""
    tmp = pathlib.Path(tempfile.mkdtemp(prefix="swegrade_"))
    try:
        handles = prepare_instance(instance, tmp)
        return apply_and_score(instance, *handles, model_patch, test_timeout=test_timeout)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def validate(test_timeout: int | None = None) -> list:
    """Self-test: grade every curated instance's GOLD (human) patch. Each must resolve, or the env did
    not reproduce the instance faithfully. This is what makes the no-Docker claim defensible: we ship
    only the instances that pass this check, so a fork never sees a false negative."""
    if shutil.which("uv") is None:
        raise SystemExit("uv is required for the local grader (https://docs.astral.sh/uv). Install it and retry.")
    timeout = test_timeout if test_timeout is not None else int(os.environ.get("SWEBENCH_TEST_TIMEOUT", "600"))
    print("  Proving the local grader: every human GOLD patch must resolve in a local uv venv (no Docker).\n")
    rows = _records()
    insts = {r["instance_id"]: r for r in rows.values()}
    good = []
    for iid in sorted(insts):
        inst = insts[iid]
        try:
            r = grade_one(inst, inst["patch"], test_timeout=timeout)
            tag = "reproduces" if r["resolved"] else "DOES NOT reproduce"
            if r["resolved"]:
                good.append(iid)
            print(f"    {tag:<19} {iid:<28} {inst.get('difficulty', '')}")
        except Exception as e:  # noqa: BLE001
            print(f"    {'ENV ERROR':<19} {iid:<28} {type(e).__name__}: {str(e)[:60]}")
    print(f"\n  {len(good)}/{len(insts)} instances reproduce locally (gold patch resolves). "
          f"These are the slice this demonstrator grades.\n")
    return good


# --------------------------------------------------------------------------- the symmetric agentic loop

def _salient(raw: str, f2p_names: list) -> str:
    """Pull the failure-relevant lines out of a big pytest log so the feedback stays focused. The same
    compression for every provider."""
    keep = [
        ln for ln in (raw or "").splitlines()
        if any(k in ln for k in ("FAILED", "ERROR", "Error", "assert", "Exception", "passed", "failed"))
        or any(n in ln for n in f2p_names)
    ]
    text = "\n".join(keep) if keep else (raw or "")
    return text[-3500:]


def _feedback(record, result) -> str:
    import json
    if not result["applied"]:
        return (
            "Your patch did not apply to the repository. The context lines must match the current "
            "source exactly and the file paths must be the ones shown. Return a corrected git unified "
            "diff in one ```diff block, editing only the source files."
        )
    f2p = json.loads(record["FAIL_TO_PASS"]) if isinstance(record["FAIL_TO_PASS"], str) else record["FAIL_TO_PASS"]
    return (
        "Your patch applied but did not resolve the issue. The test that must pass is: "
        f"{', '.join(f2p)}.\nThe test run reported:\n\n{_salient(result['raw_output'], f2p)}\n\n"
        "Fix the patch. Return ONLY the corrected git unified diff in one ```diff block, editing only "
        "the source files. Make the failing test above pass while keeping the others passing."
    )


def solve_one(record, inst, model_key, client, *, rounds=ROUNDS, effort=EFFORT,
              max_tokens=MAX_TOKENS, test_timeout=TEST_TIMEOUT) -> dict:
    """The propose-test-feedback loop for one instance and one model.

    SYMMETRIC by construction: the loop accumulates ONE messages list (user issue, assistant patch,
    user feedback, ...) and forwards the WHOLE list to whatever provider this model belongs to, through
    common.runner.call(). Claude, OpenAI, and Gemini all see the same accumulated history on every
    round. The env is built once (prepare_instance) and each round scores against the same checkout.
    """
    from common.runner import call  # lazy: pulls the SDK only for the provider that runs

    tmp = pathlib.Path(tempfile.mkdtemp(prefix="swesolve_"))
    cost = lat = 0.0
    used = 0
    last: dict = {}
    try:
        handles = prepare_instance(record, tmp)
        messages = [{"role": "user", "content": PROMPT.format(
            issue=record["problem_statement"], ctx=oracle_context(inst))}]
        for rnd in range(1, rounds + 1):
            used = rnd
            try:
                res = call(client, model_key, messages, max_tokens=max_tokens, effort=effort)
            except Exception as e:  # noqa: BLE001
                return {"key": model_key, "iid": inst.instance_id, "resolved": False, "rounds": rnd,
                        "cost": cost, "latency": lat, "error": type(e).__name__,
                        "input_tokens": 0, "output_tokens": 0}
            cost += res.cost.total
            lat += res.latency_s
            patch = extract_patch(res.text)
            if patch.strip():
                patch = repair_patch(patch, lambda p: base_file_lines(inst, p))
            last = apply_and_score(record, *handles, patch, test_timeout=test_timeout)
            if last["resolved"]:
                break
            if rnd < rounds:
                # Append the assistant turn and the feedback to the SAME history every provider sees.
                messages.append({"role": "assistant", "content": res.text})
                messages.append({"role": "user", "content": _feedback(record, last)})
        return {
            "key": model_key, "iid": inst.instance_id, "resolved": last.get("resolved", False),
            "rounds": used, "cost": cost, "latency": lat,
            "f2p": (last.get("f2p_pass", 0), last.get("f2p_total", 0)),
            "applied": last.get("applied", False),
            "input_tokens": getattr(res, "input_tokens", 0), "output_tokens": getattr(res, "output_tokens", 0),
        }
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def _clients():
    """The Anthropic / OpenAI / Gemini clients, each None when its key is absent (so its arm is
    ran=False, never faked). Lazy through the runner so an absent key needs no SDK."""
    from common.runner import get_client, get_gemini_client, get_openai_client
    return {"anthropic": get_client(), "openai": get_openai_client(), "gemini": get_gemini_client()}


def run_slice(models=DEFAULT_MODELS, *, limit=None, rounds=ROUNDS, effort=EFFORT,
              workers=None, progress=False) -> dict:
    """Run the symmetric agentic loop over the validated slice x the model set. Returns per-(model,
    instance) results plus a per-model K/N tally. A model whose key is absent is skipped (recorded
    ran=False on its arm later), never faked."""
    from concurrent.futures import ThreadPoolExecutor, as_completed
    from common.models import get

    if shutil.which("uv") is None:
        raise SystemExit("uv is required for the local grader (https://docs.astral.sh/uv).")
    clients = _clients()
    run_models = [m for m in models if clients[get(m).provider] is not None]
    skipped = [m for m in models if m not in run_models]
    insts = load_instances(limit)
    records = _records(limit)

    if progress:
        print(f"  Solving {len(insts)} instances x {len(run_models)} models = "
              f"{len(insts) * len(run_models)} runs, up to {rounds} rounds each, effort={effort}. "
              f"No Docker.")
        if skipped:
            print(f"  Skipping {', '.join(skipped)} (no API key set), recorded as did-not-run.")
        print()

    platform.used("thinking", "adaptive thinking on for the Claude arms")
    tasks = [(records[i.instance_id], i, m) for m in run_models for i in insts]
    n_workers = workers if workers is not None else min(8, max(1, len(tasks)))
    results = []
    with ThreadPoolExecutor(max_workers=n_workers) as pool:
        futs = {pool.submit(solve_one, rec, inst, m, clients[get(m).provider],
                            rounds=rounds, effort=effort): (m, inst.instance_id)
                for (rec, inst, m) in tasks}
        for fut in as_completed(futs):
            r = fut.result()
            results.append(r)
            if progress:
                verdict = "RESOLVED" if r["resolved"] else ("error " + r["error"] if r.get("error") else "no")
                mark = "x" if r["resolved"] else " "
                print(f"    [{mark}] {r['key']:<9} {r['iid']:<26} {verdict:<10} round {r['rounds']}  "
                      f"${r['cost']:.4f}  {r['latency']:.0f}s", flush=True)

    by_model = {}
    for r in results:
        by_model.setdefault(r["key"], []).append(r)
    tally = {}
    for key, rs in by_model.items():
        rounds_landed = sorted(x["rounds"] for x in rs if x["resolved"])
        tally[key] = {
            "resolved": sum(x["resolved"] for x in rs), "n": len(rs),
            "cost": sum(x["cost"] for x in rs), "latency": sum(x["latency"] for x in rs),
            "input_tokens": sum(x.get("input_tokens", 0) for x in rs),
            "output_tokens": sum(x.get("output_tokens", 0) for x in rs),
            "rounds_landed": rounds_landed, "errors": [x for x in rs if x.get("error")],
        }
    return {"results": results, "tally": tally, "n_instances": len(insts), "skipped": skipped,
            "rounds": rounds, "effort": effort}


# --------------------------------------------------------------------------- the Demonstrator interface
#
# agentic_grading: the model iterates against the real test suite and resolves where the field ties
# single-shot. The Claude arm is the strongest Claude tier's agentic K/N; the competitor arms are the
# SAME loop for OpenAI and Gemini at their frontier and balanced tiers. The gate is the real test
# suite, run identically on every arm, so the verdict is a measured K/N, not a rubric. A claude-ahead
# verdict requires every competitor arm to have run (head-to-head), enforced by the base honesty
# contract; if a competitor key was absent the verdict downgrades to never-evaluated.

class AgenticGradingDemonstrator(BaseDemonstrator):
    demo_kind = "agentic_grading"

    def estimate(self, edge, spec):
        n = len(VALIDATED)
        models = len(DEFAULT_MODELS)
        rounds = (spec or {}).get("rounds", ROUNDS)
        # The slice is small but each run can take several rounds of real model calls plus a local test
        # build. Cost scales with the model set actually keyed; the upper bound is all six arms.
        return CostEstimate(
            usd=5.0, wall_clock_s=600.0, command="make agentic",
            note=f"{n} instances x up to {models} model arms x up to {rounds} rounds, "
                 f"local no-Docker grading; spend is the model arms only, ~$4-5 with all keys set",
        )

    def _arm_for(self, key, tally, n, *, is_claude):
        from common.models import get
        from engine.demonstrators.base import Arm
        t = tally.get(key)
        if t is None:
            m = get(key)
            return Arm(provider=m.provider, model=m.id, ran=False,
                       note=f"{key} did not run (key absent); recorded did-not-run, never faked")
        m = get(key)
        return Arm(
            provider=m.provider, model=m.id, ran=True,
            latency_s=t["latency"], input_tokens=t["input_tokens"], output_tokens=t["output_tokens"],
            cost_usd=t["cost"], ctx=t["input_tokens"],
            metric={"resolved": t["resolved"], "n": t["n"], "rounds_landed": t["rounds_landed"],
                    "k_of_n": f"{t['resolved']}/{t['n']}"},
            note=("Claude arm, adaptive thinking on, disclosed" if is_claude else "same symmetric loop"),
        )

    def run_claude_arm(self, edge, spec):
        spec = spec or {}
        run = spec.get("_run") or run_slice(
            models=spec.get("models", DEFAULT_MODELS), limit=spec.get("limit"),
            rounds=spec.get("rounds", ROUNDS), effort=spec.get("effort", EFFORT),
            progress=spec.get("progress", False))
        spec["_run"] = run  # cache so the competitor-arm call reuses the same run (one slice, not two)
        # The anchor Claude arm is the strongest Claude tier that ran (opus), with sonnet carried as a
        # second Claude row in the run for the table.
        for key in CLAUDE_MODELS:
            if key in run["tally"]:
                return self._arm_for(key, run["tally"], run["n_instances"], is_claude=True)
        from common.models import get
        from engine.demonstrators.base import Arm
        return Arm(provider="anthropic", model=get("opus").id, ran=False,
                   note="no Claude arm ran (ANTHROPIC_API_KEY absent)")

    def run_competitor_arms(self, edge, spec):
        spec = spec or {}
        run = spec.get("_run")
        if run is None:
            run = run_slice(models=spec.get("models", DEFAULT_MODELS), limit=spec.get("limit"),
                            rounds=spec.get("rounds", ROUNDS), effort=spec.get("effort", EFFORT),
                            progress=spec.get("progress", False))
            spec["_run"] = run
        arms = []
        for key in COMPETITOR_MODELS:
            if key in (spec.get("models", DEFAULT_MODELS)):
                arms.append(self._arm_for(key, run["tally"], run["n_instances"], is_claude=False))
        return arms

    def score(self, claude, competitors, spec):
        # The SAME machine-checkable gate on every arm: the real test suite. The kind-specific metric is
        # K/N resolved per arm. Claude leads when its resolved count strictly exceeds every competitor
        # arm that RAN. A competitor that did not run cannot be beaten (handled by the honesty contract,
        # which holds the verdict at never-evaluated unless every competitor arm ran).
        ck = claude.metric.get("resolved", 0) if claude.ran else -1
        ran_comp = [c for c in competitors if c.ran]
        best_comp = max((c.metric.get("resolved", 0) for c in ran_comp), default=None)
        leads = claude.ran and best_comp is not None and ck > best_comp
        ties = claude.ran and best_comp is not None and ck == best_comp
        if leads:
            verdict, passed, note = "claude-ahead", True, "Claude resolved more of the slice agentically than every competitor arm"
        elif ties:
            verdict, passed, note = "parity", False, "Claude tied the best competitor arm on this slice"
        elif claude.ran and best_comp is not None and ck < best_comp:
            verdict, passed, note = "claude-behind", False, "a competitor resolved more of the slice; this ships as the product-team note"
        else:
            verdict, passed, note = "never-evaluated", False, "not every competitor arm ran, so the lead is held"
        metric = {
            "claude_resolved": claude.metric.get("k_of_n") if claude.ran else "(did not run)",
            "best_competitor_resolved": best_comp,
            "per_arm": {(c.provider + ":" + c.model): c.metric.get("k_of_n")
                        for c in [claude, *competitors] if c.ran},
        }
        return Verdict(verdict=verdict, passed=passed, metric=metric, note=note)

    def receipt(self, edge, claude, competitors, verdict, spec):
        run = (spec or {}).get("_run") or {}
        fc = self.fair_comparison(edge)
        return self.build_receipt(
            edge, claude, competitors, verdict, spec,
            workload={
                "task_shape": fc.get("task_shape",
                                     f"{len(VALIDATED)} curated SWE-bench Verified instances (flask, pylint), "
                                     f"agentic, up to {run.get('rounds', ROUNDS)} rounds, local no-Docker grading"),
                "models": {"claude": claude.model,
                           "competitors": [c.model for c in competitors]},
                "features_on": ["adaptive thinking (Claude)", "symmetric multi-turn loop (all providers)",
                                "local uv-venv grader (no Docker)"],
                "effort": run.get("effort", EFFORT),
                "assumptions": "small pure-Python slice corroborating the public SWE-bench Verified "
                               "leaderboard, not a 500-instance reproduction; oracle file context; same "
                               "effort label and same accumulated history on every arm; uv on PATH",
            },
            grounding=[
                {"claim": "Claude leads the public SWE-bench Verified leaderboard",
                 "source_url": "https://www.swebench.com/", "date": "2026-06-18"},
                {"claim": "the local grader reproduces the official harness verdict from the swebench "
                          "package recipe (no Docker), proven by validate() on the gold patches",
                 "source_url": "https://github.com/SWE-bench/SWE-bench", "date": "2026-06-18"},
            ],
            fairness={
                "best_to_best": "each provider runs its frontier and balanced tier at the same effort "
                                "label; Claude's adaptive thinking is on and disclosed",
                "isolate": "the loop, prompt, oracle context, round budget, and grader are identical on "
                           "every arm; the ONLY thing that differs is the model, and every provider sees "
                           "the SAME accumulated multi-turn history (the symmetric-loop fix)",
            },
        )


register(AgenticGradingDemonstrator())


# --------------------------------------------------------------------------- the CLI receipt

def _print_receipt(run: dict) -> None:
    from common.runner import fmt_usd
    from common.models import get
    tally = run["tally"]
    n = run["n_instances"]
    print(f"\n  === Resolved on the validated slice, agentic (iterating against the real tests, no Docker) ===")
    print(f"  {n} instances, up to {run['rounds']} rounds, effort={run['effort']}. "
          f"Every provider saw the same accumulated history (symmetric loop).\n")
    print(f"  {'model':<26}{'resolved':>10}{'rounds landed':>16}{'cost':>12}")
    print("  " + "-" * 64)
    order = sorted(tally.items(), key=lambda kv: -kv[1]["resolved"])
    for key, t in order:
        landed = ",".join(str(r) for r in t["rounds_landed"]) or "-"
        print(f"  {get(key).label:<26}{t['resolved']}/{t['n']:<8}{landed:>16}{fmt_usd(t['cost']):>12}")
    total_cost = sum(t["cost"] for t in tally.values())
    print(f"\n  total spend this run: {fmt_usd(total_cost)} (read off each usage object)")
    if run["skipped"]:
        print(f"  arms not run (key absent, recorded did-not-run, never faked): {', '.join(run['skipped'])}")


def main(argv=None) -> int:
    import argparse
    import json
    from common.client import load_env, repo_root

    p = argparse.ArgumentParser(description="agentic_grading: the SWE-bench repo-repair head-to-head, "
                                            "symmetric multi-turn loop, local no-Docker grading.")
    p.add_argument("--validate", action="store_true", help="prove the grader against the gold patches, then exit")
    p.add_argument("--models", default=",".join(DEFAULT_MODELS), help="comma-separated model keys")
    p.add_argument("--rounds", type=int, default=ROUNDS, help="max agentic rounds per instance")
    p.add_argument("--effort", default=EFFORT, help="the harness effort label, sent to every provider")
    p.add_argument("--limit", type=int, default=None, help="cap the number of instances (for a smoke run)")
    a = p.parse_args(argv)

    load_env()
    if a.validate:
        good = validate()
        print("  VALIDATED =", good)
        return 0

    print("\n  agentic_grading: does the model resolve a real repo-repair slice when it can iterate")
    print("  against the real tests? The same multi-turn loop and grader for every provider.\n")
    run = run_slice(models=tuple(a.models.split(",")), limit=a.limit, rounds=a.rounds,
                    effort=a.effort, progress=True)
    _print_receipt(run)

    out = {"n_instances": run["n_instances"], "rounds": run["rounds"], "effort": run["effort"],
           "tally": {k: {kk: vv for kk, vv in t.items() if kk != "errors"} for k, t in run["tally"].items()},
           "results": run["results"], "skipped": run["skipped"]}
    (repo_root() / "data").mkdir(exist_ok=True)
    (repo_root() / "data" / "last_agentic.json").write_text(json.dumps(out, indent=2) + "\n")
    print("\n  (per-run detail cached in gitignored data/last_agentic.json; this printout is the receipt)\n")
    print("  Re-run `make validate` any time to re-prove the grader against the gold patches.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
