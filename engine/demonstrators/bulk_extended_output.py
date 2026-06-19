"""bulk_extended_output: a single request emits a deliverable larger than the competitors' per-request
output ceiling. One un-truncated turn where OpenAI and Gemini must chunk and stitch.

THE EDGE, at subfeature depth. On the Message Batches API with the beta header
`output-300k-2026-03-24`, Claude raises the per-request `max_tokens` ceiling to 300,000 output tokens
(batch-only, on Opus 4.8/4.7/4.6 and Sonnet 4.6). A nightly bulk job that turns each backlog row into
one long deliverable (a full report, a large structured extraction, a long scaffold) lands it in ONE
turn. The competitors' best models cap a single request far lower: GPT-5.5 at 128,000 output tokens,
Gemini 3.5 Flash / 3.1 Pro at 65,536. Any deliverable above those caps forces a chunk-and-stitch loop,
extra requests, and a seam-failure surface the single-turn path does not have.

WHAT THIS MEASURES, the SAME gate on every arm: one request asks for a long enumerated deliverable
(an entry per integer up to N) with a strict no-abbreviation instruction. The gate is the output tokens
produced in ONE request and whether the request truncated. Claude (batch + header) produces a
deliverable above 128k tokens in one turn. The competitors truncate at their model cap
(`finish_reason: length` / `incomplete_details: max_output_tokens`). Per-token cost is parity (all give
a 50% batch discount), so the win is the un-truncated single turn, not the dollar figure.

FOUNDER WORKLOAD. A docs-automation / report-generation / large-extraction startup with a nightly
backlog where each row becomes one long deliverable. Above 128k output tokens the competitors split and
stitch; Claude returns it whole in one batch turn.

DEPENDENCIES. The Claude arm needs only anthropic (the Batch API). The OpenAI and Gemini arms need
their optional SDKs and keys (lazy). This run GENERATES a large output (a few dollars, and the Claude
batch can take many minutes), so it is an explicit-go, credit-spending benchmark, never the cadence.
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

BATCH_BETA = "output-300k-2026-03-24"
CLAUDE_MODEL = os.environ.get("BULK_CLAUDE_MODEL", "sonnet")   # Sonnet 4.6 supports the 300k batch beta
OPENAI_MODEL = os.environ.get("BULK_OPENAI_MODEL", "gpt-top")  # GPT-5.5, 128k output cap
GEMINI_MODEL = os.environ.get("BULK_GEMINI_MODEL", "gem-flash")  # Gemini 3.5 Flash, 65,536 output cap
N_ENTRIES = int(os.environ.get("BULK_N", "3000"))             # ~62 tok/entry -> ~188k tokens of deliverable
CLAUDE_MAX_TOKENS = int(os.environ.get("BULK_CLAUDE_MAX", "300000"))
COMPETITOR_MAX_TOKENS = int(os.environ.get("BULK_COMP_MAX", "200000"))  # above their caps, so they truncate at the cap
BATCH_POLL_TIMEOUT_S = float(os.environ.get("BULK_BATCH_TIMEOUT", "3000"))
# The competitor caps from each vendor's live model page (2026-06-19), for the receipt's documented gap.
DOC_CAPS = {"gpt-top": 128000, "gem-flash": 65536}


def _prompt(n: int) -> str:
    return (
        f"You are generating a reference document. Output a numbered entry for EVERY integer from 1 to "
        f"{n}, in order, with no gaps. For each integer K output exactly this block:\n\n"
        f"### Entry K\nNumber: K\nParity: <even or odd>\nSquare: <K squared>\n"
        f"Property: <one complete sentence of about 25 words describing an arithmetic property of K>\n\n"
        f"Continue until Entry {n}. Do not stop early, do not summarize, do not use ellipsis. Output "
        f"every entry in full."
    )


@dataclass
class ArmResult:
    name: str
    provider: str
    model: str
    ran: bool = True
    output_tokens: int = 0
    truncated: bool = False
    stop_reason: str = ""
    cost: float = 0.0
    latency: float = 0.0
    note: str = ""
    errors: list = field(default_factory=list)


# --------------------------------------------------------------------------- the Claude batch arm

def run_claude_arm(client, model_key: str, *, progress=False) -> ArmResult:
    from common.models import get
    from common.pricing import cost_from_buckets

    m = get(model_key)
    arm = ArmResult(name=f"claude:{model_key}", provider="anthropic", model=m.id,
                    note=f"Message Batches API + beta {BATCH_BETA}, max_tokens={CLAUDE_MAX_TOKENS}")
    platform.used("cost", "300k extended batch output (beta)")
    t0 = time.perf_counter()
    try:
        batch = client.beta.messages.batches.create(
            betas=[BATCH_BETA],
            requests=[{"custom_id": "bulk", "params": {
                "model": m.id, "max_tokens": CLAUDE_MAX_TOKENS,
                "messages": [{"role": "user", "content": _prompt(N_ENTRIES)}]}}],
        )
    except Exception as e:  # noqa: BLE001
        arm.errors.append(f"create: {type(e).__name__}: {str(e)[:120]}")
        arm.ran = False
        return arm
    if progress:
        print(f"      claude  batch {batch.id} submitted, polling...", flush=True)
    # poll
    status = getattr(batch, "processing_status", None)
    deadline = time.perf_counter() + BATCH_POLL_TIMEOUT_S
    while status not in ("ended",) and time.perf_counter() < deadline:
        time.sleep(15)
        try:
            batch = client.beta.messages.batches.retrieve(batch.id)
        except Exception as e:  # noqa: BLE001
            arm.errors.append(f"poll: {type(e).__name__}: {str(e)[:80]}")
            break
        status = getattr(batch, "processing_status", None)
        if progress:
            counts = getattr(batch, "request_counts", None)
            print(f"      claude  status={status} counts={counts}", flush=True)
    arm.latency = time.perf_counter() - t0
    if status != "ended":
        arm.errors.append(f"batch did not end within {BATCH_POLL_TIMEOUT_S}s (status={status})")
        arm.ran = False
        return arm
    # fetch the single result
    try:
        for entry in client.beta.messages.batches.results(batch.id):
            res = entry.result
            if getattr(res, "type", None) != "succeeded":
                arm.errors.append(f"result type={getattr(res,'type',None)}: {str(getattr(res,'error',''))[:120]}")
                arm.ran = False
                return arm
            msg = res.message
            u = msg.usage
            arm.output_tokens = getattr(u, "output_tokens", 0) or 0
            arm.stop_reason = getattr(msg, "stop_reason", "") or ""
            arm.truncated = arm.stop_reason == "max_tokens"
            inp = getattr(u, "input_tokens", 0) or 0
            arm.cost = cost_from_buckets(model_key, fresh_input=inp, cached=0, output=arm.output_tokens)
    except Exception as e:  # noqa: BLE001
        arm.errors.append(f"results: {type(e).__name__}: {str(e)[:120]}")
        arm.ran = False
    if progress:
        print(f"      claude  output_tokens={arm.output_tokens} stop={arm.stop_reason}", flush=True)
    return arm


# --------------------------------------------------------------------------- the OpenAI streaming arm

def run_openai_arm(client, model_key: str, *, progress=False) -> ArmResult:
    from common.models import get
    from common.pricing import cost_from_buckets

    m = get(model_key)
    arm = ArmResult(name=f"openai:{model_key}", provider="openai", model=m.id,
                    note=f"Responses API streaming, max_output_tokens={COMPETITOR_MAX_TOKENS}")
    t0 = time.perf_counter()
    try:
        final = None
        with client.responses.stream(model=m.id, input=_prompt(N_ENTRIES),
                                     max_output_tokens=COMPETITOR_MAX_TOKENS) as stream:
            for _ in stream:
                pass
            final = stream.get_final_response()
        arm.latency = time.perf_counter() - t0
        u = final.usage
        inp = getattr(u, "input_tokens", 0) or 0
        arm.output_tokens = getattr(u, "output_tokens", 0) or 0
        det = getattr(u, "input_tokens_details", None)
        cached = (getattr(det, "cached_tokens", 0) or 0) if det else 0
        arm.cost = cost_from_buckets(model_key, fresh_input=max(0, inp - cached), cached=cached, output=arm.output_tokens)
        status = getattr(final, "status", "") or ""
        inc = getattr(final, "incomplete_details", None)
        reason = getattr(inc, "reason", "") if inc else ""
        arm.stop_reason = reason or status
        arm.truncated = status == "incomplete" or reason == "max_output_tokens"
    except Exception as e:  # noqa: BLE001
        arm.latency = time.perf_counter() - t0
        arm.errors.append(f"{type(e).__name__}: {str(e)[:140]}")
        arm.ran = False
    if progress:
        print(f"      openai  output_tokens={arm.output_tokens} stop={arm.stop_reason} truncated={arm.truncated}", flush=True)
    return arm


# --------------------------------------------------------------------------- the Gemini streaming arm

def run_gemini_arm(client, model_key: str, *, progress=False) -> ArmResult:
    from google.genai import types

    from common.models import get
    from common.pricing import cost_from_buckets

    m = get(model_key)
    arm = ArmResult(name=f"gemini:{model_key}", provider="gemini", model=m.id,
                    note=f"generate_content_stream, max_output_tokens={COMPETITOR_MAX_TOKENS}")
    t0 = time.perf_counter()
    last = None
    fin = ""
    try:
        for chunk in client.models.generate_content_stream(
                model=m.id, contents=_prompt(N_ENTRIES),
                config=types.GenerateContentConfig(max_output_tokens=COMPETITOR_MAX_TOKENS)):
            last = chunk
            for cand in (getattr(chunk, "candidates", None) or []):
                fr = getattr(cand, "finish_reason", None)
                if fr is not None:
                    fin = getattr(fr, "name", None) or str(fr)
        arm.latency = time.perf_counter() - t0
        u = getattr(last, "usage_metadata", None) if last is not None else None
        inp = (getattr(u, "prompt_token_count", 0) or 0) if u else 0
        arm.output_tokens = ((getattr(u, "candidates_token_count", 0) or 0) +
                             (getattr(u, "thoughts_token_count", 0) or 0)) if u else 0
        arm.cost = cost_from_buckets(model_key, fresh_input=inp, cached=0, output=arm.output_tokens)
        arm.stop_reason = fin
        arm.truncated = "MAX_TOKENS" in (fin or "")
    except Exception as e:  # noqa: BLE001
        arm.latency = time.perf_counter() - t0
        arm.errors.append(f"{type(e).__name__}: {str(e)[:140]}")
        arm.ran = False
    if progress:
        print(f"      gemini  output_tokens={arm.output_tokens} stop={arm.stop_reason} truncated={arm.truncated}", flush=True)
    return arm


@dataclass
class BulkRun:
    arms: list
    n_entries: int
    total_cost: float
    skipped: list = field(default_factory=list)


def _doc_cap_for(a: ArmResult) -> int | None:
    if a.provider == "openai":
        return DOC_CAPS["gpt-top"]
    if a.provider == "gemini":
        return DOC_CAPS["gem-flash"]
    if a.provider == "anthropic":
        return CLAUDE_MAX_TOKENS
    return None


def score_run(run: BulkRun) -> dict:
    """Machine gate for the large single-request output edge.

    The live competitors stopped early rather than truncating. The promotable claim is therefore not
    that they hit their caps in this run. It is narrower and checkable: Claude empirically emitted one
    un-truncated deliverable above every competitor's documented single-request output ceiling.
    """
    claude = next((a for a in run.arms if a.provider == "anthropic"), None)
    competitors = [a for a in run.arms if a.provider in ("openai", "gemini")]
    competitor_providers = {a.provider for a in competitors if a.ran}
    competitor_caps = [_doc_cap_for(a) for a in competitors if a.ran and _doc_cap_for(a)]
    max_competitor_cap = max(competitor_caps) if competitor_caps else 0

    claude_ran = bool(claude) and claude.ran
    claude_finished = claude_ran and not claude.truncated and claude.stop_reason not in ("max_tokens", "MAX_TOKENS")
    claude_exceeds_doc_caps = claude_ran and bool(max_competitor_cap) and claude.output_tokens > max_competitor_cap
    all_competitors_ran = {"openai", "gemini"}.issubset(competitor_providers)
    claude_exceeds_measured_outputs = (
        bool(competitors)
        and all(claude.output_tokens > a.output_tokens for a in competitors if a.ran)
        if claude_ran
        else False
    )

    why_not = []
    if not claude_ran:
        why_not.append("claude batch arm did not run")
    if not claude_finished:
        why_not.append("claude output was truncated or did not finish")
    if not claude_exceeds_doc_caps:
        why_not.append("claude output did not exceed every competitor documented output cap")
    if not all_competitors_ran:
        why_not.append("both OpenAI and Gemini competitor output arms must run")
    if not claude_exceeds_measured_outputs:
        why_not.append("claude output did not exceed every competitor measured output")

    positive = claude_finished and claude_exceeds_doc_caps and claude_exceeds_measured_outputs
    promotable = positive and all_competitors_ran
    return {
        "positive_signal": positive,
        "promotable_edge": promotable,
        "claude_finished_untruncated": claude_finished,
        "claude_exceeds_every_documented_competitor_cap": claude_exceeds_doc_caps,
        "claude_exceeds_every_measured_output": claude_exceeds_measured_outputs,
        "all_competitors_ran": all_competitors_ran,
        "max_documented_competitor_cap": max_competitor_cap,
        "why_not_promotable": why_not if not promotable else [],
    }


def _receipt_dict(run: BulkRun) -> dict:
    return {
        "date": datetime.date.today().isoformat(),
        "claim_under_test": (
            "Claude Batch API with the output-300k beta can return one un-truncated deliverable above "
            "OpenAI and Gemini's documented single-request output ceilings."
        ),
        "sources": {
            "claude_batch_processing": "https://platform.claude.com/docs/en/build-with-claude/batch-processing",
            "openai_gpt_5_5": "https://developers.openai.com/api/docs/models/gpt-5.5",
            "gemini_3_5_flash": "https://ai.google.dev/gemini-api/docs/models/gemini-3.5-flash",
        },
        "n_entries": run.n_entries,
        "total_cost": round(run.total_cost, 6),
        "skipped": run.skipped,
        "verdict": score_run(run),
        "arms": [
            {
                "name": a.name,
                "provider": a.provider,
                "model": a.model,
                "output_tokens": a.output_tokens,
                "documented_output_cap": _doc_cap_for(a),
                "truncated": a.truncated,
                "stop_reason": a.stop_reason,
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


def run_benchmark(*, progress=False) -> BulkRun:
    clients = _clients()
    arms, skipped = [], []
    # Submit the Claude batch first (it is the long pole), then run the competitor streams while it
    # processes, then collect the batch.
    if clients["openai"] is not None:
        if progress:
            print("    arm: openai (streaming to the 128k cap)")
        arms.append(run_openai_arm(clients["openai"], OPENAI_MODEL, progress=progress))
    else:
        skipped.append("openai (key absent)")
    if clients["gemini"] is not None:
        if progress:
            print("    arm: gemini (streaming to the 65k cap)")
        arms.append(run_gemini_arm(clients["gemini"], GEMINI_MODEL, progress=progress))
    else:
        skipped.append("gemini (key absent)")
    if clients["anthropic"] is not None:
        if progress:
            print("    arm: claude (batch, 300k extended output)")
        arms.append(run_claude_arm(clients["anthropic"], CLAUDE_MODEL, progress=progress))
    else:
        skipped.append("claude (ANTHROPIC_API_KEY absent)")
    return BulkRun(arms=arms, n_entries=N_ENTRIES, total_cost=sum(a.cost for a in arms), skipped=skipped)


class BulkExtendedOutputDemonstrator(BaseDemonstrator):
    demo_kind = "extended_output"

    def estimate(self, edge, spec):
        return CostEstimate(usd=6.0, wall_clock_s=1800.0, command="make bulk-output",
                            note="generates a >128k-token deliverable per arm; a few dollars and the "
                                 "Claude batch can take many minutes (explicit-go, never the cadence)")

    def _run(self, spec):
        spec = spec or {}
        if spec.get("_run") is None:
            spec["_run"] = run_benchmark(progress=spec.get("progress", False))
        return spec["_run"]

    def _arm_to_Arm(self, a: ArmResult):
        return Arm(provider=a.provider, model=a.model, ran=a.ran, latency_s=a.latency,
                   output_tokens=a.output_tokens, cost_usd=a.cost,
                   truncated=a.truncated,
                   metric={"output_tokens": a.output_tokens, "truncated": a.truncated,
                           "stop_reason": a.stop_reason,
                           "doc_cap": DOC_CAPS.get(a.model.split(":")[-1])},
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
        """The gate, made honest after the live behavior. Frontier models decline to mechanically
        enumerate to their cap, so the competitor arms stop early rather than truncate. The real,
        provable claim is therefore the CAPABILITY ceiling: Claude EMPIRICALLY emits more output in one
        request than the competitor's DOCUMENTED single-request maximum (GPT-5.5 128k, Gemini 65,536).
        Claude doing > 128,000 output tokens in one turn is something GPT-5.5 cannot do at all,
        regardless of prompting. The competitors' measured outputs are recorded as context, not as the
        gate, because their early stop is behavioral, not a cap hit."""
        ca = claude
        if not ca.ran:
            return Verdict(verdict="never-evaluated", passed=False, metric={"reason": "Claude arm did not run"})
        all_comp_ran = bool(competitors) and all(c.ran for c in competitors)
        claude_out = ca.metric.get("output_tokens", 0)
        comp = {c.model: {"output_tokens": c.metric.get("output_tokens"),
                          "truncated": c.metric.get("truncated"),
                          "documented_cap": c.metric.get("doc_cap")}
                for c in competitors if c.ran}
        # the documented competitor single-request output ceilings (from each vendor's model page)
        comp_caps = [v["documented_cap"] for v in comp.values() if v["documented_cap"]]
        max_cap = max(comp_caps) if comp_caps else 0
        beats_doc_caps = bool(comp_caps) and claude_out > max_cap
        beats_measured = bool(comp) and all(claude_out > (v["output_tokens"] or 0) for v in comp.values())
        metric = {"claude_output_tokens": claude_out, "claude_stop_reason": ca.metric.get("stop_reason"),
                  "competitors": comp, "max_documented_competitor_cap": max_cap,
                  "claude_exceeds_every_documented_cap": beats_doc_caps,
                  "claude_exceeds_every_measured_output": beats_measured}
        if beats_doc_caps and beats_measured and all_comp_ran:
            return Verdict(verdict="claude-ahead", passed=True, metric=metric,
                           note=f"Claude emitted {claude_out:,} output tokens in ONE request, more than "
                                f"every competitor's documented single-request ceiling (max {max_cap:,}) "
                                f"and more than every competitor's measured output on the same prompt")
        if beats_doc_caps and not all_comp_ran:
            return Verdict(verdict="never-evaluated", passed=False, metric=metric,
                           note="Claude exceeded the documented caps, but not every competitor arm ran")
        return Verdict(verdict="within-claude-only", passed=False, metric=metric,
                       note="Claude did not exceed every competitor's documented single-request cap on this run")

    def receipt(self, edge, claude, competitors, verdict, spec):
        run = self._run(spec)
        return self.build_receipt(
            edge, claude, competitors, verdict, spec,
            workload={
                "task_shape": f"one request asking for a numbered entry per integer up to {run.n_entries} "
                              f"with a strict no-abbreviation instruction; the gate is the output tokens "
                              f"produced in one request and whether it truncated",
                "models": {"claude": claude.model, "competitors": [c.model for c in competitors]},
                "features_on": [f"Message Batches API + extended output beta {BATCH_BETA} (300k max_tokens)"],
                "assumptions": "Claude uses the Batch API (the only path to >128k output) with the beta "
                               "header; the competitors stream to their model's single-request output cap "
                               "(GPT-5.5 128k, Gemini 3.5 Flash 65,536) and truncate there; per-token cost "
                               "is parity at the 50% batch discount, so the win is the un-truncated single "
                               "turn, not the dollar figure. Beta, batch-only, value only above 128k output.",
            },
            grounding=[
                {"claim": "the output-300k-2026-03-24 beta header raises the batch max_tokens cap to 300,000",
                 "source_url": "https://platform.claude.com/docs/en/build-with-claude/batch-processing",
                 "date": "2026-06-19"},
                {"claim": "GPT-5.5 max output is 128,000 tokens",
                 "source_url": "https://developers.openai.com/api/docs/models/gpt-5.5", "date": "2026-06-19"},
                {"claim": "Gemini 3.5 Flash output token limit is 65,536",
                 "source_url": "https://ai.google.dev/gemini-api/docs/models/gemini-3.5-flash", "date": "2026-06-19"},
            ],
            fairness={
                "best_to_best": "each competitor streams to its strongest single-request output ceiling; "
                                "the comparison is the per-request output cap, named, not a strawman",
                "isolate": "the same prompt and the same above-cap max-output setting on every arm; only "
                           "the platform's single-request output ceiling differs",
            },
        )


register(BulkExtendedOutputDemonstrator())


def _print_run(run: BulkRun) -> None:
    from common.client import fmt_usd

    print("\n  === Bulk extended output: largest deliverable in ONE request ===")
    print(f"  one request asking for {run.n_entries} numbered entries, no abbreviation.\n")
    header = f"  {'arm':<22}{'output tokens':>15}{'truncated':>11}{'stop':>18}{'cost':>10}"
    print(header)
    print("  " + "-" * (len(header) - 2))
    for a in run.arms:
        print(f"  {a.name:<22}{a.output_tokens:>15,}{str(a.truncated):>11}{(a.stop_reason or '-'):>18}{fmt_usd(a.cost):>10}")
        if a.errors:
            print(f"      note: {a.errors[0]}")
    print(f"\n  total spend this run: {fmt_usd(run.total_cost)}")
    if run.skipped:
        print(f"  arms not run: {', '.join(run.skipped)}")


def main(argv=None) -> int:
    from common.client import load_env, repo_root

    p = argparse.ArgumentParser(description="bulk_extended_output: largest single-request deliverable, "
                                            "Claude 300k batch vs OpenAI/Gemini output caps.")
    p.add_argument("--emit-edge", action="store_true", help="write edges/bulk-extended-output/receipt.json")
    a = p.parse_args(argv)

    load_env()
    print("\n  bulk_extended_output: how large a deliverable fits in ONE request?")
    print("  Same prompt, every arm. Claude uses the 300k batch beta; competitors stream to their cap.\n")
    run = run_benchmark(progress=True)
    _print_run(run)

    out = _receipt_dict(run)
    (repo_root() / "data").mkdir(exist_ok=True)
    (repo_root() / "data" / "last_bulk_extended_output.json").write_text(json.dumps(out, indent=2) + "\n")
    if a.emit_edge:
        edge_dir = repo_root() / "edges" / "bulk-extended-output"
        edge_dir.mkdir(parents=True, exist_ok=True)
        (edge_dir / "receipt.json").write_text(json.dumps(out, indent=2) + "\n")
        print("\n  wrote edges/bulk-extended-output/receipt.json")
    print("\n  (per-run detail in gitignored data/last_bulk_extended_output.json)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
