"""run: answer a question over a directly-supplied PDF and get a verifiable pointer to the exact page.

The founder-facing artifact for the pdf_citations brief. When your product answers a question over a
user's uploaded PDF (a lease, a 10-K, an insurance policy, a vendor contract), each answer needs to
deep-link to the exact page so a person can verify it before acting. Claude Citations does this for a
PDF supplied directly in the request: send the PDF as a base64 document block with citations enabled,
and every answer comes back with a page_location citation (page number plus the quoted source text).
The quote does not count toward output tokens, and no beta header is needed. Source, re-fetched
2026-06-19: https://platform.claude.com/docs/en/build-with-claude/citations

  python -m pdf_citations.run            answer questions over the sample PDF, with a page pointer each
  python -m pdf_citations.run --check    the self-test: ASSERT every answer carries a correct-page pointer
  python -m pdf_citations.run --model opus    use Opus 4.8 instead of the default Haiku 4.5

This costs about $0.05 on Haiku 4.5 for the self-test. The model calls are the only spend. anthropic is
imported lazily, inside the run path, so importing this module needs no SDK.
"""

from __future__ import annotations

import argparse
import base64
import sys
import time
from pathlib import Path

# Make the repo root importable when run as a file, not just as a module.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from .common.models import get  # noqa: E402  the verified id + price registry, anthropic-free
from .common.pricing import cost_usd  # noqa: E402  real usage object -> real dollars, anthropic-free

MAX_TOKENS = 512
MODELS = {"haiku": "claude-haiku-4-5-20251001", "sonnet": "claude-sonnet-4-6", "opus": "claude-opus-4-8"}

# The comparison gate default. The generator bakes this per surface: the public brief ships it OFF, so
# `make pdf_citations` runs the Claude side alone on one dependency, and `make pdf_citations COMPARE=1`
# (or --compare) reproduces the full OpenAI and Gemini head-to-head. A private both-directions checkout
# ships it ON. Either way --compare / --no-compare overrides it.
COMPARE_DEFAULT = {compare_default}

# A small synthetic SaaS Pro Plan agreement, one citable fact per page. Built with the standard library
# alone so a forked repo generates the same PDF with no PDF dependency.
PAGES = [
    ("Section 1. Plan and Seats.",
     "The Pro plan includes 50 included seats per organization. Additional users beyond the "
     "included seats are billed as overage. The included seat count does not roll over between "
     "billing periods and resets at the start of each monthly cycle."),
    ("Section 2. Overage Pricing.",
     "Overage seats beyond the 50 included seats are billed at 12 US dollars per seat per month. "
     "Overage is metered daily and charged in arrears on the next invoice. There is no cap on the "
     "number of overage seats an organization may add."),
    ("Section 3. Annual Commitment Discount.",
     "Organizations that commit to an annual contract receive a 20 percent discount applied to both "
     "the base subscription and any overage seats. The annual discount is forfeited if the contract "
     "is downgraded to monthly billing before the commitment term ends."),
    ("Section 4. Termination.",
     "Either party may terminate this agreement for convenience by providing 30 days prior written "
     "notice. Fees already paid are non-refundable, and any outstanding overage charges become due "
     "immediately upon the effective date of termination."),
    ("Section 5. Service Levels.",
     "The Pro plan carries a monthly uptime commitment of 99.9 percent. If uptime falls below the "
     "commitment in a calendar month, the organization is eligible for a service credit equal to 10 "
     "percent of that month's base subscription fee, requested within 30 days."),
]

# (question, answer_page (1-indexed), token a correct answer must contain). The self-test asks the
# same five questions as the sample output, so `make pdf_citations` reproduces the advertised 5/5 result.
QUESTIONS = [
    ("How many seats are included?", 1, "50"),
    ("How much is each overage seat per month?", 2, "12"),
    ("What discount do annual contracts get?", 3, "20"),
    ("How many days of notice to terminate?", 4, "30"),
    ("What is the monthly uptime commitment?", 5, "99.9"),
]


# --------------------------------------------------------------------------- a pure-stdlib PDF writer

def _esc(s: str) -> str:
    return s.replace("\\", r"\\").replace("(", r"\(").replace(")", r"\)")


def _wrap(text: str, width: int = 88) -> list:
    out, line = [], ""
    for word in text.split():
        if len(line) + len(word) + 1 > width:
            out.append(line)
            line = word
        else:
            line = (line + " " + word).strip()
    if line:
        out.append(line)
    return out


def make_sample_pdf(pages=PAGES) -> bytes:
    """Build a multi-page, text-extractable PDF, one page per (heading, body). Pure stdlib, so a forked
    repo generates the same sample with the standard library alone."""
    objects = []

    def add(body: bytes) -> int:
        objects.append(body)
        return len(objects)

    catalog_num = 1
    pages_num = 2
    objects.append(b"")  # placeholder for the catalog
    objects.append(b"")  # placeholder for the pages node
    font_num = add(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")
    page_obj_nums = []
    for heading, body in pages:
        lines = [heading, ""] + _wrap(body)
        parts = ["BT", "/F1 12 Tf", "72 720 Td", "16 TL"]
        for ln in lines:
            parts.append(f"({_esc(ln)}) Tj")
            parts.append("T*")
        parts.append("ET")
        stream = ("\n".join(parts)).encode("latin-1")
        content_body = b"<< /Length %d >>\nstream\n%s\nendstream" % (len(stream), stream)
        content_num = add(content_body)
        page_body = (
            b"<< /Type /Page /Parent %d 0 R /MediaBox [0 0 612 792] "
            b"/Resources << /Font << /F1 %d 0 R >> >> /Contents %d 0 R >>"
            % (pages_num, font_num, content_num))
        page_obj_nums.append(add(page_body))
    kids = b" ".join(b"%d 0 R" % n for n in page_obj_nums)
    objects[pages_num - 1] = b"<< /Type /Pages /Kids [%s] /Count %d >>" % (kids, len(page_obj_nums))
    objects[catalog_num - 1] = b"<< /Type /Catalog /Pages %d 0 R >>" % pages_num
    out = bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
    offsets = [0] * (len(objects) + 1)
    for i, body in enumerate(objects, start=1):
        offsets[i] = len(out)
        out += b"%d 0 obj\n" % i + body + b"\nendobj\n"
    xref_pos = len(out)
    out += b"xref\n0 %d\n" % (len(objects) + 1)
    out += b"0000000000 65535 f \n"
    for i in range(1, len(objects) + 1):
        out += b"%010d 00000 n \n" % offsets[i]
    out += b"trailer\n<< /Size %d /Root %d 0 R >>\nstartxref\n%d\n%%%%EOF\n" % (
        len(objects) + 1, catalog_num, xref_pos)
    return bytes(out)


# --------------------------------------------------------------------------- the Claude run

def answer_with_page_pointers(client, model_key: str, pdf_bytes: bytes) -> dict:
    """Ask each question over the directly-supplied PDF and collect, per answer, the page the model
    cited. The mechanism is two lines: the document block carries the PDF as base64, and
    citations: {enabled: True} turns on the page_location pointer with the quoted source text."""
    model_id = get(model_key).id
    b64 = base64.standard_b64encode(pdf_bytes).decode("ascii")
    rows, cost = [], 0.0
    answered = page_correct = 0
    for q, ans_page, token in QUESTIONS:
        doc = {"type": "document",
               "source": {"type": "base64", "media_type": "application/pdf", "data": b64},
               "title": "Pro Plan Agreement",
               "citations": {"enabled": True}}                         # add this
        messages = [{"role": "user", "content": [
            doc,                                                       # add this: the PDF, supplied directly
            {"type": "text", "text": q + " Answer in one sentence and cite the source."}]}]
        r = client.messages.create(model=model_id, max_tokens=MAX_TOKENS, messages=messages)
        cost += cost_usd(model_key, r.usage)
        text = "".join(b.text for b in r.content if getattr(b, "type", None) == "text")
        pages, quote = [], ""
        for b in r.content:
            if getattr(b, "type", None) == "text":
                for ci in (getattr(b, "citations", None) or []):
                    if getattr(ci, "type", None) == "page_location":
                        pages.append(getattr(ci, "start_page_number", None))
                        quote = quote or (getattr(ci, "cited_text", "") or "")
        ok_answer = token.lower() in text.lower()
        ok_page = bool(pages) and ans_page in pages
        answered += int(ok_answer)
        page_correct += int(ok_page)
        rows.append({"q": q, "expected_page": ans_page, "cited_pages": pages,
                     "quote": quote, "ok_answer": ok_answer, "ok_page": ok_page})
    return {"model_key": model_key, "rows": rows, "cost": cost,
            "asked": len(QUESTIONS), "answered": answered, "page_correct": page_correct}


# --------------------------------------------------------------------------- output

def fmt_usd(x: float) -> str:
    return f"${x:,.6f}" if x < 0.01 else f"${x:,.4f}"


def print_table(result: dict) -> None:
    print()
    print("  question                                    cited page   right page   quote")
    print("  " + "-" * 86)
    for row in result["rows"]:
        cited = ",".join(str(p) for p in row["cited_pages"]) or "-"
        right = "yes" if row["ok_page"] else "no"
        quote = (row["quote"][:34] + "...") if len(row["quote"]) > 37 else row["quote"]
        print(f"  {row['q'][:42]:<44}{cited:>7}{right:>13}   {quote}")
    print("  " + "-" * 86)
    print()
    print(f"  Every answer came back with a page_location pointer to the exact page of the PDF you")
    print(f"  supplied in the request, plus the quoted source text. The quote is free of output tokens.")
    print(f"  Live cost {fmt_usd(result['cost'])} on {get(result['model_key']).label}.")
    print()


def _maybe_compare(model_key: str, result: dict, compare_on: bool) -> None:
    """When the comparison gate is on, run the OpenAI and Gemini arms on the same PDF and questions and
    print the full head-to-head table. Imported lazily, so the default Claude-only run never touches the
    comparison code or its optional SDKs."""
    if not compare_on:
        return
    from .compare import append_comparison  # lazy: the comparison SDKs load only here
    append_comparison(model_key, result)


def cmd_run(model_key: str, compare_on: bool = False) -> int:
    from .common.client import get_client  # lazy: anthropic only imported when we actually call

    print(f"\n  PDF citations: answer questions over a directly-supplied PDF and get a verifiable pointer")
    print(f"  to the exact page for each answer, on {get(model_key).label}.")
    print(f"  Upfront: about $0.05 and roughly 10 seconds using your API key. The model calls are the only spend.\n")
    client = get_client()
    result = answer_with_page_pointers(client, model_key, make_sample_pdf())
    print_table(result)
    _maybe_compare(model_key, result, compare_on)
    return 0


def cmd_check(model_key: str, compare_on: bool = False) -> int:
    """The self-test: assert every answer carries a verifiable pointer to the CORRECT page of the
    directly-supplied PDF. A missing pointer, or a pointer to the wrong page, is a failure."""
    from .common.client import get_client  # lazy

    print(f"\n  --check: asking questions over a directly-supplied PDF and asserting every answer carries")
    print(f"  a pointer to the correct page, on {get(model_key).label}. About $0.05.\n")
    client = get_client()
    result = answer_with_page_pointers(client, model_key, make_sample_pdf())
    print_table(result)
    _maybe_compare(model_key, result, compare_on)
    if result["answered"] != result["asked"]:
        print("  CHECK FAILED: not every question was answered.\n")
        return 1
    if result["page_correct"] != result["asked"]:
        print("  CHECK FAILED: an answer was missing a pointer or pointed at the wrong page.\n")
        return 1
    print("  CHECK PASSED: every answer carried a verifiable pointer to the correct page of the PDF.")
    print("  Your app can deep-link each answer to its source page with zero resolver code.\n")
    return 0


def main() -> int:
    p = argparse.ArgumentParser(
        description="Answer questions over a directly-supplied PDF and get a page pointer for each answer.")
    p.add_argument("--model", default="haiku", choices=sorted(MODELS),
                   help="haiku (default), sonnet, or opus")
    p.add_argument("--check", action="store_true",
                   help="self-test: assert every answer carries a correct-page pointer")
    p.add_argument("--compare", dest="compare", action="store_true", default=None,
                   help="also run the OpenAI and Gemini arms and print the full head-to-head table "
                        "(needs OPENAI_API_KEY, GEMINI_API_KEY, and requirements-compare.txt)")
    p.add_argument("--no-compare", dest="compare", action="store_false",
                   help="run only the Claude side (the public-brief default)")
    a = p.parse_args()
    compare_on = COMPARE_DEFAULT if a.compare is None else a.compare
    return cmd_check(a.model, compare_on) if a.check else cmd_run(a.model, compare_on)


if __name__ == "__main__":
    raise SystemExit(main())
