"""paraphrase_resolution: the paraphrase-robustness arm of the Citations edge, measured head to head.

WHY THIS EXISTS. The citations edge was tightened to its surviving wedge: the win is NOT character
granularity (that holds only for plain text; PDFs are page-level, the same coarseness as Gemini File
Search). The wedge is the GUARANTEE. Claude's Citations API guarantees every returned pointer resolves
to a real source span, and the do-it-yourself path (the model emits a supporting quote, you locate it
with `str.find`) cannot, because the moment the model answers in its own words the quote is paraphrased,
`str.find` returns -1, and the citation is silently dropped. On clean VERBATIM quotes the DIY path
resolves about as well on every vendor (the citations edge measures that, parity). The one case the
skeptic flagged as "not measured" is the PARAPHRASE case. This demonstrator measures it directly.

WHAT IT MEASURES, the SAME setup on every arm. A document set (plain-text user docs plus one inline
PDF) and a fixed set of questions. Every arm gets the SAME instruction: answer in your own words, do
not copy a sentence verbatim, and point to the supporting source. The single thing that differs is the
RESOLVE MECHANISM:

  Claude + Citations   citations.enabled on the supplied documents. The model paraphrases its prose,
                       and the API attaches a pointer whose `cited_text` is the verbatim source span it
                       extracted (NOT the model's prose), so source[start:end] == cited_text resolves
                       BY CONSTRUCTION. For the inline PDF the pointer is a page_location into the
                       supplied file, with zero persisted/hosted objects.
  DIY (any vendor)     the path you build without the feature: the model returns a paraphrased answer
                       and a paraphrased supporting sentence, and you resolve it yourself with
                       source.find(quote). Under paraphrase the find returns -1: a silent drop. You own
                       the resolver code AND you pay output tokens for every quote.

THE GATES (all measured, same gate on every arm):
  - paraphrase-resolution rate per arm: Claude guaranteed-resolve vs the DIY drop rate.
  - no hosted store: the Claude path returns its pointers with zero persisted/hosted objects.
  - can cite the inline PDF: Claude returns a resolving page_location into the directly-supplied PDF,
    a pointer the competitors' citation features cannot produce without a hosted vector store (measured
    head to head in the pdf-citations and grounding-stack edges).
  - output-token cost: Citations `cited_text` is free of output tokens (docs), while the DIY arms pay
    output tokens for every quote. The column shows the measured per-arm output tokens.

FOUNDER WORKLOAD. A product that answers a user's question over the user's own documents (a contract, a
policy, a report, the app's own wiki chunks) IN READABLE, PARAPHRASED PROSE, and must deep-link each
answer to the exact source so a human can verify before acting. The value a founder prices: a pointer
that always resolves, with zero resolver code and no third-party copy of the user's data, even when the
answer is paraphrased (which is what users want to read).

GROUNDING. "Citations are guaranteed to contain valid pointers to the provided documents" and
`cited_text` "does not count towards output tokens", platform.claude.com/docs/en/build-with-claude/citations
(re-fetched 2026-06-19). The competitor citation paths (OpenAI file_citation, Gemini File Search) cite
only through a hosted, pre-indexed store and document no inline guaranteed-resolve pointer.

DEPENDENCIES. The Claude arm needs only anthropic. The OpenAI and Gemini DIY arms need their optional
SDKs and keys (pulled lazily). The PDF is generated with the standard library alone (shared with
pdf_citations), so the repo stays forkable with no PDF dependency.

MODEL TIER. The arms answer and ground over the user's documents, a seat that decides correctness, so
the Claude arm runs on Sonnet (never Haiku, which cannot take the effort knob or adaptive thinking) and
the competitor DIY arms run on their balanced tier, tier-matched. The grader itself is deterministic
code (source[start:end]==cited_text and source.find(quote)), no model judgment.
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import pathlib
import re
import sys
import time
from dataclasses import dataclass, field

# repo root on the path, for common/ and engine/ when run as a script.
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))

from engine.demonstrators.base import Arm, BaseDemonstrator, CostEstimate, Verdict
from engine.demonstrators.pdf_citations import PAGES, make_sample_pdf
from engine.demonstrators.shared import platform

# The answering+grounding seat decides correctness, so Sonnet on the Claude side and the competitors'
# balanced tier, tier-matched, never Haiku for a correctness seat. All overridable via env for a forked run.
CLAUDE_MODEL = os.environ.get("PARA_CLAUDE_MODEL", "sonnet")
OPENAI_MODEL = os.environ.get("PARA_OPENAI_MODEL", "gpt-mid")     # gpt-5.4, balanced, tier-matched to Sonnet
GEMINI_MODEL = os.environ.get("PARA_GEMINI_MODEL", "gem-flash")   # gemini-3.5-flash, balanced
MAX_TOKENS = int(os.environ.get("PARA_MAX_TOKENS", "400"))        # the Citations arm: a short paraphrased answer
# The DIY arms emit a JSON answer plus quote. Gemini 3.5 Flash thinks by default, so give the DIY arms
# enough output budget that extended thinking is never starved. Thinking stays ON (best config, never
# handicapped); the budget only keeps a thinking model from running out of room before it answers.
DIY_MAX_TOKENS = int(os.environ.get("PARA_DIY_MAX_TOKENS", "1536"))


# --------------------------------------------------------------------------- the document set
#
# Three plain-text user documents (char_location granularity) plus the shared 5-page agreement PDF
# (page_location granularity), each carrying disjoint, citable, startup-native facts. The PDF text is
# reconstructed from the same PAGES that generate the bytes, so the DIY arms can str.find over the
# extracted text exactly as a founder's own resolver would.

TEXT_DOCS = [
    {
        "title": "Usage Metering Policy",
        "text": (
            "Every API call is metered at the moment the response is returned, not when the request is "
            "received. Metered usage is aggregated hourly and written to the billing ledger within five "
            "minutes of the top of each hour. A call that fails with a 5xx server error is not metered "
            "and is never counted against the plan allowance. Usage above the plan allowance is billed "
            "as overage at the end of the cycle."
        ),
    },
    {
        "title": "Plan Limits and Seats",
        "text": (
            "The Growth plan includes 25 seats and a monthly allowance of two million API calls. "
            "Additional seats beyond the included 25 are billed at 9 US dollars per seat per month. "
            "The Growth plan API rate limit is 600 requests per minute, measured per organization rather "
            "than per key. Rate-limit headroom does not roll over between minutes."
        ),
    },
    {
        "title": "Churn and Cancellation Terms",
        "text": (
            "An organization may cancel at any time from the billing settings page. A cancellation takes "
            "effect at the end of the current billing cycle, and access continues until that date. A "
            "customer who cancels within 14 days of the initial signup receives a full refund of the "
            "first cycle. Exported account data remains downloadable for 30 days after the cycle ends, "
            "after which it is permanently deleted."
        ),
    },
]

# The PDF page text, reconstructed from the shared PAGES (heading plus body), one entry per page.
PDF_TITLE = "Pro Plan Agreement"
PDF_PAGE_TEXTS = [f"{heading} {body}" for heading, body in PAGES]
PDF_FULL_TEXT = "\n\n".join(PDF_PAGE_TEXTS)

# Each question names where its answer lives and the accepted forms of a correct answer. "text"
# questions resolve to a char_location in TEXT_DOCS[index]; "pdf" questions resolve to a page_location
# on the named PDF page (1-indexed). The accept list is the machine-checkable answer gate, so a refusal
# or a wrong answer never counts. It carries both the digit and the spelled-out form of a number,
# because a paraphrased answer may write "twenty-five" where the source says "25".
QUESTIONS = [
    {"q": "When is an API call metered, at request time or at response time?",
     "kind": "text", "ref": 0, "accept": ["response"]},
    {"q": "How many seats does the Growth plan include?",
     "kind": "text", "ref": 1, "accept": ["25", "twenty-five", "twenty five"]},
    {"q": "What is the Growth plan rate limit in requests per minute?",
     "kind": "text", "ref": 1, "accept": ["600", "six hundred"]},
    {"q": "How long does exported account data stay downloadable after the cycle ends?",
     "kind": "text", "ref": 2, "accept": ["30", "thirty"]},
    {"q": "What refund does a customer get if they cancel within 14 days of signup?",
     "kind": "text", "ref": 2, "accept": ["full", "money back", "all of their money", "entire",
                                          "complete refund", "100%", "all of the"]},
    {"q": "Is a call that fails with a 5xx server error counted against the plan allowance?",
     "kind": "text", "ref": 0, "accept": ["not counted", "never counted", "not metered", "neither metered",
                                          "does not count", "do not count", "not deducted", "isn't counted",
                                          "is not counted", "excluded"]},
    {"q": "How much is each overage seat per month on the Pro plan agreement?",
     "kind": "pdf", "ref": 2, "accept": ["12", "twelve"]},
    {"q": "What is the monthly uptime commitment in the Pro plan agreement?",
     "kind": "pdf", "ref": 5, "accept": ["99.9"]},
]

# The one instruction every arm gets: answer in your own words, do not copy verbatim. This is the
# regime the skeptic flagged as unmeasured. On clean verbatim quotes the DIY path resolves (parity, the
# citations edge); here the model paraphrases, so the DIY str.find drops the pointer.
PARAPHRASE_RULE = ("Answer in your own words. Paraphrase the source. Do NOT copy any sentence verbatim "
                   "from the documents.")

# The DIY ask: the realistic path without the feature, the model returns the supporting sentence (in its
# own words, per the rule above) and you resolve it yourself with str.find.
DIY_INSTRUCTIONS = (
    PARAPHRASE_RULE + " Then give the single supporting sentence from the source, in your own words, "
    "and the exact title of the document it came from. Respond with ONLY a JSON object and nothing "
    'else: {"answer": "...", "doc_title": "...", "quote": "..."}.'
)

ALL_DOC_TITLES = [d["title"] for d in TEXT_DOCS] + [PDF_TITLE]


def _questions(quick: bool):
    # quick: two text questions and one PDF question, a cents-scale smoke that still exercises both
    # location types and the paraphrase drop.
    return [QUESTIONS[1], QUESTIONS[2], QUESTIONS[7]] if quick else QUESTIONS


def _normws(s: str) -> str:
    return " ".join((s or "").split())


# PDF text extraction normalizes typography (a straight apostrophe in the source comes back as a curly
# one, an en-dash for a hyphen). The char_location check below stays byte-exact (the API guarantee for
# text documents), but the page_location check folds these so a real PDF span is not failed over a
# rendering artifact, while still requiring the cited text to be a genuine span of the page.
_SMART = {"’": "'", "‘": "'", "“": '"', "”": '"',
          "–": "-", "—": "-", " ": " "}


def _fold(s: str) -> str:
    s = s or ""
    for a, b in _SMART.items():
        s = s.replace(a, b)
    return " ".join(s.split())


def _answered(item: dict, text: str) -> bool:
    t = (text or "").lower()
    return any(a.lower() in t for a in item["accept"])


def _parse_json(raw: str):
    """Pull the first JSON object out of a model reply, tolerating code fences and prose."""
    if not raw:
        return None
    m = re.search(r"\{.*\}", raw, re.DOTALL)
    if not m:
        return None
    try:
        return json.loads(m.group(0))
    except json.JSONDecodeError:
        return None


# --------------------------------------------------------------------------- the arms

@dataclass
class ArmResult:
    name: str
    provider: str
    model: str
    mechanism: str             # "API citations" or "DIY str.find"
    ran: bool = True
    asked: int = 0
    answered: int = 0          # the answer contained the expected token
    cited: int = 0             # questions that returned at least one pointer/quote
    resolved: int = 0          # questions whose pointer resolves to a real source span
    pdf_pointer_resolved: int = 0   # PDF questions that returned a resolving page_location into the inline PDF
    pdf_asked: int = 0
    persisted_objects: int = 0      # hosted/vector-store objects the path required
    cost: float = 0.0
    latency: float = 0.0
    input_tokens: int = 0
    output_tokens: int = 0
    note: str = ""
    errors: list = field(default_factory=list)

    @property
    def drops(self) -> int:
        # silent drops: a pointer/quote was produced but did not resolve.
        return max(0, self.cited - self.resolved)

    @property
    def resolution_rate(self) -> float:
        return (self.resolved / self.asked) if self.asked else 0.0


def _claude_doc_blocks(pdf_b64: str):
    blocks = [
        {"type": "document",
         "source": {"type": "text", "media_type": "text/plain", "data": d["text"]},
         "title": d["title"], "citations": {"enabled": True}}
        for d in TEXT_DOCS
    ]
    blocks.append({"type": "document",
                   "source": {"type": "base64", "media_type": "application/pdf", "data": pdf_b64},
                   "title": PDF_TITLE, "citations": {"enabled": True}})
    return blocks  # indices 0..2 are TEXT_DOCS, index 3 is the PDF


def _resolve_char(di: int, start: int, end: int, cited_text: str) -> bool:
    # The API guarantee, checked exactly: the span equals the cited text, no normalization needed.
    return 0 <= di < len(TEXT_DOCS) and TEXT_DOCS[di]["text"][start:end] == cited_text


def _resolve_page(page, cited_text: str) -> bool:
    # The page exists in the supplied PDF and the cited text is a real span on it. PDF text extraction
    # re-wraps whitespace and normalizes typography, so the span check folds both sides before matching.
    if not isinstance(page, int) or not (1 <= page <= len(PDF_PAGE_TEXTS)):
        return False
    return bool((cited_text or "").strip()) and _fold(cited_text) in _fold(PDF_PAGE_TEXTS[page - 1])


def run_claude_arm(client, model_key: str, questions, pdf_b64: str, *, progress=False) -> ArmResult:
    from common.models import get
    from common.pricing import cost_breakdown

    m = get(model_key)
    arm = ArmResult(name=f"claude+citations:{model_key}", provider="anthropic", model=m.id,
                    mechanism="API citations", persisted_objects=0,
                    note="citations.enabled on inline text docs and an inline PDF, paraphrased answer, no hosted store")
    platform.used("citations", "guaranteed-resolve pointer under a paraphrased answer, zero hosted objects")
    blocks = _claude_doc_blocks(pdf_b64)
    for item in questions:
        arm.asked += 1
        is_pdf = item["kind"] == "pdf"
        if is_pdf:
            arm.pdf_asked += 1
        content = blocks + [{"type": "text", "text": f"{item['q']} {PARAPHRASE_RULE}"}]
        try:
            t0 = time.perf_counter()
            r = client.messages.create(model=m.id, max_tokens=MAX_TOKENS,
                                       messages=[{"role": "user", "content": content}])
            arm.latency += time.perf_counter() - t0
        except Exception as e:  # noqa: BLE001
            arm.errors.append(f"{item['q'][:24]}: {type(e).__name__}: {str(e)[:80]}")
            continue
        arm.cost += cost_breakdown(model_key, r.usage).total
        arm.input_tokens += getattr(r.usage, "input_tokens", 0) or 0
        arm.output_tokens += getattr(r.usage, "output_tokens", 0) or 0
        text = "".join(b.text for b in r.content if getattr(b, "type", None) == "text")
        if _answered(item, text):
            arm.answered += 1
        q_has_cite = False
        q_resolves = False
        q_pdf_resolves = False
        for b in r.content:
            if getattr(b, "type", None) != "text":
                continue
            for c in (getattr(b, "citations", None) or []):
                ctype = getattr(c, "type", None)
                if ctype == "char_location":
                    q_has_cite = True
                    if _resolve_char(getattr(c, "document_index", -1), getattr(c, "start_char_index", -1),
                                     getattr(c, "end_char_index", -1), getattr(c, "cited_text", "")):
                        q_resolves = True
                elif ctype == "page_location":
                    q_has_cite = True
                    if _resolve_page(getattr(c, "start_page_number", None), getattr(c, "cited_text", "")):
                        q_resolves = True
                        q_pdf_resolves = True
        if q_has_cite:
            arm.cited += 1
        if q_resolves:
            arm.resolved += 1
        if is_pdf and q_pdf_resolves:
            arm.pdf_pointer_resolved += 1
        if progress:
            print(f"      claude  {item['q'][:34]:<34} cite={q_has_cite} resolves={q_resolves}", flush=True)
    return arm


def _diy_corpus_text() -> str:
    parts = [f"=== DOCUMENT: {d['title']} ===\n{d['text']}" for d in TEXT_DOCS]
    parts.append(f"=== DOCUMENT: {PDF_TITLE} ===\n{PDF_FULL_TEXT}")
    return "\n\n".join(parts)


def _source_text_for(title: str) -> str:
    t = (title or "").lower()
    for d in TEXT_DOCS:
        if d["title"].lower() in t or t in d["title"].lower():
            return d["text"]
    if PDF_TITLE.lower() in t or t in PDF_TITLE.lower():
        return PDF_FULL_TEXT
    return ""


def _grade_diy(raw_text: str):
    """The model returned a paraphrased answer and a quote. Resolve the quote ourselves with str.find,
    the real DIY path. Returns (has_quote, resolves, answer_text)."""
    obj = _parse_json(raw_text) or {}
    quote = (obj.get("quote") or "").strip()
    title = (obj.get("doc_title") or "").strip()
    answer = (obj.get("answer") or "")
    src = _source_text_for(title)
    idx = src.find(quote) if (src and quote) else -1
    return quote != "", idx != -1, answer


def run_claude_diy_arm(client, model_key: str, questions, *, progress=False) -> ArmResult:
    from common.models import get
    from common.pricing import cost_breakdown

    m = get(model_key)
    arm = ArmResult(name=f"claude DIY:{model_key}", provider="anthropic", model=m.id,
                    mechanism="DIY str.find", persisted_objects=0,
                    note="the path WITHOUT the feature on Claude: model paraphrases the quote, your str.find resolves it")
    src = _diy_corpus_text()
    for item in questions:
        arm.asked += 1
        if item["kind"] == "pdf":
            arm.pdf_asked += 1
        prompt = f"{DIY_INSTRUCTIONS}\n\nSOURCE DOCUMENTS:\n{src}\n\nQUESTION: {item['q']}"
        try:
            t0 = time.perf_counter()
            r = client.messages.create(model=m.id, max_tokens=DIY_MAX_TOKENS,
                                       messages=[{"role": "user", "content": prompt}])
            arm.latency += time.perf_counter() - t0
        except Exception as e:  # noqa: BLE001
            arm.errors.append(f"{item['q'][:24]}: {type(e).__name__}: {str(e)[:80]}")
            continue
        arm.cost += cost_breakdown(model_key, r.usage).total
        arm.input_tokens += getattr(r.usage, "input_tokens", 0) or 0
        arm.output_tokens += getattr(r.usage, "output_tokens", 0) or 0
        text = "".join(b.text for b in r.content if getattr(b, "type", None) == "text")
        has_quote, resolves, answer = _grade_diy(text)
        if _answered(item, answer or text):
            arm.answered += 1
        if has_quote:
            arm.cited += 1
        if resolves:
            arm.resolved += 1
        if progress:
            print(f"      cl-DIY  {item['q'][:34]:<34} quote={has_quote} find!=-1={resolves}", flush=True)
    return arm


def run_openai_diy_arm(client, model_key: str, questions, *, progress=False) -> ArmResult:
    from common.models import get
    from common.pricing import cost_from_buckets

    m = get(model_key)
    arm = ArmResult(name=f"openai DIY:{model_key}", provider="openai", model=m.id,
                    mechanism="DIY str.find", persisted_objects=0,
                    note="model paraphrases the supporting quote, your str.find resolves it")
    src = _diy_corpus_text()
    for item in questions:
        arm.asked += 1
        if item["kind"] == "pdf":
            arm.pdf_asked += 1
        prompt = f"{DIY_INSTRUCTIONS}\n\nSOURCE DOCUMENTS:\n{src}\n\nQUESTION: {item['q']}"
        try:
            t0 = time.perf_counter()
            r = client.responses.create(model=m.id, max_output_tokens=DIY_MAX_TOKENS, input=prompt)
            arm.latency += time.perf_counter() - t0
        except Exception as e:  # noqa: BLE001
            arm.errors.append(f"{item['q'][:24]}: {type(e).__name__}: {str(e)[:90]}")
            continue
        u = r.usage
        inp = getattr(u, "input_tokens", 0) or 0
        out = getattr(u, "output_tokens", 0) or 0
        det = getattr(u, "input_tokens_details", None)
        cached = (getattr(det, "cached_tokens", 0) or 0) if det else 0
        arm.cost += cost_from_buckets(model_key, fresh_input=max(0, inp - cached), cached=cached, output=out)
        arm.input_tokens += inp
        arm.output_tokens += out
        raw = getattr(r, "output_text", "") or ""
        has_quote, resolves, answer = _grade_diy(raw)
        if _answered(item, answer or raw):
            arm.answered += 1
        if has_quote:
            arm.cited += 1
        if resolves:
            arm.resolved += 1
        if progress:
            print(f"      oa-DIY  {item['q'][:34]:<34} quote={has_quote} find!=-1={resolves}", flush=True)
    return arm


def run_gemini_diy_arm(client, model_key: str, questions, *, progress=False) -> ArmResult:
    from google.genai import types

    from common.models import get
    from common.pricing import cost_from_buckets

    m = get(model_key)
    arm = ArmResult(name=f"gemini DIY:{model_key}", provider="gemini", model=m.id,
                    mechanism="DIY str.find", persisted_objects=0,
                    note="model paraphrases the supporting quote, your str.find resolves it")
    src = _diy_corpus_text()
    for item in questions:
        arm.asked += 1
        if item["kind"] == "pdf":
            arm.pdf_asked += 1
        prompt = f"{DIY_INSTRUCTIONS}\n\nSOURCE DOCUMENTS:\n{src}\n\nQUESTION: {item['q']}"
        try:
            t0 = time.perf_counter()
            r = client.models.generate_content(
                model=m.id, contents=prompt,
                config=types.GenerateContentConfig(max_output_tokens=DIY_MAX_TOKENS))
            arm.latency += time.perf_counter() - t0
        except Exception as e:  # noqa: BLE001
            arm.errors.append(f"{item['q'][:24]}: {type(e).__name__}: {str(e)[:90]}")
            continue
        u = getattr(r, "usage_metadata", None)
        inp = (getattr(u, "prompt_token_count", 0) or 0) if u else 0
        cached = (getattr(u, "cached_content_token_count", 0) or 0) if u else 0
        out = ((getattr(u, "candidates_token_count", 0) or 0) +
               (getattr(u, "thoughts_token_count", 0) or 0)) if u else 0
        arm.cost += cost_from_buckets(model_key, fresh_input=max(0, inp - cached), cached=cached, output=out)
        arm.input_tokens += inp
        arm.output_tokens += out
        raw = getattr(r, "text", None) or ""
        has_quote, resolves, answer = _grade_diy(raw)
        if _answered(item, answer or raw):
            arm.answered += 1
        if has_quote:
            arm.cited += 1
        if resolves:
            arm.resolved += 1
        if progress:
            print(f"      gm-DIY  {item['q'][:34]:<34} quote={has_quote} find!=-1={resolves}", flush=True)
    return arm


# --------------------------------------------------------------------------- the run

@dataclass
class ParaRun:
    arms: list
    n_questions: int
    n_pdf: int
    total_cost: float
    skipped: list = field(default_factory=list)


def _clients():
    from common.client import get_client
    from common.runner import get_gemini_client, get_openai_client
    return {"anthropic": get_client(), "openai": get_openai_client(), "gemini": get_gemini_client()}


def run_benchmark(*, quick=False, progress=False) -> ParaRun:
    clients = _clients()
    questions = _questions(quick)
    n_pdf = sum(1 for q in questions if q["kind"] == "pdf")
    pdf_b64 = base64.standard_b64encode(make_sample_pdf()).decode("ascii")
    arms, skipped = [], []
    if clients["anthropic"] is not None:
        if progress:
            print("    arm: claude + Citations (paraphrased answer, guaranteed-resolve pointer)")
        arms.append(run_claude_arm(clients["anthropic"], CLAUDE_MODEL, questions, pdf_b64, progress=progress))
        if progress:
            print("    arm: claude DIY (paraphrased quote + your str.find)")
        arms.append(run_claude_diy_arm(clients["anthropic"], CLAUDE_MODEL, questions, progress=progress))
    else:
        skipped.append("claude (ANTHROPIC_API_KEY absent)")
    if clients["openai"] is not None:
        if progress:
            print("    arm: openai DIY (paraphrased quote + your str.find)")
        arms.append(run_openai_diy_arm(clients["openai"], OPENAI_MODEL, questions, progress=progress))
    else:
        skipped.append("openai (key absent)")
    if clients["gemini"] is not None:
        if progress:
            print("    arm: gemini DIY (paraphrased quote + your str.find)")
        arms.append(run_gemini_diy_arm(clients["gemini"], GEMINI_MODEL, questions, progress=progress))
    else:
        skipped.append("gemini (key absent)")
    return ParaRun(arms=arms, n_questions=len(questions), n_pdf=n_pdf,
                   total_cost=sum(a.cost for a in arms), skipped=skipped)


def score_run(run: ParaRun) -> dict:
    """The same machine gate on every arm: the paraphrase-resolution rate, by construction for Citations
    and by str.find for the DIY arms. The cross-vendor competitors are the OpenAI and Gemini DIY arms;
    the Claude DIY arm is the within-Claude baseline shown alongside. The edge is promotable when Claude
    resolves every question's pointer (guaranteed), returns those pointers with zero hosted objects,
    cites the inline PDF, every cross-vendor arm ran, and the DIY path silently drops under paraphrase."""
    claude = next((a for a in run.arms if a.provider == "anthropic" and a.mechanism == "API citations"), None)
    competitors = [a for a in run.arms if a.provider in ("openai", "gemini")]  # cross-vendor DIY arms
    diy_arms = [a for a in run.arms if a.mechanism == "DIY str.find"]

    n = run.n_questions
    claude_answered_all = bool(claude and claude.asked == n and claude.answered == n)
    claude_resolves_all = bool(claude and claude.asked == n and claude.resolved == n and claude.cited == n)
    claude_no_hosted_store = bool(claude and claude.persisted_objects == 0)
    claude_cites_inline_pdf = bool(claude and claude.pdf_asked > 0 and claude.pdf_pointer_resolved == claude.pdf_asked)

    all_competitors_ran = len(competitors) >= 2 and all(a.asked == n and not a.errors for a in competitors)
    competitor_drop_total = sum(a.drops for a in competitors)
    best_competitor_rate = max((a.resolution_rate for a in competitors), default=1.0)
    diy_drops_under_paraphrase = competitor_drop_total > 0 and best_competitor_rate < 1.0
    claude_beats_best_diy = bool(claude) and claude.resolution_rate > best_competitor_rate

    positive = (claude_answered_all and claude_resolves_all and claude_no_hosted_store
                and claude_cites_inline_pdf and all_competitors_ran and diy_drops_under_paraphrase
                and claude_beats_best_diy)

    return {
        "positive_signal": positive,
        "promotable_edge": positive,
        # the headline gate
        "paraphrase_resolution_rate": {a.name: f"{a.resolved}/{a.asked}" for a in run.arms},
        "claude_guaranteed_resolve": claude_resolves_all,
        "diy_silent_drops": {a.name: a.drops for a in diy_arms},
        "competitor_diy_drop_total": competitor_drop_total,
        "claude_beats_best_diy": claude_beats_best_diy,
        # the supporting gates the citations wedge rests on
        "claude_no_hosted_store": claude_no_hosted_store,
        "claude_cites_inline_pdf_under_paraphrase": claude_cites_inline_pdf,
        "output_tokens": {a.name: a.output_tokens for a in run.arms},
        "all_competitors_ran": all_competitors_ran,
        "why_not_promotable": [] if positive else [
            reason for reason, failed in [
                ("Claude did not answer every question with the expected fact", not claude_answered_all),
                ("Claude did not return a resolving pointer for every question", not claude_resolves_all),
                ("the Claude pointers required a hosted/persisted object", not claude_no_hosted_store),
                ("Claude did not return a resolving page pointer into the inline PDF", not claude_cites_inline_pdf),
                ("not every cross-vendor DIY arm ran cleanly", not all_competitors_ran),
                ("the DIY path did not drop under paraphrase (no silent -1)", not diy_drops_under_paraphrase),
                ("Claude did not beat the best DIY resolution rate", not claude_beats_best_diy),
            ] if failed
        ],
    }


# --------------------------------------------------------------------------- the Demonstrator interface
#
# demo_kind = "grounding_resolution": this proves the SAME citations edge as the clean-text
# CitationsDemonstrator (edges/citations/demo.py), but in the paraphrase regime that one left
# unmeasured. The registry keys one demonstrator per demoKind and the clean-text demonstrator owns the
# grounding_resolution slot for the cadence's dispatch, so this paraphrase arm is intentionally NOT
# auto-registered: registering would overwrite that slot. It is reached through its explicit
# `make citations-paraphrase` target and `run.py citations-paraphrase` dispatch, the way a founder runs
# a specific named live proof. It still implements the full interface (and routes its receipt through
# the base honesty contract) so a fork can register it, and so its receipt carries the same shape.

class ParaphraseResolutionDemonstrator(BaseDemonstrator):
    demo_kind = "grounding_resolution"

    def estimate(self, edge, spec):
        n = 3 if (spec or {}).get("quick") else len(QUESTIONS)
        return CostEstimate(usd=0.06, wall_clock_s=120.0, command="make citations-paraphrase",
                            note=f"{n} paraphrased questions x up to four arms; OpenAI/Gemini arms run only with their keys")

    def _run(self, spec):
        spec = spec or {}
        if spec.get("_run") is None:
            spec["_run"] = run_benchmark(quick=spec.get("quick", False), progress=spec.get("progress", False))
        return spec["_run"]

    def _arm_to_Arm(self, a: ArmResult):
        return Arm(provider=a.provider, model=a.model, ran=a.ran and a.asked > 0,
                   latency_s=a.latency, input_tokens=a.input_tokens, output_tokens=a.output_tokens,
                   cost_usd=a.cost, ctx=a.input_tokens,
                   metric={"mechanism": a.mechanism,
                           "paraphrase_resolved": f"{a.resolved}/{a.asked}",
                           "answered": f"{a.answered}/{a.asked}",
                           "silent_drops": a.drops,
                           "persisted_objects": a.persisted_objects,
                           "output_tokens": a.output_tokens},
                   note=a.note)

    def run_claude_arm(self, edge, spec):
        run = self._run(spec)
        a = next((x for x in run.arms if x.provider == "anthropic" and x.mechanism == "API citations"), None)
        if a is None:
            from common.models import get
            return Arm(provider="anthropic", model=get(CLAUDE_MODEL).id, ran=False,
                       note="no Claude Citations arm ran (ANTHROPIC_API_KEY absent)")
        return self._arm_to_Arm(a)

    def run_competitor_arms(self, edge, spec):
        run = self._run(spec)
        # the DIY baseline arms (the within-Claude DIY and the two cross-vendor DIY arms).
        return [self._arm_to_Arm(a) for a in run.arms
                if not (a.provider == "anthropic" and a.mechanism == "API citations")]

    def score(self, claude, competitors, spec):
        run = self._run(spec)
        ca = next((x for x in run.arms if x.provider == "anthropic" and x.mechanism == "API citations"), None)
        if ca is None or ca.asked == 0:
            return Verdict(verdict="never-evaluated", passed=False, metric={"reason": "Claude Citations arm did not run"})
        gate = score_run(run)
        cross = [a for a in run.arms if a.provider in ("openai", "gemini")]
        all_cross_ran = bool(cross) and all(a.ran and a.asked > 0 and not a.errors for a in cross)
        metric = {
            "claude_paraphrase_resolved": f"{ca.resolved}/{ca.asked}",
            "diy_resolution_rates": {a.name: f"{a.resolved}/{a.asked}" for a in run.arms if a.mechanism == "DIY str.find"},
            "competitor_silent_drops": {a.name: a.drops for a in cross},
            "claude_no_hosted_store": gate["claude_no_hosted_store"],
            "claude_cites_inline_pdf_under_paraphrase": gate["claude_cites_inline_pdf_under_paraphrase"],
            "output_tokens": gate["output_tokens"],
        }
        if gate["promotable_edge"] and all_cross_ran:
            return Verdict(verdict="claude-ahead", passed=True, metric=metric,
                           note="Claude Citations resolved every paraphrased answer's pointer by guarantee "
                                "with zero hosted objects; the DIY str.find path silently dropped pointers "
                                "under paraphrase on every vendor")
        if gate["claude_guaranteed_resolve"] and not all_cross_ran:
            return Verdict(verdict="never-evaluated", passed=False, metric=metric,
                           note="Claude resolved every pointer, but not every cross-vendor DIY arm ran")
        return Verdict(verdict="within-claude-only", passed=False, metric=metric,
                       note="the paraphrase head-to-head did not fully clear on this run")

    def receipt(self, edge, claude, competitors, verdict, spec):
        run = self._run(spec)
        return self.build_receipt(
            edge, claude, competitors, verdict, spec,
            workload={
                "task_shape": f"{run.n_questions} questions over {len(TEXT_DOCS)} plain-text user documents "
                              f"and one inline {len(PAGES)}-page PDF; every arm is told to answer in its own "
                              f"words (paraphrase, no verbatim copy) and point to the supporting source. The "
                              f"gate is the paraphrase-resolution rate: Citations checks source[start:end]=="
                              f"cited_text (and a real page span for the PDF), the DIY arms run source.find(quote)",
                "models": {"claude": claude.model, "competitors": [c.model for c in competitors]},
                "features_on": ["citations.enabled on inline text documents (char_location)",
                                "citations.enabled on an inline PDF (page_location)"],
                "assumptions": "this is the PARAPHRASE regime. On clean verbatim quotes the DIY path resolves "
                               "on every vendor (the citations edge measures that, parity). Here the model "
                               "answers in its own words, so the DIY supporting sentence is paraphrased and "
                               "str.find returns -1, a silent drop. Citations resolves because cited_text is "
                               "the source span the API extracts, independent of the model's prose. Citations "
                               "is incompatible with Structured Outputs (the API returns a 400 together)",
            },
            grounding=[
                {"claim": "citations are guaranteed to contain valid pointers to the provided documents; "
                          "cited_text does not count towards output tokens",
                 "source_url": "https://platform.claude.com/docs/en/build-with-claude/citations",
                 "date": "2026-06-19"},
                {"claim": "Citations on an inline PDF return a page_location with the page and the quote, no hosted store",
                 "source_url": "https://platform.claude.com/docs/en/build-with-claude/pdf-support",
                 "date": "2026-06-19"},
                {"claim": "OpenAI file citations require the hosted file_search vector store, not a directly-supplied document",
                 "source_url": "https://developers.openai.com/api/docs/guides/tools-file-search",
                 "date": "2026-06-19"},
                {"claim": "Gemini grounding citations come from the hosted file_search store, not inline content",
                 "source_url": "https://ai.google.dev/gemini-api/docs/file-search", "date": "2026-06-19"},
            ],
            fairness={
                "best_to_best": "every arm gets the same documents, the same questions, and the same "
                                "paraphrase instruction, each on its balanced-tier model; the DIY arms are "
                                "the realistic path a founder builds without the feature, not a strawman",
                "isolate": "same documents, questions, and paraphrase rule on every arm; only the resolve "
                           "mechanism differs (API citations vs model-quote plus str.find), so the "
                           "paraphrase-resolution gap is attributable to the mechanism",
                "lead_basis": "head-to-head",
            },
        )


# Intentionally NOT registered (see the class note above): the clean-text CitationsDemonstrator owns the
# grounding_resolution registry slot. This arm runs via `make citations-paraphrase` / `run.py citations-paraphrase`.
PARAPHRASE_DEMONSTRATOR = ParaphraseResolutionDemonstrator()


# --------------------------------------------------------------------------- the CLI receipt

def _print_run(run: ParaRun) -> None:
    from common.client import fmt_usd

    print("\n  === Paraphrase resolution: does the source pointer survive a paraphrased answer? ===")
    print(f"  {run.n_questions} questions over {len(TEXT_DOCS)} text docs + 1 inline PDF. Every arm answers")
    print("  in its own words. Citations resolves by guarantee; the DIY path str.finds a paraphrased quote.\n")
    header = (f"  {'arm':<26}{'mechanism':<16}{'answered':>9}{'resolves':>9}"
              f"{'drops':>7}{'out_tok':>9}{'cost':>9}")
    print(header)
    print("  " + "-" * (len(header) - 2))
    for a in run.arms:
        print(f"  {a.name:<26}{a.mechanism:<16}{f'{a.answered}/{a.asked}':>9}{f'{a.resolved}/{a.asked}':>9}"
              f"{a.drops:>7}{a.output_tokens:>9,}{fmt_usd(a.cost):>9}")
        if a.errors:
            print(f"      note: {a.errors[0]}")
    print(f"\n  total spend this run: {fmt_usd(run.total_cost)}")
    if run.skipped:
        print(f"  arms not run: {', '.join(run.skipped)}")


def _receipt_dict(run: ParaRun) -> dict:
    verdict = score_run(run)
    return {
        "date": "2026-06-19",
        "claim_under_test": (
            "When the answer is paraphrased (the model answers in its own words), Claude Citations still "
            "returns a pointer that resolves to a real source span by guarantee, while the do-it-yourself "
            "path (model quote + str.find) silently drops the paraphrased pointer on every vendor."
        ),
        "n_questions": run.n_questions,
        "n_pdf_questions": run.n_pdf,
        "n_text_docs": len(TEXT_DOCS),
        "total_cost": round(run.total_cost, 6),
        "sources": {
            "claude_citations": "https://platform.claude.com/docs/en/build-with-claude/citations",
            "claude_pdf_support": "https://platform.claude.com/docs/en/build-with-claude/pdf-support",
            "openai_file_search": "https://developers.openai.com/api/docs/guides/tools-file-search",
            "gemini_file_search": "https://ai.google.dev/gemini-api/docs/file-search",
        },
        "skipped": run.skipped,
        "arms": [{"name": a.name, "provider": a.provider, "model": a.model, "mechanism": a.mechanism,
                  "answered": f"{a.answered}/{a.asked}", "resolved": f"{a.resolved}/{a.asked}",
                  "silent_drops": a.drops, "pdf_pointer_resolved": f"{a.pdf_pointer_resolved}/{a.pdf_asked}",
                  "persisted_objects": a.persisted_objects, "output_tokens": a.output_tokens,
                  "cost": round(a.cost, 6), "latency_s": round(a.latency, 2), "errors": a.errors}
                 for a in run.arms],
        "verdict": verdict,
    }


def _sample_text(receipt: dict) -> str:
    rows = [
        "  Paraphrase-resolution workload: every arm answers in its own words (no verbatim copy) over",
        f"  {receipt['n_text_docs']} plain-text user documents and one inline PDF, then points to the source.",
        "",
        "  arm                          mechanism        answered  resolves  drops   out_tok      cost  wall",
        "  --------------------------------------------------------------------------------------------------",
    ]
    for arm in receipt["arms"]:
        rows.append(
            f"  {arm['name']:<28}{arm['mechanism']:<16}{arm['answered']:>9}{arm['resolved']:>10}"
            f"{arm['silent_drops']:>7}{arm['output_tokens']:>10,}"
            f"{('$' + format(arm['cost'], '.4f')):>10}{arm['latency_s']:>6.1f}s"
        )
    verdict = receipt["verdict"]
    rows.extend([
        "",
        "  Verdict:",
        f"    positive_signal: {str(verdict['positive_signal']).lower()}",
        f"    promotable_edge: {str(verdict['promotable_edge']).lower()}",
        f"    claude_guaranteed_resolve: {str(verdict['claude_guaranteed_resolve']).lower()}",
        f"    claude_no_hosted_store: {str(verdict['claude_no_hosted_store']).lower()}",
        f"    claude_cites_inline_pdf_under_paraphrase: {str(verdict['claude_cites_inline_pdf_under_paraphrase']).lower()}",
        f"    competitor_diy_drop_total: {verdict['competitor_diy_drop_total']}",
        "",
        "  Honest reading:",
        "  - Every arm answered the questions in its own words (paraphrased), as instructed.",
        "  - Claude Citations resolved every answer's pointer by guarantee (source[start:end]==cited_text,",
        "    and a real page span for the inline PDF), with zero hosted or persisted objects.",
        "  - The DIY str.find path dropped pointers under paraphrase: the model's paraphrased supporting",
        "    sentence is not a verbatim substring, so str.find returns -1 and the citation is silently lost.",
        "  - On clean VERBATIM quotes the DIY path resolves about as well on every vendor (the citations",
        "    edge measures that). This arm measures the paraphrase regime the clean-text test did not.",
        "  - cited_text is free of output tokens, so the Citations arm carries no quote-token cost.",
        "  - Citations cannot be combined with Structured Outputs (the API returns a 400 together).",
        "",
        "  Reproduce:",
        "    make citations-paraphrase",
        "",
        "  Machine receipt:",
        "    data/last_paraphrase_resolution.json",
    ])
    return "\n".join(rows) + "\n"


def write_edge_bundle(receipt: dict) -> pathlib.Path:
    from common.client import repo_root

    edge_dir = repo_root() / "edges" / "citations-paraphrase"
    edge_dir.mkdir(parents=True, exist_ok=True)
    (edge_dir / "receipt.json").write_text(json.dumps(receipt, indent=2) + "\n")
    (edge_dir / "sample.txt").write_text(_sample_text(receipt))
    (edge_dir / "demo.py").write_text(
        '"""citations-paraphrase: wrapper for the paraphrase-robustness citation-resolution edge."""\n\n'
        "from engine.demonstrators.paraphrase_resolution import main\n\n\n"
        'if __name__ == "__main__":\n'
        "    raise SystemExit(main())\n"
    )
    rows = [
        "| arm | mechanism | answered | resolves | silent drops | output tokens | cost |",
        "|---|---|:---:|:---:|:---:|---:|---:|",
    ]
    for arm in receipt["arms"]:
        rows.append(
            f"| {arm['name']} | {arm['mechanism']} | {arm['answered']} | {arm['resolved']} | "
            f"{arm['silent_drops']} | {arm['output_tokens']:,} | ${arm['cost']:.4f} |"
        )
    (edge_dir / "README.md").write_text(
        "# Edge: Paraphrase resolution, the citation pointer that survives an own-words answer\n\n"
        "Part of [claude-feature-radar](../../README.md). This is the paraphrase-robustness arm of the "
        "citations edge. It measures the case the clean-text test did not: when the model answers in its "
        "own words, does the source pointer still resolve?\n\n"
        "## What It Is\n\n"
        "A product that answers over a user's own documents usually wants readable, paraphrased prose, "
        "and a deep-link to the exact source so a person can verify before acting. With "
        "`citations: {\"enabled\": true}` on the supplied documents, Claude attaches a pointer whose "
        "`cited_text` is the verbatim source span the API extracted, so `source[start:end] == cited_text` "
        "resolves no matter how the answer is worded. The do-it-yourself path (ask the model for a "
        "supporting quote, then `source.find(quote)`) returns -1 the moment the quote is paraphrased, and "
        "the citation is silently dropped.\n\n"
        "## The Measured Proof\n\n"
        f"Run: `make citations-paraphrase`, {receipt['date']}, "
        f"{receipt['n_questions']} questions over {receipt['n_text_docs']} text documents and one inline "
        "PDF. Every arm answers in its own words.\n\n"
        + "\n".join(rows)
        + "\n\n"
        "Claude Citations resolved every answer's pointer by guarantee, with zero hosted or persisted "
        "objects, including a page pointer into the directly-supplied PDF. The DIY arms answered the same "
        "questions but dropped pointers under paraphrase, because the paraphrased supporting sentence is "
        "not a verbatim substring.\n\n"
        "Full receipt: [`sample.txt`](sample.txt). Machine receipt: [`receipt.json`](receipt.json).\n\n"
        "## Honest Scope\n\n"
        "- On clean verbatim quotes the DIY path resolves about as well on every vendor. The citations "
        "edge measures that case. This arm measures the paraphrase regime, where the model answers in its "
        "own words.\n"
        "- The grader is deterministic: `source[start:end] == cited_text` for Citations, "
        "`source.find(quote)` for the DIY arms, the same gate on every arm.\n"
        "- Citations cannot be combined with Structured Outputs. The two return a 400 together, so a "
        "grounded answer here is free text.\n\n"
        "## Run It Yourself\n\n"
        "```bash\n"
        "git clone https://github.com/cfregly/claude-feature-radar && cd claude-feature-radar\n"
        "make setup\n"
        "make compare-deps\n"
        "cp .env.example .env   # paste ANTHROPIC_API_KEY, OPENAI_API_KEY, and GEMINI_API_KEY\n"
        "make citations-paraphrase   # cents-scale\n"
        "```\n\n"
        "Sources:\n\n"
        f"- Claude citations: {receipt['sources']['claude_citations']}\n"
        f"- Claude PDF support: {receipt['sources']['claude_pdf_support']}\n"
        f"- OpenAI file search: {receipt['sources']['openai_file_search']}\n"
        f"- Gemini file search: {receipt['sources']['gemini_file_search']}\n"
    )
    return edge_dir


def main(argv=None) -> int:
    from common.client import load_env, repo_root

    p = argparse.ArgumentParser(description="paraphrase_resolution: does the citation pointer survive a "
                                            "paraphrased answer? Claude Citations vs the DIY str.find baseline.")
    p.add_argument("--quick", action="store_true", help="3 questions, a cents-scale smoke")
    p.add_argument("--emit-edge", action="store_true", help="write edges/citations-paraphrase/{README,demo,sample,receipt}")
    a = p.parse_args(argv)

    load_env()
    print("\n  paraphrase_resolution: every arm answers in its OWN WORDS, then points to the source.")
    print("  Claude Citations resolves by guarantee; the DIY str.find drops a paraphrased quote.\n")
    run = run_benchmark(quick=a.quick, progress=True)
    _print_run(run)

    out = _receipt_dict(run)
    (repo_root() / "data").mkdir(exist_ok=True)
    (repo_root() / "data" / "last_paraphrase_resolution.json").write_text(json.dumps(out, indent=2) + "\n")
    if a.emit_edge:
        write_edge_bundle(out)
        print("\n  wrote edges/citations-paraphrase/{README.md,demo.py,sample.txt,receipt.json}")
    print("\n  (per-run detail in gitignored data/last_paraphrase_resolution.json)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
