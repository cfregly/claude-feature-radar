"""retention_resume: does a stateful platform feature survive a kill and re-attach, and how does the
retention compare across vendors? The honest read is doc-grounded PARITY on the capability, with a real
but narrower win on the managed-harness bundle and the time axis.

The continuity engine: start a live Claude Managed Agents session, kill the client, re-attach off the
server-side event log, replay the prior events, tail only the new ones, and report what survived
(events replayed, sandbox files present, resume gap), with a wrong-session-id negative control and a
mid-run steer.

WHY THE DEFAULT IS A DOC-GROUNDED PARITY RECEIPT, NOT A CLAUDE-ONLY CLAIM. The grounded landscape check
(live vendor docs, fetched 2026-06-18) corrects this edge: durable kill-and-resume is table stakes
across all three vendors, not a Claude-only capability.
  - OpenAI ships GA durable state: the Responses API Conversations object persists across sessions,
    devices, and jobs with no 30-day TTL, and the OpenAI Agents SDK adds file-backed sessions that
    survive a process restart and resume a paused run from any backend on the same store.
  - Gemini Live API resumes via SessionResumptionConfig within a roughly 2-hour handle window (the
    7-day figure an earlier brief carried is UNVERIFIED, held until sourced; a full Gemini managed-agent
    runtime parity pass needs the Vertex AI Agent Engine docs, which were not reachable, so any
    "Gemini has no managed agent runtime" line is held never-evaluated).
So the verdict is NEVER claude-ahead. It is doc-grounded parity on the capability. Claude's genuine,
defensible edge is two things, both labeled beta: the fully MANAGED HARNESS bundle (an Anthropic-hosted
or self-hosted sandbox plus the agent loop plus a persistent filesystem plus conversation history plus
built-in compaction in one product, so the founder builds no agent loop, sandbox, or tool layer) and
the strongest persistence on the time axis (no 30-day TTL like OpenAI standalone responses, no 2-hour
handle cap like Gemini Live). Because state stays server-side, Managed Agents is not ZDR- or
HIPAA-BAA-eligible, and that caveat is named in the receipt.

WHAT RUNS HERE BY DEFAULT: NOTHING LIVE, NO SPEND. The demonstrator's default Claude arm is the
doc-grounded parity receipt: a dated retention/bundle comparison built from the live vendor docs, with
zero Managed Agents spend. The live kill-and-resume run (start_session, resume_session, steer_session,
prove) is an OPT-IN the operator triggers explicitly with `make retention-live` (or
`prove(live=True)`), never on a schedule and never inside this default path. When it does run, its
verdict is still within-claude-only (a continuity proof plus a bundle convenience lead, labeled beta),
paired with the dated retention table, never a head-to-head capability win.

GROUNDING. Every Managed Agents claim traces to platform.claude.com/docs/en/managed-agents/overview,
fetched 2026-06-18: the beta header is `managed-agents-2026-04-01` (the SDK sets it automatically),
Managed Agents is enabled by default for all API accounts, sessions are stateful by design and resume
cleanly after pauses, event history is persisted server-side and can be fetched in full, and it is not
ZDR- or HIPAA-BAA-eligible. The competitor retention facts trace to each vendor's own docs, dated. The
surface is beta and moves monthly, so re-ground the header before quoting (scripts/check_docs.py
asserts the README names the header this module sends).

DEPENDENCIES. The default parity receipt needs NOTHING (stdlib only, no key, no network, no SDK): it is
the dated doc-grounded comparison. The opt-in live run needs ANTHROPIC_API_KEY and a current anthropic
SDK with the Managed Agents beta, pulled in lazily inside the live functions so the one-dependency core
never imports the SDK at load. No competitor SDK is called: the cross-vendor comparison is doc-grounded
by construction (the capability is parity, so there is no head-to-head arm to run), which is exactly the
honest shape for a parity edge.
"""

from __future__ import annotations

import json
import os
import pathlib
import sys
import time

# repo root on the path, for common/ and engine/ when run as a script.
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))

from engine.demonstrators.base import Arm, BaseDemonstrator, CostEstimate, Verdict
from engine.demonstrators.registry import register
from engine.demonstrators.shared import platform

# --------------------------------------------------------------------------- grounded facts (no spend)
#
# The dated retention/bundle comparison. Every row traces to a live doc, fetched 2026-06-18. This is the
# default receipt: a parity edge is proven by grounding, not by a head-to-head arm, because the
# capability itself is parity. The win Claude carries is the bundle and the time axis, both labeled beta.

BETA_HEADER = "managed-agents-2026-04-01"  # the SDK sets it automatically; platform.claude.com, 2026-06-18
AGENT_TOOLSET = "agent_toolset_20260401"   # the built-in bash/file toolset the source live run sends

# The doc-grounded retention table. Each entry: the vendor, its durable-resume mechanism, the time-axis
# bound that is the real differentiator, and the source url + date. Counted the same way on every side
# (the persistence ceiling on the durable surface), so the comparison is apples-to-apples.
RETENTION_TABLE = [
    {
        "vendor": "Claude",
        "mechanism": "Managed Agents sessions (beta), stateful by design, resume cleanly after pauses, "
                     "event history persisted server-side and fetchable in full",
        "time_axis": "no 30-day TTL and no idle handle cap on the session; state stays server-side "
                     "(so not ZDR- or HIPAA-BAA-eligible)",
        "maturity": "beta (" + BETA_HEADER + ", enabled by default, SDK sets the header)",
        "source_url": "https://platform.claude.com/docs/en/managed-agents/overview",
        "date": "2026-06-18",
    },
    {
        "vendor": "OpenAI",
        "mechanism": "Responses API Conversations object (GA), used across sessions, devices, and jobs; "
                     "Agents SDK file-backed sessions survive a process restart and resume a paused run",
        "time_axis": "conversation items have no 30-day TTL; standalone response objects default to "
                     "30-day retention (store=false to disable)",
        "maturity": "GA",
        "source_url": "https://developers.openai.com/api/docs/guides/conversation-state",
        "date": "2026-06-18",
    },
    {
        "vendor": "Gemini",
        "mechanism": "Live API session resumption via SessionResumptionConfig: capture the handle, "
                     "reconnect within the window",
        "time_axis": "resumption handle valid for about 2 hours after the session ends (a full managed "
                     "agent-runtime parity pass needs the Vertex AI Agent Engine docs, held "
                     "never-evaluated)",
        "maturity": "GA (Live API)",
        "source_url": "https://ai.google.dev/gemini-api/docs/live-session",
        "date": "2026-06-18",
    },
]

# The bundle win, stated as what the founder does NOT have to build, with the beta caveat attached.
BUNDLE_WIN = (
    "The managed-harness bundle is the genuine edge, labeled beta: an Anthropic-hosted or self-hosted "
    "sandbox plus the agent loop plus a persistent filesystem plus conversation history plus built-in "
    "compaction in one product, so the founder builds no agent loop, no sandbox, and no tool-execution "
    "layer. The capability of surviving a kill and resuming is parity across all three vendors; the "
    "bundle and the time axis are the win."
)


def grounded_receipt() -> dict:
    """The default, $0 retention receipt: the dated doc-grounded comparison plus the bundle win. No key,
    no network, no SDK, no spend. The capability is parity, so this IS the proof for a parity edge: the
    grounding, not a head-to-head arm that would only re-show parity."""
    return {
        "verdict": "doc-grounded-parity",
        "capability": "durable kill-and-resume is table stakes across Claude, OpenAI, and Gemini",
        "claude_win": BUNDLE_WIN,
        "beta_header": BETA_HEADER,
        "not_zdr_eligible": True,
        "retention_table": RETENTION_TABLE,
        "live_run": None,  # filled only when the opt-in live kill-resume runs
    }


# --------------------------------------------------------------------------- the live continuity engine
#
# OPT-IN ONLY: nothing here runs in the default path,
# on a schedule, or inside the Demonstrator interface methods below. The operator triggers it with
# `make retention-live`. It spends a small amount of Managed Agents time and is the live counterpart to
# the doc-grounded receipt. The SDK is imported lazily inside _client so the one-dependency core never
# loads anthropic at import.

STATE_PATH = pathlib.Path(os.environ.get(
    "RETENTION_STATE", str(pathlib.Path(__file__).resolve().parents[2] / "data" / "managed_state.json")))

AGENT_MODEL = os.environ.get("RETENTION_MODEL", "claude-sonnet-4-6")  # bound cost; opus for the strongest run

SYSTEM = (
    "You are a sandbox worker proving session continuity. You write a small ledger of finished work to "
    "files and run shell commands. Keep it tight, and never re-do a step already recorded in the ledger."
)


def _night1_task() -> str:
    """The first task: write a small ledger of finished work to the sandbox filesystem, so a resume has
    something concrete to recover. Deterministic, no model key needed inside the sandbox."""
    return (
        "Do this, then stop:\n"
        "1. Write a file work.md listing three steps you will do: step-a, step-b, step-c.\n"
        "2. Create a file ledger.txt and append the line 'step-a done' to it.\n"
        "3. Append 'step-b done' to ledger.txt.\n"
        "4. Run `ls -la` and `cat ledger.txt`, then stop. Leave step-c for later."
    )


def _resume_task() -> str:
    """The resume task: read the ledger off the same sandbox, finish only the missing step. This is what
    makes the continuity measurable: the agent must see the work it already did, persisted server-side."""
    return (
        "You are resuming a session you started earlier. The sandbox is the same one. Do this, then stop:\n"
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
    events that were replayed off the server-side log, with the bash-output capture so the resume can
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


def _client():
    from common.client import managed_client  # lazy: the SDK is pulled only on the opt-in live path

    return managed_client()


def _persisted_session_id() -> str:
    return json.loads(STATE_PATH.read_text())["session_id"]


def start_session(max_events: int = 400) -> dict:
    """Create a real agent, environment, and session, run the ledger task in the hosted sandbox, persist
    the ids, and return the receipt. OPT-IN, spends Managed Agents time."""
    client = _client()
    platform.used("managed_agents", f"live session, beta {BETA_HEADER}")

    env = client.beta.environments.create(
        name="retention-env",
        config={"type": "cloud", "networking": {"type": "unrestricted"}},
    )
    agent = client.beta.agents.create(
        name="retention-worker",
        model=AGENT_MODEL,
        system=SYSTEM,
        tools=[{"type": AGENT_TOOLSET}],
    )
    session = client.beta.sessions.create(
        agent=agent.id, environment_id=env.id, title="Retention continuity",
    )

    with client.beta.sessions.events.stream(session.id) as stream:
        client.beta.sessions.events.send(
            session.id,
            events=[{"type": "user.message",
                     "content": [{"type": "text", "text": _night1_task()}]}],
        )
        drained = _drain(stream, max_events)

    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    state = {"session_id": session.id, "agent_id": agent.id,
             "environment_id": env.id, "model": AGENT_MODEL}
    STATE_PATH.write_text(json.dumps(state, indent=2) + "\n")
    return {**state, "events_seen": len(drained["new_event_ids"]), **drained}


def resume_session(session_id: str | None = None, max_events: int = 400) -> dict:
    """Re-attach to a session by id with the documented reconnect pattern: retrieve the status, list the
    prior events to replay them off the server-side log, then open the stream, send the follow-up, and
    continue. A wrong or expired session id is the negative control: retrieve or list raises and we
    report recovered False, so the clean resume is attributable to server-side persistence, with the
    sandbox-files-present check added off the resume bash output."""
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

    # the ledger written on night one must still be in the sandbox after the kill, proven by the resume
    # bash output referencing the prior steps. This is the "sandbox state survived" half of the receipt.
    present = "step-a done" in drained.get("tool_output", "")
    return {
        "session_id": session_id, "recovered": True, "status": status,
        "events_replayed_on_resume": len(seen_ids), "resume_wall_clock_gap_s": gap,
        "sandbox_files_present": present, **drained,
    }


def steer_session(session_id: str | None, text: str, max_events: int = 200) -> dict:
    """Steer a live session: send an interrupt to pause the agent, then a new message that redirects it.
    The interrupt goes before the message so the redirect lands on a paused agent. Returns the tool
    calls that follow, so a with-steer run can be compared against an un-steered tail."""
    client = _client()
    if session_id is None:
        session_id = _persisted_session_id()

    seen_ids = {getattr(e, "id", None)
                for e in client.beta.sessions.events.list(session_id, order="asc")}
    seen_ids.discard(None)

    with client.beta.sessions.events.stream(session_id) as stream:
        client.beta.sessions.events.send(session_id, events=[{"type": "user.interrupt"}])
        client.beta.sessions.events.send(
            session_id,
            events=[{"type": "user.message",
                     "content": [{"type": "text", "text": text}]}],
        )
        drained = _drain(stream, max_events, seen_ids=seen_ids)

    return {"session_id": session_id, "steered": True, "steer_text": text, **drained}


def prove(max_events: int = 400) -> dict:
    """The full live continuity receipt: start a session, re-attach without steering, run the negative
    control (a wrong session id that must recover nothing), then steer and report how the next tool
    calls diverge from the un-steered tail. OPT-IN, spends Managed Agents time. Every number is measured
    from the live run, not asserted."""
    started = start_session(max_events)
    sid = started["session_id"]
    resumed = resume_session(sid, max_events)
    negative_control = resume_session("sesn_" + "0" * 24, max_events=8)
    steered = steer_session(sid, "From here on, only print the ledger, do not append anything new.", max_events)
    return {"started": started, "resumed": resumed,
            "negative_control": negative_control, "steered": steered}


def continuity_passed(live: dict) -> tuple[bool, dict]:
    """The continuity gate on a live prove() result: events were replayed off the log, the sandbox files
    are still present, the resume gap is measured, AND the wrong-session-id negative control recovered
    nothing (so the clean resume is attributable to server-side persistence, not luck). Returns
    (passed, the per-check metric). This is the SAME machine-checkable gate the receipt reports, applied
    only when the opt-in live run produced a result."""
    resumed = live.get("resumed") or {}
    neg = live.get("negative_control") or {}
    checks = {
        "events_replayed": int(resumed.get("events_replayed_on_resume", 0)),
        "sandbox_files_present": bool(resumed.get("sandbox_files_present", False)),
        "resume_gap_s": resumed.get("resume_wall_clock_gap_s"),
        "recovered": bool(resumed.get("recovered", False)),
        "negative_control_recovered": bool(neg.get("recovered", False)),
        "steer_tool_calls": len((live.get("steered") or {}).get("tools_used", [])),
    }
    passed = (
        checks["recovered"]
        and checks["events_replayed"] > 0
        and checks["sandbox_files_present"]
        and checks["negative_control_recovered"] is False
    )
    return passed, checks


# --------------------------------------------------------------------------- the Demonstrator interface
#
# retention_resume: a stateful feature survives a kill and re-attach. The default arm is the doc-grounded
# PARITY receipt (no spend), per the managedAgentsCorrection: durable kill-and-resume is table stakes,
# so the verdict is NEVER claude-ahead. It is doc-grounded-parity, and the win Claude carries is the
# managed-harness bundle and the time axis, labeled beta. The optional live kill-resume run is folded in
# only when the operator passes it on the spec (spec["live"] is a prove() result), and even then the
# verdict stays within-claude-only (a continuity proof plus a bundle convenience lead), never a
# head-to-head capability win. No competitor arm runs: a parity capability has no head-to-head arm to
# run, so the comparison is doc-grounded by construction, which is the honest shape for a parity edge.

class RetentionResumeDemonstrator(BaseDemonstrator):
    demo_kind = "retention_resume"

    def estimate(self, edge, spec):
        spec = spec or {}
        if spec.get("live"):
            # the opt-in live kill-resume run spends a small amount of Managed Agents time.
            return CostEstimate(
                usd=1.5, wall_clock_s=240.0, command="make retention-live",
                note="OPT-IN live Managed Agents kill-and-resume (start, resume, negative control, "
                     "steer) on Sonnet; bounded sandbox time, a few minutes, well under the per-demo cap",
            )
        # the default is the $0 doc-grounded parity receipt: no key, no network, no spend.
        return CostEstimate(
            usd=0.0, wall_clock_s=1.0, command="make retention",
            note="the default doc-grounded retention/bundle comparison; no Managed Agents spend (the "
                 "live kill-resume is the opt-in make retention-live)",
        )

    def run_claude_arm(self, edge, spec):
        """The Claude side. By default the doc-grounded parity receipt (no spend, no SDK). When the
        operator passes a live prove() result on spec['live'], the continuity numbers are folded into the
        arm metric, and the verdict stays within-claude-only (a continuity proof, not a head-to-head)."""
        spec = spec or {}
        platform.used("grounding", "doc-grounded retention/bundle comparison (no spend)")
        metric = {
            "verdict_basis": "doc-grounded-parity",
            "capability": "durable kill-and-resume is parity across Claude, OpenAI, Gemini",
            "claude_win": "managed-harness bundle + time axis, beta " + BETA_HEADER,
            "not_zdr_eligible": True,
            "retention_table": RETENTION_TABLE,
        }
        live = spec.get("live")
        if live:
            passed, checks = continuity_passed(live)
            metric["live_continuity"] = checks
            metric["live_continuity_passed"] = passed
            note = ("live kill-resume continuity proof folded in; still within-Claude (a bundle + "
                    "continuity proof, not a head-to-head capability win), beta")
        else:
            note = ("doc-grounded parity receipt, no Managed Agents spend; the live kill-resume is the "
                    "opt-in make retention-live")
        return Arm(provider="anthropic", model=AGENT_MODEL, ran=True, cost_usd=0.0, metric=metric, note=note)

    def run_competitor_arms(self, edge, spec):
        """No live competitor arm runs. Durable kill-and-resume is a doc-grounded PARITY capability, so
        there is no head-to-head arm to run that would show anything but parity; the comparison lives in
        the dated retention table on the Claude arm. Returning an empty list is the honest shape for a
        parity edge, and it keeps receipt() from ever reading a claude-ahead verdict (the base honesty
        contract holds a claude-ahead verdict only when every competitor arm RAN, and none did, so the
        verdict can never be claude-ahead here, which is exactly the managedAgentsCorrection)."""
        return []

    def score(self, claude, competitors, spec):
        """The gate. The verdict is doc-grounded parity by construction (capability is table stakes), so
        score NEVER returns claude-ahead. When the opt-in live run is present, the SAME machine-checkable
        continuity gate (events replayed, sandbox files present, resume gap measured, negative control
        recovered nothing) decides whether the within-Claude continuity proof passed; absent the live
        run, the parity verdict stands and passed reflects whether the doc-grounded comparison is
        complete (the retention table is present)."""
        spec = spec or {}
        live = spec.get("live")
        table_ok = bool(claude.metric.get("retention_table"))
        if live:
            passed, checks = continuity_passed(live)
            verdict = "within-claude-only"
            note = ("live continuity proof: " + ("PASSED" if passed else "did not pass") +
                    " the kill-resume gate; the cross-vendor capability is doc-grounded parity, so this "
                    "is a within-Claude continuity + bundle proof, never a head-to-head lead")
            metric = {"verdict_basis": "within-claude-only (live continuity proof + bundle, beta)",
                      "live_continuity": checks, "retention_table_present": table_ok}
        else:
            passed = table_ok
            verdict = "parity"
            note = ("doc-grounded parity: durable kill-and-resume is table stakes across all three "
                    "vendors; the Claude win is the managed-harness bundle and the time axis, beta " +
                    BETA_HEADER + ", and state stays server-side so it is not ZDR-eligible")
            metric = {"verdict_basis": "doc-grounded-parity", "retention_table_present": table_ok,
                      "claude_win": "managed-harness bundle + time axis (beta)"}
        return Verdict(verdict=verdict, passed=passed, metric=metric, note=note)

    def receipt(self, edge, claude, competitors, verdict, spec):
        spec = spec or {}
        live = spec.get("live")
        task_shape = ("a dated doc-grounded retention/bundle comparison across Claude Managed Agents "
                      "(beta), OpenAI Responses Conversations + Agents SDK sessions, and Gemini Live API "
                      "session resumption; no live run by default")
        features_on = ["doc-grounded retention table (3 vendors, dated)",
                       "managed-harness bundle framing (beta, labeled)"]
        if live:
            task_shape = ("a LIVE Claude Managed Agents kill-and-resume: start a session, kill the "
                          "client, re-attach off the server-side event log, replay events, check the "
                          "sandbox files survived, with a wrong-session-id negative control and a "
                          "mid-run steer; paired with the dated retention table")
            features_on = ["live Managed Agents session (beta " + BETA_HEADER + ")",
                           "server-side event-log replay", "sandbox-state survival check",
                           "wrong-session-id negative control", "mid-run steer",
                           "the dated retention table"]
        return self.build_receipt(
            edge, claude, competitors, verdict, spec,
            workload={
                "task_shape": task_shape,
                "models": {"claude": claude.model, "competitors": "doc-grounded (no live competitor arm)"},
                "features_on": features_on,
                "assumptions": ("durable kill-and-resume is a PARITY capability across all three vendors, "
                                "so there is no head-to-head arm to run; the receipt proves the parity "
                                "with dated docs and names the genuine Claude win (the managed-harness "
                                "bundle and the time axis), labeled beta. State stays server-side, so "
                                "Managed Agents is not ZDR- or HIPAA-BAA-eligible. The live kill-resume "
                                "is opt-in (make retention-live) and never runs on a schedule"),
                "scope": "proves the loop survives a kill and the retention terms, NOT eval quality",
            },
            grounding=[
                {"claim": "Managed Agents sessions are stateful by design, resume cleanly after pauses, "
                          "event history persisted server-side and fetchable in full; beta header "
                          + BETA_HEADER + ", enabled by default, SDK sets it; not ZDR- or HIPAA-BAA-eligible",
                 "source_url": "https://platform.claude.com/docs/en/managed-agents/overview",
                 "date": "2026-06-18"},
                {"claim": "OpenAI Responses Conversations is GA and durable (no 30-day TTL on items); the "
                          "Agents SDK file-backed sessions survive a process restart and resume a paused run",
                 "source_url": "https://developers.openai.com/api/docs/guides/conversation-state",
                 "date": "2026-06-18"},
                {"claim": "Gemini Live API resumes via SessionResumptionConfig within about a 2-hour "
                          "handle window; the 7-day figure is unverified and a full Gemini managed-agent "
                          "runtime parity pass needs the Vertex AI Agent Engine docs (held never-evaluated)",
                 "source_url": "https://ai.google.dev/gemini-api/docs/live-session",
                 "date": "2026-06-18"},
            ],
            fairness={
                "best_to_best": "the comparison uses each vendor's strongest durable-resume surface "
                                "(Claude Managed Agents beta, OpenAI Responses Conversations + Agents "
                                "SDK GA, Gemini Live resumption GA), never a handicapped competitor",
                "isolate": "the retention table counts the same thing on every side (the persistence "
                           "ceiling on the durable surface), so the time-axis comparison is "
                           "apples-to-apples; the bundle win is stated as what the founder does not "
                           "have to build, not as a capability the others lack",
            },
        )


register(RetentionResumeDemonstrator())


# --------------------------------------------------------------------------- the CLI receipt

def _print_grounded(receipt: dict) -> None:
    print("\n  === Durable kill-and-resume: doc-grounded parity, with a bundle + time-axis win ===\n")
    print("  Capability verdict: PARITY. " + receipt["capability"] + ".")
    print("  Durable kill-and-resume is table stakes, so this is never pitched as a Claude-only edge.\n")
    print(f"  {'vendor':<9}{'durable-resume mechanism (best surface)':<62}{'time axis'}")
    print("  " + "-" * 110)
    for row in receipt["retention_table"]:
        mech = (row["mechanism"][:58] + "...") if len(row["mechanism"]) > 60 else row["mechanism"]
        ta = (row["time_axis"][:38] + "...") if len(row["time_axis"]) > 40 else row["time_axis"]
        print(f"  {row['vendor']:<9}{mech:<62}{ta}")
        print(f"  {'':<9}maturity: {row['maturity']}")
        print(f"  {'':<9}source: {row['source_url']} ({row['date']})")
    print("\n  The Claude win (labeled beta):")
    print("    " + receipt["claude_win"])
    print(f"\n  Beta header: {receipt['beta_header']} (the SDK sets it automatically, enabled by default).")
    print("  State stays server-side, so Managed Agents is not ZDR- or HIPAA-BAA-eligible.")
    print("\n  No Managed Agents spend on this default path. The live kill-and-resume is opt-in:")
    print("    make retention-live   (start, resume, negative control, steer; spends a small amount)")


def _print_live(live: dict) -> None:
    passed, checks = continuity_passed(live)
    print("\n  === LIVE Managed Agents kill-and-resume (opt-in, beta) ===\n")
    r = live.get("resumed") or {}
    neg = live.get("negative_control") or {}
    st = live.get("started") or {}
    print(f"  events on the first run:        {len(st.get('new_event_ids', []))}")
    print(f"  events replayed on resume:      {checks['events_replayed']}")
    print(f"  sandbox files present on resume:{str(checks['sandbox_files_present']):>6}")
    print(f"  resume wall-clock gap (s):      {checks['resume_gap_s']}")
    print(f"  negative control recovered:     {str(neg.get('recovered', False)):>6} (must be False)")
    print(f"  steer tool calls after redirect:{checks['steer_tool_calls']:>4}")
    print(f"\n  continuity gate: {'PASSED' if passed else 'DID NOT PASS'}")
    print("  Scope: this proves the loop survives a kill and the retention terms, NOT eval quality.")
    print("  Cross-vendor capability is doc-grounded parity, so this is a within-Claude continuity proof.")


def main(argv=None) -> int:
    import argparse

    from common.client import load_env, repo_root

    p = argparse.ArgumentParser(description="retention_resume: the doc-grounded retention/bundle parity "
                                            "receipt by default, the live Managed Agents kill-and-resume "
                                            "as an opt-in.")
    p.add_argument("--live", action="store_true",
                   help="OPT-IN: run the live Managed Agents kill-and-resume (spends a small amount); "
                        "default is the $0 doc-grounded parity receipt")
    a = p.parse_args(argv)

    receipt = grounded_receipt()
    if not a.live:
        print("\n  retention_resume: durable kill-and-resume is doc-grounded PARITY across all three")
        print("  vendors. The Claude win is the managed-harness bundle and the time axis, labeled beta.")
        _print_grounded(receipt)
        return 0

    # opt-in live path: spends a small amount of Managed Agents time.
    load_env()
    print("\n  retention_resume --live: running the live Managed Agents kill-and-resume (beta).")
    print("  This spends a small, bounded amount of Managed Agents sandbox time.\n")
    live = prove()
    receipt["live_run"] = live
    _print_grounded(receipt)
    _print_live(live)

    (repo_root() / "data").mkdir(exist_ok=True)
    (repo_root() / "data" / "last_retention.json").write_text(json.dumps(receipt, indent=2, default=str) + "\n")
    print("\n  (live detail cached in gitignored data/last_retention.json; this printout is the receipt)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
