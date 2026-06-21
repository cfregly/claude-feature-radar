"""Cite your own RAG chunks inline, resolver-free, with Claude search_result content blocks.

Your retriever (pgvector, Pinecone, a reranker you wrote) returns passages. Pass them straight
into the request as search_result content blocks with citations enabled, and every answer comes
back with a search_result_location pointer: which chunk, the block span inside it, and the verbatim
cited text. No hosted vector store, no upload step, no third-party copy of your users' data, no
resolver code.

Usage:
    python run.py            # run the citation workload, print the table and cost
    python run.py --check    # self-test: assert every answer cited the correct chunk inline

Cost: $0.05 for the full measured run, $0.01 for --check.
Doc: https://platform.claude.com/docs/en/build-with-claude/search-results
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from .common.models import get
from .common.pricing import cost_usd

CLAUDE_MODEL = "haiku"
MAX_TOKENS = 512

# The comparison gate default. The generator bakes this per surface: the public brief ships it OFF, so
# `make search_results` runs the Claude side alone on one dependency, and `make search_results COMPARE=1`
# (or --compare) reproduces the full OpenAI and Gemini head-to-head. A private both-directions checkout
# ships it ON. Either way --compare / --no-compare overrides it.
COMPARE_DEFAULT = {compare_default}

# Five RAG chunks a founder's own retriever might return for a support-bot product. Each chunk has a
# stable id and one distinct citable fact, so a correct answer must point at the chunk that holds it.
CHUNKS = [
    ("seats.txt", "Seats and plans",
     "The Growth plan includes 25 included seats. Every additional seat beyond the included 25 is an "
     "overage seat. Included seats reset at the start of each billing month and do not roll over."),
    ("overage.txt", "Overage billing",
     "Overage seats are billed at 9 US dollars per seat per month. Overage is metered daily and "
     "invoiced in arrears. Customers can set a monthly overage spend cap in the billing settings."),
    ("trials.txt", "Free trial",
     "New organizations get a 14 day free trial of the Growth plan with full features and no credit "
     "card required. At the end of the trial the organization is downgraded to the Starter plan "
     "unless a paid plan is selected."),
    ("sso.txt", "Single sign-on",
     "Single sign-on with SAML and SCIM provisioning is available on the Growth plan and above. SSO "
     "enforcement can be turned on per organization so that all members must authenticate through the "
     "identity provider."),
    ("refunds.txt", "Refund policy",
     "Annual subscriptions can be refunded on a prorated basis within the first 30 days of the term. "
     "Monthly subscriptions are non-refundable. Overage charges already invoiced are never refunded."),
]

# (question, the chunk index whose content answers it, a token the answer must contain)
QUESTIONS = [
    ("How much does each overage seat cost per month?", 1, "9"),
    ("How many seats are included in the Growth plan?", 0, "25"),
    ("How long is the free trial?", 2, "14"),
    ("Which plans support SAML single sign-on?", 3, "Growth"),
    ("Within how many days can an annual plan be refunded?", 4, "30"),
]


def _ask_all(client, model_id, questions):
    """Run each question over the inline chunks. Returns (answered, cited, asked, cost, wall, rows)."""
    blocks = [{"type": "search_result", "source": f"kb://{cid}", "title": title,
               "content": [{"type": "text", "text": body}],
               "citations": {"enabled": True}}  # add this: turn each chunk into a citable source
              for cid, title, body in CHUNKS]
    answered = cited = asked = 0
    cost = 0.0
    rows = []
    t0 = time.perf_counter()
    for q, ans_idx, token in questions:
        asked += 1
        content = blocks + [{"type": "text", "text": q + " Answer in one sentence and cite the source."}]
        r = client.messages.create(model=model_id, max_tokens=MAX_TOKENS,
                                   messages=[{"role": "user", "content": content}])
        cost += cost_usd(CLAUDE_MODEL, r.usage)
        text = "".join(b.text for b in r.content if getattr(b, "type", None) == "text")
        if token.lower() in text.lower():
            answered += 1
        idxs = []
        for b in r.content:
            if getattr(b, "type", None) == "text":
                for ci in (getattr(b, "citations", None) or []):
                    if getattr(ci, "type", None) == "search_result_location":
                        idxs.append(getattr(ci, "search_result_index", None))
        hit = ans_idx in idxs
        if hit:
            cited += 1
        rows.append((q, ans_idx, idxs, hit))
    wall = time.perf_counter() - t0
    return answered, cited, asked, cost, wall, rows


def _maybe_compare(compare_on: bool) -> None:
    """When the comparison gate is on, run the OpenAI and Gemini file_search arms on the same chunks and
    print the full head-to-head table. Imported lazily, so the default Claude-only run never touches the
    comparison code or its optional SDKs."""
    if not compare_on:
        return
    from .compare import append_comparison  # lazy: the comparison SDKs load only here
    append_comparison(CLAUDE_MODEL, {"pointer": "block-range", "objects": 0})


def cmd_run(compare_on: bool = False) -> int:
    from .common.client import get_client

    m = get(CLAUDE_MODEL)
    print(f"\n  search_result inline citations on {m.label} ({m.id})")
    print(f"  {len(QUESTIONS)} questions over {len(CHUNKS)} chunks you supply inline. No hosted store.")
    print(f"  est cost $0.05, about 15s\n")
    client = get_client()
    answered, cited, asked, cost, wall, rows = _ask_all(client, m.id, QUESTIONS)
    print(f"  {'question':<48}{'cited chunk':>13}{'expected':>10}{'ok':>5}")
    print("  " + "-" * 74)
    for q, ans_idx, idxs, hit in rows:
        shown = idxs[0] if len(idxs) == 1 else idxs
        print(f"  {q[:46]:<48}{str(shown):>13}{ans_idx:>10}{('yes' if hit else 'no'):>5}")
    print("  " + "-" * 74)
    print(f"  answered {answered}/{asked}   correct-source cite {cited}/{asked}   "
          f"hosted objects 0   pointer block-span")
    print(f"  cost ${cost:.2f}   wall {wall:.1f}s\n")
    _maybe_compare(compare_on)
    return 0


def cmd_check(compare_on: bool = False) -> int:
    """Self-test: assert every answer cites the correct chunk inline, with zero hosted objects."""
    from .common.client import get_client

    m = get(CLAUDE_MODEL)
    print(f"\n  --check: every answer must cite the right chunk inline (block-span, 0 hosted objects)")
    print(f"  model {m.id}, a moderate slice for a few cents\n")
    client = get_client()
    answered, cited, asked, cost, wall, rows = _ask_all(client, m.id, QUESTIONS[:3])
    for q, ans_idx, idxs, hit in rows:
        print(f"  {q[:46]:<48} cited={idxs} expected={ans_idx} {'OK' if hit else 'MISS'}")
    print(f"\n  answered {answered}/{asked}  correct-cite {cited}/{asked}  cost ${cost:.2f}  {wall:.1f}s")
    assert answered == asked, "not every question was answered"
    assert cited == asked, "an answer did not carry a search_result_location to the correct chunk"
    print("  INVARIANT HOLDS: inline citations resolved to the right chunk, 0 hosted objects, "
          "0 resolver code\n")
    _maybe_compare(compare_on)
    return 0


def main(argv=None) -> int:
    from .common.client import load_env

    p = argparse.ArgumentParser(description="Cite your own RAG chunks inline with Claude search_result blocks.")
    p.add_argument("--check", action="store_true", help="self-test the inline-citation invariant")
    p.add_argument("--compare", dest="compare", action="store_true", default=None,
                   help="also run the OpenAI and Gemini file_search arms and print the full head-to-head "
                        "table (needs OPENAI_API_KEY, GEMINI_API_KEY, and requirements-compare.txt)")
    p.add_argument("--no-compare", dest="compare", action="store_false",
                   help="run only the Claude side (the public-brief default)")
    a = p.parse_args(argv)
    load_env()
    compare_on = COMPARE_DEFAULT if a.compare is None else a.compare
    return cmd_check(compare_on) if a.check else cmd_run(compare_on)


if __name__ == "__main__":
    raise SystemExit(main())
