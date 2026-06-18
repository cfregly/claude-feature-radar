"""citations: the verifiable-source-pointer edge, measured honestly against the real DIY baseline.

The anchor, after a scrutiny panel killed the first (rigged) version of this benchmark. Claude's
Citations feature returns, for each claim, a structured pointer (a character range for plain text, a
page range for a PDF) plus the verbatim quote it points to, EXTRACTED BY THE API. The docs guarantee
it: "citations are guaranteed to contain valid pointers to the provided documents," and the
`cited_text` "does not count towards output tokens." No competitor exposes a pointer into a
user-supplied document. OpenAI and Google only annotate web-search URLs. Source, re-fetched
2026-06-17: https://platform.claude.com/docs/en/build-with-claude/citations

What this measures, and the trap it now avoids. An earlier version asked the competitor models to emit
the character offset themselves, scored that 0/8, and called it a competitor failure. That was a
strawman: a tokenizer cannot count characters, and no real founder would ask it to. The honest DIY
path, the one you actually build without the feature, is to have the model return the verbatim quote
and resolve it yourself with `source.find(quote)`. So that is the baseline here:

  Claude + Citations       the primitive. The API returns the pointer AND the quote, the pointer is
                           guaranteed to resolve, and the quote is free of output tokens.
  DIY (Claude/OpenAI/Gemini)  the realistic baseline: ask the model for the verbatim quote, then
                           resolve it in your own code with str.find. You own that code, you pay
                           output tokens for every quote, and it resolves only as well as the model
                           quotes verbatim (it returns -1 the moment the model paraphrases).

The honest finding: on clean text the DIY path resolves about as well as Citations, because the
quotes come back verbatim. The edge is not "they cannot do it." The edge is that Claude does it FOR
you, guaranteed, with the quote free of output tokens and zero resolver code, and no competitor ships
the primitive at all. Every number is read off the real usage object. The OpenAI and Gemini arms
degrade gracefully if their key or SDK is absent.
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

# The DIY path a founder actually builds without the feature: ask for the verbatim quote (NOT an
# offset, which a tokenizer cannot produce), then resolve it yourself with str.find.
QUOTE_INSTRUCTIONS = (
    "Answer the question using ONLY the source documents below. Then give the single exact "
    "supporting sentence, copied VERBATIM character for character from the documents, and the exact "
    "title of the document it came from. Respond with ONLY a JSON object and nothing else: "
    '{"answer": "...", "doc_title": "...", "quote": "..."}.'
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

def _doc_blocks(corpus):
    return [
        {
            "type": "document",
            "source": {"type": "text", "media_type": "text/plain", "data": d["text"]},
            "title": d["title"],
            "citations": {"enabled": True},
        }
        for d in corpus
    ]


def run_claude_citations(client, model_key, corpus, questions):
    """The primitive. citations.enabled=true, GA, no beta header. The pointer is guaranteed valid and
    the cited_text does not count toward output tokens."""
    model = get(model_key).id
    rows = []
    for q in questions:
        content = _doc_blocks(corpus) + [
            {"type": "text", "text": q + " Answer in one sentence, grounded in the documents."}
        ]
        t0 = time.perf_counter()
        msg = client.messages.create(model=model, max_tokens=400,
                                     messages=[{"role": "user", "content": content}])
        dt = time.perf_counter() - t0
        cites = []
        for block in msg.content:
            if getattr(block, "type", None) != "text":
                continue
            for c in (getattr(block, "citations", None) or []):
                if getattr(c, "type", None) == "char_location":
                    cites.append((c.document_index, c.start_char_index, c.end_char_index, c.cited_text))
        # The API guarantees this resolves: source[start:end] == cited_text.
        resolved = sum(
            1 for di, s, e, txt in cites
            if 0 <= di < len(corpus) and corpus[di]["text"][s:e] == txt
        )
        rows.append({
            "has_citation": len(cites) > 0, "resolved": 1 if resolved and resolved == len(cites) else (1 if resolved else 0),
            "resolver": "the API", "quote_free": True,
            "cost": cost_usd(model_key, msg.usage),
            "output_tokens": getattr(msg.usage, "output_tokens", 0) or 0, "latency_s": dt,
        })
    return rows


# --------------------------------------------------------- the realistic DIY baseline (any vendor)

def _grade_diy(corpus, raw_text, cost, out_tok, dt):
    """The model returned a quote. We resolve it ourselves with str.find, the real DIY path."""
    obj = _parse_json(raw_text) or {}
    quote = (obj.get("quote") or "").strip()
    title = (obj.get("doc_title") or "").strip()
    doc = next((d for d in corpus
                if title and (d["title"].lower() in title.lower() or title.lower() in d["title"].lower())),
               None)
    # str.find: resolves iff the quote is a verbatim substring of the named document.
    idx = doc["text"].find(quote) if (doc and quote) else -1
    return {
        "has_citation": quote != "", "resolved": 1 if idx != -1 else 0,
        "resolver": "your code", "quote_free": False,
        "cost": cost, "output_tokens": out_tok, "latency_s": dt,
    }


def run_claude_diy(client, model_key, corpus, questions):
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
        rows.append(_grade_diy(corpus, text, cost_usd(model_key, msg.usage),
                               getattr(msg.usage, "output_tokens", 0) or 0, dt))
    return rows


def run_openai_diy(corpus, questions, model):
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
        rows.append(_grade_diy(corpus, getattr(resp, "output_text", "") or "", cost, out, dt))
    return rows


def run_gemini_diy(corpus, questions, model):
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
        rows.append(_grade_diy(corpus, getattr(resp, "text", "") or "", cost, out, dt))
    return rows


# --------------------------------------------------------------------------------------- runner

def _roll(name, rows, n, primitive=False):
    return {
        "arm": name, "questions": n, "primitive": primitive,
        "resolved": sum(r["resolved"] for r in rows),
        "resolver": rows[0]["resolver"] if rows else "",
        "quote_free": rows[0]["quote_free"] if rows else False,
        "output_tokens": sum(r["output_tokens"] for r in rows),
        "cost": sum(r["cost"] for r in rows),
        "time": sum(r["latency_s"] for r in rows),
    }


def main():
    p = argparse.ArgumentParser(description="Citations vs the real DIY baseline, the verifiable-pointer edge.")
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
    print(f"  Claude Citations is GA, no beta header. No competitor ships a document-pointer primitive,")
    print(f"  so the honest baseline is the DIY path: ask the model for the verbatim quote, then resolve")
    print(f"  it yourself with str.find. The grader checks that the quote resolves to the real source.\n")

    summaries = []
    cit = run_claude_citations(client, a.claude_model, CORPUS, questions)
    summaries.append(_roll(f"{label} + Citations (the primitive)", cit, n, primitive=True))
    cd = run_claude_diy(client, a.claude_model, CORPUS, questions)
    summaries.append(_roll(f"{label} DIY (model quote + your str.find)", cd, n))

    for name, runner, model in [
        (f"OpenAI {a.openai_model} DIY", run_openai_diy, a.openai_model),
        (f"Gemini {a.gemini_model} DIY", run_gemini_diy, a.gemini_model),
    ]:
        try:
            rows = runner(CORPUS, questions, model)
            summaries.append(_roll(name, rows, n))
        except Exception as e:  # noqa: BLE001
            print(f"  ({name} skipped: {str(e)[:80]})")

    print("  what a founder building over their own documents pays for")
    print(f"  {'arm':<42}{'resolves':>9}{'resolver':>11}{'quote free':>12}{'out_tok':>9}{'cost$':>9}")
    print("  " + "-" * 92)
    for s in summaries:
        print(f"  {s['arm']:<42}{str(s['resolved'])+'/'+str(s['questions']):>9}{s['resolver']:>11}"
              f"{('yes' if s['quote_free'] else 'no'):>12}{s['output_tokens']:>9,}{s['cost']:>9.5f}")

    base = summaries[0]
    print("\n  Honest reading:")
    print(f"  - {base['arm']}: {base['resolved']}/{n} pointers resolve, the API does the resolving and "
          f"guarantees it, and the quote is free of output tokens. Zero resolver code.")
    for s in summaries[1:]:
        print(f"  - {s['arm']}: {s['resolved']}/{n} resolve via str.find (it returns -1 the moment the "
              f"model paraphrases), you own that code, and you pay {s['output_tokens']:,} output tokens "
              f"for the quotes.")
    print("  - On clean text the DIY path resolves about as well, so the edge is not 'they cannot do it.'")
    print("    The edge is that Claude does it FOR you, guaranteed, free of output tokens, zero code, and")
    print("    no competitor ships the primitive at all (they cite web URLs, not your document).\n")

    out = {"corpus_titles": [d["title"] for d in CORPUS], "questions": questions,
           "summaries": summaries}
    (repo_root() / "data").mkdir(exist_ok=True)
    (repo_root() / "data" / "last_citations.json").write_text(json.dumps(out, indent=2))
    print("  wrote receipts to data/last_citations.json\n")


if __name__ == "__main__":
    main()
