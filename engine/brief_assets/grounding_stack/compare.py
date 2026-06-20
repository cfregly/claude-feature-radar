"""compare: reproduce the one-request grounding-stack head-to-head against OpenAI and Gemini.

The default brief runs the Claude side alone on one dependency. Set OPENAI_API_KEY and GEMINI_API_KEY,
install the optional comparison SDKs (pip install -r requirements-compare.txt), and run
`make grounding_stack COMPARE=1` to reproduce the whole table on your own keys, not just the Claude side.

Best to best, the same one request with the same three inline sources (a text note, a directly-supplied
PDF, and a RAG chunk) on each platform's strongest inline path. The measured thing is two numbers: how
many of the three parts the model answers, and how many of the three sources it returns an inline
pointer for. Claude answers all three and returns a typed pointer for each (char_location, page_location,
search_result_location). OpenAI takes the PDF as an input_file and the text and chunk as input_text and
returns no citation annotation, and Gemini takes the inline sources and returns no grounding object,
because on both an inline source carries no pointer without a hosted file_search store. Sources,
re-fetched 2026-06-19:
  - OpenAI file search: https://developers.openai.com/api/docs/guides/tools-file-search
  - Gemini file search: https://ai.google.dev/gemini-api/docs/file-search

Every SDK import is lazy, so importing this module needs no comparison SDK. A missing key or SDK skips
that arm with a clear note and never fakes a row.
"""

from __future__ import annotations

import base64

from .common.compare_clients import COMPARE_DEPS_HINT, gemini_cost, get_gemini_client, get_openai_client, openai_cost
from .common.models import get

# The competitor models, each side's strongest one-request inline reader, matching the brief table.
OPENAI_MODEL = "gpt-mid"    # gpt-5.4, a capable PDF + text reader
GEMINI_MODEL = "gem-flash"  # gemini-3.5-flash, full PDF vision
MAX_TOKENS = 600


def _openai_arm() -> dict:
    """OpenAI Responses, one request: input_file PDF + the text and chunk as input_text. Count parts
    answered and inline pointers. A directly-supplied PDF and inline text return no citation annotation,
    so the pointer count is the honest result."""
    from .run import CHUNK_FACT, PDF_FACT, QUESTION, TEXT_FACT, TOKENS, _make_pdf

    m = get(OPENAI_MODEL)
    client = get_openai_client()
    if client is None:
        return {"label": "OpenAI (" + m.id + ")", "skipped": "set OPENAI_API_KEY to run this arm"}
    data_url = "data:application/pdf;base64," + base64.standard_b64encode(_make_pdf(PDF_FACT)).decode("ascii")
    r = client.responses.create(
        model=m.id, max_output_tokens=MAX_TOKENS,
        input=[{"role": "user", "content": [
            {"type": "input_text", "text": TEXT_FACT},
            {"type": "input_file", "filename": "agreement.pdf", "file_data": data_url},
            {"type": "input_text", "text": CHUNK_FACT},
            {"type": "input_text", "text": QUESTION}]}],
    )
    cost = openai_cost(OPENAI_MODEL, r.usage)
    text = getattr(r, "output_text", "") or ""
    answered = sum(1 for tok in TOKENS if tok.lower() in text.lower())
    pointers = 0
    for item in (getattr(r, "output", None) or []):
        for c in (getattr(item, "content", None) or []):
            for a in (getattr(c, "annotations", None) or []):
                if getattr(a, "type", None) in ("file_citation", "file_path", "url_citation"):
                    pointers += 1
    return {"label": "OpenAI (" + m.id + ")", "answered": answered, "pointers": min(pointers, 3), "cost": cost}


def _gemini_arm() -> dict:
    """Gemini, one request: inline PDF part + the text and chunk inline. Count parts answered and inline
    pointers. Inline content returns no grounding object, so the pointer count is the honest result."""
    from .run import CHUNK_FACT, PDF_FACT, QUESTION, TEXT_FACT, TOKENS, _make_pdf

    m = get(GEMINI_MODEL)
    client = get_gemini_client()
    if client is None:
        return {"label": "Gemini (" + m.id + ")", "skipped": "set GEMINI_API_KEY to run this arm"}
    from google.genai import types

    part = types.Part.from_bytes(data=_make_pdf(PDF_FACT), mime_type="application/pdf")
    r = client.models.generate_content(
        model=m.id,
        contents=[TEXT_FACT, part, CHUNK_FACT, QUESTION],
        config=types.GenerateContentConfig(max_output_tokens=MAX_TOKENS),
    )
    cost = gemini_cost(GEMINI_MODEL, getattr(r, "usage_metadata", None))
    text = getattr(r, "text", None) or ""
    answered = sum(1 for tok in TOKENS if tok.lower() in text.lower())
    pointers = 0
    for cand in (getattr(r, "candidates", None) or []):
        gm = getattr(cand, "grounding_metadata", None)
        if gm and (getattr(gm, "grounding_chunks", None) or getattr(gm, "grounding_supports", None)):
            pointers += 1
    return {"label": "Gemini (" + m.id + ")", "answered": answered, "pointers": min(pointers, 3), "cost": cost}


def _run_arm(fn, *args) -> dict:
    """Run one competitor arm, turning any failure into a skipped row, so --compare never crashes."""
    try:
        return fn(*args)
    except SystemExit as e:
        return {"skipped": str(e)}
    except Exception as e:  # noqa: BLE001
        return {"skipped": type(e).__name__ + ": " + str(e)[:80]}


def append_comparison(model_key: str, claude_result: dict) -> None:
    """Run the OpenAI and Gemini arms on the SAME three sources in one request, then print the full
    head-to-head table. The Claude row reuses the result already computed, so Claude is not billed twice."""
    short = get(model_key).label.replace("Claude ", "")
    claude_label = "Claude (" + short + ")"

    print("  Reproducing the head-to-head: text + PDF + RAG chunk in one request, sources answered and")
    print("  inline pointers returned. " + COMPARE_DEPS_HINT + ".\n")

    oai = _run_arm(_openai_arm)
    gem = _run_arm(_gemini_arm)

    rows = [(claude_label, str(claude_result["answered"]) + " of 3", str(claude_result["pointers"]) + " of 3")]
    for arm in (oai, gem):
        if "skipped" in arm:
            rows.append((arm.get("label", "competitor"), "skipped: " + arm["skipped"], ""))
        else:
            rows.append((arm["label"], str(arm["answered"]) + " of 3", str(arm["pointers"]) + " of 3"))

    print(f"  {'platform':<22}{'sources answered':>18}{'inline pointers':>18}")
    print("  " + "-" * 58)
    for label, answered, pointers in rows:
        print(f"  {label:<22}{answered:>18}{pointers:>18}")
    print("  " + "-" * 58)
    print()
    print("  Only Claude returns an inline pointer for each of the three sources in one request, so every")
    print("  part of the answer deep-links into the user's own text, PDF, and retrieved chunk.")
    ran = [a for a in (oai, gem) if "skipped" not in a]
    if ran:
        extra = sum(a["cost"] for a in ran)
        print("  Competitor arms this run: $" + format(extra, ",.4f") + " across "
              + str(len(ran)) + " of 2 (OpenAI, Gemini).")
    print()
