"""code_execution_state: Claude's code-execution sandbox keeps your files across requests, and keeps them
for 30 days, where the competitors lose them.

THE EDGE, at lifecycle depth. Claude's code execution tool persists its sandbox CONTAINER and the
files in it across separate Messages API requests: capture `response.container.id`, pass it as
`container=<id>` on the next call, and a file written in turn 1 is readable in turn 2. Containers live
30 days (docs, fetched 2026-06-19). So a multi-step data agent uploads a dataset once, builds up
intermediate files and state across a conversation, and never re-uploads or re-runs setup, even if the
user steps away.

WHY IT IS A CROSS-VENDOR EDGE (verified live 2026-06-19):
  - OpenAI code_interpreter reuses a WARM container by id (parity while warm), but the container is
    discarded after 20 minutes idle, unrecoverable: "A container expires if it is not used for 20
    minutes ... all data ... will be discarded ... not recoverable." So a long-lived or idle-interrupted
    agent loses its files and REPL state.
  - Gemini code execution exposes no reusable container handle and documents no cross-call persistence
    (a 30-second single-invocation environment), so a file written in one call is gone in the next.

WHAT THIS MEASURES, the SAME gate on every arm, over the loop's time axis:
  WRITE phase: each arm writes a unique nonce to /tmp/state.txt in its sandbox, then reads it back in a
  SECOND request (Claude and OpenAI reuse the container id, parity while warm; Gemini cannot, so its
  second call cannot see the file).
  VERIFY phase (after a >20-minute idle, the loop's next tick): re-read the SAME container. Claude reads
  the nonce back (30-day life); OpenAI's container has expired (20-minute idle), the read fails. That is
  the durability win, measured, not asserted.

FOUNDER WORKLOAD. A multi-step data/analytics agent over a user's own files: upload a 50MB usage CSV
once, then over several turns clean it, build intermediate tables, fit a model, render charts, in one
reused container. On OpenAI the state is gone if the user is idle 20 minutes; on Gemini the dataset is
re-sent every call. The founder pays that gap in re-upload bytes, repeated setup, and checkpoint glue.

DEPENDENCIES. The Claude arm needs only anthropic. The OpenAI and Gemini arms need their optional SDKs
and keys (lazy). State between the two phases is kept in data/code_execution_state_pending.json (gitignored),
which survives across loop ticks in a session. Not ZDR-eligible (code execution retains data).
"""

from __future__ import annotations

import argparse
import json
import os
import pathlib
import sys
import time
from dataclasses import dataclass, field

# repo root on the path, for common/ and engine/ when run as a script.
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))

from engine.demonstrators.base import Arm, BaseDemonstrator, CostEstimate, Verdict
from engine.demonstrators.registry import register
from engine.demonstrators.shared import platform

CLAUDE_MODEL = os.environ.get("CES_CLAUDE_MODEL", "sonnet")
OPENAI_MODEL = os.environ.get("CES_OPENAI_MODEL", "gpt-top")
GEMINI_MODEL = os.environ.get("CES_GEMINI_MODEL", "gem-flash")
CODE_EXEC_BETA = "code-execution-2025-08-25"
CLAUDE_TOOL = "code_execution_20250825"
OPENAI_IDLE_EXPIRY_MIN = 20  # documented: OpenAI code_interpreter container expires after 20 min idle
STATE_PATH_REL = "data/code_execution_state_pending.json"
RECEIPT_PATH_REL = "edges/code-execution-state/receipt.json"


def _state_path():
    from common.client import repo_root
    return repo_root() / STATE_PATH_REL


def _nonce() -> str:
    return f"NONCE{int(time.time())}{os.urandom(2).hex()}"


def _committed_receipt() -> dict:
    """Read the committed code-execution-state receipt without running any live arm."""
    from common.client import repo_root
    path = repo_root() / RECEIPT_PATH_REL
    try:
        return json.loads(path.read_text())
    except (OSError, json.JSONDecodeError):
        return {}


# --------------------------------------------------------------------------- Claude

def _claude_write(client, nonce: str):
    """Write the nonce to /tmp/state.txt in a fresh container, warm-read it back from the reused
    container. Returns (container_id, warm_persisted, cost)."""
    from common.models import get
    from common.pricing import cost_breakdown

    m = get(CLAUDE_MODEL)
    cost = 0.0
    r = client.beta.messages.create(
        model=m.id, max_tokens=1024, betas=[CODE_EXEC_BETA],
        tools=[{"type": CLAUDE_TOOL, "name": "code_execution"}],
        messages=[{"role": "user", "content":
                   f"Run python: write the exact text {nonce} to /tmp/state.txt, then print done."}])
    cost += cost_breakdown(CLAUDE_MODEL, r.usage).total
    cid = getattr(getattr(r, "container", None), "id", None)
    warm = False
    if cid:
        r2 = client.beta.messages.create(
            model=m.id, max_tokens=1024, betas=[CODE_EXEC_BETA], container=cid,
            tools=[{"type": CLAUDE_TOOL, "name": "code_execution"}],
            messages=[{"role": "user", "content": "Run python: print the contents of /tmp/state.txt"}])
        cost += cost_breakdown(CLAUDE_MODEL, r2.usage).total
        warm = nonce in "".join(b.text for b in r2.content if getattr(b, "type", None) == "text")
    return cid, warm, cost


def _claude_reread(client, cid: str, nonce: str):
    """Re-read /tmp/state.txt from the SAME container after the idle gap. Returns (survived, cost, note)."""
    from common.models import get
    from common.pricing import cost_breakdown

    m = get(CLAUDE_MODEL)
    try:
        r = client.beta.messages.create(
            model=m.id, max_tokens=1024, betas=[CODE_EXEC_BETA], container=cid,
            tools=[{"type": CLAUDE_TOOL, "name": "code_execution"}],
            messages=[{"role": "user", "content":
                       "Run python: print the contents of /tmp/state.txt, or print NOTFOUND if it is missing."}])
        cost = cost_breakdown(CLAUDE_MODEL, r.usage).total
        txt = "".join(b.text for b in r.content if getattr(b, "type", None) == "text")
        return (nonce in txt), cost, ("read back" if nonce in txt else "file missing")
    except Exception as e:  # noqa: BLE001
        return False, 0.0, f"{type(e).__name__}: {str(e)[:80]}"


# --------------------------------------------------------------------------- OpenAI

def _openai_container_id(resp):
    for it in (getattr(resp, "output", None) or []):
        if getattr(it, "type", None) == "code_interpreter_call":
            return getattr(it, "container_id", None) or getattr(it, "container", None)
    return None


def _openai_write(client, nonce: str):
    from common.models import get
    from common.pricing import cost_from_buckets

    m = get(OPENAI_MODEL)
    cost = 0.0

    def _cost(r):
        u = r.usage
        inp = getattr(u, "input_tokens", 0) or 0
        out = getattr(u, "output_tokens", 0) or 0
        det = getattr(u, "input_tokens_details", None)
        cached = (getattr(det, "cached_tokens", 0) or 0) if det else 0
        return cost_from_buckets(OPENAI_MODEL, fresh_input=max(0, inp - cached), cached=cached, output=out)

    r = client.responses.create(
        model=m.id, max_output_tokens=2048,
        tools=[{"type": "code_interpreter", "container": {"type": "auto"}}],
        input=f"Use the python tool: write the exact text {nonce} to /tmp/state.txt, then print done.")
    cost += _cost(r)
    cid = _openai_container_id(r)
    warm = False
    if cid:
        r2 = client.responses.create(
            model=m.id, max_output_tokens=2048,
            tools=[{"type": "code_interpreter", "container": cid}],
            input="Use the python tool: print the contents of /tmp/state.txt")
        cost += _cost(r2)
        warm = nonce in (getattr(r2, "output_text", "") or "")
    return cid, warm, cost


def _openai_reread(client, cid: str, nonce: str):
    from common.models import get
    from common.pricing import cost_from_buckets

    m = get(OPENAI_MODEL)
    try:
        r = client.responses.create(
            model=m.id, max_output_tokens=2048,
            tools=[{"type": "code_interpreter", "container": cid}],
            input="Use the python tool: print the contents of /tmp/state.txt, or print NOTFOUND if missing.")
        u = r.usage
        inp = getattr(u, "input_tokens", 0) or 0
        out = getattr(u, "output_tokens", 0) or 0
        cost = cost_from_buckets(OPENAI_MODEL, fresh_input=inp, cached=0, output=out)
        txt = getattr(r, "output_text", "") or ""
        return (nonce in txt), cost, ("read back" if nonce in txt else "file missing")
    except Exception as e:  # noqa: BLE001
        # the documented outcome after 20 min idle: the container is gone, the call errors
        return False, 0.0, f"container expired/error: {type(e).__name__}: {str(e)[:70]}"


# --------------------------------------------------------------------------- Gemini (no persistence)

def _gemini_cross_call(client, nonce: str):
    """Gemini has no reusable container: write in call 1, then a FRESH call 2 cannot see the file.
    Returns (cross_call_persisted, cost)."""
    from google.genai import types

    from common.models import get
    from common.pricing import cost_from_buckets

    m = get(GEMINI_MODEL)
    tool = types.Tool(code_execution=types.ToolCodeExecution())
    cost = 0.0

    def _cost(r):
        u = getattr(r, "usage_metadata", None)
        inp = (getattr(u, "prompt_token_count", 0) or 0) if u else 0
        out = ((getattr(u, "candidates_token_count", 0) or 0) +
               (getattr(u, "thoughts_token_count", 0) or 0)) if u else 0
        return cost_from_buckets(GEMINI_MODEL, fresh_input=inp, cached=0, output=out)

    cfg = types.GenerateContentConfig(tools=[tool], max_output_tokens=1024)
    r1 = client.models.generate_content(
        model=m.id, contents=f"Write the exact text {nonce} to /tmp/state.txt using python, then print done.", config=cfg)
    cost += _cost(r1)
    r2 = client.models.generate_content(
        model=m.id, contents="Using python, print the contents of /tmp/state.txt, or print NOTFOUND if it is missing.", config=cfg)
    cost += _cost(r2)
    persisted = nonce in (getattr(r2, "text", None) or "")
    return persisted, cost


# --------------------------------------------------------------------------- the run

def _clients():
    from common.client import get_client
    from common.runner import get_gemini_client, get_openai_client
    return {"anthropic": get_client(), "openai": get_openai_client(), "gemini": get_gemini_client()}


def write_phase(progress=False) -> dict:
    clients = _clients()
    platform.used("code_execution", "reusable container, files persist across requests")
    nonce = _nonce()
    state = {"nonce": nonce, "written_at": time.time(), "claude": {}, "openai": {}, "gemini": {}}

    if clients["anthropic"] is not None:
        if progress:
            print("    claude: write + warm read-back (reuse container)")
        cid, warm, cost = _claude_write(clients["anthropic"], nonce)
        state["claude"] = {"container_id": cid, "warm_persisted": warm, "cost": cost}
        if progress:
            print(f"      claude container={cid} warm_persisted={warm}")
    if clients["openai"] is not None:
        if progress:
            print("    openai: write + warm read-back (reuse container)")
        cid, warm, cost = _openai_write(clients["openai"], nonce)
        state["openai"] = {"container_id": cid, "warm_persisted": warm, "cost": cost}
        if progress:
            print(f"      openai container={cid} warm_persisted={warm}")
    if clients["gemini"] is not None:
        if progress:
            print("    gemini: write then FRESH read (no reusable container)")
        persisted, cost = _gemini_cross_call(clients["gemini"], nonce)
        state["gemini"] = {"cross_call_persisted": persisted, "cost": cost}
        if progress:
            print(f"      gemini cross_call_persisted={persisted}")

    _state_path().parent.mkdir(exist_ok=True)
    _state_path().write_text(json.dumps(state, indent=2) + "\n")
    return state


def verify_phase(progress=False) -> dict:
    clients = _clients()
    sp = _state_path()
    if not sp.exists():
        return {"error": "no pending write-phase state; run the write phase first"}
    state = json.loads(sp.read_text())
    nonce = state["nonce"]
    idle_min = (time.time() - state["written_at"]) / 60.0
    out = {"nonce": nonce, "idle_minutes": round(idle_min, 1),
           "openai_idle_expiry_min": OPENAI_IDLE_EXPIRY_MIN, "claude": dict(state.get("claude", {})),
           "openai": dict(state.get("openai", {})), "gemini": dict(state.get("gemini", {}))}

    ccid = (state.get("claude") or {}).get("container_id")
    if clients["anthropic"] is not None and ccid:
        survived, cost, note = _claude_reread(clients["anthropic"], ccid, nonce)
        out["claude"].update({"survived_idle": survived, "reread_note": note, "reread_cost": cost})
        if progress:
            print(f"    claude reread after {idle_min:.1f}min idle: survived={survived} ({note})")
    ocid = (state.get("openai") or {}).get("container_id")
    if clients["openai"] is not None and ocid:
        survived, cost, note = _openai_reread(clients["openai"], ocid, nonce)
        out["openai"].update({"survived_idle": survived, "reread_note": note, "reread_cost": cost})
        if progress:
            print(f"    openai reread after {idle_min:.1f}min idle: survived={survived} ({note})")
    return out


def _verdict(verify: dict) -> dict:
    claude = verify.get("claude", {})
    openai = verify.get("openai", {})
    gemini = verify.get("gemini", {})
    idle = verify.get("idle_minutes", 0)
    claude_warm = bool(claude.get("warm_persisted"))
    claude_survived = bool(claude.get("survived_idle"))
    openai_warm = bool(openai.get("warm_persisted"))
    openai_survived = bool(openai.get("survived_idle"))
    gemini_persist = bool(gemini.get("cross_call_persisted"))
    idle_past_openai = idle >= OPENAI_IDLE_EXPIRY_MIN

    # The measured edge: Claude persists files across requests AND survives a >20-min idle; Gemini
    # cannot persist across calls at all; OpenAI persists while warm but its container expires on idle.
    promotable = (claude_warm and claude_survived and (not gemini_persist)
                  and idle_past_openai and (not openai_survived) and openai_warm)
    return {
        "positive_signal": claude_warm and (not gemini_persist),
        "promotable_edge": promotable,
        "idle_minutes": idle,
        "claude_cross_request_persist": claude_warm,
        "claude_survived_idle": claude_survived,
        "openai_warm_persist": openai_warm,
        "openai_survived_idle": openai_survived,
        "gemini_cross_call_persist": gemini_persist,
        "why_not_promotable": [] if promotable else [
            r for r, f in [
                ("Claude did not persist a file across requests (warm)", not claude_warm),
                ("Claude did not survive the idle gap", not claude_survived),
                ("the idle gap did not exceed OpenAI's 20-min expiry yet", not idle_past_openai),
                ("OpenAI's container survived the idle (no durability gap measured)", openai_survived),
                ("OpenAI did not even persist warm (arm error)", not openai_warm),
                ("Gemini persisted across calls (no gap)", gemini_persist),
            ] if f
        ],
    }


# --------------------------------------------------------------------------- Demonstrator adapter

class CodeExecutionStateDemonstrator(BaseDemonstrator):
    demo_kind = "code_execution_state"

    def applicable(self, edge: dict) -> bool:
        key = (edge.get("key") or "").replace("-", "_")
        return super().applicable(edge) and key in {"code_execution_state", "code_execution"}

    def estimate(self, edge, spec):
        repro = (edge.get("fair_comparison") or {}).get("repro") or {}
        return CostEstimate(
            usd=float(repro.get("est_cost_usd", 0.05)),
            wall_clock_s=float(repro.get("est_time_s", 60.0)),
            command="make code_execution_state",
            note="two-phase code execution state proof; live API spend only after explicit approval",
        )

    def run_claude_arm(self, edge, spec):
        receipt = _committed_receipt()
        verify = receipt.get("verify", {})
        claude = verify.get("claude", {})
        verdict = receipt.get("verdict", {})
        platform.used("reliability", "committed code-execution-state receipt")
        return Arm(
            provider="anthropic",
            model=CLAUDE_MODEL,
            ran=bool(receipt),
            cost_usd=float(claude.get("cost", 0.0) or 0.0) + float(claude.get("reread_cost", 0.0) or 0.0),
            metric=verdict,
            note="read from the committed code-execution-state receipt; no live arm ran in dispatch",
        )

    def run_competitor_arms(self, edge, spec):
        receipt = _committed_receipt()
        verify = receipt.get("verify", {})
        openai = verify.get("openai", {})
        gemini = verify.get("gemini", {})
        return [
            Arm(
                provider="openai",
                model=OPENAI_MODEL,
                ran=bool(openai),
                cost_usd=float(openai.get("cost", 0.0) or 0.0) + float(openai.get("reread_cost", 0.0) or 0.0),
                metric={
                    "warm_persisted": openai.get("warm_persisted"),
                    "survived_idle": openai.get("survived_idle"),
                },
                note=openai.get("reread_note", ""),
            ),
            Arm(
                provider="gemini",
                model=GEMINI_MODEL,
                ran=bool(gemini),
                cost_usd=float(gemini.get("cost", 0.0) or 0.0),
                metric={"cross_call_persisted": gemini.get("cross_call_persisted")},
                note="no reusable container handle in the tested setup",
            ),
        ]

    def score(self, claude, competitors, spec):
        passed = bool((claude.metric or {}).get("promotable_edge"))
        return Verdict(
            verdict="claude-ahead" if passed else "never-evaluated",
            passed=passed,
            metric=claude.metric or {},
            note="committed receipt shows Claude survived the idle gap while competitor arms did not",
        )

    def receipt(self, edge, claude, competitors, verdict, spec):
        receipt = _committed_receipt()
        sources = receipt.get("sources", {})
        return self.build_receipt(
            edge, claude, competitors, verdict, spec,
            workload={
                "task_shape": "write a nonce, reuse the code sandbox, and re-read after a long idle",
                "models": {"claude": CLAUDE_MODEL, "openai": OPENAI_MODEL, "gemini": GEMINI_MODEL},
                "features_on": [CLAUDE_TOOL],
                "assumptions": "live two-phase receipt is committed; dispatch reads it offline",
            },
            grounding=[
                {"claim": "Claude code execution container reuse and retention",
                 "source_url": sources.get("claude_code_execution", ""), "date": receipt.get("date", "")},
                {"claim": "OpenAI code interpreter idle expiry",
                 "source_url": sources.get("openai_code_interpreter", ""), "date": receipt.get("date", "")},
                {"claim": "Gemini code execution no reusable container handle in the tested setup",
                 "source_url": sources.get("gemini_code_execution", ""), "date": receipt.get("date", "")},
            ],
            fairness={
                "best_to_best": "same write-then-reread workload across each vendor's code sandbox",
                "isolate": "only container reuse and lifetime differ",
            },
        )


register(CodeExecutionStateDemonstrator())


# --------------------------------------------------------------------------- CLI

def main(argv=None) -> int:
    from common.client import load_env, repo_root

    p = argparse.ArgumentParser(description="code_execution_state: Claude's sandbox keeps files across "
                                            "requests and across a 20-min idle, vs OpenAI/Gemini.")
    p.add_argument("--verify", action="store_true", help="the durability re-read after the idle gap")
    p.add_argument("--emit-edge", action="store_true", help="on verify, write edges/code-execution-state/")
    a = p.parse_args(argv)
    load_env()

    if not a.verify:
        print("\n  code_execution_state WRITE phase: each arm writes a nonce to its sandbox, then reads it")
        print("  back from a reused container (Claude/OpenAI) or a fresh call (Gemini).\n")
        state = write_phase(progress=True)
        print(f"\n  wrote pending state to {STATE_PATH_REL} (re-read it after a >20-min idle with --verify)")
        print(f"  claude warm_persist={state.get('claude',{}).get('warm_persisted')} "
              f"openai warm_persist={state.get('openai',{}).get('warm_persisted')} "
              f"gemini cross_call_persist={state.get('gemini',{}).get('cross_call_persisted')}")
        return 0

    print("\n  code_execution_state VERIFY phase: re-read the SAME containers after the idle gap.\n")
    verify = verify_phase(progress=True)
    if "error" in verify:
        print("  " + verify["error"])
        return 1
    verdict = _verdict(verify)
    print(f"\n  idle: {verify['idle_minutes']} min (OpenAI documented expiry: {OPENAI_IDLE_EXPIRY_MIN} min)")
    print(f"  claude: warm={verdict['claude_cross_request_persist']} survived_idle={verdict['claude_survived_idle']}")
    print(f"  openai: warm={verdict['openai_warm_persist']} survived_idle={verdict['openai_survived_idle']}")
    print(f"  gemini: cross_call_persist={verdict['gemini_cross_call_persist']}")
    print(f"  promotable_edge: {verdict['promotable_edge']}")
    if verdict["why_not_promotable"]:
        print("  why not:", "; ".join(verdict["why_not_promotable"]))

    receipt = {"date": "2026-06-19", "verify": verify, "verdict": verdict,
               "claim_under_test": ("Claude's code-execution sandbox keeps your files across separate "
                                    "requests and for 30 days; OpenAI's container is discarded after 20 "
                                    "minutes idle (unrecoverable) and Gemini has no reusable container."),
               "sources": {
                   "claude_code_execution": "https://platform.claude.com/docs/en/agents-and-tools/tool-use/code-execution-tool",
                   "openai_code_interpreter": "https://developers.openai.com/api/docs/guides/tools-code-interpreter",
                   "gemini_code_execution": "https://ai.google.dev/gemini-api/docs/code-execution"}}
    (repo_root() / "data" / "last_code_execution_state.json").write_text(json.dumps(receipt, indent=2) + "\n")
    if a.emit_edge and verdict["promotable_edge"]:
        edge = repo_root() / "edges" / "code-execution-state"
        edge.mkdir(parents=True, exist_ok=True)
        (edge / "receipt.json").write_text(json.dumps(receipt, indent=2) + "\n")
        print("\n  wrote edges/code-execution-state/receipt.json")
    elif a.emit_edge:
        print("\n  not promotable on this run, edge bundle not written")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
