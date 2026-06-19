"""web_citations: every web-grounded claim arrives with the verbatim source quote, so a human
verifies it in seconds instead of re-fetching the page.

Claude's web_search tool returns each web-grounded claim as a `web_search_result_location` citation
carrying the `url`, the `title`, and the verbatim `cited_text` (up to 150 characters of the actual
source passage). Those citation fields are free of input and output tokens. So a research,
monitoring, or compliance agent over live web sources hands back a claim that is self-verifying: the
quote is in the response, lifted from the source page.

Usage:
  python run.py            # run the workload, print the table
  python run.py --check    # cheap live self-test: assert every web citation carries a source quote

Cost: about $0.05 for --check, about $0.12 for the full run (claude-sonnet-4-6, on your key).
Doc: https://platform.claude.com/docs/en/agents-and-tools/tool-use/web-search-tool
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from .common.models import get
from .common.pricing import cost_usd

CLAUDE_MODEL = "sonnet"               # claude-sonnet-4-6, web-search capable
WEB_TAG = "web_search_20250305"       # the basic web_search tag returns the citation object directly
MAX_TOKENS = 700

# Questions that force a live web search (current or specific facts a model verifies, not answers from
# memory). The answer content does not matter to the gate, only the citation object that comes back.
QUESTIONS = [
    "Search the web: how tall is the Burj Khalifa in meters? Cite a source.",
    "Search the web: what year was the first iPhone released? Cite a source.",
    "Search the web: what is the boiling point of water at the summit of Mount Everest in Celsius? Cite a source.",
]


def _run_claude(questions):
    """Run the web-research workload on Claude. Returns answered, web_citations, with_quote, cost,
    latency, and a few sample (url, cited_text) pairs for the table."""
    from .common.client import get_client  # lazy: anthropic is imported only when we actually call

    client = get_client()
    m = get(CLAUDE_MODEL)
    answered = web_citations = with_quote = 0
    cost = latency = 0.0
    samples = []
    for q in questions:
        t0 = time.perf_counter()
        r = client.messages.create(
            model=m.id, max_tokens=MAX_TOKENS,
            tools=[{"type": WEB_TAG, "name": "web_search", "max_uses": 4}],
            messages=[{"role": "user", "content": q}],
        )
        latency += time.perf_counter() - t0
        cost += cost_usd(m.id, r.usage)
        text = "".join(b.text for b in r.content if getattr(b, "type", None) == "text")
        if text.strip():
            answered += 1
        for b in r.content:
            if getattr(b, "type", None) == "text":
                for ci in (getattr(b, "citations", None) or []):
                    if getattr(ci, "type", None) == "web_search_result_location":
                        web_citations += 1
                        quote = (getattr(ci, "cited_text", "") or "").strip()
                        if quote:
                            with_quote += 1
                            if len(samples) < 3:
                                samples.append((getattr(ci, "url", ""), quote))
    return answered, web_citations, with_quote, cost, latency, samples


def _print_table(answered, n, web_citations, with_quote, cost, latency):
    print()
    print(f"  workload: {n} web-research questions, each forced to search the live web")
    print(f"  model: {get(CLAUDE_MODEL).id}, tool: {WEB_TAG}")
    print()
    header = f"  {'metric':<34}{'value':>12}"
    print(header)
    print("  " + "-" * (len(header) - 2))
    print(f"  {'questions answered':<34}{f'{answered}/{n}':>12}")
    print(f"  {'web citations returned':<34}{web_citations:>12}")
    print(f"  {'with verbatim source quote':<34}{with_quote:>12}")
    print(f"  {'cost':<34}{f'${cost:.6f}':>12}")
    print(f"  {'wall clock':<34}{f'{latency:.1f}s':>12}")


def cmd_run(args):
    print("\n  web_citations: every web-grounded claim comes back with the verbatim source quote.")
    print(f"  about ${0.12:.2f} on claude-sonnet-4-6, on your key.")
    answered, web_citations, with_quote, cost, latency, samples = _run_claude(QUESTIONS)
    _print_table(answered, len(QUESTIONS), web_citations, with_quote, cost, latency)
    if samples:
        print("\n  sample citations (url + verbatim source quote):")
        for url, quote in samples:
            print(f"    {url}")
            print(f"      \"{quote[:120]}\"")
    print()
    return 0


def cmd_check(args):
    """Cheap live self-test. Asserts the win invariant: every web citation carries a source quote."""
    qs = QUESTIONS[:2]  # two questions keeps --check around $0.05
    print("\n  web_citations --check: every Claude web citation must carry a verbatim source quote.")
    print(f"  about ${0.05:.2f} on claude-sonnet-4-6, on your key.")
    answered, web_citations, with_quote, cost, latency, _ = _run_claude(qs)
    _print_table(answered, len(qs), web_citations, with_quote, cost, latency)
    assert web_citations > 0, "no web citations returned"
    assert with_quote == web_citations, (
        f"only {with_quote} of {web_citations} web citations carried a source quote"
    )
    assert answered == len(qs), "Claude did not answer every web question"
    print("\n  PASS: every web citation carried a verbatim source quote.\n")
    return 0


def main(argv=None):
    p = argparse.ArgumentParser(description="web_citations: a verifiable quote from the web source.")
    p.add_argument("--check", action="store_true",
                   help="cheap live self-test asserting every web citation carries a source quote")
    a = p.parse_args(argv)
    return cmd_check(a) if a.check else cmd_run(a)


if __name__ == "__main__":
    raise SystemExit(main())
