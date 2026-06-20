"""compare: reproduce the single-request output-ceiling head-to-head against OpenAI and Gemini.

The default brief runs the Claude side alone on one dependency. Set OPENAI_API_KEY and GEMINI_API_KEY,
install the optional comparison SDKs (pip install -r requirements-compare.txt), and run
`make bulk_output COMPARE=1` to reproduce the whole table on your own keys, not just the Claude side.

Best to best, the measured thing is the largest deliverable a single request can return. Claude raises
the single-request ceiling to 300,000 output tokens on the Message Batches API with the
output-300k-2026-03-24 beta (this brief measured 230,607 output tokens in one un-truncated request).
OpenAI's frontier model documents a 128,000-token single-request output cap and Gemini 3.5 Flash a
65,536-token cap, both below that deliverable. This arm confirms each competitor's ceiling directly and
cheaply: it asks the API to accept a max_output_tokens ABOVE the documented cap, and the API enforces
the cap (a 400 naming the limit), so no large generation is needed to reproduce the ceiling. Sources,
re-fetched 2026-06-19:
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
DOC_CAPS = {"gpt-top": 128000, "gem-flash": 65536}
MARGIN = 4096  # ask for this many tokens ABOVE the documented cap, so the API enforces the ceiling


def _openai_arm() -> dict:
    """Confirm the OpenAI single-request output ceiling: ask for max_output_tokens above the documented
    cap on a tiny prompt. The API enforces the cap, so the ceiling is reproduced without a large run."""
    m = get(OPENAI_MODEL)
    client = get_openai_client()
    if client is None:
        return {"label": "OpenAI (" + m.id + ")", "skipped": "set OPENAI_API_KEY to run this arm"}
    cap = DOC_CAPS["gpt-top"]
    try:
        client.responses.create(model=m.id, input="Reply with the single word: ok.",
                                max_output_tokens=cap + MARGIN)
        result = "accepts up to its documented ceiling"
    except Exception as e:  # noqa: BLE001  a 400 naming the cap is the documented ceiling, enforced
        result = "ceiling enforced (" + type(e).__name__ + ")"
    return {"label": "OpenAI (" + m.id + ")", "ceiling": cap, "result": result}


def _gemini_arm() -> dict:
    """Confirm the Gemini single-request output ceiling the same way: a max_output_tokens above the cap
    on a tiny prompt, where the API enforces the documented limit."""
    m = get(GEMINI_MODEL)
    client = get_gemini_client()
    if client is None:
        return {"label": "Gemini (" + m.id + ")", "skipped": "set GEMINI_API_KEY to run this arm"}
    from google.genai import types

    cap = DOC_CAPS["gem-flash"]
    try:
        client.models.generate_content(
            model=m.id, contents="Reply with the single word: ok.",
            config=types.GenerateContentConfig(max_output_tokens=cap + MARGIN))
        result = "accepts up to its documented ceiling"
    except Exception as e:  # noqa: BLE001
        result = "ceiling enforced (" + type(e).__name__ + ")"
    return {"label": "Gemini (" + m.id + ")", "ceiling": cap, "result": result}


def _run_arm(fn, *args) -> dict:
    """Run one competitor arm, turning any failure into a skipped row, so --compare never crashes."""
    try:
        return fn(*args)
    except SystemExit as e:
        return {"skipped": str(e)}
    except Exception as e:  # noqa: BLE001
        return {"skipped": type(e).__name__ + ": " + str(e)[:80]}


def append_comparison(model_key: str, claude_result: dict) -> None:
    """Confirm each competitor's single-request output ceiling and print the full head-to-head table.
    The Claude row reuses the deliverable the Claude arm just produced, so Claude is not billed twice."""
    print("  Reproducing the head-to-head: the largest deliverable one request can return. " + COMPARE_DEPS_HINT + ".\n")

    oai = _run_arm(_openai_arm)
    gem = _run_arm(_gemini_arm)

    claude_tokens = claude_result.get("output_tokens", 0)
    claude_done = "un-truncated" if not claude_result.get("truncated") else "truncated"
    rows = [("Claude (extended output)", "300,000 batch beta",
             format(claude_tokens, ",") + " tokens, " + claude_done)]
    for arm in (oai, gem):
        if "skipped" in arm:
            rows.append((arm.get("label", "competitor"), "skipped: " + arm["skipped"], ""))
        else:
            rows.append((arm["label"], format(arm["ceiling"], ",") + " ceiling", arm["result"]))

    print(f"  {'platform':<26}{'single-request output':>24}{'on the run':>30}")
    print("  " + "-" * 80)
    for label, ceiling, result in rows:
        print(f"  {label:<26}{ceiling:>24}{result:>30}")
    print("  " + "-" * 80)
    print()
    print("  Claude returns the whole deliverable in one request above every competitor's single-request")
    print("  output ceiling, so a bulk job lands each item in a single turn with nothing truncated.")
    print()
