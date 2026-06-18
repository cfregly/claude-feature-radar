"""citations: the verifiable-source-pointer edge, measured against the prompt-for-quotes baseline.

The anchor. Claude's Citations feature returns, for each claim, a structured pointer (a character
range for plain text, a page range for a PDF) plus the verbatim quote it points to, extracted by the
API. The docs guarantee the pointer is valid: "citations are guaranteed to contain valid pointers to
the provided documents." That is the differentiator a founder building over their users' own
documents (contract review, clinical summaries, financial research, support over docs, RAG) cannot
get from OpenAI or Google: both only annotate web-search URLs, neither exposes a char or page pointer
into a user-supplied document. Source, re-fetched 2026-06-17:
https://platform.claude.com/docs/en/build-with-claude/citations

What this measures, with a grader the model cannot game. For every pointer any arm returns, we check
ONE thing against the source text: does source[start:end] equal the quoted text exactly. A pointer
that resolves is trustworthy. A pointer that does not is a hallucinated citation. The arms:

  Claude + Citations          the primitive. Pointers are parsed and extracted, so they resolve by
                              construction, and cited_text does not count toward output tokens.
  Claude prompt-for-quotes    the baseline a founder builds WITHOUT the feature: ask the model to
                              quote the source and report the offsets. Same model, citations off.
  OpenAI prompt-for-quotes    the only option on OpenAI (no document-pointer primitive).
  Gemini prompt-for-quotes    the only option on Google (no document-pointer primitive).

Two numbers ship per arm: the pointer-resolution rate (the offsets land on the exact quote) and the
quote-verbatim rate (the quote is a real substring of the source). Plus the cost: the prompt arms pay
output tokens for every quoted sentence, the Citations arm does not. Every dollar is read off the
real usage object. The OpenAI and Gemini arms degrade gracefully if their key or SDK is absent.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import time

from common.client import fmt_usd, get_client, load_env, repo_root
from common.models import get
from common.pricing import cost_usd

# A small corpus of plain-text "your own documents", the RAG shape: short internal docs with
# specific, citable facts. Plain text so a citation is a character range we can resolve exactly.
CORPUS = [
    {
        "title": "Acme Cloud Service Level Agreement",
        "text": (
            "Acme Cloud commits to a monthly uptime of 99.9 percent for all Standard plan "
            "customers. Enterprise plan customers receive a monthly uptime commitment of 99.99 "
            "percent. If monthly uptime falls below the committed level, the customer is eligible "
            "for a service credit equal to 10 percent of the monthly fee for each full hour of "
            "downtime. Support tickets from Enterprise customers receive a first response within 30 "
            "minutes, around the clock. Standard plan tickets receive a first response within one "
            "business day."
        ),
    },
    {
        "title": "Acme Data Protection and Retention Policy",
        "text": (
            "All customer data is encrypted at rest using AES-256 and in transit using TLS 1.3. "
            "Deleted records are retained in backups for 35 days before permanent erasure. Customer "
            "data is stored in the region selected at signup and is never replicated outside that "
            "region without written consent. Acme retains audit logs for two years. Personal data "
            "deletion requests are completed within 30 days of verification."
        ),
    },
    {
        "title": "Acme Billing and Refund Terms",
        "text": (
            "Acme bills monthly in advance on the first day of each billing cycle. Usage above the "
            "plan allowance is charged at 2 cents per additional API call. Annual plans are "
            "discounted 20 percent compared to monthly billing. A customer who cancels within 14 "
            "days of initial signup receives a full refund. After 14 days, fees are non-refundable "
            "except where required by law."
        ),
    },
]

QUESTIONS = [
    "What is the monthly uptime commitment for the Enterprise plan?",
    "How is customer data encrypted in transit?",
    "How long are deleted records kept in backups before permanent erasure?",
    "What service credit applies when uptime falls below the committed level?",
    "What is the charge for usage above the plan allowance?",
    "Within how long must a personal data deletion request be completed?",
    "What refund does a customer get if they cancel within 14 days of signup?",
    "How quickly do Enterprise support tickets get a first response?",
]

QUOTE_INSTRUCTIONS = (
    "Answer the question using ONLY the source documents below. Then give the single exact "
    "supporting sentence, copied VERBATIM character for character from the documents, the exact "
    "title of the document it came from, and the 0-indexed character offset range of that exact "
    "sentence within that document's own text, where end is exclusive. Respond with ONLY a JSON "
    'object and nothing else: {"answer": "...", "doc_title": "...", "quote": "...", '
    '"start_char": 0, "end_char": 0}.'
)


def _docs_as_text(corpus) -> str:
    return "\n\n".join(f"=== DOCUMENT: {d['title']} ===\n{d['text']}" for d in corpus)


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


# ------------------------------------------------------------------- the Claude Citations arm

def _doc_blocks(corpus, *, cite: bool):
    blocks = []
    for d in corpus:
        b = {
            "type": "document",
            "source": {"type": "text", "media_type": "text/plain", "data": d["text"]},
            "title": d["title"],
        }
        if cite:
            b["citations"] = {"enabled": True}
        blocks.append(b)
    return blocks


def run_claude_citations(client, model_key, corpus, questions):
    """The primitive. citations.enabled=true on every document, GA, no beta header."""
    model = get(model_key).id
    rows = []
    for q in questions:
        content = _doc_blocks(corpus, cite=True) + [
            {"type": "text", "text": q + " Answer in one sentence, grounded in the documents."}
        ]
        t0 = time.perf_counter()
        msg = client.messages.create(model=model, max_tokens=400,
                                     messages=[{"role": "user", "content": content}])
        dt = time.perf_counter() - t0
        answer, cites = "", []
        for block in msg.content:
            if getattr(block, "type", None) != "text":
                continue
            answer += block.text
            for c in (getattr(block, "citations", None) or []):
                if getattr(c, "type", None) == "char_location":
                    cites.append({
                        "document_index": c.document_index,
                        "cited_text": c.cited_text,
                        "start": c.start_char_index,
                        "end": c.end_char_index,
                    })
        # Resolve every pointer against the real source. The API guarantees this passes.
        resolved = sum(
            1 for c in cites
            if 0 <= c["document_index"] < len(corpus)
            and corpus[c["document_index"]]["text"][c["start"]:c["end"]] == c["cited_text"]
        )
        rows.append({
            "q": q, "answer": answer.strip(), "n_cites": len(cites), "resolved": resolved,
            "verbatim": resolved, "has_pointer": len(cites) > 0,
            "cost": cost_usd(model_key, msg.usage),
            "output_tokens": getattr(msg.usage, "output_tokens", 0) or 0,
            "latency_s": dt,
        })
    return rows


# ------------------------------------------------------ the prompt-for-quotes baselines (any vendor)

def _grade_quote(corpus, raw_text, cost, out_tok, dt):
    """Grade one prompt-for-quotes reply: did the quote and its offsets resolve to the source."""
    obj = _parse_json(raw_text) or {}
    quote = (obj.get("quote") or "").strip()
    title = (obj.get("doc_title") or "").strip()
    start, end = obj.get("start_char"), obj.get("end_char")
    doc = next((d for d in corpus
                if title and (d["title"].lower() in title.lower() or title.lower() in d["title"].lower())),
               None)
    verbatim = bool(quote) and doc is not None and quote in doc["text"]
    resolves = (
        doc is not None and isinstance(start, int) and isinstance(end, int)
        and 0 <= start <= end <= len(doc["text"]) and doc["text"][start:end] == quote
    )
    return {
        "answer": (obj.get("answer") or "").strip(), "quote": quote, "doc_title": title,
        "start": start, "end": end, "n_cites": 1 if quote else 0,
        "resolved": 1 if resolves else 0, "verbatim": 1 if verbatim else 0,
        "has_pointer": quote != "", "cost": cost, "output_tokens": out_tok, "latency_s": dt,
    }


def run_claude_quotes(client, model_key, corpus, questions):
    model = get(model_key).id
    src = _docs_as_text(corpus)
    rows = []
    for q in questions:
        prompt = f"{QUOTE_INSTRUCTIONS}\n\nSOURCE DOCUMENTS:\n{src}\n\nQUESTION: {q}"
        t0 = time.perf_counter()
        msg = client.messages.create(model=model, max_tokens=400,
                                     messages=[{"role": "user", "content": prompt}])
        dt = time.perf_counter() - t0
        text = "".join(b.text for b in msg.content if getattr(b, "type", None) == "text")
        rows.append(_grade_quote(corpus, text, cost_usd(model_key, msg.usage),
                                 getattr(msg.usage, "output_tokens", 0) or 0, dt))
    return rows


def run_openai_quotes(corpus, questions, model):
    from engine.openai_arm import OPENAI_PRICES, DEFAULT_OPENAI_MODEL
    try:
        from openai import OpenAI
    except ImportError:
        raise SystemExit("The OpenAI arm needs the SDK. Run: make compare-deps")
    if not os.environ.get("OPENAI_API_KEY"):
        raise SystemExit("OPENAI_API_KEY is not set.")
    client = OpenAI()
    p = OPENAI_PRICES.get(model, OPENAI_PRICES[DEFAULT_OPENAI_MODEL])
    src = _docs_as_text(corpus)
    rows = []
    for q in questions:
        prompt = f"{QUOTE_INSTRUCTIONS}\n\nSOURCE DOCUMENTS:\n{src}\n\nQUESTION: {q}"
        t0 = time.perf_counter()
        resp = client.responses.create(model=model, input=prompt)
        dt = time.perf_counter() - t0
        u = resp.usage
        inp = getattr(u, "input_tokens", 0) or 0
        out = getattr(u, "output_tokens", 0) or 0
        det = getattr(u, "input_tokens_details", None)
        cached = (getattr(det, "cached_tokens", 0) or 0) if det else 0
        cost = (max(0, inp - cached) * p["input"] + cached * p["cached"] + out * p["output"]) / 1e6
        rows.append(_grade_quote(corpus, getattr(resp, "output_text", "") or "", cost, out, dt))
    return rows


def run_gemini_quotes(corpus, questions, model):
    from engine.gemini_arm import GEMINI_PRICES, DEFAULT_GEMINI_MODEL
    try:
        from google import genai
    except ImportError:
        raise SystemExit("The Gemini arm needs the SDK. Run: make compare-deps")
    if not os.environ.get("GEMINI_API_KEY"):
        raise SystemExit("GEMINI_API_KEY is not set.")
    client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
    p = GEMINI_PRICES.get(model, GEMINI_PRICES[DEFAULT_GEMINI_MODEL])
    src = _docs_as_text(corpus)
    rows = []
    for q in questions:
        prompt = f"{QUOTE_INSTRUCTIONS}\n\nSOURCE DOCUMENTS:\n{src}\n\nQUESTION: {q}"
        t0 = time.perf_counter()
        resp = client.models.generate_content(model=model, contents=prompt)
        dt = time.perf_counter() - t0
        um = resp.usage_metadata
        prompt_tok = getattr(um, "prompt_token_count", 0) or 0
        cached = getattr(um, "cached_content_token_count", 0) or 0
        out = (getattr(um, "candidates_token_count", 0) or 0) + (getattr(um, "thoughts_token_count", 0) or 0)
        cost = (max(0, prompt_tok - cached) * p["input"] + cached * p["cached"] + out * p["output"]) / 1e6
        rows.append(_grade_quote(corpus, getattr(resp, "text", "") or "", cost, out, dt))
    return rows


# --------------------------------------------------------------------------------------- runner

def _roll(name, rows, n):
    return {
        "arm": name,
        "questions": n,
        "with_pointer": sum(1 for r in rows if r["has_pointer"]),
        "resolved": sum(r["resolved"] for r in rows),
        "verbatim": sum(r["verbatim"] for r in rows),
        "output_tokens": sum(r["output_tokens"] for r in rows),
        "cost": sum(r["cost"] for r in rows),
        "time": sum(r["latency_s"] for r in rows),
    }


def main():
    p = argparse.ArgumentParser(description="Citations vs prompt-for-quotes, the verifiable-pointer edge.")
    p.add_argument("--quick", action="store_true", help="first 3 questions, a cents-scale smoke")
    p.add_argument("--claude-model", default="haiku")
    p.add_argument("--openai-model", default="gpt-5.4-mini")
    p.add_argument("--gemini-model", default="gemini-3.5-flash")
    a = p.parse_args()

    load_env()
    client = get_client()
    questions = QUESTIONS[:3] if a.quick else QUESTIONS
    n = len(questions)
    label = get(a.claude_model).label

    print(f"\n  Verifiable source citations: {len(CORPUS)} of your own documents, {n} questions.")
    print(f"  Grader (ungameable): does each returned offset resolve to the exact source substring?")
    print(f"  Claude Citations is GA, no beta header. Others have no document-pointer primitive, so")
    print(f"  their only option is to prompt the model for a quote and offsets. Source documents and")
    print(f"  the verbatim cited_text are checked against the real text, not the model's say-so.\n")

    summaries = []
    cit = run_claude_citations(client, a.claude_model, CORPUS, questions)
    summaries.append(_roll(f"{label} + Citations (the primitive)", cit, n))
    cq = run_claude_quotes(client, a.claude_model, CORPUS, questions)
    summaries.append(_roll(f"{label} prompt-for-quotes (no feature)", cq, n))

    for name, runner, model in [
        (f"OpenAI {a.openai_model} prompt-for-quotes", run_openai_quotes, a.openai_model),
        (f"Gemini {a.gemini_model} prompt-for-quotes", run_gemini_quotes, a.gemini_model),
    ]:
        try:
            rows = runner(CORPUS, questions, model)
            summaries.append(_roll(name, rows, n))
        except Exception as e:  # noqa: BLE001
            print(f"  ({name} skipped: {str(e)[:80]})")

    print("  what a founder building over their own documents pays for")
    print(f"  {'arm':<40}{'pointer':>9}{'resolved':>10}{'verbatim':>10}{'out_tok':>9}{'cost$':>10}")
    print("  " + "-" * 88)
    for s in summaries:
        print(f"  {s['arm']:<40}{str(s['with_pointer'])+'/'+str(s['questions']):>9}"
              f"{str(s['resolved'])+'/'+str(s['questions']):>10}"
              f"{str(s['verbatim'])+'/'+str(s['questions']):>10}"
              f"{s['output_tokens']:>9,}{s['cost']:>10.5f}")

    base = summaries[0]
    print("\n  Honest reading:")
    print(f"  - {base['arm']}: {base['resolved']}/{n} pointers resolve to the exact source text, "
          f"guaranteed by the API, and the quotes are free of output tokens.")
    for s in summaries[1:]:
        print(f"  - {s['arm']}: {s['resolved']}/{n} of its claimed offsets resolve, "
              f"{s['verbatim']}/{n} quotes are verbatim, and it pays {s['output_tokens']:,} output tokens "
              f"for the quotes.")
    print("  - A pointer that does not resolve is a citation a user cannot trust. Only the Citations")
    print("    primitive makes every pointer resolve by construction. No competitor exposes it.\n")

    out = {"corpus_titles": [d["title"] for d in CORPUS], "questions": questions,
           "summaries": summaries,
           "detail": {"claude_citations": cit, "claude_quotes": cq}}
    (repo_root() / "data").mkdir(exist_ok=True)
    (repo_root() / "data" / "last_citations.json").write_text(json.dumps(out, indent=2))
    print("  wrote receipts to data/last_citations.json\n")


if __name__ == "__main__":
    main()
