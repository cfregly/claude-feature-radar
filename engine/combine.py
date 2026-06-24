"""combine: the active combinatorial edge generator.

Rule 16 of the engine (CLAUDE.md "Find the global edge" and "Check subfeatures AND combinations")
says a single Claude feature can read as parity while a STACK of two or three features on one workload
is a real edge, because the value compounds. The engine already ships one hand-built combination
demonstrator (engine/demonstrators/grounding_stack.py: Citations + native PDF + tool-returned search
results in one call) and the skeptic in engine/verify.py defensively checks combinations. This module
is the missing piece: it actively GENERATES new combination candidates across the whole platform
surface instead of waiting for a human to hand-code the next grounding_stack.

THE FLOW, two model calls, both on the top tier with adaptive thinking (this is a creative generation
and judgment seat, so tier tracks stakes x reasoning, not "default to cheap"):

  1. generate   Opus + adaptive thinking proposes feature stacks, each mapped to a founder workload,
                with the competitor's BEST counter-stack named and any mutually-exclusive conflict
                flagged. Forced tool use pins the output to a schema so there is nothing to parse.
  2. skeptic    Opus + adaptive thinking tries to break each one: KILLED if OpenAI or Gemini can
                assemble an equivalent best stack on the same workload, SURVIVES only when they cannot.
                The writer is never the grader (same discipline as engine/demonstrators/eval_quality).

Survivors persist to landscape/combinations.json (the durable spine, committed, survives a clone, per
CLAUDE.md "State survives a clone"). Each survivor is a candidate for a real demonstrator, the way
grounding_stack already proves its stack with a measured receipt. This module proposes; it does not
ship a claim. A combination ships only after a demonstrator measures it at promotable_edge: true.

This SPENDS (two Opus calls, cents-scale), so it is an ASK target in the gate model, never part of the
unattended $0 cadence. Run it with `make combine`.
"""

from __future__ import annotations

import argparse
import json
import os

from common.client import get_client, repo_root
from common.models import get, request_kwargs
from engine.budget import BudgetLedger
from engine.scan import current_edges

# The platform surface the generator stacks from. Grounded in the same enumeration CLAUDE.md and
# SKILL.md carry. The generator is told to ground each named feature against the live docs the engine
# already fetched under sources/, and to label maturity (GA vs beta) on anything it leans on.
FEATURES = [
    "prompt caching", "the Batch API", "the memory tool", "context editing", "Citations",
    "native PDF input", "tool-returned search results (search_result blocks)", "code execution",
    "programmatic tool calling (allowed_callers keeps tool outputs out of context)",
    "extended/adaptive thinking", "the effort knob", "the 1M-token context window",
    "forced tool use / structured outputs", "the advisor tool", "Managed Agents (beta)",
    "Agent Skills", "the MCP connector", "the model tiers (Haiku/Sonnet/Opus/Fable)",
]

# Mutually-exclusive pairs the engine has already verified (CLAUDE.md "Record combinations that
# conflict"). A conflict bounds which stacks are real and is itself a finding, so the generator must
# respect these and may surface new ones it grounds.
KNOWN_CONFLICTS = [
    "Citations and structured outputs return a 400 together",
    "tool-returned search results are incompatible with structured outputs",
    "context editing clear_tool_uses is not fully compatible with advisor blocks",
]

# Combinations the engine already proves, so the generator proposes NEW stacks, not these.
ALREADY_BUILT = [
    "Citations + native PDF + tool-returned search results in one request (the grounding_stack "
    "demonstrator: three mixed user-source types cited inline with typed pointers in a single call)",
]

PILLARS = ["cost", "speed", "reliability", "accuracy", "security"]

GEN_SYSTEM = (
    "You are a staff engineer who has shipped production agents on Anthropic Claude, OpenAI, and "
    "Google Gemini, and your job is to find COMBINATION edges on the Claude Developer Platform: a "
    "stack of two or three Claude features on ONE founder workload where the value COMPOUNDS beyond "
    "what any single feature gives, in a currency a founder pays for (cost, speed, reliability, "
    "accuracy, or security). A single feature that is parity alone can become "
    "a real edge when stacked. For each candidate: name the 2-3 features, the concrete founder "
    "workload that exercises the stack (the task, the agent shape, the document set or request "
    "volume), what compounds and in which currency, and the BEST equivalent stack OpenAI or Gemini "
    "could assemble for the same workload at the same request count. Flag any mutually-exclusive "
    "conflict between the features you stacked. Be honest: if the competitor's best stack matches it, "
    "say so in competitor_best_stack. Propose genuinely new stacks, not the ones already built."
)

SKEPTIC_SYSTEM = (
    "You are a skeptical startup CTO who has shipped on OpenAI, Google Gemini, and Anthropic Claude. "
    "For each proposed Claude feature COMBINATION, try to assemble an equivalent best stack on the "
    "SAME workload using OpenAI's or Gemini's own best features at the same request count. Be harsh. "
    "If either competitor can match the compounded value, the combination is KILLED. It SURVIVES only "
    "when no competitor stack can match it on the founder currency named. Reply with exactly one line "
    "per combination, in the form: <KILLED|SURVIVES> - <id> - <one sentence naming the competitor "
    "stack you tried and why it does or does not match>."
)

_TOOL = {
    "name": "record_combinations",
    "description": "Record the candidate Claude feature combinations.",
    "input_schema": {
        "type": "object",
        "properties": {
            "combinations": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "features": {"type": "array", "items": {"type": "string"},
                                     "description": "the 2-3 Claude features stacked"},
                        "workload": {"type": "string",
                                     "description": "the concrete founder workload that exercises the stack"},
                        "founder_axis": {"type": "string",
                                         "enum": PILLARS},
                        "compounded_value": {"type": "string",
                                             "description": "what the stack does that no single feature does, in the axis currency"},
                        "competitor_best_stack": {"type": "string",
                                                  "description": "the best equivalent stack OpenAI or Gemini could assemble"},
                        "conflict": {"type": "string",
                                     "description": "any mutually-exclusive pair among the features, or 'none'"},
                    },
                    "required": ["features", "workload", "founder_axis", "compounded_value",
                                 "competitor_best_stack", "conflict"],
                    "additionalProperties": False,
                },
            },
        },
        "required": ["combinations"],
        "additionalProperties": False,
    },
}


def _claude_effort() -> str:
    return os.environ.get("RADAR_CLAUDE_EFFORT", "xhigh")


def _max_tokens(default: int, env_name: str) -> int:
    raw = os.environ.get(env_name)
    if raw:
        return int(raw)
    return default * 4 if _claude_effort() == "max" else default


def _create_claude_message(client, **kwargs):
    if _claude_effort() == "max" or kwargs.get("max_tokens", 0) > 16000:
        with client.messages.stream(**kwargs) as stream:
            stream.until_done()
            return stream.get_final_message()
    return client.messages.create(**kwargs)


def _message_text(msg) -> str:
    return "".join(getattr(b, "text", "") for b in msg.content if getattr(b, "type", None) == "text").strip()


def _opus_kwargs():
    # The generator and the skeptic are creative-judgment seats: top tier with adaptive thinking and
    # xhigh effort. Tier tracks stakes x reasoning difficulty x volume (CLAUDE.md "Model tier tracks
    # stakes"). These are two low-volume calls per run, so the top tier costs pennies.
    return request_kwargs("opus", effort=_claude_effort(), adaptive_thinking=True)


def generate(client, budget: BudgetLedger, n: int = 7) -> list[dict]:
    """Opus + adaptive thinking proposes up to n combination candidates. The shape is pinned with a
    json_schema via output_config.format, NOT a forced tool: the live API rejects thinking when
    tool_choice forces a tool ("Thinking may not be enabled when tool_choice forces tool use"), while
    structured outputs is thinking-compatible, so this is how the generator gets to BOTH think hard and
    return a parseable shape. Falls back to a forced tool without thinking only if structured output is
    ever rejected, so the loop never dies on a platform change (the fallback is logged, never silent)."""
    edge_keys = ", ".join(e["key"] for e in current_edges())
    prompt = (
        f"The Claude features you may stack: {'; '.join(FEATURES)}.\n\n"
        f"Known mutually-exclusive conflicts to respect: {'; '.join(KNOWN_CONFLICTS)}.\n\n"
        f"Already proven, do NOT propose these: {'; '.join(ALREADY_BUILT)}.\n\n"
        f"The single-feature edges the engine already tracks: {edge_keys}. A combination is most "
        f"valuable when it compounds one of these into a stack a competitor cannot match.\n\n"
        f"Propose {n} genuinely new combination candidates, strongest first."
    )
    base = dict(max_tokens=_max_tokens(16000, "RADAR_COMBINE_GENERATE_MAX_TOKENS"), system=GEN_SYSTEM,
                messages=[{"role": "user", "content": prompt}])
    reservation = budget.preflight("combine:opus-generate", "opus", messages=base["messages"],
                                   max_tokens=base["max_tokens"], system=GEN_SYSTEM)
    try:
        msg = _create_claude_message(
            client,
            **base,
            model=get("opus").id,
            thinking={"type": "adaptive"},
            output_config={"effort": _claude_effort(),
                           "format": {"type": "json_schema", "schema": _TOOL["input_schema"]}},
        )
        budget.commit_usage(reservation, msg.usage)
        text = _message_text(msg)
        if not text:
            kinds = ", ".join(getattr(b, "type", "?") for b in msg.content)
            raise ValueError(f"generate returned no visible JSON text (content blocks: {kinds or 'none'})")
        combos = json.loads(text).get("combinations", [])
    except Exception as e:  # noqa: BLE001  resilience: if structured output is ever rejected, fall back
        budget.mark_failed(reservation, e)
        # to a forced tool WITHOUT thinking (forced-tool + thinking is itself rejected). Logged, never silent.
        print(f"  (note: structured-output generate failed, falling back to forced tool without thinking: {e})")
        reservation = budget.preflight("combine:opus-generate-fallback", "opus",
                                       messages=base["messages"], max_tokens=base["max_tokens"],
                                       system=GEN_SYSTEM)
        try:
            msg = _create_claude_message(
                client,
                **base, tools=[_TOOL], tool_choice={"type": "tool", "name": "record_combinations"},
                **request_kwargs("opus", effort=_claude_effort()))
        except Exception as fallback_error:  # noqa: BLE001
            budget.mark_failed(reservation, fallback_error)
            raise
        budget.commit_usage(reservation, msg.usage)
        block = next((b for b in msg.content if getattr(b, "type", None) == "tool_use"), None)
        combos = block.input.get("combinations", []) if block else []
    for i, c in enumerate(combos, 1):
        c["id"] = f"combo-{i}"
    return combos


def skeptic(client, combos: list[dict], budget: BudgetLedger) -> dict[str, tuple[str, str]]:
    """One batched Opus + adaptive thinking pass that tries to break each combination by assembling the
    competitor's best stack. Returns {id: (KILLED|SURVIVES, why)}. The writer is never the grader."""
    if not combos:
        return {}
    body = "\n\n".join(
        f"id: {c['id']}\nstack: {' + '.join(c['features'])}\nworkload: {c['workload']}\n"
        f"compounds ({c['founder_axis']}): {c['compounded_value']}\n"
        f"claimed competitor best: {c['competitor_best_stack']}"
        for c in combos
    )
    messages = [{"role": "user", "content": body}]
    max_tokens = _max_tokens(8000, "RADAR_COMBINE_SKEPTIC_MAX_TOKENS")
    reservation = budget.preflight("combine:opus-skeptic", "opus", messages=messages,
                                   max_tokens=max_tokens, system=SKEPTIC_SYSTEM)
    try:
        msg = _create_claude_message(
            client,
            max_tokens=max_tokens, system=SKEPTIC_SYSTEM,
            messages=messages,
            **_opus_kwargs(),
        )
    except Exception as e:
        budget.mark_failed(reservation, e)
        raise
    budget.commit_usage(reservation, msg.usage)
    text = _message_text(msg)
    if not text:
        kinds = ", ".join(getattr(b, "type", "?") for b in msg.content)
        raise SystemExit(
            f"combine skeptic returned no visible verdict text after {max_tokens} max_tokens "
            f"(content blocks: {kinds or 'none'})."
        )
    verdicts: dict[str, tuple[str, str]] = {}
    for line in text.splitlines():
        s = line.strip()
        if not s or " - " not in s:
            continue
        parts = [p.strip() for p in s.split(" - ", 2)]
        if len(parts) < 2:
            continue
        verdict = parts[0].upper().lstrip("-* ").strip()
        cid = parts[1]
        why = parts[2] if len(parts) > 2 else ""
        if verdict in ("KILLED", "SURVIVES"):
            verdicts[cid] = (verdict, why)
    if not verdicts:
        raise SystemExit("combine skeptic returned no parseable KILLED/SURVIVES verdicts")
    return verdicts


def main(argv=None):
    parser = argparse.ArgumentParser(description="Generate feature-stack candidates under a budget cap.")
    parser.add_argument("--budget-usd", type=float, default=None,
                        help="Daily budget cap. Defaults to RADAR_BUDGET_USD or $2.")
    parser.add_argument("--budget-label", default=None,
                        help="Budget ledger label. Defaults to RADAR_BUDGET_LABEL or grind-deep.")
    args = parser.parse_args(argv)
    budget = BudgetLedger.from_env(cap_usd=args.budget_usd, label=args.budget_label)
    client = get_client()
    print(f"\n  Combinatorial generation ({get('opus').label}, {_claude_effort()} effort, adaptive thinking): stacking the "
          f"platform surface for compounding edges...\n")
    combos = generate(client, budget)
    if not combos:
        raise SystemExit("  the generator returned no combinations (check the API response)")

    verdicts = skeptic(client, combos, budget)
    for c in combos:
        v, why = verdicts.get(c["id"], ("UNJUDGED", ""))
        c["skeptic_verdict"] = v
        c["skeptic_why"] = why

    survivors = [c for c in combos if c["skeptic_verdict"] == "SURVIVES"]
    print(f"  {len(combos)} proposed, {len(survivors)} survived the competitor-stack skeptic:\n")
    for c in combos:
        mark = {"SURVIVES": "KEEP", "KILLED": "kill", "UNJUDGED": "??? "}.get(c["skeptic_verdict"], "??? ")
        print(f"    [{mark}] {' + '.join(c['features'])}")
        print(f"           workload: {c['workload']}")
        print(f"           compounds ({c['founder_axis']}): {c['compounded_value']}")
        if c.get("conflict") and c["conflict"].lower() != "none":
            print(f"           conflict: {c['conflict']}")
        print(f"           skeptic: {c['skeptic_verdict']} - {c['skeptic_why']}")
        print()

    out = {
        "generated_by": get("opus").label + " + adaptive thinking",
        "proposed": len(combos),
        "survived": len(survivors),
        "combinations": combos,
        "note": "Candidates only. A combination ships only after a demonstrator measures it at "
                "promotable_edge: true, the way engine/demonstrators/grounding_stack.py proves its stack. "
                "competitor_best_stack and the skeptic verdict are the internal both-directions read.",
    }
    dest = repo_root() / "landscape" / "combinations.json"
    dest.write_text(json.dumps(out, indent=2) + "\n")
    print(f"  wrote {dest.relative_to(repo_root())} ({len(survivors)} survivors to consider building).\n")


if __name__ == "__main__":
    main()
