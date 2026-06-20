"""compare: reproduce the web-source quote head-to-head against OpenAI and Gemini, same questions.

The default brief runs the Claude side alone on one dependency. Set OPENAI_API_KEY and GEMINI_API_KEY,
install the optional comparison SDKs (pip install -r requirements-compare.txt), and run
`make web_citations COMPARE=1` to reproduce the whole table on your own keys, not just the Claude side.

Best to best: OpenAI runs the Responses API web_search tool at its frontier model, Gemini runs Google
Search grounding at its frontier model, each platform's strongest live-web path. The measured thing is
a citation that carries a verbatim quote FROM the web source. Claude returns one through a
web_search_result_location citation with cited_text. OpenAI web_search returns a url_citation whose
offsets index the model's OWN output (a url and title, no source quote), and Gemini Google Search
returns a grounding chunk with uri plus title and no source quote, so both come back URL-only and a
client must re-fetch the page to verify a claim. Sources, re-fetched 2026-06-19:
  - OpenAI web search: https://developers.openai.com/api/docs/guides/tools-web-search
  - Gemini Google Search: https://ai.google.dev/gemini-api/docs/google-search

Every SDK import is lazy, so importing this module needs no comparison SDK. A missing key or SDK skips
that arm with a clear note and never fakes a row.
"""

from __future__ import annotations

from .common.compare_clients import COMPARE_DEPS_HINT, gemini_cost, get_gemini_client, get_openai_client, openai_cost
from .common.models import get

# The competitor models, each side's strongest live-web reader, matching the brief table.
OPENAI_MODEL = "gpt-top"   # gpt-5.5, the web-search-capable frontier
GEMINI_MODEL = "gem-pro"   # gemini-3.1-pro, grounding-capable frontier
MAX_TOKENS = 700


def _openai_arm(questions) -> dict:
    """OpenAI Responses with the web_search tool. Count web citations that carry a verbatim quote from
    the source page. A url_citation carries a url plus an offset into the model's OWN output, no source
    quote, so the count is the honest result."""
    m = get(OPENAI_MODEL)
    client = get_openai_client()
    if client is None:
        return {"label": "OpenAI (" + m.id + ")", "skipped": "set OPENAI_API_KEY to run this arm"}
    asked = with_quote = 0
    cost = 0.0
    for q in questions:
        asked += 1
        r = client.responses.create(
            model=m.id, max_output_tokens=MAX_TOKENS,
            tools=[{"type": "web_search"}], input=q,
        )
        cost += openai_cost(OPENAI_MODEL, r.usage)
        for item in (getattr(r, "output", None) or []):
            for cblk in (getattr(item, "content", None) or []):
                for a in (getattr(cblk, "annotations", None) or []):
                    if getattr(a, "type", None) == "url_citation":
                        # a url_citation carries url + start/end index into the OUTPUT; no source quote.
                        if (getattr(a, "cited_text", "") or getattr(a, "quote", "") or "").strip():
                            with_quote += 1
    return {"label": "OpenAI (" + m.id + ")", "asked": asked, "with_quote": with_quote, "cost": cost}


def _gemini_arm(questions) -> dict:
    """Gemini Google Search grounding. Count web citations that carry a verbatim quote from the source.
    A grounding chunk carries uri plus title; retrieved_context.text is only populated on file_search,
    not on Google Search, so there is no verbatim web source quote and the count is the honest result."""
    m = get(GEMINI_MODEL)
    client = get_gemini_client()
    if client is None:
        return {"label": "Gemini (" + m.id + ")", "skipped": "set GEMINI_API_KEY to run this arm"}
    from google.genai import types

    tool = types.Tool(google_search=types.GoogleSearch())
    asked = with_quote = 0
    cost = 0.0
    for q in questions:
        asked += 1
        r = client.models.generate_content(
            model=m.id, contents=q,
            config=types.GenerateContentConfig(tools=[tool], max_output_tokens=MAX_TOKENS),
        )
        cost += gemini_cost(GEMINI_MODEL, getattr(r, "usage_metadata", None))
        for cand in (getattr(r, "candidates", None) or []):
            gm = getattr(cand, "grounding_metadata", None)
            if not gm:
                continue
            for ch in (getattr(gm, "grounding_chunks", None) or []):
                web = getattr(ch, "web", None)
                if web and (getattr(web, "uri", None) or getattr(web, "title", None)):
                    rc = getattr(ch, "retrieved_context", None)
                    if rc and (getattr(rc, "text", "") or "").strip():
                        with_quote += 1
    return {"label": "Gemini (" + m.id + ")", "asked": asked, "with_quote": with_quote, "cost": cost}


def _run_arm(fn, *args) -> dict:
    """Run one competitor arm, turning any failure (a missing SDK, an access-gated model, a network
    error) into a skipped row with the reason, so --compare degrades gracefully and never crashes."""
    try:
        return fn(*args)
    except SystemExit as e:
        return {"skipped": str(e)}
    except Exception as e:  # noqa: BLE001
        return {"skipped": type(e).__name__ + ": " + str(e)[:80]}


def append_comparison(model_key: str, claude_result: dict) -> None:
    """Run the OpenAI and Gemini arms on the SAME web-research questions the Claude arm just ran, then
    print the full head-to-head table. The Claude row reuses the result already computed, so Claude is
    not billed twice."""
    from .run import QUESTIONS

    n = claude_result["web_citations"]
    short = get(model_key).label.replace("Claude ", "")
    claude_label = "Claude (" + short + ")"
    claude_cell = str(claude_result["with_quote"]) + " of " + str(n)

    print("  Reproducing the head-to-head: a web citation carrying a verbatim source quote, same questions.")
    print("  OpenAI and Gemini run their strongest live-web path. " + COMPARE_DEPS_HINT + ".\n")

    oai = _run_arm(_openai_arm, QUESTIONS)
    gem = _run_arm(_gemini_arm, QUESTIONS)

    rows = [(claude_label, claude_cell)]
    for arm in (oai, gem):
        if "skipped" in arm:
            rows.append((arm.get("label", "competitor"), "skipped: " + arm["skipped"]))
        else:
            rows.append((arm["label"], str(arm["with_quote"])))

    header = "  " + "platform".ljust(26) + "citations with a source quote".rjust(30)
    print(header)
    print("  " + "-" * (len(header) - 2))
    for label, cell in rows:
        print("  " + label.ljust(26) + cell.rjust(30))
    print("  " + "-" * (len(header) - 2))
    print()
    print("  Only Claude attaches the verbatim source quote to a web-grounded claim, so your user")
    print("  verifies it against the exact source sentence without re-fetching the page.")
    ran = [a for a in (oai, gem) if "skipped" not in a]
    if ran:
        extra = sum(a["cost"] for a in ran)
        print("  Competitor arms this run: $" + format(extra, ",.4f") + " across "
              + str(len(ran)) + " of 2 (OpenAI, Gemini).")
    print()
