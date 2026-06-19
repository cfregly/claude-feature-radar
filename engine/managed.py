"""engine/managed.py: the Tier-2 monthly resumable runtime, wired but not run.

The cadence has two tiers. Tier-1 is the weekly cheap sweep (engine/cadence.py): a $0 stdlib doc
fetch, diff, rank, dispatch, and draft-to-outbox, all unattended. Tier-2 is an optional monthly deep
run on Claude Managed Agents: the hosted, stateful, resumable sandbox runs the agent loop for you, so
a long deep-dive survives a kill and re-attaches off the server-side event log instead of starting
cold. This module is that Tier-2 runtime.

WIRED, NOT RUN. Nothing here runs on a schedule, and nothing here runs in the default cadence. The
cadence imports the boundary fact (TIER2_GATE = ASK) and the state path, never these live functions.
Starting a Managed Agents session spends a small, bounded amount of sandbox time and stores state
server-side, so it is an explicit ASK the operator triggers, never an unattended motion. This file
exists so the Tier-2 surface is real and re-groundable, not so the cadence calls it. A live run is the
operator's `run.py managed --apply` decision, the same shape as retention_resume's opt-in live arm.

GROUNDING. Every Managed Agents claim traces to platform.claude.com/docs/en/managed-agents/overview,
fetched 2026-06-18: the beta header is managed-agents-2026-04-01 (the SDK sets it automatically for the
beta.agents and beta.sessions calls), Managed Agents is enabled by default for all API accounts,
sessions are stateful by design and resume cleanly after pauses, event history is persisted server-side
and fetchable in full, and because state stays server-side it is not ZDR- or HIPAA-BAA-eligible. The
surface is beta and moves monthly, so re-ground the header before any live run.

DEPENDENCIES. The SDK (anthropic) is imported lazily inside _client(), only on a live run, so the
one-dependency core never loads it at import. No competitor SDK is touched. This module imports nothing
third-party at load, so scripts/check_core_imports.py keeps passing with anthropic alone.
"""

from __future__ import annotations

import json
import pathlib
import time

ROOT = pathlib.Path(__file__).resolve().parent.parent

# Tier-2 is ASK by design: a live Managed Agents session spends sandbox time and stores state
# server-side, so it never runs unattended. The cadence reads this constant, never the live functions.
TIER2_GATE = "ask"

# The durable session ids live under the committed state/ root (per state/README.md), not under
# gitignored data/, so a monthly resume survives a clone the way the landscape baseline does. An env
# override lets a fork point it elsewhere without editing this file.
import os

STATE_PATH = pathlib.Path(os.environ.get(
    "MANAGED_STATE", str(ROOT / "state" / "managed_state.json")))

BETA_HEADER = "managed-agents-2026-04-01"   # the SDK sets it automatically; platform.claude.com, 2026-06-18
AGENT_TOOLSET = "agent_toolset_20260401"    # the built-in bash/file toolset the live session sends
AGENT_MODEL = os.environ.get("MANAGED_MODEL", "claude-sonnet-4-6")  # bound cost; opus for the strongest run

SYSTEM = (
    "You are the feature-radar deep-dive worker running in a sandbox. You sweep a set of source "
    "pages, write a small ledger of what you finished to files, and never re-do a step already in the "
    "ledger. Keep it tight, and grade your own work deterministically."
)


def _client():
    from common.client import managed_client  # lazy: the SDK is pulled only on a live run

    return managed_client()


def _run1_task() -> str:
    """The first task: write a small ledger of finished deep-dive steps to the sandbox filesystem, so a
    resume has concrete state to recover. Deterministic, no model key needed inside the sandbox."""
    return (
        "Do this, then stop:\n"
        "1. Write plan.md listing three deep-dive steps you will run: step-a, step-b, step-c.\n"
        "2. Create ledger.txt and append the line 'step-a done' to it.\n"
        "3. Append 'step-b done' to ledger.txt.\n"
        "4. Run `ls -la` and `cat ledger.txt`, then stop. Leave step-c for the resume."
    )


def _resume_task() -> str:
    """The resume task: read the ledger off the same sandbox and finish only the missing step. This is
    what makes the continuity measurable: the agent must see the work it already did, persisted
    server-side, after the client was killed."""
    return (
        "You are resuming a deep-dive session you started earlier. The sandbox is the same one. "
        "Do this, then stop:\n"
        "1. Run `ls -la` and `cat ledger.txt` to see exactly what you already finished.\n"
        "2. Treat every line already in ledger.txt as done. Do not redo a step already there.\n"
        "3. If step-c is missing, append 'step-c done' to ledger.txt. If nothing is missing, say so.\n"
        "4. Print a final `cat ledger.txt`, then stop."
    )


def _block_text(block) -> str:
    if getattr(block, "type", None) == "text":
        return getattr(block, "text", "") or ""
    return ""


def _drain(stream, max_events: int, seen_ids: set | None = None) -> dict:
    """Consume a live event stream until the session goes idle or the cap is hit. Collect the agent
    text, the tool calls, the bash outputs, and the ids of the new events, so a resume can skip the
    events that were replayed off the server-side log, with the bash-output capture so a resume can
    prove the sandbox files are still present."""
    transcript: list[str] = []
    tools_used: list[str] = []
    tool_output: list[str] = []
    new_event_ids: list[str] = []
    n = 0
    for event in stream:
        eid = getattr(event, "id", None)
        if seen_ids is not None and eid is not None and eid in seen_ids:
            continue
        n += 1
        if eid is not None:
            new_event_ids.append(eid)
        etype = getattr(event, "type", None)
        if etype == "agent.message":
            for block in getattr(event, "content", []) or []:
                transcript.append(_block_text(block))
        elif etype == "agent.tool_use":
            tools_used.append(getattr(event, "name", None) or "tool")
        elif etype == "agent.tool_result":
            tool_output.append(str(getattr(event, "content", "") or ""))
        elif etype == "session.status_idle":
            break
        if n >= max_events:
            break
    return {
        "transcript": "".join(transcript),
        "tools_used": tools_used,
        "tool_output": "\n".join(tool_output),
        "new_event_ids": new_event_ids,
    }


def _persisted_session_id() -> str:
    return json.loads(STATE_PATH.read_text())["session_id"]


def start_session(max_events: int = 400) -> dict:
    """Create a real agent, environment, and session, run the deep-dive ledger task in the hosted
    sandbox, persist the ids under state/, and return the receipt. LIVE, spends Managed Agents time, so
    it is the operator's ASK, never an unattended motion."""
    client = _client()

    env = client.beta.environments.create(
        name="feature-radar-env",
        config={"type": "cloud", "networking": {"type": "unrestricted"}},
    )
    agent = client.beta.agents.create(
        name="deep-dive-worker",
        model=AGENT_MODEL,
        system=SYSTEM,
        tools=[{"type": AGENT_TOOLSET}],
    )
    session = client.beta.sessions.create(
        agent=agent.id, environment_id=env.id, title="Monthly deep dive",
    )

    with client.beta.sessions.events.stream(session.id) as stream:
        client.beta.sessions.events.send(
            session.id,
            events=[{"type": "user.message",
                     "content": [{"type": "text", "text": _run1_task()}]}],
        )
        drained = _drain(stream, max_events)

    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    state = {"session_id": session.id, "agent_id": agent.id,
             "environment_id": env.id, "model": AGENT_MODEL}
    STATE_PATH.write_text(json.dumps(state, indent=2) + "\n")
    return {**state, "events_seen": len(drained["new_event_ids"]), **drained}


def resume_session(session_id: str | None = None, max_events: int = 400) -> dict:
    """Re-attach to a session by id with the documented reconnect pattern: retrieve the status, list
    the prior events to replay them off the server-side log, then open the stream, send the follow-up,
    and continue. A wrong or expired session id is the negative control: retrieve or list raises and we
    report recovered False, so the clean resume is attributable to server-side persistence, with the
    sandbox-files-present check off the resume bash output."""
    client = _client()
    if session_id is None:
        session_id = _persisted_session_id()

    try:
        session = client.beta.sessions.retrieve(session_id)
        status = getattr(session, "status", None)
        replayed = list(client.beta.sessions.events.list(session_id, order="asc"))
    except Exception as exc:  # noqa: BLE001 - the negative control lands here on a bad id
        return {
            "session_id": session_id, "recovered": False, "error": type(exc).__name__,
            "events_replayed_on_resume": 0, "resume_wall_clock_gap_s": None,
            "sandbox_files_present": False, "tools_used": [], "transcript": "", "tool_output": "",
        }

    seen_ids = {getattr(e, "id", None) for e in replayed}
    seen_ids.discard(None)

    t0 = time.monotonic()
    with client.beta.sessions.events.stream(session_id) as stream:
        client.beta.sessions.events.send(
            session_id,
            events=[{"type": "user.message",
                     "content": [{"type": "text", "text": _resume_task()}]}],
        )
        drained = _drain(stream, max_events, seen_ids=seen_ids)
    gap = round(time.monotonic() - t0, 2)

    present = "step-a done" in drained.get("tool_output", "")
    return {
        "session_id": session_id, "recovered": True, "status": status,
        "events_replayed_on_resume": len(seen_ids), "resume_wall_clock_gap_s": gap,
        "sandbox_files_present": present, **drained,
    }


def prove(max_events: int = 400) -> dict:
    """The full Tier-2 continuity receipt: start a session, re-attach, and run the wrong-session-id
    negative control (which must recover nothing, so the clean resume is attributable to server-side
    persistence). LIVE, spends Managed Agents time, the operator's ASK."""
    started = start_session(max_events)
    sid = started["session_id"]
    resumed = resume_session(sid, max_events)
    negative_control = resume_session("sesn_" + "0" * 24, max_events=8)
    return {"started": started, "resumed": resumed, "negative_control": negative_control}


def boundary() -> dict:
    """The Tier-2 boundary, for the cadence and tests to read WITHOUT importing the SDK or running a
    session. The cadence reads this to know the monthly deep run is ASK, never an unattended motion."""
    return {
        "tier": 2,
        "name": "monthly resumable Managed Agents deep run",
        "gate": TIER2_GATE,                  # ask: spends sandbox time and stores state server-side
        "beta_header": BETA_HEADER,
        "agent_toolset": AGENT_TOOLSET,
        "model": AGENT_MODEL,
        "state_path": str(STATE_PATH.relative_to(ROOT)) if STATE_PATH.is_relative_to(ROOT) else str(STATE_PATH),
        "not_zdr_eligible": True,
        "source_url": "https://platform.claude.com/docs/en/managed-agents/overview",
        "fetched_date": "2026-06-18",
        "note": "wired, not run. The cadence never calls the live functions; a live run is the "
                "operator's explicit ASK (run.py managed --apply), never an unattended motion.",
    }


def main(argv=None) -> int:
    import argparse

    p = argparse.ArgumentParser(
        description="engine/managed.py: the Tier-2 monthly resumable Managed Agents runtime, wired but "
                    "not run. By default it prints the boundary ($0, no session). --apply runs a live "
                    "session (spends a small bounded amount of Managed Agents time).")
    p.add_argument("--apply", action="store_true",
                   help="OPT-IN: run a live Managed Agents start + resume + negative control (spends a "
                        "small bounded amount); default prints the boundary and spends nothing")
    a = p.parse_args(argv)

    b = boundary()
    print("\n  Tier-2 monthly resumable runtime (Claude Managed Agents, beta). Wired, not run.\n")
    print(f"    gate:          {b['gate']} (spends sandbox time and stores state server-side)")
    print(f"    beta header:   {b['beta_header']} (the SDK sets it automatically, enabled by default)")
    print(f"    agent toolset: {b['agent_toolset']}")
    print(f"    model:         {b['model']}")
    print(f"    state path:    {b['state_path']} (committed, survives a clone)")
    print(f"    not ZDR/HIPAA-BAA eligible: {b['not_zdr_eligible']} (state stays server-side)")
    print(f"    source:        {b['source_url']} ({b['fetched_date']})")
    print(f"\n  {b['note']}")

    if not a.apply:
        print("\n  No session started. This is the wired-not-run default ($0). To run a live deep "
              "dive: run.py managed --apply\n")
        return 0

    print("\n  --apply: starting a live Managed Agents session (beta). This spends a small, bounded "
          "amount of Managed Agents sandbox time.\n")
    from common.client import load_env, repo_root
    load_env()
    result = prove()
    r = result.get("resumed") or {}
    neg = result.get("negative_control") or {}
    st = result.get("started") or {}
    print(f"  events on the first run:         {len(st.get('new_event_ids', []))}")
    print(f"  events replayed on resume:       {r.get('events_replayed_on_resume')}")
    print(f"  sandbox files present on resume: {r.get('sandbox_files_present')}")
    print(f"  resume wall-clock gap (s):       {r.get('resume_wall_clock_gap_s')}")
    print(f"  negative control recovered:      {neg.get('recovered')} (must be False)")
    (repo_root() / "data").mkdir(exist_ok=True)
    (repo_root() / "data" / "last_managed.json").write_text(json.dumps(result, indent=2, default=str) + "\n")
    print("\n  (live detail cached in gitignored data/last_managed.json)\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
