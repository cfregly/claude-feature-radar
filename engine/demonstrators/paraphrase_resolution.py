"""citations vs the other models, best citation FEATURE against best citation feature.

THE TEST. Every vendor answers the same questions over the same user documents and must return a
citation pointer INTO those documents using its real citation tool:
  - Claude  : citations.enabled on the inline documents -> a char-range span, API-guaranteed to resolve,
              with ZERO hosted/persisted objects (the user's data never leaves the request).
  - OpenAI  : file_search, which REQUIRES a hosted vector store -> the user's documents are uploaded and
              indexed (persisted objects), and the citation is FILE-level (which file, no char/page span).
  - Gemini  : File Search, which REQUIRES a hosted file_search_store -> documents uploaded and indexed
              (persisted objects), and the grounding is CHUNK-level (no character offset into the source).

WHY IT IS A REAL, FRONTIER-SURVIVING WIN. Grounded and adversarially verified against the vendors' live
docs 2026-06-19: neither OpenAI nor Gemini returns a structured, API-emitted, guaranteed-to-resolve
pointer into a directly-supplied document without a hosted store. That is an API-surface gap, not a
model-quality difference, so it holds at the competitors' frontier tier (gpt-5.5, gemini-3.1-pro). The
competitor arms reuse the proven hosted-store flow from search_results_grounding and DELETE the store
afterward, so no copy of the user's data is left behind.

THERE IS NO str.find HERE. Every arm reads the citation its real API returns. The Claude grader verifies
the API's char offsets against the source (source[start:end] == cited_text, the documented guarantee);
the competitor graders read the returned file_citation / grounding chunk and check it maps to the right
document. The earlier do-it-yourself str.find baseline (a model quote located with source.find) was an
artificial path nobody builds, and its only finding was that the resolve guarantee is PARITY against a
competent resolver, an internal both-directions note, not a founder claim. That parity analysis lives in
the internal scale probe (scripts/paraphrase_scale_probe.py), which imports the four helper constants
retained at the bottom of this module. It is not part of this edge.

FOUNDER WORKLOAD. A product that answers over a user's own documents (a contract, a report, the app's
wiki) and must deep-link each answer to the exact source so a person can verify before acting, without
shipping a copy of the user's data to a third-party hosted store. The value: a verifiable per-character
pointer, zero resolver code, and no persisted copy of the user's data.

DEPENDENCIES. The Claude arm needs only anthropic. The OpenAI and Gemini arms need their optional SDKs
and keys (pulled lazily) and create then delete a hosted store.

MODEL TIER. Claude runs Sonnet, the competitors run their FRONTIER tier (run the stronger competitor
before a correctness claim). Claude on the lower tier still wins, because the gap is the API surface,
not the model. Never Haiku for a correctness seat.
"""

from __future__ import annotations

import argparse
import json
import os
import pathlib
import re
import sys
import time
import unicodedata
from dataclasses import dataclass, field

# repo root on the path, for common/ and engine/ when run as a script.
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))

from engine.demonstrators.base import Arm, BaseDemonstrator, CostEstimate, Verdict
from engine.demonstrators.shared import platform

CLAUDE_MODEL = os.environ.get("PARA_CLAUDE_MODEL", "sonnet")
OPENAI_MODEL = os.environ.get("PARA_OPENAI_MODEL", "gpt-top")     # gpt-5.5, frontier
GEMINI_MODEL = os.environ.get("PARA_GEMINI_MODEL", "gem-pro")     # gemini-3.1-pro, frontier
MAX_TOKENS = int(os.environ.get("PARA_MAX_TOKENS", "400"))        # the Claude answer is one short sentence
# The competitor file_search/File Search queries run their frontier models, which think by default, so
# give them enough output budget that extended thinking is never starved before they answer.
DIY_MAX_TOKENS = int(os.environ.get("PARA_DIY_MAX_TOKENS", "1536"))
# A per-request wall-clock cap so one stuck network read can never hang an unattended run. A failed or
# slow call is recorded as an arm error (never faked), and a missing arm holds the verdict, never pitched.
REQUEST_TIMEOUT_S = float(os.environ.get("PARA_REQUEST_TIMEOUT_S", "90"))


# --------------------------------------------------------------------------- the user documents
#
# Three plain-text user documents, each carrying disjoint, citable, startup-native facts, so a correct
# citation must point to the right document among several similar ones.

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

# Each question's answer lives in the document named by ``ref`` (an index into TEXT_DOCS), so a correct
# citation must point there.
QUESTIONS = [
    {"q": "When is an API call metered, at request time or at response time?", "ref": 0},
    {"q": "How many seats does the Growth plan include?", "ref": 1},
    {"q": "What is the Growth plan rate limit in requests per minute?", "ref": 1},
    {"q": "How long does exported account data stay downloadable after the cycle ends?", "ref": 2},
    {"q": "What refund does a customer get if they cancel within 14 days of signup?", "ref": 2},
    {"q": "Is a call that fails with a 5xx server error counted against the plan allowance?", "ref": 0},
]


def _resolve_char(di: int, start: int, end: int, cited_text: str) -> bool:
    # The API guarantee, checked exactly: the char offsets slice the supplied document to the cited text.
    return 0 <= di < len(TEXT_DOCS) and TEXT_DOCS[di]["text"][start:end] == cited_text


# --------------------------------------------------------------------------- the arms

@dataclass
class ArmResult:
    name: str
    provider: str
    model: str
    mechanism: str                  # "inline citations" | "hosted file_search" | "hosted File Search"
    ran: bool = True
    asked: int = 0
    cited: int = 0                  # questions that returned a citation pointer into the supplied docs
    resolved: int = 0              # questions whose pointer resolves to the supplied docs
    source_correct: int = 0        # questions whose pointer lands in the EXPECTED document
    persisted_objects: int = 0      # hosted/vector-store objects required (a third-party copy of the user's data)
    setup_calls: int = 0            # hosted-store setup API calls before answering (0 for the inline path)
    pointer_kind: str = ""          # char-span (Claude) | file-level (OpenAI) | chunk-level (Gemini) | none
    cost: float = 0.0
    latency: float = 0.0
    input_tokens: int = 0
    output_tokens: int = 0
    note: str = ""
    errors: list = field(default_factory=list)


# The competitors cite at the granularity of an uploaded FILE, so each user document is one file.
def _feature_files():
    out = []
    for i, d in enumerate(TEXT_DOCS):
        slug = "".join(c if c.isalnum() else "-" for c in d["title"].lower()).strip("-")
        out.append((i, f"doc{i}-{slug}.txt", d["title"], d["text"]))
    return out  # (doc_index, filename, title, body)


def _tmp_textfile(body: str, name: str) -> str:
    import tempfile
    d = tempfile.mkdtemp()
    path = os.path.join(d, name)
    with open(path, "w") as f:
        f.write(body)
    return path


def run_claude_feature_arm(client, model_key: str, text_questions, *, progress=False) -> ArmResult:
    """Claude's citation FEATURE over the user's inline documents: a char-range span, guaranteed to
    resolve, zero hosted objects. The same documents and questions the competitor feature arms get."""
    from common.models import get
    from common.pricing import cost_breakdown

    m = get(model_key)
    arm = ArmResult(name=f"claude citations:{model_key}", provider="anthropic", model=m.id,
                    mechanism="inline citations", persisted_objects=0, setup_calls=0, pointer_kind="char-span",
                    note="citations.enabled on the inline documents; guaranteed-resolve char span, no hosted store")
    platform.used("citations", "char-span pointer into the supplied documents, zero hosted objects")
    blocks = [
        {"type": "document", "source": {"type": "text", "media_type": "text/plain", "data": d["text"]},
         "title": d["title"], "citations": {"enabled": True}} for d in TEXT_DOCS]
    for item in text_questions:
        arm.asked += 1
        content = blocks + [{"type": "text", "text": item["q"] + " Answer in one sentence and cite the source."}]
        try:
            t0 = time.perf_counter()
            r = client.messages.create(model=m.id, max_tokens=MAX_TOKENS, timeout=REQUEST_TIMEOUT_S,
                                       messages=[{"role": "user", "content": content}])
            arm.latency += time.perf_counter() - t0
        except Exception as e:  # noqa: BLE001
            arm.errors.append(f"{item['q'][:24]}: {type(e).__name__}: {str(e)[:80]}")
            continue
        arm.cost += cost_breakdown(model_key, r.usage).total
        arm.input_tokens += getattr(r.usage, "input_tokens", 0) or 0
        arm.output_tokens += getattr(r.usage, "output_tokens", 0) or 0
        resolves, correct = False, False
        for b in r.content:
            if getattr(b, "type", None) != "text":
                continue
            for c in (getattr(b, "citations", None) or []):
                if getattr(c, "type", None) == "char_location":
                    di = getattr(c, "document_index", -1)
                    if _resolve_char(di, getattr(c, "start_char_index", -1),
                                     getattr(c, "end_char_index", -1), getattr(c, "cited_text", "")):
                        resolves = True
                        if di == item["ref"]:
                            correct = True
        if resolves:
            arm.cited += 1
            arm.resolved += 1
        if correct:
            arm.source_correct += 1
        if progress:
            print(f"      C-cite  {item['q'][:32]:<32} char-span resolves={resolves} src_ok={correct}", flush=True)
    return arm


def run_openai_feature_arm(client, model_key: str, text_questions, *, progress=False) -> ArmResult:
    """OpenAI's citation feature: file_search over a hosted vector store. The user's documents must be
    uploaded and indexed (persisted objects), and the file_citation is file-level (no char span)."""
    import io

    from common.models import get
    from common.pricing import cost_from_buckets

    m = get(model_key)
    arm = ArmResult(name=f"openai file_search:{model_key}", provider="openai", model=m.id,
                    mechanism="hosted file_search", pointer_kind="none",
                    note="file_search REQUIRES a hosted vector store; file_citation is file-level, not a char span")
    files = _feature_files()
    store, file_ids = None, []
    try:
        store = client.vector_stores.create(name="feature-radar-docs")
        arm.setup_calls += 1
        arm.persisted_objects += 1
        for di, fname, _title, body in files:
            f = client.files.create(file=(fname, io.BytesIO(body.encode()), "text/plain"), purpose="assistants")
            file_ids.append((f.id, di))
            client.vector_stores.files.create(vector_store_id=store.id, file_id=f.id)
            arm.setup_calls += 2
            arm.persisted_objects += 1
        for _ in range(30):
            lst = client.vector_stores.files.list(vector_store_id=store.id)
            if lst.data and all(getattr(x, "status", "") == "completed" for x in lst.data):
                break
            time.sleep(2)
        id_to_idx = {fid: di for fid, di in file_ids}
        for item in text_questions:
            arm.asked += 1
            try:
                t0 = time.perf_counter()
                r = client.responses.create(
                    model=m.id, max_output_tokens=DIY_MAX_TOKENS, timeout=REQUEST_TIMEOUT_S,
                    tools=[{"type": "file_search", "vector_store_ids": [store.id]}],
                    input=item["q"] + " Answer in one sentence and cite the source.")
                arm.latency += time.perf_counter() - t0
            except Exception as e:  # noqa: BLE001
                arm.errors.append(f"{item['q'][:24]}: {type(e).__name__}: {str(e)[:80]}")
                continue
            u = r.usage
            inp = getattr(u, "input_tokens", 0) or 0
            out = getattr(u, "output_tokens", 0) or 0
            det = getattr(u, "input_tokens_details", None)
            cached = (getattr(det, "cached_tokens", 0) or 0) if det else 0
            arm.cost += cost_from_buckets(model_key, fresh_input=max(0, inp - cached), cached=cached, output=out)
            arm.input_tokens += inp
            arm.output_tokens += out
            cited_idx = None
            for it in (getattr(r, "output", None) or []):
                for c in (getattr(it, "content", None) or []):
                    for a in (getattr(c, "annotations", None) or []):
                        if getattr(a, "type", None) == "file_citation":
                            arm.pointer_kind = "file-level"
                            cited_idx = id_to_idx.get(getattr(a, "file_id", None), cited_idx)
            if cited_idx is not None:
                arm.cited += 1
                arm.resolved += 1                  # a file-level pointer into the supplied docs was returned
                if cited_idx == item["ref"]:
                    arm.source_correct += 1
            if progress:
                print(f"      oa-fs   {item['q'][:32]:<32} cited_file={cited_idx} expected={item['ref']} kind={arm.pointer_kind}", flush=True)
    except Exception as e:  # noqa: BLE001
        arm.errors.append(f"setup: {type(e).__name__}: {str(e)[:120]}")
        arm.ran = arm.asked > 0
    finally:
        try:
            if store is not None:
                client.vector_stores.delete(store.id)
            for fid, _ in file_ids:
                try:
                    client.files.delete(fid)
                except Exception:  # noqa: BLE001
                    pass
        except Exception:  # noqa: BLE001
            pass
    return arm


def run_gemini_feature_arm(client, model_key: str, text_questions, *, progress=False) -> ArmResult:
    """Gemini's citation feature: File Search over a hosted file_search_store. The user's documents must
    be uploaded and indexed (persisted objects), and the grounding is chunk-level (no character offset)."""
    from google.genai import types

    from common.models import get
    from common.pricing import cost_from_buckets

    m = get(model_key)
    arm = ArmResult(name=f"gemini File Search:{model_key}", provider="gemini", model=m.id,
                    mechanism="hosted File Search", pointer_kind="none",
                    note="File Search REQUIRES a hosted file_search_store; grounding is chunk-level, no char offset")
    files = _feature_files()
    store = None
    try:
        store = client.file_search_stores.create(config={"display_name": "feature-radar-docs"})
        arm.setup_calls += 1
        arm.persisted_objects += 1
        title_to_idx = {}
        for di, fname, title, body in files:
            title_to_idx[fname] = di
            title_to_idx[title] = di
            op = client.file_search_stores.upload_to_file_search_store(
                file=_tmp_textfile(body, fname), file_search_store_name=store.name,
                config={"display_name": fname})
            arm.setup_calls += 1
            arm.persisted_objects += 1
            for _ in range(30):
                op = client.operations.get(op)
                if getattr(op, "done", False):
                    break
                time.sleep(2)
        tool = types.Tool(file_search=types.FileSearch(file_search_store_names=[store.name]))
        for item in text_questions:
            arm.asked += 1
            try:
                t0 = time.perf_counter()
                r = client.models.generate_content(
                    model=m.id, contents=item["q"] + " Answer in one sentence and cite the source.",
                    config=types.GenerateContentConfig(
                        tools=[tool], max_output_tokens=DIY_MAX_TOKENS,
                        http_options=types.HttpOptions(timeout=int(REQUEST_TIMEOUT_S * 1000))))
                arm.latency += time.perf_counter() - t0
            except Exception as e:  # noqa: BLE001
                arm.errors.append(f"{item['q'][:24]}: {type(e).__name__}: {str(e)[:80]}")
                continue
            u = getattr(r, "usage_metadata", None)
            inp = (getattr(u, "prompt_token_count", 0) or 0) if u else 0
            out = ((getattr(u, "candidates_token_count", 0) or 0) +
                   (getattr(u, "thoughts_token_count", 0) or 0)) if u else 0
            arm.cost += cost_from_buckets(model_key, fresh_input=inp, cached=0, output=out)
            arm.input_tokens += inp
            arm.output_tokens += out
            cited_idx = None
            for cand in (getattr(r, "candidates", None) or []):
                gm = getattr(cand, "grounding_metadata", None)
                for ch in ((getattr(gm, "grounding_chunks", None) or []) if gm else []):
                    arm.pointer_kind = "chunk-level"
                    rc = getattr(ch, "retrieved_context", None)
                    title = (getattr(rc, "title", "") or "") if rc else ""
                    for key, di in title_to_idx.items():
                        if key and (key in title or title in key):
                            cited_idx = di
            if cited_idx is not None:
                arm.cited += 1
                arm.resolved += 1
                if cited_idx == item["ref"]:
                    arm.source_correct += 1
            if progress:
                print(f"      gm-fs   {item['q'][:32]:<32} cited_chunk={cited_idx} expected={item['ref']} kind={arm.pointer_kind}", flush=True)
    except Exception as e:  # noqa: BLE001
        arm.errors.append(f"setup: {type(e).__name__}: {str(e)[:120]}")
        arm.ran = arm.asked > 0
    finally:
        try:
            if store is not None:
                client.file_search_stores.delete(name=store.name, config={"force": True})
        except Exception:  # noqa: BLE001
            pass
    return arm


# --------------------------------------------------------------------------- the run and the gate

@dataclass
class ParaRun:
    arms: list
    n_questions: int
    total_cost: float
    skipped: list = field(default_factory=list)


def _clients():
    from common.client import get_client
    from common.runner import get_gemini_client, get_openai_client
    return {"anthropic": get_client(), "openai": get_openai_client(), "gemini": get_gemini_client()}


def run_benchmark(*, quick=False, progress=False) -> ParaRun:
    clients = _clients()
    tq = QUESTIONS[:2] if quick else QUESTIONS
    arms, skipped = [], []
    if clients["anthropic"] is not None:
        if progress:
            print("    arm: claude citations (inline, char-span, zero hosted objects)")
        arms.append(run_claude_feature_arm(clients["anthropic"], CLAUDE_MODEL, tq, progress=progress))
    else:
        skipped.append("claude (ANTHROPIC_API_KEY absent)")
    if clients["openai"] is not None:
        if progress:
            print("    arm: openai file_search (hosted vector store)")
        arms.append(run_openai_feature_arm(clients["openai"], OPENAI_MODEL, tq, progress=progress))
    else:
        skipped.append("openai (key absent)")
    if clients["gemini"] is not None:
        if progress:
            print("    arm: gemini File Search (hosted store)")
        arms.append(run_gemini_feature_arm(clients["gemini"], GEMINI_MODEL, tq, progress=progress))
    else:
        skipped.append("gemini (key absent)")
    return ParaRun(arms=arms, n_questions=len(tq), total_cost=sum(a.cost for a in arms), skipped=skipped)


def score_run(run: ParaRun) -> dict:
    """The cross-vendor gate: Claude grounds every answer in the supplied documents with a char-span
    pointer (guaranteed to resolve) and ZERO hosted objects, while both competitors require a hosted
    store (persisted objects, a third-party copy of the user's data) and return only a coarser
    file/chunk-level pointer. An API-surface win, so it holds at the competitors' frontier tier."""
    claude = next((a for a in run.arms if a.provider == "anthropic"), None)
    comps = [a for a in run.arms if a.provider in ("openai", "gemini")]
    n = run.n_questions

    claude_char_span_all = bool(claude and claude.pointer_kind == "char-span"
                                and claude.resolved == n and claude.source_correct == n)
    claude_zero_hosted = bool(claude and claude.persisted_objects == 0)
    all_comps_ran = len(comps) >= 2 and all(a.ran and a.resolved > 0 and not a.errors for a in comps)
    comps_need_hosted_store = bool(comps) and all(a.persisted_objects > 0 for a in comps)
    comps_coarser = bool(comps) and all(a.pointer_kind in ("file-level", "chunk-level", "none") for a in comps)
    total_persisted = sum(a.persisted_objects for a in comps)

    positive = (claude_char_span_all and claude_zero_hosted and all_comps_ran
                and comps_need_hosted_store and comps_coarser)
    return {
        "positive_signal": positive,
        "promotable_edge": positive,
        "claude_char_span_into_supplied_docs": claude_char_span_all,
        "claude_persisted_objects": claude.persisted_objects if claude else None,
        "competitor_persisted_objects": {a.name: a.persisted_objects for a in comps},
        "competitor_pointer_kinds": {a.name: a.pointer_kind for a in comps},
        "competitor_total_persisted_objects": total_persisted,
        "all_competitors_ran": all_comps_ran,
        "why_not_promotable": [] if positive else [
            reason for reason, failed in [
                ("Claude did not return a resolving char-span into the supplied docs for every question", not claude_char_span_all),
                ("the Claude path required a hosted/persisted object", not claude_zero_hosted),
                ("not every competitor citation-feature arm ran cleanly", not all_comps_ran),
                ("a competitor cited without a hosted store (no persisted objects)", not comps_need_hosted_store),
                ("a competitor returned a char-span pointer (parity on granularity)", not comps_coarser),
            ] if failed
        ],
    }


# --------------------------------------------------------------------------- the Demonstrator interface
#
# demo_kind = "grounding_resolution": this proves the citations edge. The registry keys one demonstrator
# per demoKind and the clean-text CitationsDemonstrator (edges/citations/demo.py) owns that slot for the
# cadence's dispatch, so this arm is intentionally NOT auto-registered (it would overwrite that slot). It
# runs via its explicit `make citations-paraphrase` target and `run.py citations-paraphrase` dispatch.

class CitationsVsStoresDemonstrator(BaseDemonstrator):
    demo_kind = "grounding_resolution"

    def estimate(self, edge, spec):
        return CostEstimate(usd=0.15, wall_clock_s=120.0, command="make citations-paraphrase",
                            note="Claude inline citations vs OpenAI file_search vs Gemini File Search (live "
                                 "hosted stores), over a few user documents; OpenAI/Gemini arms run only with their keys")

    def _run(self, spec):
        spec = spec or {}
        if spec.get("_run") is None:
            spec["_run"] = run_benchmark(quick=spec.get("quick", False), progress=spec.get("progress", False))
        return spec["_run"]

    def _arm_to_Arm(self, a: ArmResult):
        return Arm(provider=a.provider, model=a.model, ran=a.ran and a.asked > 0,
                   latency_s=a.latency, input_tokens=a.input_tokens, output_tokens=a.output_tokens,
                   cost_usd=a.cost, ctx=a.input_tokens,
                   metric={"mechanism": a.mechanism, "pointer_kind": a.pointer_kind,
                           "resolved": f"{a.resolved}/{a.asked}",
                           "grounded_correct_source": f"{a.source_correct}/{a.asked}",
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
        if ca is None or ca.asked == 0:
            return Verdict(verdict="never-evaluated", passed=False, metric={"reason": "Claude arm did not run"})
        gate = score_run(run)
        metric = {
            "claude_pointer": ca.pointer_kind,
            "claude_resolved": f"{ca.resolved}/{ca.asked}",
            "claude_persisted_objects": ca.persisted_objects,
            "competitor_persisted_objects": gate["competitor_persisted_objects"],
            "competitor_pointer_kinds": gate["competitor_pointer_kinds"],
        }
        all_comp_ran = gate["all_competitors_ran"]
        if gate["promotable_edge"] and all_comp_ran:
            return Verdict(verdict="claude-ahead", passed=True, metric=metric,
                           note="Claude returned a guaranteed-resolve char-span into the supplied documents "
                                "with zero hosted objects; OpenAI and Gemini required a hosted store and "
                                "returned only file/chunk-level citations")
        if gate["claude_char_span_into_supplied_docs"] and not all_comp_ran:
            return Verdict(verdict="never-evaluated", passed=False, metric=metric,
                           note="Claude grounded every answer, but not every competitor arm ran")
        return Verdict(verdict="within-claude-only", passed=False, metric=metric,
                       note="the cross-vendor feature comparison did not fully clear on this run")

    def receipt(self, edge, claude, competitors, verdict, spec):
        return self.build_receipt(
            edge, claude, competitors, verdict, spec,
            workload={
                "task_shape": f"{len(QUESTIONS)} questions over {len(TEXT_DOCS)} user documents; every vendor "
                              "returns a citation pointer INTO those documents with its real citation tool. The "
                              "gate is whether the pointer resolves to the supplied documents, at what "
                              "granularity, and how many hosted objects it required",
                "models": {"claude": claude.model, "competitors": [c.model for c in competitors]},
                "features_on": ["Claude citations.enabled (inline, char_location)",
                                "OpenAI file_search (hosted vector store)",
                                "Gemini File Search (hosted file_search_store)"],
                "assumptions": "Claude cites the directly-supplied documents inline; the competitors cannot "
                               "cite a directly-supplied document and must upload it to a hosted store first. "
                               "Verified against the vendors' live docs 2026-06-19. Citations is incompatible "
                               "with Structured Outputs (the API returns a 400 together)",
            },
            grounding=[
                {"claim": "citations are guaranteed to contain valid pointers into the provided documents; "
                          "cited_text does not count towards output tokens",
                 "source_url": "https://platform.claude.com/docs/en/build-with-claude/citations",
                 "date": "2026-06-19"},
                {"claim": "OpenAI file_search requires a hosted vector store; file citations are file-level, "
                          "not a char span into a directly-supplied document",
                 "source_url": "https://developers.openai.com/api/docs/guides/tools-file-search",
                 "date": "2026-06-19"},
                {"claim": "Gemini File Search requires a hosted file_search_store; grounding is chunk-level "
                          "with no character offset into the source",
                 "source_url": "https://ai.google.dev/gemini-api/docs/file-search", "date": "2026-06-19"},
            ],
            fairness={
                "best_to_best": "every vendor uses its real citation tool over the same user documents and the "
                                "same questions; the competitors run their FRONTIER tier while Claude runs the "
                                "lower Sonnet tier, so the win is the API surface, not the model",
                "isolate": "same documents, same questions; only each vendor's citation mechanism differs, so "
                           "the pointer granularity and the hosted-object count are attributable to the API",
                "lead_basis": "head-to-head",
            },
        )


CITATIONS_VS_STORES_DEMONSTRATOR = CitationsVsStoresDemonstrator()


# --------------------------------------------------------------------------- the CLI receipt

def _print_run(run: ParaRun) -> None:
    from common.client import fmt_usd

    print("\n  === Claude vs the other models: best citation FEATURE, head to head ===")
    print(f"  {run.n_questions} questions over {len(TEXT_DOCS)} user documents. Each vendor returns a citation")
    print("  pointer INTO those documents with its real citation tool.\n")
    header = f"  {'arm':<30}{'pointer':<13}{'resolves':>9}{'src ok':>8}{'hosted objs':>13}{'cost':>9}"
    print(header)
    print("  " + "-" * (len(header) - 2))
    for a in run.arms:
        print(f"  {a.name:<30}{a.pointer_kind:<13}{f'{a.resolved}/{a.asked}':>9}{f'{a.source_correct}/{a.asked}':>8}"
              f"{a.persisted_objects:>13}{fmt_usd(a.cost):>9}")
        if a.errors:
            print(f"      note: {a.errors[0]}")
    v = score_run(run)
    print(f"\n  promotable_edge: {str(v['promotable_edge']).lower()}  "
          f"(Claude: char-span into the supplied docs, {v.get('claude_persisted_objects')} hosted objects; "
          f"competitors needed {v.get('competitor_total_persisted_objects')} hosted objects total)")
    print(f"\n  total spend this run: {fmt_usd(run.total_cost)}")
    if run.skipped:
        print(f"  arms not run: {', '.join(run.skipped)}")


def _receipt_dict(run: ParaRun) -> dict:
    verdict = score_run(run)
    return {
        "date": "2026-06-19",
        "claim_under_test": (
            "Over the same user documents, Claude's citation feature returns a structured, API-guaranteed-"
            "to-resolve CHAR-SPAN pointer into a directly-supplied document with ZERO hosted objects, while "
            "OpenAI file_search and Gemini File Search require uploading those documents to a hosted vector "
            "store (persisted objects, a third-party copy of the user's data) and return only a coarser "
            "file/chunk-level citation. Grounded and adversarially verified against the vendors' live docs "
            "2026-06-19."
        ),
        "n_questions": run.n_questions,
        "n_text_docs": len(TEXT_DOCS),
        "total_cost": round(run.total_cost, 6),
        "sources": {
            "claude_citations": "https://platform.claude.com/docs/en/build-with-claude/citations",
            "openai_file_search": "https://developers.openai.com/api/docs/guides/tools-file-search",
            "gemini_file_search": "https://ai.google.dev/gemini-api/docs/file-search",
        },
        "skipped": run.skipped,
        "arms": [{"name": a.name, "provider": a.provider, "model": a.model, "mechanism": a.mechanism,
                  "pointer_kind": a.pointer_kind, "resolved": f"{a.resolved}/{a.asked}",
                  "source_correct": f"{a.source_correct}/{a.asked}", "persisted_objects": a.persisted_objects,
                  "setup_calls": a.setup_calls, "cost": round(a.cost, 6), "latency_s": round(a.latency, 2),
                  "errors": a.errors, "ran": a.ran} for a in run.arms],
        "verdict": verdict,
    }


def _sample_text(receipt: dict) -> str:
    v = receipt["verdict"]
    rows = [
        "  Claude vs the other models: best citation FEATURE, head to head.",
        f"  {receipt['n_questions']} questions over {receipt['n_text_docs']} user documents. Each vendor returns a citation",
        "  pointer INTO those documents with its real tool (Claude inline citations, OpenAI file_search,",
        "  Gemini File Search). Same documents, same questions, every arm reads its own API's citation.",
        "",
        "  arm                             pointer       resolves  src ok   hosted objs      cost",
        "  ------------------------------------------------------------------------------------------",
    ]
    for a in receipt["arms"]:
        rows.append(
            f"  {a['name']:<32}{a['pointer_kind']:<13}{a['resolved']:>9}{a['source_correct']:>8}"
            f"{a['persisted_objects']:>13}{('$' + format(a['cost'], '.4f')):>10}"
        )
        if a["errors"]:
            rows.append(f"      note: {a['errors'][0]}")
    rows.extend([
        "",
        "  Verdict:",
        f"    positive_signal: {str(v['positive_signal']).lower()}",
        f"    promotable_edge: {str(v['promotable_edge']).lower()}",
        f"    claude_char_span_into_supplied_docs: {str(v['claude_char_span_into_supplied_docs']).lower()}",
        f"    claude_hosted_objects: {v.get('claude_persisted_objects')}",
        f"    competitor_hosted_objects: {v.get('competitor_persisted_objects')}",
        f"    competitor_pointer_kinds: {v.get('competitor_pointer_kinds')}",
        "",
        "  Honest reading:",
        "  - Claude returns a structured, API-guaranteed-to-resolve CHAR-SPAN pointer into the user's",
        "    directly-supplied documents, with ZERO hosted objects (the data never leaves the request).",
        "  - OpenAI file_search and Gemini File Search cannot cite a directly-supplied document: they",
        "    REQUIRE uploading it to a hosted vector store first (the hosted-objs column, a third-party",
        "    copy of the user's data), and even then the citation is file-level (OpenAI) or chunk-level",
        "    (Gemini), never a guaranteed char span into the source. Verified vs their live docs 2026-06-19.",
        "  - This is an API-surface gap, so it holds at the competitors' FRONTIER tier, not a model contest.",
    ])
    if v.get("why_not_promotable"):
        rows.append("  - not promotable this run: " + "; ".join(v["why_not_promotable"]))
    rows.extend([
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
        '"""citations-paraphrase: wrapper for the Claude-vs-competitors citation feature edge."""\n\n'
        "from engine.demonstrators.paraphrase_resolution import main\n\n\n"
        'if __name__ == "__main__":\n'
        "    raise SystemExit(main())\n"
    )
    tool_name = {"inline citations": "Claude Citations (inline)", "hosted file_search": "OpenAI file_search",
                 "hosted File Search": "Gemini File Search"}
    rows = ["| arm | citation tool | pointer granularity | resolves | cites right doc | hosted objects (copies of the user's data) | cost |",
            "|---|---|:---:|:---:|:---:|:---:|---:|"]
    for a in receipt["arms"]:
        rows.append(
            f"| {a['name']} | {tool_name.get(a['mechanism'], a['mechanism'])} | {a['pointer_kind']} | "
            f"{a['resolved']} | {a['source_correct']} | {a['persisted_objects']} | ${a['cost']:.4f} |")
    v = receipt["verdict"]
    comp_objs = v.get("competitor_persisted_objects", {})
    comp_total = sum(comp_objs.values()) if comp_objs else 0
    comp_each = "/".join(str(x) for x in comp_objs.values()) if comp_objs else "0"
    (edge_dir / "README.md").write_text(
        "# Edge: Citations, Claude vs the other models on grounding a user's own documents\n\n"
        "Part of [claude-feature-radar](../../README.md). Each vendor reads a user's own documents and must "
        "return a citation pointer INTO them with its real citation tool: Claude inline `citations`, OpenAI "
        "`file_search`, Gemini `File Search`. No string matching, each reads what its own API returns.\n\n"
        "## What It Is\n\n"
        "A product that answers over a user's own documents (a contract, a report, the app's wiki) needs to "
        "deep-link each answer to the exact source so a person can verify before acting. With "
        "`citations: {\"enabled\": true}` on the supplied documents, Claude attaches a pointer whose "
        "`cited_text` is the verbatim source span the API extracted, guaranteed to resolve, with zero "
        "resolver code, the quote free of output tokens, and no copy of the user's data leaving the request. "
        "The competitors' citation tools cannot cite a directly-supplied document at all: they require "
        "uploading it to a hosted vector store first.\n\n"
        "## The Measured Proof\n\n"
        f"Run: `make citations-paraphrase`, {receipt['date']}, {receipt['n_questions']} questions over "
        f"{receipt['n_text_docs']} user documents. Claude runs Sonnet, the competitors run their frontier "
        "tier (run the stronger competitor before a correctness claim).\n\n"
        + "\n".join(rows)
        + "\n\n"
        "Claude returns a structured, API-guaranteed-to-resolve **char-span** pointer into the user's "
        "directly-supplied documents with **zero hosted objects**, so the data never leaves the request. "
        "OpenAI `file_search` and Gemini `File Search` **cannot cite a directly-supplied document**: they "
        f"require uploading it to a hosted vector store first ({comp_each} hosted objects, {comp_total} in "
        "total, a third-party copy of the user's data), and even then the citation is file-level (OpenAI) or "
        "chunk-level (Gemini), never a guaranteed char span into the source. Verified against the vendors' "
        "live docs on 2026-06-19. Because this is an API-surface gap, it holds at the competitors' frontier "
        "tier, it is not a model contest.\n\n"
        f"Verdict: `promotable_edge: {str(bool(v.get('promotable_edge'))).lower()}`.\n\n"
        "Full receipt: [`sample.txt`](sample.txt). Machine receipt: [`receipt.json`](receipt.json).\n\n"
        "## Honest Scope\n\n"
        "- The win is feature vs feature and is an API-surface gap (the competitors cannot return a "
        "structured, guaranteed-resolve pointer into a directly-supplied document without a hosted store), so "
        "it survives their frontier models.\n"
        "- The competitors CAN cite their own content through a hosted vector store. That hosted path, and "
        "its file/chunk granularity and persisted objects, is also measured in the "
        "[search-results](../search-results/README.md), [pdf-citations](../pdf-citations/README.md), and "
        "[grounding-stack](../grounding-stack/README.md) edges.\n"
        "- Citations cannot be combined with Structured Outputs. The two return a 400 together, so a "
        "grounded answer here is free text.\n\n"
        "## Run It Yourself\n\n"
        "```bash\n"
        "git clone https://github.com/cfregly/claude-feature-radar && cd claude-feature-radar\n"
        "make setup\n"
        "make compare-deps\n"
        "cp .env.example .env   # paste ANTHROPIC_API_KEY, OPENAI_API_KEY, and GEMINI_API_KEY\n"
        f"make citations-paraphrase   # about ${receipt['total_cost']:.2f}, the competitor arms create and delete a hosted store\n"
        "```\n\n"
        "Sources:\n\n"
        f"- Claude citations: {receipt['sources']['claude_citations']}\n"
        f"- OpenAI file search: {receipt['sources']['openai_file_search']}\n"
        f"- Gemini file search: {receipt['sources']['gemini_file_search']}\n"
    )
    return edge_dir


def main(argv=None) -> int:
    from common.client import load_env, repo_root

    p = argparse.ArgumentParser(description="Claude citations vs OpenAI file_search vs Gemini File Search, "
                                            "over a user's own documents.")
    p.add_argument("--quick", action="store_true", help="2 questions, a cheap smoke")
    p.add_argument("--emit-edge", action="store_true", help="write edges/citations-paraphrase/{README,demo,sample,receipt}")
    a = p.parse_args(argv)

    load_env()
    print("\n  Claude vs the other models on grounding a user's own documents.")
    print("  Each vendor returns a citation pointer with its real citation tool.\n")
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


# ----------------------------------------------------------------- internal analysis helpers (NOT the edge)
#
# The do-it-yourself str.find baseline is NOT part of this edge (a model quote located with source.find is
# an artificial path nobody builds, and its only finding was that the resolve guarantee is PARITY against a
# competent resolver). That internal both-directions analysis lives in scripts/paraphrase_scale_probe.py,
# which imports the four small helpers below. They are kept here only so that probe keeps working.

PARAPHRASE_RULE = ("Answer in your own words. Paraphrase the source. Do NOT copy any sentence verbatim "
                   "from the documents.")
DIY_INSTRUCTIONS = (
    PARAPHRASE_RULE + " Then give the single supporting sentence from the source, in your own words, "
    "and the exact title of the document it came from. Respond with ONLY a JSON object and nothing "
    'else: {"answer": "...", "doc_title": "...", "quote": "..."}.')

_PUNCT_FOLD = {
    "’": "'", "‘": "'", "‛": "'", "ʼ": "'", "´": "'", "`": "'",
    "“": '"', "”": '"', "„": '"', "‟": '"',
    "‐": "-", "‑": "-", "‒": "-", "–": "-", "—": "-", "―": "-", "−": "-",
    "…": "...",
}


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


def _fold(s: str) -> str:
    """Normalize typography and whitespace for a tolerant substring check (used by the scale probe)."""
    s = unicodedata.normalize("NFKC", s or "")
    for a, b in _PUNCT_FOLD.items():
        s = s.replace(a, b)
    return "".join(s.casefold().split())


def _normws(s: str) -> str:
    return " ".join((s or "").split())


if __name__ == "__main__":
    raise SystemExit(main())
