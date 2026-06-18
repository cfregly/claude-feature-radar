"""Run model-generated code against a problem's hidden tests, in a sandboxed subprocess.

Ported from ship-on-claude edges/cost-and-effort/grader.py, the no-Docker sandboxed executor for the
eval_quality and agentic_grading demonstrators. The score() gate of a code edge runs the SAME machine
check on every arm by feeding each arm's program through grade(), so the verdict is the test suite,
never a rubric.

SECURITY: this executes code written by a model. Each run is a fresh subprocess with a wall-clock
timeout, a new session (so a runaway can be killed), and best-effort resource limits (CPU seconds and
address space). That is the same posture as the official LiveCodeBench runner, which does not use
Docker either. Run this on a machine you do not mind exposing to arbitrary code, ideally a throwaway
VM or container. It is a deliberate trade for the one-command, no-Docker promise.
"""

from __future__ import annotations

import os
import re
import resource
import subprocess
import sys
import tempfile

_CODE_BLOCK = re.compile(r"```(?:python)?\s*\n(.*?)```", re.DOTALL)


def extract_code(text: str) -> str:
    """Pull the Python program out of the model's reply.

    The prompt asks for one fenced python block. If there are several, the last one is taken, since a
    model that shows work tends to put the final program last.
    """
    blocks = _CODE_BLOCK.findall(text or "")
    return (blocks[-1] if blocks else (text or "")).strip()


def _set_limits() -> None:
    # Best-effort. Runs in the child before exec. Not all limits bind on every OS.
    for res, soft, hard in (
        (resource.RLIMIT_CPU, 10, 10),
        (resource.RLIMIT_AS, 2 * 1024 * 1024 * 1024, 2 * 1024 * 1024 * 1024),
    ):
        try:
            resource.setrlimit(res, (soft, hard))
        except (ValueError, OSError):
            pass


def run_program(code: str, stdin: str, timeout: float = 8.0) -> tuple[str | None, str]:
    """Run code with stdin piped in. Returns (stdout, status).

    status is one of: "ok", "timeout", "error:<msg>".
    """
    with tempfile.TemporaryDirectory() as d:
        src = os.path.join(d, "sol.py")
        with open(src, "w") as f:
            f.write(code)
        try:
            proc = subprocess.run(
                [sys.executable, src],
                input=stdin,
                capture_output=True,
                text=True,
                timeout=timeout,
                cwd=d,
                start_new_session=True,
                preexec_fn=_set_limits,
                env={"PATH": os.environ.get("PATH", "")},
            )
        except subprocess.TimeoutExpired:
            return None, "timeout"
        except Exception as e:  # noqa: BLE001
            return None, f"error:{type(e).__name__}"
        if proc.returncode != 0:
            tail = proc.stderr.strip().splitlines()[-1][:80] if proc.stderr.strip() else "nonzero exit"
            return None, f"error:{tail}"
        return proc.stdout, "ok"


def _norm(s: str) -> str:
    return "\n".join(line.rstrip() for line in (s or "").strip().splitlines())


def grade(code: str, tests: list[tuple[str, str]], timeout: float = 8.0) -> tuple[bool, str]:
    """Pass iff the program matches the expected output on every test. Stops at the first failure."""
    if not (code or "").strip():
        return False, "no code"
    for i, (stdin, expected) in enumerate(tests):
        out, status = run_program(code, stdin, timeout)
        if status != "ok":
            return False, f"test {i}: {status}"
        if _norm(out) != _norm(expected):
            return False, f"test {i}: wrong answer"
    return True, "pass"
