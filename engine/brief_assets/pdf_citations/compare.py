"""compare: reproduce the page-pointer head-to-head against OpenAI and Gemini, same PDF, same questions.

The default brief runs the Claude side alone on one dependency. Set OPENAI_API_KEY and GEMINI_API_KEY,
install the optional comparison SDKs (pip install -r requirements-compare.txt), and run
`make pdf_citations COMPARE=1` to reproduce the direct-PDF table using your own API keys, not just the
Claude side.

Best to best: OpenAI runs the Responses API with the PDF supplied directly as an input_file, Gemini
runs the inline PDF part (document processing), both their strongest directly-supplied-PDF path. The
measured thing is a verifiable page pointer back into the supplied PDF. Claude returns one through
page_location citations. OpenAI and Gemini answer from the PDF but return no page pointer on a directly
supplied document (a file pointer there needs a hosted file_search vector store, a different persisted
path). Sources, re-fetched 2026-06-19:
  - OpenAI file search: https://developers.openai.com/api/docs/guides/tools-file-search
  - Gemini file search: https://ai.google.dev/gemini-api/docs/file-search

Every SDK import is lazy, so importing this module needs no comparison SDK. A missing API key or SDK skips
that arm with a clear note and never fakes a row.
"""

from __future__ import annotations

import base64

from .common.compare_clients import COMPARE_DEPS_HINT, gemini_cost, get_gemini_client, get_openai_client, openai_cost
from .common.models import get

# The competitor models, each side's strongest directly-supplied-PDF reader, matching the brief table.
OPENAI_MODEL = "gpt-mid"   # gpt-5.4, a capable PDF reader
GEMINI_MODEL = "gem-flash"  # gemini-3.5-flash, full PDF vision
MAX_TOKENS = 512


def _openai_arm(pdf_bytes: bytes, questions) -> dict:
    """OpenAI Responses with the PDF supplied directly (input_file). Count how many answers came back
    with a verifiable pointer into the supplied PDF (a file_citation). For a direct input_file there is
    none, so the count is the honest result."""
    m = get(OPENAI_MODEL)
    client = get_openai_client()
    if client is None:
        return {"label": f"OpenAI ({m.id})", "skipped": "set OPENAI_API_KEY to run this arm"}
    data_url = "data:application/pdf;base64," + base64.standard_b64encode(pdf_bytes).decode("ascii")
    asked = pointer = 0
    cost = 0.0
    for q, ans_page, token in questions:
        asked += 1
        r = client.responses.create(
            model=m.id, max_output_tokens=MAX_TOKENS,
            input=[{"role": "user", "content": [
                {"type": "input_file", "filename": "agreement.pdf", "file_data": data_url},
                {"type": "input_text", "text": q + " Answer in one sentence and cite the page."}]}],
        )
        cost += openai_cost(OPENAI_MODEL, r.usage)
        for item in (getattr(r, "output", None) or []):
            for c in (getattr(item, "content", None) or []):
                for a in (getattr(c, "annotations", None) or []):
                    if getattr(a, "type", None) in ("file_citation", "file_path"):
                        pointer += 1
    return {"label": f"OpenAI ({m.id})", "asked": asked, "pointer": pointer, "cost": cost}


def _gemini_arm(pdf_bytes: bytes, questions) -> dict:
    """Gemini inline PDF (document processing). Count answers that carried a grounding pointer into the
    supplied PDF. An inline PDF returns none, so the count is the honest result."""
    m = get(GEMINI_MODEL)
    client = get_gemini_client()
    if client is None:
        return {"label": f"Gemini ({m.id})", "skipped": "set GEMINI_API_KEY to run this arm"}
    from google.genai import types

    part = types.Part.from_bytes(data=pdf_bytes, mime_type="application/pdf")
    asked = pointer = 0
    cost = 0.0
    for q, ans_page, token in questions:
        asked += 1
        r = client.models.generate_content(
            model=m.id,
            contents=[part, q + " Answer in one sentence and cite the page."],
            config=types.GenerateContentConfig(max_output_tokens=MAX_TOKENS),
        )
        cost += gemini_cost(GEMINI_MODEL, getattr(r, "usage_metadata", None))
        for cand in (getattr(r, "candidates", None) or []):
            gm = getattr(cand, "grounding_metadata", None)
            if gm and (getattr(gm, "grounding_chunks", None) or getattr(gm, "grounding_supports", None)):
                pointer += 1
    return {"label": f"Gemini ({m.id})", "asked": asked, "pointer": pointer, "cost": cost}


def _run_arm(fn, *args) -> dict:
    """Run one competitor arm, turning any failure (a missing SDK, an access-gated model, a network
    error) into a skipped row with the reason, so --compare degrades gracefully and never crashes."""
    try:
        return fn(*args)
    except SystemExit as e:
        return {"skipped": str(e)}
    except Exception as e:  # noqa: BLE001
        return {"skipped": f"{type(e).__name__}: {str(e)[:80]}"}


def append_comparison(model_key: str, claude_result: dict) -> None:
    """Run the OpenAI and Gemini arms on the SAME PDF and questions the Claude arm just ran, then print
    the full head-to-head table. The Claude row reuses the result already computed, so Claude is not
    billed twice."""
    from .run import QUESTIONS, make_sample_pdf

    pdf = make_sample_pdf()
    n = claude_result["asked"]
    short = get(model_key).label.replace("Claude ", "")
    claude_label = "Claude (" + short + ")"

    print("  Reproducing the direct-PDF head-to-head: a page pointer to the right page, same questions, same PDF.")
    print("  No arm creates a hosted file-search store first. " + COMPARE_DEPS_HINT + ".\n")

    oai = _run_arm(_openai_arm, pdf, QUESTIONS)
    gem = _run_arm(_gemini_arm, pdf, QUESTIONS)

    rows = [(claude_label, str(claude_result["page_correct"]) + "/" + str(n))]
    for arm in (oai, gem):
        if "skipped" in arm:
            rows.append((arm.get("label", "competitor"), "skipped: " + arm["skipped"]))
        else:
            rows.append((arm["label"], str(arm["pointer"]) + "/" + str(arm["asked"])))

    print(f"  {'platform':<24}{'direct-PDF page pointer':>32}")
    print("  " + "-" * 56)
    for label, cell in rows:
        print(f"  {label:<24}{cell:>32}")
    print("  " + "-" * 56)
    print()
    print("  On this direct-request path, Claude returns the page pointer in the same response,")
    print("  with no hosted vector store or pre-upload step.")
    ran = [a for a in (oai, gem) if "skipped" not in a]
    if ran:
        extra = sum(a["cost"] for a in ran)
        print(f"  Competitor arms this run: ${extra:,.2f} across {len(ran)} of 2 (OpenAI, Gemini).")
    print()
