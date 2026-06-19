"""paraphrase_scale_probe: does the citation resolve-GUARANTEE beat a steel-manned DIY AT SCALE?

The paraphrase-resolution arm found PARITY at 3 documents: a steel-manned DIY (model paraphrases the
ANSWER but copies the supporting quote VERBATIM, resolved with a normalized str.find) resolves as well
as Claude Citations, on frontier and on the cheapest tiers. This probe pushes the one realistic regime
left: SCALE. Over ~30 distinct product-policy documents that share fact TYPES (every product has a rate
limit, an overage price, a refund window) but distinct VALUES, a DIY model must attribute its quote to
the RIGHT product. The hypothesis: at scale the DIY str.find still RESOLVES (the verbatim quote is
somewhere in the corpus) but lands in the WRONG product's document (the model misattributes among many
similar docs), a silent wrong-grounding. Claude Citations grounds by document_index, guaranteed to be
the span it actually used.

ISOLATE ONE VARIABLE: both arms are the SAME model (Sonnet), same paraphrased-answer instruction, same
corpus. The only difference is the resolve mechanism, API citations vs str.find. So a gap is the
mechanism, not the model.

The decisive metric is source_correct: the pointer lands in the EXPECTED document, not merely somewhere.
- Claude Citations: char_location.document_index == ref (and the span resolves, by guarantee).
- DIY: the verbatim quote folds-into the EXPECTED document's text (not just into the corpus).

If Claude source_correct == N and DIY source_correct < N (DIY resolved but to the wrong product), the
guarantee earns a real correctness edge at scale. If both are N, the wedge is parity even at scale, and
that is the honest finding. This is a PROBE (run it, read the number), not a shipped demonstrator.

The documents are genuinely distinct products with distinct values, a real RAG workload. The many-doc
attribution ambiguity is natural, not a planted verbatim duplicate, so this finds a genuine condition,
never a rigged one. Run: `.venv/bin/python scripts/paraphrase_scale_probe.py`
"""

from __future__ import annotations

import time

from common.client import get_client
from common.models import get
from engine.demonstrators.paraphrase_resolution import (
    DIY_INSTRUCTIONS, PARAPHRASE_RULE, _fold, _parse_json,
)

MODEL_KEY = "sonnet"   # same tier for both arms: the only variable is citations vs str.find
MAX_TOKENS = 400

# 30 distinct fictional SaaS products. Each policy doc carries the SAME fact types with DISTINCT values,
# so answering a question about one product means attributing to the right document among many similar
# ones. Genuinely distinct content, not a planted verbatim duplicate.
PRODUCTS = [
    "Aerolyte", "Borealis", "Cindermark", "Dovetail", "Embergrove", "Flintwick", "Glasswing",
    "Halcyon", "Ironwood", "Junipero", "Kestrelink", "Lumenpath", "Marrowstone", "Nightjar",
    "Opaline", "Pinebluff", "Quillstone", "Riverbend", "Saltmarsh", "Thornfield", "Umberwell",
    "Vantage", "Wexford", "Xanthe", "Yarrowmist", "Zephyrine", "Ashridge", "Brackenhall",
    "Coldwater", "Driftmoor",
]


def _doc_text(i: int) -> str:
    rl = 100 + i * 50          # rate limit, requests per minute
    seat = 5 + i               # overage seat price, US dollars per seat per month
    refund = 7 + i             # refund window, days
    retention = 30 + i * 5     # export retention, days
    seats = 10 + i * 2         # included seats
    p = PRODUCTS[i]
    return (
        f"{p} Plan Policy. The {p} API rate limit is {rl} requests per minute, measured per "
        f"organization. Additional seats beyond the included {seats} are billed at {seat} US dollars "
        f"per seat per month. A customer who cancels {p} within {refund} days of signup receives a "
        f"full refund of the first cycle. Exported {p} account data remains downloadable for "
        f"{retention} days after the billing cycle ends, after which it is permanently deleted."
    )


DOCS = [{"title": f"{PRODUCTS[i]} Plan Policy", "text": _doc_text(i)} for i in range(len(PRODUCTS))]


def _q(i, fact, question, answer):
    return {"ref": i, "fact": fact, "q": question, "accept": [str(answer)]}


# Questions spread across products and fact types. Each fact type exists in EVERY document with a
# different value, so a correct answer requires grounding in the RIGHT product's document.
QUESTIONS = [
    _q(3, "rate_limit", "What is Dovetail's API rate limit in requests per minute?", 100 + 3 * 50),
    _q(7, "rate_limit", "What is Halcyon's API rate limit in requests per minute?", 100 + 7 * 50),
    _q(7, "seat_price", "How much is each additional seat per month on Halcyon?", 5 + 7),
    _q(21, "refund_window", "Within how many days of signup does a Vantage customer get a full refund?", 7 + 21),
    _q(12, "rate_limit", "What is Marrowstone's API rate limit in requests per minute?", 100 + 12 * 50),
    _q(28, "retention", "How many days does Coldwater keep exported account data downloadable?", 30 + 28 * 5),
    _q(5, "refund_window", "Within how many days of signup does a Flintwick customer get a full refund?", 7 + 5),
    _q(24, "seat_price", "How much is each additional seat per month on Yarrowmist?", 5 + 24),
    _q(9, "retention", "How many days does Junipero keep exported account data downloadable?", 30 + 9 * 5),
    _q(15, "rate_limit", "What is Opaline's API rate limit in requests per minute?", 100 + 15 * 50),
    _q(0, "seat_price", "How much is each additional seat per month on Aerolyte?", 5 + 0),
    _q(19, "refund_window", "Within how many days of signup does a Saltmarsh customer get a full refund?", 7 + 19),
]


def _answered(item, text: str) -> bool:
    return any(a.lower() in (text or "").lower() for a in item["accept"])


def claude_citations_arm(client):
    m = get(MODEL_KEY)
    docs = [{"type": "document", "source": {"type": "text", "media_type": "text/plain", "data": d["text"]},
             "title": d["title"], "citations": {"enabled": True}} for d in DOCS]
    asked = answered = cited = resolved = source_correct = 0
    wrong_source = 0
    for item in QUESTIONS:
        asked += 1
        content = docs + [{"type": "text", "text": f"{item['q']} {PARAPHRASE_RULE}"}]
        r = client.messages.create(model=m.id, max_tokens=MAX_TOKENS,
                                   messages=[{"role": "user", "content": content}])
        ans = "".join(b.text for b in r.content if getattr(b, "type", None) == "text")
        if _answered(item, ans):
            answered += 1
        q_cite = q_res = q_src = False
        for b in r.content:
            if getattr(b, "type", None) != "text":
                continue
            for c in (getattr(b, "citations", None) or []):
                if getattr(c, "type", None) != "char_location":
                    continue
                q_cite = True
                di = getattr(c, "document_index", -1)
                s, e, ct = getattr(c, "start_char_index", -1), getattr(c, "end_char_index", -1), getattr(c, "cited_text", "")
                if 0 <= di < len(DOCS) and DOCS[di]["text"][s:e] == ct:   # resolves by guarantee
                    q_res = True
                    if di == item["ref"]:
                        q_src = True
        cited += q_cite
        resolved += q_res
        source_correct += q_src
        if q_res and not q_src:
            wrong_source += 1
        print(f"    citations  {item['q'][:40]:<40} resolves={q_res} src_ok={q_src}", flush=True)
    return {"name": f"claude+citations:{MODEL_KEY}", "asked": asked, "answered": answered,
            "cited": cited, "resolved": resolved, "source_correct": source_correct, "wrong_source": wrong_source}


def claude_diy_arm(client):
    m = get(MODEL_KEY)
    corpus = "\n\n".join(f"=== DOCUMENT: {d['title']} ===\n{d['text']}" for d in DOCS)
    folded_docs = [_fold(d["text"]) for d in DOCS]
    asked = answered = cited = resolved = source_correct = 0
    wrong_source = 0
    for item in QUESTIONS:
        asked += 1
        prompt = f"{DIY_INSTRUCTIONS}\n\nSOURCE DOCUMENTS:\n{corpus}\n\nQUESTION: {item['q']}"
        r = client.messages.create(model=m.id, max_tokens=MAX_TOKENS,
                                   messages=[{"role": "user", "content": prompt}])
        text = "".join(b.text for b in r.content if getattr(b, "type", None) == "text")
        obj = _parse_json(text) or {}
        quote = (obj.get("quote") or "").strip()
        answer = obj.get("answer") or text
        if _answered(item, answer):
            answered += 1
        fq = _fold(quote)
        q_cite = quote != ""
        q_res = bool(fq) and fq in _fold(corpus)                 # resolves SOMEWHERE in the corpus
        q_src = bool(fq) and fq in folded_docs[item["ref"]]      # resolves in the EXPECTED document
        cited += q_cite
        resolved += q_res
        source_correct += q_src
        if q_res and not q_src:
            wrong_source += 1
        print(f"    DIY        {item['q'][:40]:<40} resolves={q_res} src_ok={q_src}", flush=True)
    return {"name": f"claude DIY:{MODEL_KEY}", "asked": asked, "answered": answered,
            "cited": cited, "resolved": resolved, "source_correct": source_correct, "wrong_source": wrong_source}


def main():
    client = get_client()
    n = len(QUESTIONS)
    print(f"\n  Scale probe: {len(DOCS)} distinct product-policy docs, {n} questions, same model "
          f"({get(MODEL_KEY).label}) both arms.\n  The only variable is the resolve mechanism: API "
          f"citations vs your own str.find.\n")
    print("  Claude Citations arm (grounds by document_index, guaranteed):")
    t0 = time.perf_counter()
    cit = claude_citations_arm(client)
    print("\n  Claude DIY arm (verbatim quote + normalized str.find):")
    diy = claude_diy_arm(client)
    dt = time.perf_counter() - t0

    print("\n  === Scale result: does the pointer land in the RIGHT document among many similar ones? ===\n")
    print(f"    {'arm':<26} {'answered':>9} {'resolves':>9} {'src_correct':>12} {'wrong_source':>13}")
    print(f"    {'-'*26} {'-'*9} {'-'*9} {'-'*12} {'-'*13}")
    for a in (cit, diy):
        print(f"    {a['name']:<26} {a['answered']}/{a['asked']:<7} {a['resolved']}/{a['asked']:<7} "
              f"{a['source_correct']}/{a['asked']:<10} {a['wrong_source']:>13}")
    edge = cit["source_correct"] > diy["source_correct"]
    print(f"\n    wall {dt:.1f}s")
    print(f"\n  Honest reading: at {len(DOCS)} documents, Claude grounds {cit['source_correct']}/{n} in the "
          f"correct source, the DIY path {diy['source_correct']}/{n} "
          f"({diy['wrong_source']} resolved to the WRONG document, a silent misgrounding).")
    print(f"  Verdict: {'EDGE at scale (the guarantee grounds correctly where DIY misattributes).' if edge else 'PARITY even at scale (DIY attributes correctly too). The wedge does not survive.'}\n")


if __name__ == "__main__":
    main()
