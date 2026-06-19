"""web_citations: a verifiable pointer into the WEB source, with the verbatim quote, where the
competitors return only a URL plus an offset into the model's own answer.

THE EDGE, at response-field depth. Claude's web_search tool returns each web-grounded claim with a
`web_search_result_location` citation: the `url`, the `title`, and the verbatim `cited_text` (up to
150 characters of the actual source passage), and the citation fields are free of input and output
tokens. So a claim arrives self-verifying: the quote is in the response, lifted from the source page.

WHY IT IS A CROSS-VENDOR EDGE, at the citation-object level (verified live 2026-06-19):
  - OpenAI web_search returns a `url_citation` annotation whose `start_index`/`end_index` point into
    the MODEL'S OWN OUTPUT TEXT, plus a `url` and `title`. There is no verbatim source passage and no
    offset into the source page. To verify a claim a client must re-fetch the URL and find the text.
  - Gemini Google Search grounding returns `grounding_supports[].segment` whose offsets also index the
    model's output, and `grounding_chunks[].web` with only `uri` and `title`. No source passage, no
    source offset.
So all three cite a URL, but only Claude hands back the verbatim source quote that makes the claim
checkable without a second fetch. This is the grounding-fidelity thesis (already shipped for user docs,
PDFs, and RAG chunks) extended to WEB sources.

WHAT THIS MEASURES, the SAME gate on every arm: the same web-research questions on every vendor, each
forced to search the live web. The gate is how many returned citations carry a verbatim quote from the
source (a self-verifying pointer), versus a bare URL plus an offset into the model's own answer.

FOUNDER WORKLOAD. A research / monitoring / compliance agent over live web sources (a regulator's
rules page, a competitor's pricing or terms page, a standards spec) where every flagged claim must
deep-link to the exact sentence so a human verifies it in seconds, not by re-reading the page.

DEPENDENCIES. The Claude arm needs only anthropic. The OpenAI and Gemini arms need their optional SDKs
and keys (lazy). Note: the dynamic-filtering web tags route web content through code execution, which
trades the citation linkage for pre-context filtering, so this edge uses the basic web_search tag where
the citation object is returned directly.
"""

from __future__ import annotations

import argparse
import datetime
import json
import os
import pathlib
import sys
import time
from dataclasses import dataclass, field

# repo root on the path, for common/ and engine/ when run as a script.
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))

from engine.demonstrators.base import Arm, BaseDemonstrator, CostEstimate, Verdict
from engine.demonstrators.registry import register
from engine.demonstrators.shared import platform

CLAUDE_MODEL = os.environ.get("WC_CLAUDE_MODEL", "sonnet")
OPENAI_MODEL = os.environ.get("WC_OPENAI_MODEL", "gpt-top")   # gpt-5.5, the web-search-capable frontier
GEMINI_MODEL = os.environ.get("WC_GEMINI_MODEL", "gem-pro")   # gemini-3.1-pro, grounding-capable
CLAUDE_WEB_TAG = os.environ.get("WC_CLAUDE_TAG", "web_search_20250305")  # basic tag returns the citation object
MAX_TOKENS = int(os.environ.get("WC_MAX_TOKENS", "700"))

# Questions that force a live web search (current/specific facts a model should verify, not answer from
# memory). The answer content does not matter to the gate, only the citation object that comes back.
QUESTIONS = [
    "Search the web: what is the boiling point of water at the summit of Mount Everest in Celsius? Cite a source.",
    "Search the web for the current list price of the Anthropic Claude Opus 4.8 API per million input tokens. Cite a source.",
    "Search the web: how tall is the Burj Khalifa in meters? Cite a source.",
]


@dataclass
class ArmResult:
    name: str
    provider: str
    model: str
    ran: bool = True
    asked: int = 0
    answered: int = 0          # produced a non-empty answer
    web_citations: int = 0     # citations that name a web source (any vendor)
    source_quote_citations: int = 0  # citations that carry a verbatim quote FROM the source page
    cost: float = 0.0
    latency: float = 0.0
    note: str = ""
    errors: list = field(default_factory=list)


def run_claude_arm(client, model_key: str, *, progress=False) -> ArmResult:
    from common.models import get
    from common.pricing import cost_breakdown

    m = get(model_key)
    arm = ArmResult(name=f"claude:{model_key}", provider="anthropic", model=m.id,
                    note=f"{CLAUDE_WEB_TAG}, web_search_result_location with verbatim cited_text")
    platform.used("citations", "web_search_result_location with the verbatim source quote")
    for q in QUESTIONS:
        arm.asked += 1
        try:
            t0 = time.perf_counter()
            r = client.messages.create(model=m.id, max_tokens=MAX_TOKENS,
                                       tools=[{"type": CLAUDE_WEB_TAG, "name": "web_search", "max_uses": 4}],
                                       messages=[{"role": "user", "content": q}])
            arm.latency += time.perf_counter() - t0
        except Exception as e:  # noqa: BLE001
            arm.errors.append(f"{q[:24]}: {type(e).__name__}: {str(e)[:80]}")
            continue
        arm.cost += cost_breakdown(model_key, r.usage).total
        text = "".join(b.text for b in r.content if getattr(b, "type", None) == "text")
        if text.strip():
            arm.answered += 1
        for b in r.content:
            if getattr(b, "type", None) == "text":
                for ci in (getattr(b, "citations", None) or []):
                    if getattr(ci, "type", None) == "web_search_result_location":
                        arm.web_citations += 1
                        if (getattr(ci, "cited_text", "") or "").strip():
                            arm.source_quote_citations += 1
        if progress:
            print(f"      claude  {q[:34]:<34} web_cites={arm.web_citations} with_quote={arm.source_quote_citations}", flush=True)
    return arm


def run_openai_arm(client, model_key: str, *, progress=False) -> ArmResult:
    from common.models import get
    from common.pricing import cost_from_buckets

    m = get(model_key)
    arm = ArmResult(name=f"openai:{model_key}", provider="openai", model=m.id,
                    note="web_search url_citation (url + offset into the model's output, no source quote)")
    for q in QUESTIONS:
        arm.asked += 1
        try:
            t0 = time.perf_counter()
            r = client.responses.create(model=m.id, max_output_tokens=MAX_TOKENS,
                                        tools=[{"type": "web_search"}], input=q)
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
        text = getattr(r, "output_text", "") or ""
        if text.strip():
            arm.answered += 1
        for item in (getattr(r, "output", None) or []):
            for cblk in (getattr(item, "content", None) or []):
                for a in (getattr(cblk, "annotations", None) or []):
                    if getattr(a, "type", None) == "url_citation":
                        arm.web_citations += 1
                        # a url_citation carries url + start/end index into the OUTPUT; no source quote.
                        if (getattr(a, "cited_text", "") or getattr(a, "quote", "") or "").strip():
                            arm.source_quote_citations += 1
        if progress:
            print(f"      openai  {q[:34]:<34} web_cites={arm.web_citations} with_quote={arm.source_quote_citations}", flush=True)
    return arm


def run_gemini_arm(client, model_key: str, *, progress=False) -> ArmResult:
    from google.genai import types

    from common.models import get
    from common.pricing import cost_from_buckets

    m = get(model_key)
    arm = ArmResult(name=f"gemini:{model_key}", provider="gemini", model=m.id,
                    note="google_search grounding (uri + title + output-offset segment, no source quote)")
    tool = types.Tool(google_search=types.GoogleSearch())
    for q in QUESTIONS:
        arm.asked += 1
        try:
            t0 = time.perf_counter()
            r = client.models.generate_content(model=m.id, contents=q,
                    config=types.GenerateContentConfig(tools=[tool], max_output_tokens=MAX_TOKENS))
            arm.latency += time.perf_counter() - t0
        except Exception as e:  # noqa: BLE001
            arm.errors.append(f"{q[:24]}: {type(e).__name__}: {str(e)[:90]}")
            continue
        u = getattr(r, "usage_metadata", None)
        inp = (getattr(u, "prompt_token_count", 0) or 0) if u else 0
        out = ((getattr(u, "candidates_token_count", 0) or 0) +
               (getattr(u, "thoughts_token_count", 0) or 0)) if u else 0
        arm.cost += cost_from_buckets(model_key, fresh_input=inp, cached=0, output=out)
        if (getattr(r, "text", None) or "").strip():
            arm.answered += 1
        for cand in (getattr(r, "candidates", None) or []):
            gm = getattr(cand, "grounding_metadata", None)
            if not gm:
                continue
            for ch in (getattr(gm, "grounding_chunks", None) or []):
                web = getattr(ch, "web", None)
                if web and (getattr(web, "uri", None) or getattr(web, "title", None)):
                    arm.web_citations += 1
                    # a grounding chunk carries uri + title; retrieved_context.text only on file_search,
                    # not on Google Search, so there is no verbatim web source quote here.
                    rc = getattr(ch, "retrieved_context", None)
                    if rc and (getattr(rc, "text", "") or "").strip():
                        arm.source_quote_citations += 1
        if progress:
            print(f"      gemini  {q[:34]:<34} web_cites={arm.web_citations} with_quote={arm.source_quote_citations}", flush=True)
    return arm


@dataclass
class WcRun:
    arms: list
    n_questions: int
    total_cost: float
    skipped: list = field(default_factory=list)


def score_run(run: WcRun) -> dict:
    """Machine gate for the web-citation fidelity edge.

    The high-level feature is web search, which is parity. The subfeature under test is the returned
    citation object: Claude must return a web citation with the verbatim source quote, while the
    competitor web-grounding objects cite URLs but carry no source quote.
    """
    claude = next((a for a in run.arms if a.provider == "anthropic"), None)
    competitors = [a for a in run.arms if a.provider in ("openai", "gemini")]
    competitor_providers = {a.provider for a in competitors if a.ran and a.asked > 0}

    claude_answered_all = bool(claude) and claude.ran and claude.asked == run.n_questions and claude.answered == claude.asked
    claude_has_source_quotes = (
        bool(claude)
        and claude.web_citations > 0
        and claude.source_quote_citations == claude.web_citations
    )
    all_competitors_ran = {"openai", "gemini"}.issubset(competitor_providers)
    competitors_answered_all = bool(competitors) and all(a.answered == a.asked == run.n_questions for a in competitors if a.ran)
    competitors_cited_urls = bool(competitors) and all(a.web_citations > 0 for a in competitors if a.ran)
    competitors_returned_no_source_quote = bool(competitors) and all(a.source_quote_citations == 0 for a in competitors if a.ran)

    why_not = []
    if not claude_answered_all:
        why_not.append("claude did not answer every web question")
    if not claude_has_source_quotes:
        why_not.append("claude did not return a source quote on every web citation")
    if not all_competitors_ran:
        why_not.append("both OpenAI and Gemini competitor web arms must run")
    if not competitors_answered_all:
        why_not.append("a competitor did not answer every web question")
    if not competitors_cited_urls:
        why_not.append("competitors must cite web URLs, not fail the grounding task")
    if not competitors_returned_no_source_quote:
        why_not.append("a competitor returned a citation with a source quote, blocking the edge")

    positive = claude_answered_all and claude_has_source_quotes and competitors_cited_urls and competitors_returned_no_source_quote
    promotable = positive and all_competitors_ran and competitors_answered_all
    return {
        "positive_signal": positive,
        "promotable_edge": promotable,
        "claude_all_web_citations_have_source_quote": claude_has_source_quotes,
        "all_competitors_ran": all_competitors_ran,
        "competitors_answered_all": competitors_answered_all,
        "competitors_cited_urls": competitors_cited_urls,
        "competitors_returned_no_source_quote": competitors_returned_no_source_quote,
        "why_not_promotable": why_not if not promotable else [],
    }


def _receipt_dict(run: WcRun) -> dict:
    return {
        "date": datetime.date.today().isoformat(),
        "claim_under_test": (
            "Claude web_search returns a citation object with a verbatim quote from the web source; "
            "OpenAI web_search and Gemini Google Search return URL citations without a source quote."
        ),
        "sources": {
            "claude_web_search": "https://platform.claude.com/docs/en/agents-and-tools/tool-use/web-search-tool",
            "openai_web_search": "https://developers.openai.com/api/docs/guides/tools-web-search",
            "gemini_google_search": "https://ai.google.dev/gemini-api/docs/google-search",
        },
        "n_questions": run.n_questions,
        "total_cost": round(run.total_cost, 6),
        "skipped": run.skipped,
        "verdict": score_run(run),
        "arms": [
            {
                "name": a.name,
                "provider": a.provider,
                "model": a.model,
                "answered": f"{a.answered}/{a.asked}",
                "web_citations": a.web_citations,
                "citations_with_source_quote": a.source_quote_citations,
                "cost": round(a.cost, 6),
                "latency_s": round(a.latency, 1),
                "errors": a.errors,
            }
            for a in run.arms
        ],
    }


def _clients():
    from common.client import get_client
    from common.runner import get_gemini_client, get_openai_client
    return {"anthropic": get_client(), "openai": get_openai_client(), "gemini": get_gemini_client()}


def run_benchmark(*, progress=False) -> WcRun:
    clients = _clients()
    arms, skipped = [], []
    if clients["anthropic"] is not None:
        if progress:
            print("    arm: claude (web_search, web_search_result_location)")
        arms.append(run_claude_arm(clients["anthropic"], CLAUDE_MODEL, progress=progress))
    else:
        skipped.append("claude (ANTHROPIC_API_KEY absent)")
    if clients["openai"] is not None:
        if progress:
            print("    arm: openai (web_search, url_citation)")
        arms.append(run_openai_arm(clients["openai"], OPENAI_MODEL, progress=progress))
    else:
        skipped.append("openai (key absent)")
    if clients["gemini"] is not None:
        if progress:
            print("    arm: gemini (google_search grounding)")
        arms.append(run_gemini_arm(clients["gemini"], GEMINI_MODEL, progress=progress))
    else:
        skipped.append("gemini (key absent)")
    return WcRun(arms=arms, n_questions=len(QUESTIONS), total_cost=sum(a.cost for a in arms), skipped=skipped)


class WebCitationsDemonstrator(BaseDemonstrator):
    demo_kind = "web_grounding"

    def estimate(self, edge, spec):
        return CostEstimate(usd=0.15, wall_clock_s=60.0, command="make web-citations",
                            note=f"{len(QUESTIONS)} web-research questions x 3 vendors, cents-scale")

    def _run(self, spec):
        spec = spec or {}
        if spec.get("_run") is None:
            spec["_run"] = run_benchmark(progress=spec.get("progress", False))
        return spec["_run"]

    def _arm_to_Arm(self, a: ArmResult):
        return Arm(provider=a.provider, model=a.model, ran=a.ran and a.asked > 0,
                   latency_s=a.latency, cost_usd=a.cost,
                   metric={"answered": f"{a.answered}/{a.asked}",
                           "web_citations": a.web_citations,
                           "citations_with_source_quote": a.source_quote_citations},
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
        all_comp_ran = bool(competitors) and all(c.ran for c in competitors)
        comp = {a.name: {"web_citations": a.web_citations, "with_source_quote": a.source_quote_citations}
                for a in run.arms if a.provider in ("openai", "gemini")}
        metric = {"claude_citations_with_source_quote": ca.source_quote_citations,
                  "claude_web_citations": ca.web_citations, "competitors": comp}
        # the edge: Claude returns web citations carrying the verbatim source quote; every competitor
        # cites web URLs but returns NO citation with a verbatim source quote (url + output-offset only).
        claude_wins = ca.source_quote_citations > 0
        comp_no_quote = bool(comp) and all(v["with_source_quote"] == 0 for v in comp.values())
        if claude_wins and comp_no_quote and all_comp_ran:
            return Verdict(verdict="claude-ahead", passed=True, metric=metric,
                           note="Claude returned web citations with the verbatim source quote; every "
                                "competitor cited URLs but returned no citation carrying a source quote")
        if claude_wins and not all_comp_ran:
            return Verdict(verdict="never-evaluated", passed=False, metric=metric,
                           note="Claude returned source-quoted web citations, but not every competitor arm ran")
        return Verdict(verdict="within-claude-only", passed=False, metric=metric,
                       note="the web-citation fidelity gap did not fully clear on this run")

    def receipt(self, edge, claude, competitors, verdict, spec):
        run = self._run(spec)
        return self.build_receipt(
            edge, claude, competitors, verdict, spec,
            workload={
                "task_shape": f"{run.n_questions} web-research questions, each forced to search the live "
                              f"web, on every vendor; the gate is how many returned citations carry a "
                              f"verbatim quote FROM the source page (a self-verifying pointer) vs a bare "
                              f"URL plus an offset into the model's own answer",
                "models": {"claude": claude.model, "competitors": [c.model for c in competitors]},
                "features_on": ["web_search with web_search_result_location citations (cited_text)"],
                "assumptions": "Claude uses the basic web_search tag, where the citation object is "
                               "returned directly (the dynamic-filtering tags route web content through "
                               "code execution, trading the citation for pre-context filtering); the "
                               "competitors run their web_search / Google Search grounding at their best",
            },
            grounding=[
                {"claim": "web_search returns web_search_result_location with cited_text (up to 150 chars "
                          "of the source), free of input/output tokens",
                 "source_url": "https://platform.claude.com/docs/en/agents-and-tools/tool-use/web-search-tool",
                 "date": "2026-06-19"},
                {"claim": "OpenAI url_citation start/end index points into the model's output text",
                 "source_url": "https://developers.openai.com/api/docs/guides/tools-web-search",
                 "date": "2026-06-19"},
                {"claim": "Gemini grounding segment offsets index the model's answer; chunks carry uri+title",
                 "source_url": "https://ai.google.dev/gemini-api/docs/google-search", "date": "2026-06-19"},
            ],
            fairness={
                "best_to_best": "each competitor runs its own web grounding (OpenAI web_search, Gemini "
                                "Google Search) at its frontier model; the comparison is the citation "
                                "object each returns, named, not a strawman",
                "isolate": "the same web-research questions on every arm; only the platform's web "
                           "citation mechanism differs, so the source-quote count is attributable",
            },
        )


register(WebCitationsDemonstrator())


def _print_run(run: WcRun) -> None:
    from common.client import fmt_usd

    print("\n  === Web citations: a verifiable pointer into the web source, with the quote ===")
    print(f"  {run.n_questions} web-research questions, each forced to search the live web, every arm.\n")
    header = f"  {'arm':<22}{'answered':>10}{'web citations':>15}{'with source quote':>19}{'cost':>10}"
    print(header)
    print("  " + "-" * (len(header) - 2))
    for a in run.arms:
        print(f"  {a.name:<22}{f'{a.answered}/{a.asked}':>10}{a.web_citations:>15}"
              f"{a.source_quote_citations:>19}{fmt_usd(a.cost):>10}")
        if a.errors:
            print(f"      note: {a.errors[0]}")
    print(f"\n  total spend this run: {fmt_usd(run.total_cost)}")
    if run.skipped:
        print(f"  arms not run: {', '.join(run.skipped)}")


def main(argv=None) -> int:
    from common.client import load_env, repo_root

    p = argparse.ArgumentParser(description="web_citations: a verifiable pointer into the web source "
                                            "with the verbatim quote, vs OpenAI/Gemini web citations.")
    p.add_argument("--emit-edge", action="store_true", help="write edges/web-citations/receipt.json")
    a = p.parse_args(argv)

    load_env()
    print("\n  web_citations: which platform returns a verifiable quote FROM the web source, not just a")
    print("  URL plus an offset into its own answer? Same web-research questions, every arm.\n")
    run = run_benchmark(progress=True)
    _print_run(run)

    out = _receipt_dict(run)
    (repo_root() / "data").mkdir(exist_ok=True)
    (repo_root() / "data" / "last_web_citations.json").write_text(json.dumps(out, indent=2) + "\n")
    if a.emit_edge:
        edge_dir = repo_root() / "edges" / "web-citations"
        edge_dir.mkdir(parents=True, exist_ok=True)
        (edge_dir / "receipt.json").write_text(json.dumps(out, indent=2) + "\n")
        print("\n  wrote edges/web-citations/receipt.json")
    print("\n  (per-run detail in gitignored data/last_web_citations.json)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
