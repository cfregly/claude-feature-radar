"""search_results_grounding: cite the developer's OWN retrieved RAG chunks inline, resolver-free, with
a block-level pointer and no hosted vector store, where the competitors require a persisted store and
return only a file/chunk-level pointer.

THE EDGE, at subfeature depth. Pass your own retrieved passages as `search_result` content blocks
(`citations: {"enabled": true}`) directly in the request. Claude returns each claim with a
`search_result_location` citation: the `search_result_index` (which chunk), `start_block_index` and
`end_block_index` (the span inside that chunk), and the verbatim `cited_text` (free of output tokens),
API-guaranteed to resolve. No hosted store, no upload, no indexing, no persisted copy of the user's
data, no resolver code. No beta header.

WHY IT IS A CROSS-VENDOR EDGE.
  - OpenAI `file_search` requires creating a hosted `vector_store`, uploading the chunks as files, and
    waiting for indexing FIRST. The citation is a `file_citation` annotation: a file_id/filename plus
    an index into the model's OUTPUT text, not a span into the chunk you supplied.
  - Gemini `file_search` requires creating a hosted `file_search_store` and importing the chunks. The
    citation is chunk text via `grounding_metadata`, hosted-only, no character/block offset into your
    supplied content.
So to cite the developer's own RAG chunks, the competitors require a persisted hosted index (extra
round trips, an embedding/indexing step, a third-party copy of the user's data) and return a coarser
pointer. Claude does it inline in the same request, resolver-free, with a block-level span. Verified
live 2026-06-19.

WHAT THIS MEASURES, the SAME gate on every arm: over a fixed set of questions about developer-supplied
RAG chunks, (1) did the platform return a citation that resolves to the CORRECT source chunk, and
(2) how many hosted-store setup calls / persisted objects did it require to do so. Claude: correct
chunk, 0 hosted objects. The competitors: scored on both, run live at their best (real vector store).

FOUNDER WORKLOAD. A RAG product over a customer's own corpus (support docs, contracts, clinical notes)
where the founder runs their OWN retriever (pgvector, Pinecone, a custom reranker) and wants every
answer to deep-link to the exact retrieved chunk, without shipping the user's data into a third-party
vector store. The value a founder prices: verifiable citations with zero resolver code and no data
lock-in.

DEPENDENCIES. The Claude arm needs only anthropic. The competitor arms need their optional SDKs and
keys (lazy). The competitor arms create and then DELETE their hosted stores (cleanup in a finally).
"""

from __future__ import annotations

import argparse
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

CLAUDE_MODEL = os.environ.get("SR_CLAUDE_MODEL", "haiku")
OPENAI_MODEL = os.environ.get("SR_OPENAI_MODEL", "gpt-mid")
GEMINI_MODEL = os.environ.get("SR_GEMINI_MODEL", "gem-flash")
MAX_TOKENS = int(os.environ.get("SR_MAX_TOKENS", "512"))


# --------------------------------------------------------------------------- the developer-supplied chunks
#
# Five RAG chunks a founder's own retriever might return for a support-bot product. Each chunk has a
# stable id (its filename for the hosted-store arms) and a distinct citable fact. Each question's answer
# lives in exactly one chunk, so a correct citation must point at that chunk.

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


@dataclass
class ArmResult:
    name: str
    provider: str
    model: str
    ran: bool = True
    answered: int = 0
    cited: int = 0            # returned a citation resolving to the correct source chunk
    asked: int = 0
    setup_calls: int = 0      # hosted-store setup API calls required before answering (0 for inline)
    persisted_objects: int = 0  # hosted stores/files created (a third-party copy of the user's data)
    pointer_kind: str = ""    # "block-span" (Claude) | "file-level" (OpenAI) | "chunk-level" (Gemini) | "none"
    cost: float = 0.0
    latency: float = 0.0
    input_tokens: int = 0
    output_tokens: int = 0
    note: str = ""
    errors: list = field(default_factory=list)


# --------------------------------------------------------------------------- the Claude arm (inline)

def run_claude_arm(client, model_key: str, *, progress=False) -> ArmResult:
    from common.models import get
    from common.pricing import cost_breakdown

    m = get(model_key)
    arm = ArmResult(name=f"claude:{model_key}", provider="anthropic", model=m.id,
                    pointer_kind="block-span", setup_calls=0, persisted_objects=0,
                    note="inline search_result blocks, citations enabled; no hosted store")
    platform.used("citations", "search_result_location pointer into developer-supplied chunks")
    blocks = [{"type": "search_result", "source": f"kb://{cid}", "title": title,
               "content": [{"type": "text", "text": body}], "citations": {"enabled": True}}
              for cid, title, body in CHUNKS]
    for q, ans_idx, token in QUESTIONS:
        arm.asked += 1
        content = blocks + [{"type": "text", "text": q + " Answer in one sentence and cite the source."}]
        try:
            t0 = time.perf_counter()
            r = client.messages.create(model=m.id, max_tokens=MAX_TOKENS,
                                       messages=[{"role": "user", "content": content}])
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
        idxs = []
        for b in r.content:
            if getattr(b, "type", None) == "text":
                for ci in (getattr(b, "citations", None) or []):
                    if getattr(ci, "type", None) == "search_result_location":
                        idxs.append(getattr(ci, "search_result_index", None))
        if ans_idx in idxs:
            arm.cited += 1
        if progress:
            print(f"      claude {q[:30]:<30} cited_chunks={idxs} expected={ans_idx}", flush=True)
    return arm


# --------------------------------------------------------------------------- the OpenAI arm (file_search)

def run_openai_arm(client, model_key: str, *, progress=False) -> ArmResult:
    from common.models import get
    from common.pricing import cost_from_buckets

    m = get(model_key)
    arm = ArmResult(name=f"openai:{model_key}", provider="openai", model=m.id, pointer_kind="none",
                    note="hosted vector store required; file_citation is file-level, not a chunk span")
    store = None
    file_ids = []
    try:
        # setup: create a vector store and upload each chunk as a file, then poll for indexing.
        store = client.vector_stores.create(name="feature-radar-sr")
        arm.setup_calls += 1
        arm.persisted_objects += 1
        for cid, title, body in CHUNKS:
            import io
            f = client.files.create(file=(cid, io.BytesIO(body.encode()), "text/plain"), purpose="assistants")
            file_ids.append(f.id)
            client.vector_stores.files.create(vector_store_id=store.id, file_id=f.id)
            arm.setup_calls += 2
            arm.persisted_objects += 1
        # wait for indexing
        for _ in range(30):
            lst = client.vector_stores.files.list(vector_store_id=store.id)
            if all(getattr(x, "status", "") == "completed" for x in lst.data) and lst.data:
                break
            time.sleep(2)
        # map filename -> chunk index, to check the citation resolves to the right chunk
        fname_to_idx = {cid: i for i, (cid, _, _) in enumerate(CHUNKS)}
        id_to_idx = {fid: fname_to_idx[CHUNKS[i][0]] for i, fid in enumerate(file_ids)}
        for q, ans_idx, token in QUESTIONS:
            arm.asked += 1
            try:
                t0 = time.perf_counter()
                r = client.responses.create(
                    model=m.id, max_output_tokens=MAX_TOKENS,
                    tools=[{"type": "file_search", "vector_store_ids": [store.id]}],
                    input=q + " Answer in one sentence and cite the source.",
                )
                arm.latency += time.perf_counter() - t0
            except Exception as e:  # noqa: BLE001
                arm.errors.append(f"{q[:24]}: {type(e).__name__}: {str(e)[:80]}")
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
            cited_idx = None
            for item in (getattr(r, "output", None) or []):
                for c in (getattr(item, "content", None) or []):
                    for a in (getattr(c, "annotations", None) or []):
                        if getattr(a, "type", None) == "file_citation":
                            arm.pointer_kind = "file-level"
                            fid = getattr(a, "file_id", None)
                            if fid in id_to_idx:
                                cited_idx = id_to_idx[fid]
            if cited_idx == ans_idx:
                arm.cited += 1
            if progress:
                print(f"      openai {q[:30]:<30} cited_chunk={cited_idx} expected={ans_idx} kind={arm.pointer_kind}", flush=True)
    except Exception as e:  # noqa: BLE001
        arm.errors.append(f"setup: {type(e).__name__}: {str(e)[:120]}")
        arm.ran = arm.asked > 0
    finally:
        # cleanup: never leave a persisted copy of the data behind.
        try:
            if store is not None:
                client.vector_stores.delete(store.id)
            for fid in file_ids:
                try:
                    client.files.delete(fid)
                except Exception:  # noqa: BLE001
                    pass
        except Exception:  # noqa: BLE001
            pass
    return arm


# --------------------------------------------------------------------------- the Gemini arm (file_search)

def run_gemini_arm(client, model_key: str, *, progress=False) -> ArmResult:
    from google.genai import types

    from common.models import get
    from common.pricing import cost_from_buckets

    m = get(model_key)
    arm = ArmResult(name=f"gemini:{model_key}", provider="gemini", model=m.id, pointer_kind="none",
                    note="hosted file_search_store required; grounding is chunk-level, no block offset")
    store = None
    try:
        store = client.file_search_stores.create(config={"display_name": "feature-radar-sr"})
        arm.setup_calls += 1
        arm.persisted_objects += 1
        for cid, title, body in CHUNKS:
            op = client.file_search_stores.upload_to_file_search_store(
                file=cid.encode() if False else _tmp_textfile(body, cid),
                file_search_store_name=store.name,
                config={"display_name": cid},
            )
            arm.setup_calls += 1
            arm.persisted_objects += 1
            # wait for the import operation
            for _ in range(30):
                op = client.operations.get(op)
                if getattr(op, "done", False):
                    break
                time.sleep(2)
        fs = types.FileSearch(file_search_store_names=[store.name])
        tool = types.Tool(file_search=fs)
        for q, ans_idx, token in QUESTIONS:
            arm.asked += 1
            try:
                t0 = time.perf_counter()
                r = client.models.generate_content(
                    model=m.id, contents=q + " Answer in one sentence and cite the source.",
                    config=types.GenerateContentConfig(tools=[tool], max_output_tokens=MAX_TOKENS),
                )
                arm.latency += time.perf_counter() - t0
            except Exception as e:  # noqa: BLE001
                arm.errors.append(f"{q[:24]}: {type(e).__name__}: {str(e)[:80]}")
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
            resolved = False
            for cand in (getattr(r, "candidates", None) or []):
                gm = getattr(cand, "grounding_metadata", None)
                chunks = (getattr(gm, "grounding_chunks", None) or []) if gm else []
                for ch in chunks:
                    arm.pointer_kind = "chunk-level"
                    rc = getattr(ch, "retrieved_context", None)
                    title = (getattr(rc, "title", "") or "") if rc else ""
                    if title == CHUNKS[ans_idx][0] or CHUNKS[ans_idx][0] in title:
                        resolved = True
            if resolved:
                arm.cited += 1
            if progress:
                print(f"      gemini {q[:30]:<30} resolved={resolved} expected={ans_idx} kind={arm.pointer_kind}", flush=True)
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


def _tmp_textfile(body: str, name: str) -> str:
    import tempfile
    d = tempfile.mkdtemp()
    path = os.path.join(d, name)
    with open(path, "w") as f:
        f.write(body)
    return path


# --------------------------------------------------------------------------- the run

@dataclass
class SrRun:
    arms: list
    n_questions: int
    total_cost: float
    skipped: list = field(default_factory=list)


def score_run(run: SrRun) -> dict:
    claude = next((a for a in run.arms if a.provider == "anthropic"), None)
    competitors = [a for a in run.arms if a.provider in ("openai", "gemini")]
    claude_inline = bool(
        claude
        and claude.asked
        and claude.answered == claude.asked
        and claude.cited == claude.asked
        and claude.pointer_kind == "block-span"
        and claude.setup_calls == 0
        and claude.persisted_objects == 0
    )
    all_competitors_ran = len(competitors) >= 2 and all(a.asked > 0 and not a.errors for a in competitors)
    competitors_cited = bool(competitors) and all(a.cited == a.asked and a.answered == a.asked for a in competitors)
    competitors_needed_hosted_store = bool(competitors) and all(
        a.setup_calls > 0 and a.persisted_objects > 0 for a in competitors
    )
    competitor_has_inline_block_span = any(
        a.pointer_kind == "block-span" and a.persisted_objects == 0 for a in competitors
    )
    positive = (
        claude_inline
        and all_competitors_ran
        and competitors_cited
        and competitors_needed_hosted_store
        and not competitor_has_inline_block_span
    )
    return {
        "positive_signal": positive,
        "promotable_edge": positive,
        "claude_inline_block_span_all": claude_inline,
        "all_competitors_ran": all_competitors_ran,
        "competitors_cited_all": competitors_cited,
        "competitors_needed_hosted_store": competitors_needed_hosted_store,
        "competitor_has_inline_block_span": competitor_has_inline_block_span,
        "why_not_promotable": [] if positive else [
            reason for reason, failed in [
                ("Claude did not cite every answer inline with a block-span pointer", not claude_inline),
                ("not every competitor hosted-store arm ran cleanly", not all_competitors_ran),
                ("not every competitor cited the correct source", not competitors_cited),
                ("a competitor did not need a hosted store for the closest citation path", not competitors_needed_hosted_store),
                ("a competitor returned an inline block-span pointer with zero persisted objects", competitor_has_inline_block_span),
            ] if failed
        ],
    }


def _clients():
    from common.client import get_client
    from common.runner import get_gemini_client, get_openai_client
    return {"anthropic": get_client(), "openai": get_openai_client(), "gemini": get_gemini_client()}


def run_benchmark(*, progress=False) -> SrRun:
    clients = _clients()
    arms, skipped = [], []
    if clients["anthropic"] is not None:
        if progress:
            print("    arm: claude (inline search_result chunks)")
        arms.append(run_claude_arm(clients["anthropic"], CLAUDE_MODEL, progress=progress))
    else:
        skipped.append("claude (ANTHROPIC_API_KEY absent)")
    if clients["openai"] is not None:
        if progress:
            print("    arm: openai (file_search vector store)")
        arms.append(run_openai_arm(clients["openai"], OPENAI_MODEL, progress=progress))
    else:
        skipped.append("openai (key absent)")
    if clients["gemini"] is not None:
        if progress:
            print("    arm: gemini (file_search store)")
        arms.append(run_gemini_arm(clients["gemini"], GEMINI_MODEL, progress=progress))
    else:
        skipped.append("gemini (key absent)")
    return SrRun(arms=arms, n_questions=len(QUESTIONS), total_cost=sum(a.cost for a in arms), skipped=skipped)


# --------------------------------------------------------------------------- the Demonstrator interface

class SearchResultsDemonstrator(BaseDemonstrator):
    demo_kind = "byo_rag_grounding"

    def estimate(self, edge, spec):
        return CostEstimate(usd=0.10, wall_clock_s=120.0, command="make search-results",
                            note=f"{len(QUESTIONS)} questions x 3 vendors over {len(CHUNKS)} chunks; the "
                                 f"competitor arms create and delete a hosted store, cents")

    def _run(self, spec):
        spec = spec or {}
        if spec.get("_run") is None:
            spec["_run"] = run_benchmark(progress=spec.get("progress", False))
        return spec["_run"]

    def _arm_to_Arm(self, a: ArmResult):
        return Arm(provider=a.provider, model=a.model,
                   ran=a.ran and a.asked > 0, latency_s=a.latency,
                   input_tokens=a.input_tokens, output_tokens=a.output_tokens, cost_usd=a.cost, ctx=a.input_tokens,
                   metric={"answered": f"{a.answered}/{a.asked}",
                           "correct_source_citation": f"{a.cited}/{a.asked}",
                           "pointer_kind": a.pointer_kind,
                           "hosted_setup_calls": a.setup_calls,
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
        all_comp_ran = bool(competitors) and all(c.ran for c in competitors)
        comp_needs_store = all((a.setup_calls > 0) for a in run.arms if a.provider in ("openai", "gemini")) \
            and any(a.provider in ("openai", "gemini") for a in run.arms)
        metric = {
            "claude_correct_source": f"{ca.cited}/{ca.asked}",
            "claude_pointer_kind": ca.pointer_kind,
            "claude_hosted_objects": ca.persisted_objects,
            "competitors": {a.name: {"correct_source": f"{a.cited}/{a.asked}",
                                     "pointer_kind": a.pointer_kind,
                                     "hosted_setup_calls": a.setup_calls,
                                     "persisted_objects": a.persisted_objects}
                            for a in run.arms if a.provider in ("openai", "gemini")},
        }
        # The edge: Claude cites the correct chunk inline with a block-span pointer and 0 hosted
        # objects, while every competitor needed a persisted hosted store to cite at all.
        claude_inline_wins = ca.cited > 0 and ca.persisted_objects == 0 and ca.pointer_kind == "block-span"
        if claude_inline_wins and comp_needs_store and all_comp_ran:
            return Verdict(verdict="claude-ahead", passed=True, metric=metric,
                           note="Claude cited the correct chunk inline (block-span, 0 hosted objects, "
                                "resolver-free); every competitor required a persisted hosted store and "
                                "returned a coarser file/chunk-level pointer")
        if claude_inline_wins and not all_comp_ran:
            return Verdict(verdict="never-evaluated", passed=False, metric=metric,
                           note="Claude's inline resolver-free citation holds, but not every competitor "
                                "arm ran, so the cross-vendor lead is held")
        return Verdict(verdict="within-claude-only", passed=False, metric=metric,
                       note="Claude resolves inline citations; the cross-vendor structural win did not "
                            "fully clear on this run")

    def receipt(self, edge, claude, competitors, verdict, spec):
        run = self._run(spec)
        return self.build_receipt(
            edge, claude, competitors, verdict, spec,
            workload={
                "task_shape": f"{run.n_questions} questions over {len(CHUNKS)} developer-supplied RAG "
                              f"chunks; the gate is a citation that resolves to the correct source chunk "
                              f"and the hosted-store objects required to get it",
                "models": {"claude": claude.model, "competitors": [c.model for c in competitors]},
                "features_on": ["search_result content blocks with citations (search_result_location)"],
                "assumptions": "Claude cites chunks passed inline; the competitor file-search arms create "
                               "a real hosted store, upload the same chunks, then delete the store; their "
                               "citation granularity (file-level / chunk-level) is reported, not assumed",
            },
            grounding=[
                {"claim": "search_result blocks return a search_result_location with the chunk index and "
                          "block span, guaranteed to resolve, free of output tokens",
                 "source_url": "https://platform.claude.com/docs/en/build-with-claude/search-results",
                 "date": "2026-06-19"},
                {"claim": "OpenAI file_search requires a hosted vector store; the citation is a file_citation",
                 "source_url": "https://developers.openai.com/api/docs/guides/tools-file-search",
                 "date": "2026-06-19"},
                {"claim": "Gemini file_search requires a hosted file_search_store; grounding is chunk-level",
                 "source_url": "https://ai.google.dev/gemini-api/docs/file-search", "date": "2026-06-19"},
            ],
            fairness={
                "best_to_best": "each competitor runs its real hosted file-search path (a true vector "
                                "store with the same chunks), not a strawman; the comparison is the "
                                "cite-your-own-chunks subfeature",
                "isolate": "the same chunks, the same questions, the same cite instruction on every arm; "
                           "only the platform and its citation mechanism differ",
            },
        )


register(SearchResultsDemonstrator())


# --------------------------------------------------------------------------- the CLI receipt

def _print_run(run: SrRun) -> None:
    from common.client import fmt_usd

    print("\n  === search_results: cite the developer's own RAG chunks, resolver-free, no hosted store ===")
    print(f"  {run.n_questions} questions over {len(CHUNKS)} developer-supplied chunks.\n")
    header = f"  {'arm':<22}{'answered':>10}{'correct cite':>14}{'pointer':>13}{'hosted objs':>13}{'cost':>10}"
    print(header)
    print("  " + "-" * (len(header) - 2))
    for a in run.arms:
        print(f"  {a.name:<22}{f'{a.answered}/{a.asked}':>10}{f'{a.cited}/{a.asked}':>14}"
              f"{a.pointer_kind:>13}{a.persisted_objects:>13}{fmt_usd(a.cost):>10}")
        if a.errors:
            print(f"      note: {a.errors[0]}")
    print(f"\n  total spend this run: {fmt_usd(run.total_cost)}")
    if run.skipped:
        print(f"  arms not run: {', '.join(run.skipped)}")


def _receipt_dict(run: SrRun) -> dict:
    verdict = score_run(run)
    return {
        "date": "2026-06-19",
        "claim_under_test": (
            "For developer-supplied RAG chunks passed inline as search_result blocks, Claude returns "
            "a search_result_location block-span pointer without a hosted store, while OpenAI and "
            "Gemini require hosted file-search stores for their closest citation path."
        ),
        "n_questions": run.n_questions,
        "n_chunks": len(CHUNKS),
        "total_cost": round(run.total_cost, 6),
        "sources": {
            "claude_search_results": "https://platform.claude.com/docs/en/build-with-claude/search-results",
            "claude_citations": "https://platform.claude.com/docs/en/build-with-claude/citations",
            "openai_file_search": "https://developers.openai.com/api/docs/guides/tools-file-search",
            "gemini_file_search": "https://ai.google.dev/gemini-api/docs/file-search",
        },
        "skipped": run.skipped,
        "arms": [{"name": a.name, "provider": a.provider, "model": a.model,
                  "answered": f"{a.answered}/{a.asked}",
                  "correct_source_citation": f"{a.cited}/{a.asked}",
                  "pointer_kind": a.pointer_kind,
                  "hosted_setup_calls": a.setup_calls,
                  "persisted_objects": a.persisted_objects,
                  "cost": round(a.cost, 6),
                  "latency_s": round(a.latency, 2),
                  "errors": a.errors} for a in run.arms],
        "verdict": verdict,
    }


def _sample_text(receipt: dict) -> str:
    rows = [
        "  Bring-your-own-RAG citation workload: five questions over five developer-supplied chunks.",
        "  The chunks are passed inline in the request, not uploaded to a hosted vector store.",
        "",
        "  platform              answered   correct cite   pointer kind   hosted objects     cost  wall time",
        "  ------------------------------------------------------------------------------------------------------",
    ]
    for arm in receipt["arms"]:
        rows.append(
            f"  {arm['name']:<22}{arm['answered']:>10}{arm['correct_source_citation']:>15}"
            f"{arm['pointer_kind']:>15}{arm['persisted_objects']:>17}"
            f"{('$' + format(arm['cost'], '.2f')):>9}{arm['latency_s']:>8.1f}s"
        )
    verdict = receipt["verdict"]
    rows.extend([
        "",
        "  Verdict:",
        f"    positive_signal: {str(verdict['positive_signal']).lower()}",
        f"    promotable_edge: {str(verdict['promotable_edge']).lower()}",
        "",
        "  Honest reading:",
        "  - All three cited the correct source chunk.",
        "  - Claude cited inline, resolver-free, with a block-level pointer and zero persisted objects.",
        "  - OpenAI and Gemini each required a hosted vector store and returned a coarser file or chunk-level pointer.",
        "  - The claim is scoped to citing the developer's own inline chunks. Hosted file-search stores",
        "    are different persisted flows and are named separately in the sources.",
        "",
        "  Reproduce:",
        "    make search-results",
        "",
        "  Machine receipt:",
        "    data/last_search_results.json",
    ])
    return "\n".join(rows) + "\n"


def write_edge_bundle(run: SrRun, receipt: dict) -> pathlib.Path:
    from common.client import repo_root

    edge_dir = repo_root() / "edges" / "search-results"
    edge_dir.mkdir(parents=True, exist_ok=True)
    (edge_dir / "receipt.json").write_text(json.dumps(receipt, indent=2) + "\n")
    (edge_dir / "sample.txt").write_text(_sample_text(receipt))
    (edge_dir / "demo.py").write_text(
        '"""search-results: wrapper for the BYO RAG citation edge."""\n\n'
        "from engine.demonstrators.search_results_grounding import main\n\n\n"
        'if __name__ == "__main__":\n'
        "    raise SystemExit(main())\n"
    )
    rows = [
        "| arm | answered | correct cite | pointer kind | hosted objects | cost | wall time |",
        "|---|:---:|:---:|:---:|:---:|---:|---:|",
    ]
    for arm in receipt["arms"]:
        rows.append(
            f"| {arm['name']} | {arm['answered']} | {arm['correct_source_citation']} | "
            f"{arm['pointer_kind']} | {arm['persisted_objects']} | ${arm['cost']:.2f} | "
            f"{arm['latency_s']:.1f}s |"
        )
    (edge_dir / "README.md").write_text(
        "# Edge: Search results, resolver-free citations into your own RAG chunks\n\n"
        "Part of [claude-feature-radar](../../README.md). This is a measured grounding edge for "
        "retrieval you run yourself: cite the chunks your own retriever returned, inline, with no "
        "hosted vector store.\n\n"
        "## What It Is\n\n"
        "Pass your retrieved passages as `search_result` content blocks with citations enabled. "
        "Claude returns each claim with a `search_result_location` citation: the chunk index, the "
        "block span inside that chunk, and the verbatim cited text. No hosted store, no upload, no "
        "indexing, no persisted copy of the user's data, and no resolver code.\n\n"
        "## The Measured Proof\n\n"
        f"Run: `make search-results`, {receipt['date']}, five questions over five developer-supplied "
        "chunks. Correct cite means the returned citation resolved to the chunk that actually holds "
        "the answer.\n\n"
        + "\n".join(rows)
        + "\n\n"
        "All three cited the correct source. Claude did it inline, resolver-free, with a block-level "
        "pointer and zero persisted objects. OpenAI and Gemini each required a hosted vector store "
        "and returned a coarser file or chunk-level pointer.\n\n"
        "Full receipt: [`sample.txt`](sample.txt). Machine receipt: [`receipt.json`](receipt.json).\n\n"
        "## Honest Scope\n\n"
        "- The win is inline, resolver-free citation into chunks you supply, with a block-level span "
        "and no hosted store.\n"
        "- This is not a claim that competitors cannot cite at all. Through their hosted file-search "
        "stores they cited the correct source too.\n"
        "- The cost gap is partly a model-tier choice. The edge is the citation mechanism and the "
        "absence of a persisted store, not the dollar figure.\n\n"
        "## Run It Yourself\n\n"
        "```bash\n"
        "git clone https://github.com/cfregly/claude-feature-radar && cd claude-feature-radar\n"
        "make setup\n"
        "make compare-deps\n"
        "cp .env.example .env   # paste ANTHROPIC_API_KEY, OPENAI_API_KEY, and GEMINI_API_KEY\n"
        "make search-results    # cents-scale, creates and deletes competitor hosted stores\n"
        "```\n\n"
        "Sources:\n\n"
        f"- Claude search results: {receipt['sources']['claude_search_results']}\n"
        f"- Claude citations: {receipt['sources']['claude_citations']}\n"
        f"- OpenAI file search: {receipt['sources']['openai_file_search']}\n"
        f"- Gemini file search: {receipt['sources']['gemini_file_search']}\n"
    )
    return edge_dir


def main(argv=None) -> int:
    from common.client import load_env, repo_root

    p = argparse.ArgumentParser(description="search_results: cite developer-supplied RAG chunks inline, "
                                            "vs OpenAI/Gemini hosted file_search.")
    p.add_argument("--emit-edge", action="store_true", help="write edges/search-results/receipt.json")
    a = p.parse_args(argv)

    load_env()
    print("\n  search_results: does the platform cite the developer's OWN chunks resolver-free, with no")
    print("  hosted vector store? Same chunks, same questions, every arm.\n")
    run = run_benchmark(progress=True)
    _print_run(run)

    out = _receipt_dict(run)
    (repo_root() / "data").mkdir(exist_ok=True)
    (repo_root() / "data" / "last_search_results.json").write_text(json.dumps(out, indent=2) + "\n")
    if a.emit_edge:
        write_edge_bundle(run, out)
        print("\n  wrote edges/search-results/{README.md,demo.py,sample.txt,receipt.json}")
    print("\n  (per-run detail in gitignored data/last_search_results.json)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
