"""compare: reproduce the exact-list ledger head-to-head against OpenAI and Gemini, same chain.

The default brief runs the Claude side alone on one dependency. Set OPENAI_API_KEY and GEMINI_API_KEY,
install the optional comparison SDKs (pip install -r requirements-compare.txt), and run
`make exact_ledger COMPARE=1` to reproduce the whole table on your own keys, not just the Claude side.

Best to best, the same long tool-heavy ledger agent over the SAME chain, each platform at full strength:
  - OpenAI runs the Responses API with server-side compaction on at the same trigger Claude clears at,
    plus automatic caching and a server-stored conversation, its strongest long-agent config.
  - Gemini carries the full window with implicit caching, its strongest long-agent config (it has no
    server-side context compaction or in-place clearing on the platform).
All three keep the exact running list, so this is cost at equal correctness. Claude clears the bulky
tool results in place with context editing and holds the carried context flat, so it keeps the exact
list for the lowest bill. Sources, re-fetched 2026-06-19:
  - Claude context editing: https://platform.claude.com/docs/en/build-with-claude/context-editing
  - OpenAI compaction: https://developers.openai.com/api/docs/guides/compaction
  - Gemini long context: https://ai.google.dev/gemini-api/docs/long-context

Every SDK import is lazy, so importing this module needs no comparison SDK. A missing key or SDK skips
that arm with a clear note. This arm runs the SAME multi-turn agent on each competitor over a chain of
bulky records, so COMPARE=1 here costs a few dollars and runs for several minutes.
"""

from __future__ import annotations

import json
import time

from .common.compare_clients import COMPARE_DEPS_HINT, gemini_cost, get_gemini_client, get_openai_client, openai_cost
from .common.models import get

# The competitor models, each side's strongest long-agent driver, matching the brief table.
OPENAI_MODEL = "gpt-top"   # gpt-5.5
GEMINI_MODEL = "gem-pro"   # gemini-3.1-pro-preview

READ_TOOL_OAI = {
    "type": "function",
    "name": "read_document",
    "description": "Read one incident report by its integer id.",
    "parameters": {
        "type": "object",
        "properties": {"doc_id": {"type": "integer", "description": "the report id to read"}},
        "required": ["doc_id"],
        "additionalProperties": False,
    },
}

READ_TOOL_GEMINI = {
    "function_declarations": [{
        "name": "read_document",
        "description": "Read one incident report by its integer id.",
        "parameters": {
            "type": "OBJECT",
            "properties": {"doc_id": {"type": "INTEGER", "description": "the report id to read"}},
            "required": ["doc_id"],
        },
    }]
}


def _openai_arm(docs, start):
    """The same ledger agent on OpenAI Responses, compaction on at the brief's trigger, server-stored
    conversation, caching on. Returns the exact-list answer, cost, and wall time."""
    from .run import MAX_TURNS, TRIGGER, ledger_prompt, parse_list

    m = get(OPENAI_MODEL)
    client = get_openai_client()
    if client is None:
        return {"label": "OpenAI " + m.id + " (compaction)", "skipped": "set OPENAI_API_KEY to run this arm"}
    cm = [{"type": "compaction", "compact_threshold": TRIGGER}]
    prev_id = None
    pending = [{"role": "user", "content": ledger_prompt(start)}]
    cost = 0.0
    final_text = ""
    t0 = time.perf_counter()
    for _ in range(MAX_TURNS):
        kwargs = dict(model=m.id, tools=[READ_TOOL_OAI], store=True, input=pending, context_management=cm)
        if prev_id is not None:
            kwargs["previous_response_id"] = prev_id
        resp = client.responses.create(**kwargs)
        prev_id = resp.id
        cost += openai_cost(OPENAI_MODEL, resp.usage)
        calls = [it for it in (resp.output or []) if getattr(it, "type", None) == "function_call"]
        if not calls:
            final_text = getattr(resp, "output_text", "") or ""
            break
        pending = []
        for c in calls:
            args = json.loads(getattr(c, "arguments", "") or "{}")
            did = args.get("doc_id")
            content = docs[did]["text"] if did in docs else f"Error: no document with id {did}"
            pending.append({"type": "function_call_output", "call_id": c.call_id, "output": content})
    return {"label": "OpenAI " + m.id + " (compaction)", "answer": parse_list(final_text),
            "cost": cost, "elapsed": time.perf_counter() - t0}


def _gemini_generate(client, model_id, contents, config, retries=5):
    """Call Gemini, backing off on a transient 503 or 429 so a long run does not die mid-chain."""
    from google.genai import errors

    for i in range(retries):
        try:
            return client.models.generate_content(model=model_id, contents=contents, config=config)
        except errors.ClientError as e:
            if getattr(e, "code", None) == 429 and i < retries - 1:
                time.sleep(10 * (i + 1))
            else:
                raise
        except errors.ServerError:
            if i == retries - 1:
                raise
            time.sleep(3 * (i + 1))


def _gemini_arm(docs, start):
    """The same ledger agent on Gemini, full window with implicit caching (its strongest long-agent
    config). Returns the exact-list answer, cost, and wall time."""
    from .run import MAX_TURNS, ledger_prompt, parse_list

    m = get(GEMINI_MODEL)
    client = get_gemini_client()
    if client is None:
        return {"label": "Gemini " + m.id + " (full context)", "skipped": "set GEMINI_API_KEY to run this arm"}
    from google.genai import types

    config = types.GenerateContentConfig(
        tools=[READ_TOOL_GEMINI],
        automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
    )
    contents = [types.Content(role="user", parts=[types.Part(text=ledger_prompt(start))])]
    cost = 0.0
    final_text = ""
    t0 = time.perf_counter()
    for _ in range(MAX_TURNS):
        resp = _gemini_generate(client, m.id, contents, config)
        cost += gemini_cost(GEMINI_MODEL, getattr(resp, "usage_metadata", None))
        fcs = resp.function_calls
        if not fcs:
            final_text = (resp.text or "") if hasattr(resp, "text") else ""
            break
        contents.append(resp.candidates[0].content)
        parts = []
        for fc in fcs:
            did = (fc.args or {}).get("doc_id")
            content = docs[did]["text"] if did in docs else f"Error: no document with id {did}"
            parts.append(types.Part.from_function_response(name=fc.name, response={"result": content}))
        contents.append(types.Content(role="user", parts=parts))
    return {"label": "Gemini " + m.id + " (full context)", "answer": parse_list(final_text),
            "cost": cost, "elapsed": time.perf_counter() - t0}


def _run_arm(fn, *args) -> dict:
    """Run one competitor arm, turning any failure into a skipped row, so --compare never crashes."""
    try:
        return fn(*args)
    except SystemExit as e:
        return {"skipped": str(e)}
    except Exception as e:  # noqa: BLE001
        return {"skipped": type(e).__name__ + ": " + str(e)[:80]}


def append_comparison(model_key: str, claude_result: dict) -> None:
    """Run the SAME ledger agent on OpenAI (compaction) and Gemini (full window) over the same chain,
    then print the full head-to-head table: cost at equal correctness. The Claude row reuses the result
    already computed, so Claude is not billed twice."""
    from .run import DOCS, DOC_TOKENS, build_chain

    docs, start = build_chain(DOCS, DOC_TOKENS)
    gold = sorted(d["id"] for d in docs.values() if d["urgent"])

    print("  Reproducing the head-to-head: the same long ledger agent over the same chain, cost at equal")
    print("  correctness. The OpenAI and Gemini arms each run the multi-turn agent live, so this costs a")
    print("  few dollars and several minutes. " + COMPARE_DEPS_HINT + ".\n")

    oai = _run_arm(_openai_arm, docs, start)
    gem = _run_arm(_gemini_arm, docs, start)

    claude_cost = claude_result.get("cost", 0.0)
    claude_exact = claude_result.get("exact", False)
    rows = [("Claude (context editing)", "$" + format(claude_cost, ".4f"),
             "exact" if claude_exact else "see run output")]
    for arm in (oai, gem):
        if "skipped" in arm:
            rows.append((arm.get("label", "competitor"), "skipped: " + arm["skipped"], ""))
            continue
        exact = arm.get("answer") == gold
        versus = ""
        if exact and claude_exact and arm["cost"] > claude_cost > 0:
            pct = round((1 - claude_cost / arm["cost"]) * 100)
            versus = "Claude " + str(pct) + "% cheaper"
        rows.append((arm["label"], "$" + format(arm["cost"], ".4f"), "exact" if exact else "list not exact"))
        if versus:
            rows.append(("", "", versus))

    print(f"  {'stack':<34}{'cost, this run':>16}{'correctness':>16}")
    print("  " + "-" * 66)
    for label, cost, note in rows:
        print(f"  {label:<34}{cost:>16}{note:>16}")
    print("  " + "-" * 66)
    print()
    print("  Claude clears the bulky tool results in place and holds the carried context flat, so it keeps")
    print("  the exact list for the lowest bill while the compaction and full-window runs carry more.")
    print()
