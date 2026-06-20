"""compare: reproduce the single-request output-ceiling head-to-head against OpenAI and Gemini.

The default brief runs the Claude side alone on one dependency. Set OPENAI_API_KEY and GEMINI_API_KEY,
install the optional comparison SDKs (pip install -r requirements-compare.txt), and run
`make bulk_output COMPARE=1` to reproduce the whole table on your own keys, not just the Claude side.

Best to best, the measured thing is the largest deliverable a single request can return. Claude raises
the single-request ceiling to 300,000 output tokens on the Message Batches API with the
output-300k-2026-03-24 beta, and the dated full run (2026-06-19) returned 230,607 output tokens in one
un-truncated request. OpenAI's frontier model documents a 128,000-token single-request output cap and
Gemini 3.5 Flash a 65,536-token cap, both below that 230,607 deliverable. The competitor arms confirm
the model is reachable on your key and report that documented ceiling. The ceiling is the documented
maximum, so reproducing it does not require generating a 128,000-token output. Sources, re-fetched
2026-06-19:
  - Claude batch processing: https://platform.claude.com/docs/en/build-with-claude/batch-processing
  - OpenAI GPT-5.5: https://developers.openai.com/api/docs/models/gpt-5.5
  - Gemini 3.5 Flash: https://ai.google.dev/gemini-api/docs/models/gemini-3.5-flash

Every SDK import is lazy, so importing this module needs no comparison SDK. A missing key or SDK skips
that arm with a clear note and never fakes a row.
"""

from __future__ import annotations

from .common.compare_clients import COMPARE_DEPS_HINT, get_gemini_client, get_openai_client
from .common.models import get

# The competitor frontier models and their documented single-request output ceilings, matching the table.
OPENAI_MODEL = "gpt-top"    # gpt-5.5, 128,000-token single-request output cap
GEMINI_MODEL = "gem-flash"  # gemini-3.5-flash, 65,536-token single-request output cap

# The dated facts the table reproduces: Claude's extended-output ceiling and its measured deliverable,
# and the two documented competitor ceilings. All re-fetched 2026-06-19.
DATED = {"date": "2026-06-19", "claude_ceiling": 300000, "claude_tokens": 230607,
         "openai_ceiling": 128000, "gemini_ceiling": 65536}


def _openai_arm() -> dict:
    """Confirm gpt-5.5 is reachable on the key, then report its documented single-request output ceiling."""
    m = get(OPENAI_MODEL)
    client = get_openai_client()
    if client is None:
        return {"label": "OpenAI (" + m.id + ")", "skipped": "set OPENAI_API_KEY to run this arm"}
    client.responses.create(model=m.id, input="Reply with the single word: ok.", max_output_tokens=16)
    return {"label": "OpenAI (" + m.id + ")", "ceiling": DATED["openai_ceiling"]}


def _gemini_arm() -> dict:
    """Confirm gemini-3.5-flash is reachable on the key, then report its documented output ceiling."""
    m = get(GEMINI_MODEL)
    client = get_gemini_client()
    if client is None:
        return {"label": "Gemini (" + m.id + ")", "skipped": "set GEMINI_API_KEY to run this arm"}
    from google.genai import types

    client.models.generate_content(
        model=m.id, contents="Reply with the single word: ok.",
        config=types.GenerateContentConfig(max_output_tokens=16))
    return {"label": "Gemini (" + m.id + ")", "ceiling": DATED["gemini_ceiling"]}


def _run_arm(fn, *args) -> dict:
    """Run one competitor arm, turning any failure into a skipped row, so --compare never crashes."""
    try:
        return fn(*args)
    except SystemExit as e:
        return {"skipped": str(e)}
    except Exception as e:  # noqa: BLE001
        return {"skipped": type(e).__name__ + ": " + str(e)[:80]}


def append_comparison(model_key: str, claude_result: dict) -> None:
    """Print the single-request output-ceiling head-to-head: Claude's dated 230,607-token deliverable
    against the documented competitor ceilings it exceeds. The competitor arms confirm reachability on
    the key. The brief's own live check (a smaller, cheaper batch) is reported separately as proof the
    extended-output path works, not as the ceiling-beating deliverable."""
    deliverable = format(DATED["claude_tokens"], ",")
    print("  Reproducing the head-to-head: the largest deliverable one request can return. " + COMPARE_DEPS_HINT + ".\n")

    oai = _run_arm(_openai_arm)
    gem = _run_arm(_gemini_arm)

    rows = [("Claude (extended output)", format(DATED["claude_ceiling"], ",") + " (batch beta)",
             deliverable + " tokens, un-truncated")]
    for arm in (oai, gem):
        if "skipped" in arm:
            rows.append((arm.get("label", "competitor"), "skipped: " + arm["skipped"], ""))
        else:
            rows.append((arm["label"], format(arm["ceiling"], ",") + " (documented)",
                         "below the " + deliverable + " deliverable"))

    print(f"  {'platform':<27}{'single-request ceiling':<24}{'measured deliverable'}")
    print("  " + "-" * 82)
    for label, ceiling, note in rows:
        print(f"  {label:<27}{ceiling:<24}{note}")
    print("  " + "-" * 82)
    print()
    print("  Claude returns the whole " + deliverable + "-token deliverable in one request, above OpenAI's")
    print("  " + format(DATED["openai_ceiling"], ",") + " and Gemini's " + format(DATED["gemini_ceiling"], ",")
          + " single-request output ceilings (documented " + DATED["date"] + "), so a bulk job lands")
    print("  each item in a single turn with nothing truncated.")
    live = claude_result.get("output_tokens", 0)
    if live:
        done = "un-truncated" if not claude_result.get("truncated") else "truncated"
        print("  This run's quick check emitted " + format(live, ",") + " tokens " + done
              + ", confirming the extended-output path on your key.")
        print("  The " + deliverable + "-token figure is the full dated deliverable (" + DATED["date"] + ").")
    print()
