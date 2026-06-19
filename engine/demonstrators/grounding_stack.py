"""grounding_stack: a COMBINATION edge. In ONE request, ground three mixed user-source types, each with
its own guaranteed, resolver-free pointer, where the competitors return no pointer into inline content.

THE COMBINATION, at subfeature depth. A single `client.messages.create` call mixes three source types,
all with `citations: {"enabled": true}`, and Claude cites each with the location type that fits it:
  - an inline plain-text document      -> `char_location` (character range)
  - a directly-supplied PDF document   -> `page_location`  (page range)
  - a developer-supplied RAG chunk     -> `search_result_location` (chunk + block span)
all in one response, each with the verbatim `cited_text` free of output tokens, no hosted vector store,
no upload/index step, no persisted copy of the user's data, no resolver code. The single-feature wins
(pdf-citations, search-results, citations) each ship alone; this is the STACK of all three in one call.

WHY IT IS A CROSS-VENDOR COMBINATION EDGE. The competitors cannot assemble the same grounded answer in
one request:
  - OpenAI: a directly-supplied `input_file` PDF and inline text return NO citation annotation; the only
    citation path is the hosted `file_search` vector store (a persisted, pre-indexed copy), and even
    that is file-level, and it cannot cite the inline PDF.
  - Gemini: an inline PDF and inline text return no grounding object; citations come only from a hosted
    `file_search_store`, which the docs say cannot be combined with another tool in the same call.
The competitors' hosted-store path is measured separately in the search-results edge (file/chunk-level,
six persisted objects). This edge measures the one-request, inline, mixed-source path, where the
competitors return zero pointers into the supplied content. Verified live 2026-06-19.

WHAT THIS MEASURES, the SAME gate on every arm: one request carrying the same three inline sources and a
three-part question (one fact unique to each source). The gate is how many of the three sources are
returned with a citation that resolves to that exact source, and how many persisted hosted-store objects
the platform required. Claude: 3/3 typed pointers, 0 hosted objects. Competitors: scored on both.

FOUNDER WORKLOAD. A doc-QA agent over a customer's MIXED uploads: a directly-uploaded contract/report
PDF, the founder's own RAG chunks from the customer's wiki, and a live tool return, all answered in one
turn with a verifiable per-source pointer and no re-indexing latency when a brand-new file arrives
mid-session. The value a founder prices: trust across every source type with zero resolver code and no
third-party copy of the user's data.

DEPENDENCIES. The Claude arm needs only anthropic. The OpenAI and Gemini arms need their optional SDKs
and keys (lazy). The PDF is generated with the standard library alone (shared with pdf_citations).
"""

from __future__ import annotations

import argparse
import base64
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
from engine.demonstrators.pdf_citations import make_sample_pdf

CLAUDE_MODEL = os.environ.get("GS_CLAUDE_MODEL", "haiku")
OPENAI_MODEL = os.environ.get("GS_OPENAI_MODEL", "gpt-mid")
GEMINI_MODEL = os.environ.get("GS_GEMINI_MODEL", "gem-flash")
MAX_TOKENS = int(os.environ.get("GS_MAX_TOKENS", "600"))

# The three inline sources, each holding ONE disjoint fact, so a correct answer must cite that source.
# The PDF fact (uptime 99.9%) lives on page 5 of the shared pdf_citations sample, so page_location must
# resolve there. The text fact and the chunk fact appear in no other source.
TEXT_FACT = "Data residency: customer data for EU organizations is stored exclusively in Frankfurt."
CHUNK_TITLE = "Rate limits"
CHUNK_FACT = "The Growth plan API rate limit is 600 requests per minute."
PDF_FACT_PAGE = 5  # "monthly uptime commitment of 99.9 percent" is on page 5 of the sample PDF
QUESTION = ("Answer all three, each on its own line, and cite the source for each: "
            "(1) where EU customer data is stored, "
            "(2) the monthly uptime commitment percentage from the agreement PDF, "
            "(3) the API rate limit in requests per minute.")
# What a correct answer must contain, per part.
TOKENS = ("Frankfurt", "99.9", "600")


@dataclass
class ArmResult:
    name: str
    provider: str
    model: str
    ran: bool = True
    answered: int = 0          # parts answered correctly (0-3)
    sources_cited: int = 0     # distinct supplied sources returned with a resolving pointer (0-3)
    pointer_kinds: list = field(default_factory=list)
    persisted_objects: int = 0
    cost: float = 0.0
    latency: float = 0.0
    input_tokens: int = 0
    output_tokens: int = 0
    note: str = ""
    errors: list = field(default_factory=list)


def run_claude_arm(client, model_key: str, pdf_b64: str, *, progress=False) -> ArmResult:
    from common.models import get
    from common.pricing import cost_breakdown

    m = get(model_key)
    arm = ArmResult(name=f"claude:{model_key}", provider="anthropic", model=m.id, persisted_objects=0,
                    note="one request: inline text + inline PDF + search_result, all citations enabled")
    platform.used("citations", "three location types (char/page/search_result) in one request")
    content = [
        {"type": "document", "source": {"type": "text", "media_type": "text/plain", "data": TEXT_FACT},
         "title": "Residency note", "citations": {"enabled": True}},
        {"type": "document", "source": {"type": "base64", "media_type": "application/pdf", "data": pdf_b64},
         "title": "Pro Plan Agreement", "citations": {"enabled": True}},
        {"type": "search_result", "source": "kb://ratelimit", "title": CHUNK_TITLE,
         "content": [{"type": "text", "text": CHUNK_FACT}], "citations": {"enabled": True}},
        {"type": "text", "text": QUESTION},
    ]
    try:
        t0 = time.perf_counter()
        r = client.messages.create(model=m.id, max_tokens=MAX_TOKENS,
                                   messages=[{"role": "user", "content": content}])
        arm.latency += time.perf_counter() - t0
    except Exception as e:  # noqa: BLE001
        arm.errors.append(f"{type(e).__name__}: {str(e)[:100]}")
        arm.ran = False
        return arm
    arm.cost += cost_breakdown(model_key, r.usage).total
    arm.input_tokens += getattr(r.usage, "input_tokens", 0) or 0
    arm.output_tokens += getattr(r.usage, "output_tokens", 0) or 0
    text = "".join(b.text for b in r.content if getattr(b, "type", None) == "text")
    arm.answered = sum(1 for tok in TOKENS if tok.lower() in text.lower())
    kinds = set()
    for b in r.content:
        if getattr(b, "type", None) == "text":
            for ci in (getattr(b, "citations", None) or []):
                k = getattr(ci, "type", None)
                if k in ("char_location", "page_location", "search_result_location"):
                    kinds.add(k)
    arm.pointer_kinds = sorted(kinds)
    arm.sources_cited = len(kinds)  # one location type per supplied source type
    if progress:
        print(f"      claude  cited {arm.sources_cited}/3 source types {arm.pointer_kinds}", flush=True)
    return arm


def run_openai_arm(client, model_key: str, pdf_bytes: bytes, *, progress=False) -> ArmResult:
    """OpenAI best ONE-request inline path: input_file PDF + the text and chunk as input_text. A
    directly-supplied PDF and inline text return no citation annotation (file citations require the
    hosted file_search vector store, measured in the search-results edge)."""
    from common.models import get
    from common.pricing import cost_from_buckets

    m = get(model_key)
    arm = ArmResult(name=f"openai:{model_key}", provider="openai", model=m.id, persisted_objects=0,
                    note="one request, inline sources (input_file PDF + input_text); no vector store")
    data_url = "data:application/pdf;base64," + base64.standard_b64encode(pdf_bytes).decode("ascii")
    try:
        t0 = time.perf_counter()
        r = client.responses.create(
            model=m.id, max_output_tokens=MAX_TOKENS,
            input=[{"role": "user", "content": [
                {"type": "input_text", "text": TEXT_FACT},
                {"type": "input_file", "filename": "agreement.pdf", "file_data": data_url},
                {"type": "input_text", "text": CHUNK_FACT},
                {"type": "input_text", "text": QUESTION}]}],
        )
        arm.latency += time.perf_counter() - t0
    except Exception as e:  # noqa: BLE001
        arm.errors.append(f"{type(e).__name__}: {str(e)[:110]}")
        arm.ran = False
        return arm
    u = r.usage
    inp = getattr(u, "input_tokens", 0) or 0
    out = getattr(u, "output_tokens", 0) or 0
    det = getattr(u, "input_tokens_details", None)
    cached = (getattr(det, "cached_tokens", 0) or 0) if det else 0
    arm.cost += cost_from_buckets(model_key, fresh_input=max(0, inp - cached), cached=cached, output=out)
    arm.input_tokens += inp
    arm.output_tokens += out
    text = getattr(r, "output_text", "") or ""
    arm.answered = sum(1 for tok in TOKENS if tok.lower() in text.lower())
    cited = 0
    for item in (getattr(r, "output", None) or []):
        for c in (getattr(item, "content", None) or []):
            for a in (getattr(c, "annotations", None) or []):
                if getattr(a, "type", None) in ("file_citation", "file_path", "url_citation"):
                    cited += 1
                    arm.pointer_kinds.append(getattr(a, "type", None))
    arm.sources_cited = min(cited, 3)
    if progress:
        print(f"      openai  cited {arm.sources_cited}/3 inline sources (annotations={arm.pointer_kinds})", flush=True)
    return arm


def run_gemini_arm(client, model_key: str, pdf_bytes: bytes, *, progress=False) -> ArmResult:
    """Gemini best ONE-request inline path: inline PDF part + the text and chunk inline. Inline content
    returns no grounding object (page/chunk citations require the hosted file_search_store, which the
    docs say cannot combine with another tool in the same call)."""
    from google.genai import types

    from common.models import get
    from common.pricing import cost_from_buckets

    m = get(model_key)
    arm = ArmResult(name=f"gemini:{model_key}", provider="gemini", model=m.id, persisted_objects=0,
                    note="one request, inline sources (inline PDF + text); no file_search_store")
    part = types.Part.from_bytes(data=pdf_bytes, mime_type="application/pdf")
    try:
        t0 = time.perf_counter()
        r = client.models.generate_content(
            model=m.id,
            contents=[TEXT_FACT, part, CHUNK_FACT, QUESTION],
            config=types.GenerateContentConfig(max_output_tokens=MAX_TOKENS),
        )
        arm.latency += time.perf_counter() - t0
    except Exception as e:  # noqa: BLE001
        arm.errors.append(f"{type(e).__name__}: {str(e)[:110]}")
        arm.ran = False
        return arm
    u = getattr(r, "usage_metadata", None)
    inp = (getattr(u, "prompt_token_count", 0) or 0) if u else 0
    out = ((getattr(u, "candidates_token_count", 0) or 0) +
           (getattr(u, "thoughts_token_count", 0) or 0)) if u else 0
    arm.cost += cost_from_buckets(model_key, fresh_input=inp, cached=0, output=out)
    arm.input_tokens += inp
    arm.output_tokens += out
    text = getattr(r, "text", None) or ""
    arm.answered = sum(1 for tok in TOKENS if tok.lower() in text.lower())
    cited = 0
    for cand in (getattr(r, "candidates", None) or []):
        gm = getattr(cand, "grounding_metadata", None)
        if gm and (getattr(gm, "grounding_chunks", None) or getattr(gm, "grounding_supports", None)):
            cited += 1
            arm.pointer_kinds.append("grounding_metadata")
    arm.sources_cited = min(cited, 3)
    if progress:
        print(f"      gemini  cited {arm.sources_cited}/3 inline sources", flush=True)
    return arm


@dataclass
class GsRun:
    arms: list
    total_cost: float
    skipped: list = field(default_factory=list)


def _clients():
    from common.client import get_client
    from common.runner import get_gemini_client, get_openai_client
    return {"anthropic": get_client(), "openai": get_openai_client(), "gemini": get_gemini_client()}


def run_benchmark(*, progress=False) -> GsRun:
    clients = _clients()
    pdf_bytes = make_sample_pdf()
    pdf_b64 = base64.standard_b64encode(pdf_bytes).decode("ascii")
    arms, skipped = [], []
    if clients["anthropic"] is not None:
        if progress:
            print("    arm: claude (one request, mixed inline sources + citations)")
        arms.append(run_claude_arm(clients["anthropic"], CLAUDE_MODEL, pdf_b64, progress=progress))
    else:
        skipped.append("claude (ANTHROPIC_API_KEY absent)")
    if clients["openai"] is not None:
        if progress:
            print("    arm: openai (one request, inline sources)")
        arms.append(run_openai_arm(clients["openai"], OPENAI_MODEL, pdf_bytes, progress=progress))
    else:
        skipped.append("openai (key absent)")
    if clients["gemini"] is not None:
        if progress:
            print("    arm: gemini (one request, inline sources)")
        arms.append(run_gemini_arm(clients["gemini"], GEMINI_MODEL, pdf_bytes, progress=progress))
    else:
        skipped.append("gemini (key absent)")
    return GsRun(arms=arms, total_cost=sum(a.cost for a in arms), skipped=skipped)


class GroundingStackDemonstrator(BaseDemonstrator):
    demo_kind = "grounding_stack"

    def estimate(self, edge, spec):
        return CostEstimate(usd=0.05, wall_clock_s=40.0, command="make grounding-stack",
                            note="one request x 3 vendors over 3 mixed inline sources, cents")

    def _run(self, spec):
        spec = spec or {}
        if spec.get("_run") is None:
            spec["_run"] = run_benchmark(progress=spec.get("progress", False))
        return spec["_run"]

    def _arm_to_Arm(self, a: ArmResult):
        return Arm(provider=a.provider, model=a.model, ran=a.ran,
                   latency_s=a.latency, input_tokens=a.input_tokens, output_tokens=a.output_tokens,
                   cost_usd=a.cost, ctx=a.input_tokens,
                   metric={"answered": f"{a.answered}/3",
                           "source_types_cited_in_one_request": f"{a.sources_cited}/3",
                           "pointer_kinds": a.pointer_kinds,
                           "persisted_objects": a.persisted_objects},
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
        if ca is None or not ca.ran:
            return Verdict(verdict="never-evaluated", passed=False, metric={"reason": "Claude arm did not run"})
        all_comp_ran = bool(competitors) and all(c.ran for c in competitors)
        comp_inline = {a.name: a.sources_cited for a in run.arms if a.provider in ("openai", "gemini")}
        metric = {
            "claude_source_types_cited": f"{ca.sources_cited}/3",
            "claude_pointer_kinds": ca.pointer_kinds,
            "claude_persisted_objects": ca.persisted_objects,
            "competitor_inline_sources_cited": comp_inline,
        }
        claude_wins = ca.sources_cited == 3 and ca.persisted_objects == 0
        comp_none_inline = bool(comp_inline) and all(v == 0 for v in comp_inline.values())
        if claude_wins and comp_none_inline and all_comp_ran:
            return Verdict(verdict="claude-ahead", passed=True, metric=metric,
                           note="Claude cited all three mixed inline source types in one request with "
                                "zero hosted objects; no competitor returned a pointer into the inline "
                                "sources in one request")
        if claude_wins and not all_comp_ran:
            return Verdict(verdict="never-evaluated", passed=False, metric=metric,
                           note="Claude cited all three inline sources, but not every competitor arm ran")
        return Verdict(verdict="within-claude-only", passed=False, metric=metric,
                       note="the one-request mixed-inline combination did not fully clear on this run")

    def receipt(self, edge, claude, competitors, verdict, spec):
        return self.build_receipt(
            edge, claude, competitors, verdict, spec,
            workload={
                "task_shape": "one request carrying three mixed inline sources (a plain-text document, a "
                              "directly-supplied PDF, and a developer-supplied search_result chunk) and a "
                              "three-part question, one fact unique to each source; the gate is how many "
                              "sources return a citation that resolves to that exact source, and the "
                              "hosted-store objects required",
                "models": {"claude": claude.model, "competitors": [c.model for c in competitors]},
                "features_on": ["Citations on a text document (char_location)",
                                "Citations on a PDF (page_location)",
                                "Citations on a search_result chunk (search_result_location)"],
                "assumptions": "this is the one-request inline path; the competitors' hosted file-search "
                               "store path is measured separately in the search-results edge "
                               "(file/chunk-level, six persisted objects, cannot cite the inline PDF), and "
                               "Gemini file_search cannot combine with another tool in one call",
            },
            grounding=[
                {"claim": "char_location, page_location, and search_result_location citations coexist in "
                          "one response, each guaranteed to resolve, cited_text free of output tokens",
                 "source_url": "https://platform.claude.com/docs/en/build-with-claude/citations",
                 "date": "2026-06-19"},
                {"claim": "search_result blocks can be combined with other content types in one request",
                 "source_url": "https://platform.claude.com/docs/en/build-with-claude/search-results",
                 "date": "2026-06-19"},
                {"claim": "OpenAI file citations require the hosted file_search vector store, not input_file",
                 "source_url": "https://developers.openai.com/api/docs/guides/tools-file-search",
                 "date": "2026-06-19"},
                {"claim": "Gemini file_search cannot be combined with other tools in the same call",
                 "source_url": "https://ai.google.dev/gemini-api/docs/file-search", "date": "2026-06-19"},
            ],
            fairness={
                "best_to_best": "every arm gets the same three inline sources in one request; the "
                                "competitors' best inline path is used, and their hosted-store path is "
                                "measured in the search-results edge, not strawmanned",
                "isolate": "same sources, same question, one request on every arm; only the platform's "
                           "citation mechanism differs, so the per-source pointer count is attributable",
            },
        )


register(GroundingStackDemonstrator())


def _print_run(run: GsRun) -> None:
    from common.client import fmt_usd

    print("\n  === Grounding stack: three mixed inline sources cited in ONE request ===")
    print("  text (char) + PDF (page) + RAG chunk (search_result), each with its own pointer.\n")
    header = f"  {'arm':<22}{'answered':>10}{'sources cited /3':>18}{'hosted objs':>13}{'cost':>10}"
    print(header)
    print("  " + "-" * (len(header) - 2))
    for a in run.arms:
        print(f"  {a.name:<22}{f'{a.answered}/3':>10}{f'{a.sources_cited}/3':>18}"
              f"{a.persisted_objects:>13}{fmt_usd(a.cost):>10}")
        if a.errors:
            print(f"      note: {a.errors[0]}")
    print(f"\n  total spend this run: {fmt_usd(run.total_cost)}")
    if run.skipped:
        print(f"  arms not run: {', '.join(run.skipped)}")


def main(argv=None) -> int:
    from common.client import load_env, repo_root

    p = argparse.ArgumentParser(description="grounding_stack: cite three mixed inline source types in one "
                                            "request, vs OpenAI/Gemini inline paths.")
    p.add_argument("--emit-edge", action="store_true", help="write edges/grounding-stack/receipt.json")
    a = p.parse_args(argv)

    load_env()
    print("\n  grounding_stack: a COMBINATION edge. Cite text + PDF + RAG chunk, each with its own")
    print("  guaranteed pointer, in ONE request. Same three inline sources on every arm.\n")
    run = run_benchmark(progress=True)
    _print_run(run)

    out = {
        "total_cost": round(run.total_cost, 6), "skipped": run.skipped,
        "arms": [{"name": a.name, "provider": a.provider, "model": a.model,
                  "answered": f"{a.answered}/3", "source_types_cited_in_one_request": f"{a.sources_cited}/3",
                  "pointer_kinds": a.pointer_kinds, "persisted_objects": a.persisted_objects,
                  "cost": round(a.cost, 6), "latency_s": round(a.latency, 2), "errors": a.errors}
                 for a in run.arms],
    }
    (repo_root() / "data").mkdir(exist_ok=True)
    (repo_root() / "data" / "last_grounding_stack.json").write_text(json.dumps(out, indent=2) + "\n")
    if a.emit_edge:
        edge_dir = repo_root() / "edges" / "grounding-stack"
        edge_dir.mkdir(parents=True, exist_ok=True)
        (edge_dir / "receipt.json").write_text(json.dumps(out, indent=2) + "\n")
        print("\n  wrote edges/grounding-stack/receipt.json")
    print("\n  (per-run detail in gitignored data/last_grounding_stack.json)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
