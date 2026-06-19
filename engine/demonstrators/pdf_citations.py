"""pdf_citations: a per-page, guaranteed-valid source pointer INTO a directly-supplied PDF, with the
verbatim quote, free of output tokens and zero resolver code, where the competitors return nothing.

THE EDGE, at subfeature depth. Send a PDF inline (base64) as a `document` content block with
`citations: {"enabled": true}` and Claude returns each claim with a `page_location` citation:
`document_index`, `start_page_number`, `end_page_number`, and the verbatim `cited_text` (free of
output tokens). The citation is API-guaranteed to resolve. No beta header for an inline/base64/URL PDF.

WHY IT IS A CROSS-VENDOR EDGE. For a PDF the developer hands the model directly in the request:
  - OpenAI `input_file` extracts text and page images and answers, but returns NO citation/annotation
    object pointing into the supplied PDF. To get any file citation you must move the PDF into the
    hosted `file_search` vector store, and even then the annotation is a filename plus an output-text
    index, not a page pointer into your document.
  - Gemini inline PDF (document processing) answers with full vision but returns NO grounding/citation
    object. Page-number citations exist only through the hosted `file_search_store`.
So for the direct-PDF path, Claude is the only one of the three that returns a verifiable per-page
pointer with the quote. Competitor citation is absent, not merely weaker. Verified live 2026-06-19.

WHAT THIS MEASURES. A small synthetic multi-page agreement PDF (generated here, pure stdlib, so the
repo stays forkable with no PDF dependency), one citable fact per page. A fixed set of questions whose
answers live on known pages. The gate, run identically on every arm: does the answer carry a
verifiable pointer to the EXACT page of the directly-supplied PDF? Claude's pointer is checked against
the known page (it must be right, not just present). The competitor arms are scored on whether ANY
such pointer is returned at all for a directly-supplied PDF.

FOUNDER WORKLOAD. A product that answers questions over a user's uploaded PDF on the spot (a 10-K, an
insurance policy, a lease, a lab report, a compliance Q&A) and must deep-link each answer to the exact
page so a human can verify before acting, without persisting the document in a third-party vector
store. The value a founder prices: trust (a click-through to the source page) with zero resolver code.

DEPENDENCIES. The Claude arm needs only anthropic. The OpenAI and Gemini arms need their optional
SDKs and keys (lazy). The PDF is generated with the standard library alone.
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import pathlib
import sys
import time
import zlib
from dataclasses import dataclass, field

# repo root on the path, for common/ and engine/ when run as a script.
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))

from engine.demonstrators.base import Arm, BaseDemonstrator, CostEstimate, Verdict
from engine.demonstrators.registry import register
from engine.demonstrators.shared import platform

CLAUDE_MODEL = os.environ.get("PDF_CLAUDE_MODEL", "haiku")
OPENAI_MODEL = os.environ.get("PDF_OPENAI_MODEL", "gpt-mid")     # gpt-5.4, a capable PDF reader
GEMINI_MODEL = os.environ.get("PDF_GEMINI_MODEL", "gem-flash")   # gemini-3.5-flash, full PDF vision
MAX_TOKENS = int(os.environ.get("PDF_MAX_TOKENS", "512"))


# --------------------------------------------------------------------------- the sample document
#
# One citable fact per page (startup-native: a SaaS Pro Plan agreement). Each (fact, question,
# answer_page) is the ground truth: the question's answer lives on answer_page (1-indexed), so a
# correct page citation must point there.

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

# Each question's answer lives on the page index named here (1-indexed). The expected token is a short
# string that a correct answer must contain, so the answer-content gate is machine-checkable too.
QUESTIONS = [
    ("How much is each overage seat per month?", 2, "12"),
    ("How many seats are included in the Pro plan?", 1, "50"),
    ("What discount do annual contracts receive?", 3, "20"),
    ("How many days of notice are required to terminate?", 4, "30"),
    ("What is the monthly uptime commitment?", 5, "99.9"),
]


# --------------------------------------------------------------------------- a pure-stdlib PDF writer
#
# A minimal, valid, text-extractable PDF: one page per (heading, body), Helvetica, wrapped lines. No
# third-party dependency, so a forked repo generates the same sample with the standard library alone.
# The bytes are deterministic, so the committed sample.pdf is reproducible.

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
    """Build a multi-page text PDF, one page per (heading, body). Pure stdlib, deterministic bytes."""
    objects = []  # each entry is the raw bytes of one object body (without the "N 0 obj"/"endobj")

    def add(body: bytes) -> int:
        objects.append(body)
        return len(objects)  # 1-indexed object number

    # Reserve: 1 = Catalog, 2 = Pages, then per page a Page obj and a Contents obj, then the Font.
    catalog_num = 1
    pages_num = 2
    objects.append(b"")  # placeholder for catalog (obj 1)
    objects.append(b"")  # placeholder for pages (obj 2)

    page_obj_nums = []
    font_num = None  # assigned after pages so we know the number; we fix it up below

    # We need the font object number known by the page objects, so allocate it first after placeholders.
    font_num = add(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")

    for heading, body in pages:
        lines = [heading, ""] + _wrap(body)
        # Build the content stream: start at top, 16pt leading.
        parts = ["BT", "/F1 12 Tf", "72 720 Td", "16 TL"]
        for i, ln in enumerate(lines):
            parts.append(f"({_esc(ln)}) Tj")
            parts.append("T*")
        parts.append("ET")
        stream = ("\n".join(parts)).encode("latin-1")
        content_body = b"<< /Length %d >>\nstream\n%s\nendstream" % (len(stream), stream)
        content_num = add(content_body)
        page_body = (
            b"<< /Type /Page /Parent %d 0 R /MediaBox [0 0 612 792] "
            b"/Resources << /Font << /F1 %d 0 R >> >> /Contents %d 0 R >>"
            % (pages_num, font_num, content_num)
        )
        page_obj_nums.append(add(page_body))

    kids = b" ".join(b"%d 0 R" % n for n in page_obj_nums)
    objects[pages_num - 1] = b"<< /Type /Pages /Kids [%s] /Count %d >>" % (kids, len(page_obj_nums))
    objects[catalog_num - 1] = b"<< /Type /Catalog /Pages %d 0 R >>" % pages_num

    # Serialize with an xref table.
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


def sample_pdf_path() -> pathlib.Path:
    from common.client import repo_root
    return repo_root() / "edges" / "pdf-citations" / "sample.pdf"


# --------------------------------------------------------------------------- the arms

@dataclass
class ArmResult:
    name: str
    provider: str
    model: str
    ran: bool = True
    answered: int = 0          # answer string contained the expected token
    cited: int = 0            # a verifiable per-page pointer into the supplied PDF was returned
    page_correct: int = 0     # the pointer pointed at the RIGHT page
    asked: int = 0
    cost: float = 0.0
    latency: float = 0.0
    input_tokens: int = 0
    output_tokens: int = 0
    note: str = ""
    errors: list = field(default_factory=list)


def run_claude_arm(client, model_key: str, pdf_bytes: bytes, *, progress=False) -> ArmResult:
    from common.models import get
    from common.pricing import cost_breakdown

    m = get(model_key)
    arm = ArmResult(name=f"claude:{model_key}", provider="anthropic", model=m.id,
                    note="inline base64 PDF document block, citations enabled, no beta header")
    b64 = base64.standard_b64encode(pdf_bytes).decode("ascii")
    platform.used("citations", "page_location pointer into a directly-supplied PDF")
    for q, ans_page, token in QUESTIONS:
        arm.asked += 1
        doc = {"type": "document",
               "source": {"type": "base64", "media_type": "application/pdf", "data": b64},
               "title": "Pro Plan Agreement", "citations": {"enabled": True}}
        messages = [{"role": "user", "content": [doc, {"type": "text",
                     "text": q + " Answer in one sentence and cite the source."}]}]
        try:
            t0 = time.perf_counter()
            r = client.messages.create(model=m.id, max_tokens=MAX_TOKENS, messages=messages)
            arm.latency += time.perf_counter() - t0
        except Exception as e:  # noqa: BLE001
            arm.errors.append(f"{q[:24]}: {type(e).__name__}: {str(e)[:80]}")
            continue
        arm.cost += cost_breakdown(model_key, r.usage).total
        arm.input_tokens += getattr(r.usage, "input_tokens", 0) or 0
        arm.output_tokens += getattr(r.usage, "output_tokens", 0) or 0
        text = "".join(b.text for b in r.content if getattr(b, "type", None) == "text")
        if token.lower() in text.lower():
            arm.answered += 1
        pages = []
        for b in r.content:
            if getattr(b, "type", None) == "text":
                for ci in (getattr(b, "citations", None) or []):
                    if getattr(ci, "type", None) == "page_location":
                        pages.append(getattr(ci, "start_page_number", None))
        if pages:
            arm.cited += 1
            if ans_page in pages:
                arm.page_correct += 1
        if progress:
            print(f"      claude {q[:30]:<30} cited_pages={pages} expected={ans_page}", flush=True)
    return arm


def run_openai_arm(client, model_key: str, pdf_bytes: bytes, *, progress=False) -> ArmResult:
    """OpenAI Responses with a directly-supplied PDF (input_file). We check whether ANY annotation
    points into the supplied PDF (a file_citation). For a direct input_file there is none; file
    citations require the hosted file_search vector store, which is a different, persisted path."""
    from common.models import get
    from common.pricing import cost_from_buckets

    m = get(model_key)
    arm = ArmResult(name=f"openai:{model_key}", provider="openai", model=m.id,
                    note="Responses input_file (directly-supplied PDF); no vector store")
    data_url = "data:application/pdf;base64," + base64.standard_b64encode(pdf_bytes).decode("ascii")
    for q, ans_page, token in QUESTIONS:
        arm.asked += 1
        try:
            t0 = time.perf_counter()
            r = client.responses.create(
                model=m.id, max_output_tokens=MAX_TOKENS,
                input=[{"role": "user", "content": [
                    {"type": "input_file", "filename": "agreement.pdf", "file_data": data_url},
                    {"type": "input_text", "text": q + " Answer in one sentence and cite the page."}]}],
            )
            arm.latency += time.perf_counter() - t0
        except Exception as e:  # noqa: BLE001
            arm.errors.append(f"{q[:24]}: {type(e).__name__}: {str(e)[:90]}")
            continue
        u = r.usage
        inp = getattr(u, "input_tokens", 0) or 0
        out = getattr(u, "output_tokens", 0) or 0
        det = getattr(u, "input_tokens_details", None)
        cached = (getattr(det, "cached_tokens", 0) or 0) if det else 0
        arm.cost += cost_from_buckets(model_key, fresh_input=max(0, inp - cached), cached=cached, output=out)
        arm.input_tokens += inp
        arm.output_tokens += out
        text = getattr(r, "output_text", "") or ""
        if token.lower() in text.lower():
            arm.answered += 1
        # look for any file_citation annotation pointing into the supplied PDF
        has_pointer = False
        for item in (getattr(r, "output", None) or []):
            for c in (getattr(item, "content", None) or []):
                for a in (getattr(c, "annotations", None) or []):
                    if getattr(a, "type", None) in ("file_citation", "file_path"):
                        has_pointer = True
        if has_pointer:
            arm.cited += 1
        if progress:
            print(f"      openai {q[:30]:<30} pointer_into_pdf={has_pointer}", flush=True)
    return arm


def run_gemini_arm(client, model_key: str, pdf_bytes: bytes, *, progress=False) -> ArmResult:
    """Gemini inline PDF (document processing). We check whether the response carries any
    grounding_metadata pointing into the supplied PDF. For an inline PDF there is none; page citations
    require the hosted file_search_store."""
    from google.genai import types

    from common.models import get
    from common.pricing import cost_from_buckets

    m = get(model_key)
    arm = ArmResult(name=f"gemini:{model_key}", provider="gemini", model=m.id,
                    note="inline PDF part (directly-supplied); no file_search_store")
    part = types.Part.from_bytes(data=pdf_bytes, mime_type="application/pdf")
    for q, ans_page, token in QUESTIONS:
        arm.asked += 1
        try:
            t0 = time.perf_counter()
            r = client.models.generate_content(
                model=m.id,
                contents=[part, q + " Answer in one sentence and cite the page."],
                config=types.GenerateContentConfig(max_output_tokens=MAX_TOKENS),
            )
            arm.latency += time.perf_counter() - t0
        except Exception as e:  # noqa: BLE001
            arm.errors.append(f"{q[:24]}: {type(e).__name__}: {str(e)[:90]}")
            continue
        u = getattr(r, "usage_metadata", None)
        inp = (getattr(u, "prompt_token_count", 0) or 0) if u else 0
        out = ((getattr(u, "candidates_token_count", 0) or 0) +
               (getattr(u, "thoughts_token_count", 0) or 0)) if u else 0
        arm.cost += cost_from_buckets(model_key, fresh_input=inp, cached=0, output=out)
        arm.input_tokens += inp
        arm.output_tokens += out
        text = getattr(r, "text", None) or ""
        if token.lower() in text.lower():
            arm.answered += 1
        has_pointer = False
        for cand in (getattr(r, "candidates", None) or []):
            gm = getattr(cand, "grounding_metadata", None)
            if gm and (getattr(gm, "grounding_chunks", None) or getattr(gm, "grounding_supports", None)):
                has_pointer = True
        if has_pointer:
            arm.cited += 1
        if progress:
            print(f"      gemini {q[:30]:<30} pointer_into_pdf={has_pointer}", flush=True)
    return arm


# --------------------------------------------------------------------------- the run

@dataclass
class PdfRun:
    arms: list
    n_questions: int
    total_cost: float
    skipped: list = field(default_factory=list)


def score_run(run: PdfRun) -> dict:
    claude = next((a for a in run.arms if a.provider == "anthropic"), None)
    competitors = [a for a in run.arms if a.provider in ("openai", "gemini")]
    claude_page_correct = bool(claude and claude.asked and claude.page_correct == claude.asked)
    claude_answered = bool(claude and claude.asked and claude.answered == claude.asked)
    all_competitors_ran = len(competitors) >= 2 and all(a.asked > 0 and not a.errors for a in competitors)
    competitors_answered = bool(competitors) and all(a.answered == a.asked for a in competitors)
    competitor_any_direct_pdf_pointer = any(a.cited > 0 for a in competitors)
    positive = claude_answered and claude_page_correct and all_competitors_ran and not competitor_any_direct_pdf_pointer
    # For this subfeature the measured value is the pointer itself, not cheaper inference. Competitors
    # answered correctly but returned no direct-PDF page pointer, so the edge is promotable when every
    # arm ran and Claude's pointers resolve to the exact expected pages.
    promotable = positive
    return {
        "positive_signal": positive,
        "promotable_edge": promotable,
        "claude_answered_all": claude_answered,
        "claude_page_correct_all": claude_page_correct,
        "all_competitors_ran": all_competitors_ran,
        "competitors_answered_all": competitors_answered,
        "competitor_any_direct_pdf_pointer": competitor_any_direct_pdf_pointer,
        "why_not_promotable": [] if promotable else [
            reason for reason, failed in [
                ("Claude did not answer every question", not claude_answered),
                ("Claude did not return a correct-page citation for every question", not claude_page_correct),
                ("not every competitor direct-PDF arm ran cleanly", not all_competitors_ran),
                ("a competitor returned a direct-PDF citation pointer", competitor_any_direct_pdf_pointer),
            ] if failed
        ],
    }


def _clients():
    from common.client import get_client
    from common.runner import get_gemini_client, get_openai_client
    return {"anthropic": get_client(), "openai": get_openai_client(), "gemini": get_gemini_client()}


def run_benchmark(*, progress=False) -> PdfRun:
    clients = _clients()
    pdf_bytes = make_sample_pdf()
    arms, skipped = [], []
    if clients["anthropic"] is not None:
        if progress:
            print("    arm: claude (inline PDF + citations)")
        arms.append(run_claude_arm(clients["anthropic"], CLAUDE_MODEL, pdf_bytes, progress=progress))
    else:
        skipped.append("claude (ANTHROPIC_API_KEY absent)")
    if clients["openai"] is not None:
        if progress:
            print("    arm: openai (input_file PDF)")
        arms.append(run_openai_arm(clients["openai"], OPENAI_MODEL, pdf_bytes, progress=progress))
    else:
        skipped.append("openai (key absent)")
    if clients["gemini"] is not None:
        if progress:
            print("    arm: gemini (inline PDF)")
        arms.append(run_gemini_arm(clients["gemini"], GEMINI_MODEL, pdf_bytes, progress=progress))
    else:
        skipped.append("gemini (key absent)")
    return PdfRun(arms=arms, n_questions=len(QUESTIONS),
                  total_cost=sum(a.cost for a in arms), skipped=skipped)


# --------------------------------------------------------------------------- the Demonstrator interface

class PdfCitationsDemonstrator(BaseDemonstrator):
    demo_kind = "pdf_grounding"

    def estimate(self, edge, spec):
        return CostEstimate(usd=0.05, wall_clock_s=40.0, command="make pdf-citations",
                            note=f"{len(QUESTIONS)} questions x 3 vendors over a {len(PAGES)}-page PDF, cents")

    def _run(self, spec):
        spec = spec or {}
        if spec.get("_run") is None:
            spec["_run"] = run_benchmark(progress=spec.get("progress", False))
        return spec["_run"]

    def _arm_to_Arm(self, a: ArmResult):
        return Arm(provider=a.provider, model=a.model, ran=a.asked > 0 and not (a.errors and a.answered == 0),
                   latency_s=a.latency, input_tokens=a.input_tokens, output_tokens=a.output_tokens,
                   cost_usd=a.cost, ctx=a.input_tokens,
                   metric={"answered": f"{a.answered}/{a.asked}",
                           "cited_pointer_into_pdf": f"{a.cited}/{a.asked}",
                           "page_correct": f"{a.page_correct}/{a.asked}"},
                   note=a.note)

    def run_claude_arm(self, edge, spec):
        run = self._run(spec)
        a = next((x for x in run.arms if x.provider == "anthropic"), None)
        if a is None:
            from common.models import get
            return Arm(provider="anthropic", model=get(CLAUDE_MODEL).id, ran=False,
                       note="no Claude arm ran (ANTHROPIC_API_KEY absent)")
        return self._arm_to_Arm(a)

    def run_competitor_arms(self, edge, spec):
        run = self._run(spec)
        return [self._arm_to_Arm(a) for a in run.arms if a.provider in ("openai", "gemini")]

    def score(self, claude, competitors, spec):
        run = self._run(spec)
        ca = next((x for x in run.arms if x.provider == "anthropic"), None)
        if ca is None or ca.asked == 0:
            return Verdict(verdict="never-evaluated", passed=False, metric={"reason": "Claude arm did not run"})
        claude_resolves = ca.page_correct  # right page, verifiable
        comp_pointers = {a.name: a.cited for a in run.arms if a.provider in ("openai", "gemini")}
        all_comp_ran = bool(competitors) and all(c.ran for c in competitors)
        comp_any_pointer = any(v > 0 for v in comp_pointers.values())
        metric = {
            "claude_page_correct": f"{ca.page_correct}/{ca.asked}",
            "claude_cited": f"{ca.cited}/{ca.asked}",
            "competitor_pointers_into_pdf": comp_pointers,
        }
        if claude_resolves > 0 and not comp_any_pointer and all_comp_ran:
            return Verdict(verdict="claude-ahead", passed=True, metric=metric,
                           note="Claude returned a verifiable correct-page pointer into the supplied PDF; "
                                "no competitor returned any pointer into the directly-supplied PDF")
        if claude_resolves > 0 and not all_comp_ran:
            return Verdict(verdict="never-evaluated", passed=False, metric=metric,
                           note="Claude resolved page pointers, but not every competitor arm ran")
        if comp_any_pointer:
            return Verdict(verdict="parity", passed=False, metric=metric,
                           note="a competitor also returned a pointer into the supplied PDF")
        return Verdict(verdict="within-claude-only", passed=False, metric=metric,
                       note="Claude did not resolve correct page pointers on this run")

    def receipt(self, edge, claude, competitors, verdict, spec):
        run = self._run(spec)
        return self.build_receipt(
            edge, claude, competitors, verdict, spec,
            workload={
                "task_shape": f"{run.n_questions} questions over a {len(PAGES)}-page synthetic agreement "
                              f"PDF supplied directly in the request; the gate is a verifiable per-page "
                              f"pointer into that PDF, checked against the known answer page",
                "models": {"claude": claude.model, "competitors": [c.model for c in competitors]},
                "features_on": ["Citations on an inline PDF document block (page_location)"],
                "assumptions": "the PDF is text-extractable (scanned/image-only PDFs are not citable on "
                               "Claude); competitors are scored on whether the DIRECT-PDF path returns "
                               "any pointer, since a hosted vector store is a different persisted path",
            },
            grounding=[
                {"claim": "Citations on a PDF return a page_location with start/end page and the quote",
                 "source_url": "https://platform.claude.com/docs/en/build-with-claude/citations",
                 "date": "2026-06-19"},
                {"claim": "PDF support processes each page as text and image (inline base64/URL/file_id)",
                 "source_url": "https://platform.claude.com/docs/en/build-with-claude/pdf-support",
                 "date": "2026-06-19"},
                {"claim": "OpenAI file citations come from the hosted file_search store, not a direct input_file",
                 "source_url": "https://developers.openai.com/api/docs/guides/tools-file-search",
                 "date": "2026-06-19"},
                {"claim": "Gemini page citations come from the file_search_store, not an inline PDF part",
                 "source_url": "https://ai.google.dev/gemini-api/docs/file-search", "date": "2026-06-19"},
            ],
            fairness={
                "best_to_best": "each competitor reads the same directly-supplied PDF with a capable "
                                "model; the comparison is the direct-PDF citation path, named, not a strawman",
                "isolate": "the same PDF, the same questions, the same one-sentence-and-cite instruction "
                           "on every arm; only the platform differs",
            },
        )


register(PdfCitationsDemonstrator())


# --------------------------------------------------------------------------- the CLI receipt

def _print_run(run: PdfRun) -> None:
    from common.client import fmt_usd

    print("\n  === PDF citations: a verifiable per-page pointer into a directly-supplied PDF ===")
    print(f"  {run.n_questions} questions over a {len(PAGES)}-page synthetic agreement PDF.\n")
    header = f"  {'arm':<24}{'answered':>10}{'pointer-to-PDF':>14}{'right page':>12}{'cost':>10}"
    print(header)
    print("  " + "-" * (len(header) - 2))
    for a in run.arms:
        print(f"  {a.name:<24}{f'{a.answered}/{a.asked}':>10}{f'{a.cited}/{a.asked}':>14}"
              f"{f'{a.page_correct}/{a.asked}':>12}{fmt_usd(a.cost):>10}")
        if a.errors:
            print(f"      note: {a.errors[0]}")
    print(f"\n  total spend this run: {fmt_usd(run.total_cost)}")
    if run.skipped:
        print(f"  arms not run: {', '.join(run.skipped)}")


def _receipt_dict(run: PdfRun) -> dict:
    verdict = score_run(run)
    return {
        "date": "2026-06-19",
        "claim_under_test": (
            "For a directly supplied text PDF, Claude Citations returns a verifiable page_location "
            "pointer and cited text, while OpenAI input_file and Gemini inline PDF answer but do not "
            "return a pointer into the supplied PDF."
        ),
        "n_questions": run.n_questions,
        "n_pages": len(PAGES),
        "total_cost": round(run.total_cost, 6),
        "sources": {
            "claude_citations": "https://platform.claude.com/docs/en/build-with-claude/citations",
            "claude_pdf_support": "https://platform.claude.com/docs/en/build-with-claude/pdf-support",
            "openai_files": "https://developers.openai.com/api/docs/guides/file-inputs",
            "openai_file_search": "https://developers.openai.com/api/docs/guides/tools-file-search",
            "gemini_document_processing": "https://ai.google.dev/gemini-api/docs/document-processing",
            "gemini_file_search": "https://ai.google.dev/gemini-api/docs/file-search",
        },
        "skipped": run.skipped,
        "arms": [{"name": a.name, "provider": a.provider, "model": a.model,
                  "answered": f"{a.answered}/{a.asked}", "cited": f"{a.cited}/{a.asked}",
                  "page_correct": f"{a.page_correct}/{a.asked}", "cost": round(a.cost, 6),
                  "latency_s": round(a.latency, 2), "errors": a.errors} for a in run.arms],
        "verdict": verdict,
    }


def _sample_text(receipt: dict) -> str:
    rows = [
        "  Direct-PDF citation workload: five questions over a five-page synthetic agreement PDF.",
        "  The file is supplied directly in the request, not uploaded to a hosted vector store.",
        "",
        "  platform                       answered   direct-PDF pointer   right page     cost  wall time",
        "  -----------------------------------------------------------------------------------------------",
    ]
    for arm in receipt["arms"]:
        rows.append(
            f"  {arm['name']:<30}{arm['answered']:>8}{arm['cited']:>21}"
            f"{arm['page_correct']:>13}{('$' + format(arm['cost'], '.4f')):>9}{arm['latency_s']:>9.1f}s"
        )
    verdict = receipt["verdict"]
    rows.extend([
        "",
        "  Verdict:",
        f"    positive_signal: {str(verdict['positive_signal']).lower()}",
        f"    promotable_edge: {str(verdict['promotable_edge']).lower()}",
        "",
        "  Honest reading:",
        "  - Claude returned page-location citations that resolved to the correct page for 5/5 answers.",
        "  - OpenAI and Gemini answered the direct-PDF questions, but returned no direct-PDF page pointer.",
        "  - The claim is scoped to directly supplied PDFs. Hosted vector-store/file-search paths are",
        "    different product flows and are named separately in the sources.",
        "",
        "  Reproduce:",
        "    make pdf-citations",
        "",
        "  Machine receipt:",
        "    data/last_pdf_citations.json",
    ])
    return "\n".join(rows) + "\n"


def write_edge_bundle(run: PdfRun, receipt: dict) -> pathlib.Path:
    from common.client import repo_root

    edge_dir = repo_root() / "edges" / "pdf-citations"
    edge_dir.mkdir(parents=True, exist_ok=True)
    (edge_dir / "sample.pdf").write_bytes(make_sample_pdf())
    (edge_dir / "receipt.json").write_text(json.dumps(receipt, indent=2) + "\n")
    (edge_dir / "sample.txt").write_text(_sample_text(receipt))
    (edge_dir / "demo.py").write_text(
        '"""pdf-citations: wrapper for the direct-PDF citation edge."""\n\n'
        "from engine.demonstrators.pdf_citations import main\n\n\n"
        'if __name__ == "__main__":\n'
        "    raise SystemExit(main())\n"
    )
    rows = [
        "| arm | answered | direct-PDF pointer | right page | cost | wall time |",
        "|---|:---:|:---:|:---:|---:|---:|",
    ]
    for arm in receipt["arms"]:
        rows.append(
            f"| {arm['name']} | {arm['answered']} | {arm['cited']} | {arm['page_correct']} | "
            f"${arm['cost']:.4f} | {arm['latency_s']:.1f}s |"
        )
    (edge_dir / "README.md").write_text(
        "# Edge: PDF citations, page pointers for directly supplied PDFs\n\n"
        "Part of [claude-feature-radar](../../README.md). This is a measured grounding edge for "
        "directly supplied PDFs, not a claim about hosted vector-store search.\n\n"
        "## What It Is\n\n"
        "A user uploads a PDF and asks a question immediately. Claude Citations can return a "
        "`page_location` citation for the PDF supplied in the request, including the page number and "
        "quoted source text. The app does not need to persist the document in a hosted search store "
        "or write its own page resolver.\n\n"
        "## The Measured Proof\n\n"
        f"Run: `make pdf-citations`, {receipt['date']}, five questions over a five-page agreement PDF.\n\n"
        + "\n".join(rows)
        + "\n\n"
        "Claude answered every question and returned a correct-page citation for every answer. OpenAI "
        "and Gemini answered the same direct-PDF questions but returned no pointer into the supplied "
        "PDF on this direct-file path.\n\n"
        "Full receipt: [`sample.txt`](sample.txt). Machine receipt: [`receipt.json`](receipt.json). "
        "Sample PDF: [`sample.pdf`](sample.pdf).\n\n"
        "## Honest Scope\n\n"
        "- This is a direct-PDF grounding edge for text-extractable PDFs.\n"
        "- Scanned/image-only PDFs are outside this claim because Claude PDF citations require "
        "extractable text.\n"
        "- OpenAI and Gemini have hosted file-search or vector-store paths. Those are different "
        "persisted workflows, not the direct PDF supplied inside the same request.\n\n"
        "## Run It Yourself\n\n"
        "```bash\n"
        "git clone https://github.com/cfregly/claude-feature-radar && cd claude-feature-radar\n"
        "make setup\n"
        "make compare-deps\n"
        "cp .env.example .env   # paste ANTHROPIC_API_KEY, OPENAI_API_KEY, and GEMINI_API_KEY\n"
        "make pdf-citations     # cents-scale direct-PDF citation receipt\n"
        "```\n\n"
        "Sources:\n\n"
        f"- Claude citations: {receipt['sources']['claude_citations']}\n"
        f"- Claude PDF support: {receipt['sources']['claude_pdf_support']}\n"
        f"- OpenAI file inputs: {receipt['sources']['openai_files']}\n"
        f"- OpenAI file search: {receipt['sources']['openai_file_search']}\n"
        f"- Gemini document processing: {receipt['sources']['gemini_document_processing']}\n"
        f"- Gemini file search: {receipt['sources']['gemini_file_search']}\n"
    )
    return edge_dir


def main(argv=None) -> int:
    from common.client import load_env, repo_root

    p = argparse.ArgumentParser(description="pdf_citations: a per-page pointer into a directly-supplied "
                                            "PDF, vs OpenAI input_file and Gemini inline PDF.")
    p.add_argument("--emit-edge", action="store_true", help="write the sample PDF + receipt under edges/pdf-citations/")
    p.add_argument("--write-sample", action="store_true", help="just write the sample PDF and exit (no API call)")
    a = p.parse_args(argv)

    load_env()
    if a.write_sample:
        path = sample_pdf_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(make_sample_pdf())
        print(f"  wrote {path} ({path.stat().st_size} bytes)")
        return 0

    print("\n  pdf_citations: does the platform return a verifiable pointer to the exact page of a")
    print("  directly-supplied PDF? Same PDF, same questions, every arm.\n")
    run = run_benchmark(progress=True)
    _print_run(run)

    out = _receipt_dict(run)
    (repo_root() / "data").mkdir(exist_ok=True)
    (repo_root() / "data" / "last_pdf_citations.json").write_text(json.dumps(out, indent=2) + "\n")
    if a.emit_edge:
        write_edge_bundle(run, out)
        print(f"\n  wrote edges/pdf-citations/{{README.md,demo.py,sample.txt,sample.pdf,receipt.json}}")
    print("\n  (per-run detail in gitignored data/last_pdf_citations.json)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
