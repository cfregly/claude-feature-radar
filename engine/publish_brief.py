"""publish_brief: turn a VERIFIED Claude-win edge into a self-contained public brief, offline, for $0.

This is the one-source-of-truth fix for the drift between this engine and the public claude-feature-hits
repo. The engine holds the committed truth (the swept landscape, the per-edge demonstrator, the measured
receipt). A hand-edited public brief drifts from that truth the moment a number, a model id, or a verdict
moves here and nobody copies it across. So we generate the public brief FROM the engine's own committed
truth instead of hand-maintaining a second copy: the verdict gate reads landscape/landscape.json and the
data/last_<edge>.json receipt, the code is vendored verbatim from the engine modules, and a PROVENANCE
stamp records exactly which engine state produced it.

THE VERDICT GATE is the load-bearing safety property, and it is fail-closed. We refuse to publish unless
the edge is a clean, measured, non-regime-bounded Claude win, read off the engine's committed records:

  1. The landscape edge must carry verdict == "claude-ahead" AND lead_score > 0. On a fresh checkout with
     no landscape.json we fall back to scan.DIFFERENTIATORS, the committed seed leads (those are exactly
     the claude-ahead, ranked differentiators that survived the skeptic and the parity check).
  2. If a receipt data/last_<edge>.json exists, it must ALSO indicate a Claude win (a truthy
     verdict/passed/mode_b_correct). A receipt that disagrees with the landscape VETOES the publish: a
     stale or failing measurement must never ship under a green landscape verdict.
  3. The edge must not be regime-bounded. A cost-model edge wins only in a price regime that can flip on
     the next vendor price change, so its fair_comparison.lead_basis is never a stable, head-to-head /
     absence-of-evidence / within-claude-only basis. We refuse any edge whose lead_basis is not one of
     those three (which refuses doc-grounded-parity and any held basis), AND we refuse the cost-model key
     explicitly, so a future mislabeled cost edge can never slip through.

On refusal we print the edge key, the verdict we read, and the source, exit non-zero, and WRITE NOTHING
(no partial directory). The net effect, verified by tests/test_publish_brief.py and the proof runs:
programmatic-tool-calling and citations PUBLISH; eval-quality, retention-resume, cost-model, and
parity-gated all REFUSE.

Nothing here imports anthropic, openai, or google. It reads JSON and files and copies bytes, so it
imports with `anthropic` alone (in fact with no SDK at all) and runs offline, with no key and no spend.
No model call, no git, no send. The generated brief's run.py imports anthropic lazily, the same way the
engine's own demo does, so the published brief stays one-dependency.
"""

from __future__ import annotations

import argparse
import json
import pathlib
import re
import subprocess
import sys
from dataclasses import dataclass
from datetime import date

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from engine import scan  # noqa: E402  committed seed + landscape reader, anthropic-free
from engine.adversarial import VALUE_LEAD_BASES, receipt_value_positive, value_confirmed  # noqa: E402
from engine.demokinds import PRIVATE_ONLY_DEMOKINDS, demokind_for  # noqa: E402
from engine.public_hits import PublicHitsPublishError, copy_artifact  # noqa: E402

# The lead_basis values that are NOT regime-bounded: a stable head-to-head win, a documented
# absence-of-evidence lead, or a within-Claude value-add. doc-grounded-parity is a parity, not a lead,
# and a cost-model lead is a price-regime lead that flips on the next price change, so neither is here.
PUBLISHABLE_LEAD_BASES = tuple(sorted(VALUE_LEAD_BASES))

# Keys we refuse outright regardless of how their lead_basis is labeled. cost-model is regime-bounded by
# construction (it wins only in one price regime), so it never publishes even if a record mislabels it.
REGIME_BOUNDED_KEYS = {"cost-model", "cost_model", "cost"}


# --------------------------------------------------------------------------- the per-edge vendor plan
#
# Each publishable edge declares, statically, the engine files its brief needs and how the brief lays
# them out, so the generated brief runs with one dependency (anthropic), exactly like the existing
# public programmatic_tool_calling and citations briefs. The copier flattens common/ into a local common/ package and rewrites
# import lines by a DETERMINISTIC PREFIX SWAP only (no semantic rewrite):
#
#   from common.X import                          ->  from .common.X import
#
# After the swap, every vendored file must import only from the declared closure (stdlib, anthropic, or a
# sibling in the brief). If a vendored file imports anything outside that closure, we REFUSE: a shipped
# brief must never carry a dangling `from engine.` or non-dot `from common.` import.


@dataclass(frozen=True)
class VendorFile:
    """One file copied into the brief. ``src`` is relative to the engine repo root, ``dst`` is relative
    to the brief dir. ``run_entry`` marks the file the make target runs (`python -m <slug>.<stem>`)."""
    src: str
    dst: str
    run_entry: bool = False


@dataclass(frozen=True)
class BriefPlan:
    """The static publish plan for one edge: its public slug, the demoKind, the doc URL the public brief
    points at, the vendored files, and the make-target help line. ``edit_surface`` is the file or
    directory a forker edits, surfaced in the README run-it-on-your-own-data section when present."""
    slug: str
    title: str
    demo_kind: str
    doc_url: str
    files: tuple[VendorFile, ...]
    make_help: str
    edit_surface: str | None = None
    run_module: str | None = None
    public_bundle: bool = False
    # Data-driven briefs: when from_assets is True, the brief's README.md, run.py, sample.txt, and
    # email.md are read from engine/brief_assets/<slug>/ instead of a per-slug generator function, so a
    # new edge is content, not code. headline is the demo.tape headline line, index_blurb the root README
    # one-liner. The asset files may use {slug}, {title}, {doc_url} placeholders, substituted on assembly.
    from_assets: bool = False
    headline: str = ""
    index_blurb: str = ""
    # head_to_head briefs carry a real, measured competitor arm, so they vendor common/compare_clients.py
    # and a compare.py the gate option runs (OpenAI + Gemini on the same workload). The capability-gap
    # briefs (programmatic_tool_calling, citations, cache_diagnostics, task_budgets) have no head-to-head
    # number and stay Claude-only: no compare arm, no competitor table.
    head_to_head: bool = False


PLANS: dict[str, BriefPlan] = {
    "programmatic-tool-calling": BriefPlan(
        slug="programmatic_tool_calling",
        title="programmatic tool calling",
        demo_kind="token_accounting",
        doc_url="https://platform.claude.com/docs/en/agents-and-tools/tool-use/programmatic-tool-calling",
        files=(),
        make_help="build .venv, install anthropic, run the customer-evidence programmatic tool calling comparison (~$0.08)",
        edit_surface="founder_workload.py",
        run_module="compare_direct_vs_programmatic",
        public_bundle=True,
        index_blurb=("Find three at-risk customer accounts from five raw evidence sources while keeping "
                     "the raw rows out of model context."),
    ),
    # citations: the verifiable-source-pointer edge. The brief needs only the anthropic-free
    # client/models/pricing trio (flattened to a local common/). The run entry is a generated cite.py:
    # the demonstrator's Claude Citations arm (the in-API char_location pointer, resolved and asserted)
    # plus a --check self-test, with the DIY/competitor arms stripped. The edit surface is the docs/
    # corpus a forker replaces with their own .txt files.
    "citations": BriefPlan(
        slug="citations",
        title="verifiable source citations",
        demo_kind="grounding_resolution",
        doc_url="https://platform.claude.com/docs/en/build-with-claude/citations",
        files=(
            VendorFile("common/client.py", "common/client.py"),
            VendorFile("common/models.py", "common/models.py"),
            VendorFile("common/pricing.py", "common/pricing.py"),
        ),
        make_help="build .venv, install anthropic, answer questions over your docs with citations (~$0.01)",
        edit_surface="docs",  # the corpus folder a forker fills with their own .txt files
    ),
    # code-execution-state: the stateful-sandbox edge. A multi-step agent that runs code needs its sandbox to
    # keep files and state across turns. The brief needs only the anthropic-free client/models/pricing
    # trio (flattened to a local common/). The run entry is a generated run.py: write a unique value to
    # /tmp/state.txt in a fresh container, capture container.id, then read it back from the REUSED
    # container on a separate request, plus a --check self-test. Claude-only, wins-only, no competitor arm
    # on the public surface. The slug is underscored so `python -m code_execution_state.run` imports cleanly.
    "code-execution-state": BriefPlan(
        slug="code_execution_state",
        head_to_head=True,
        title="code execution state",
        demo_kind="retention_resume",
        doc_url="https://platform.claude.com/docs/en/agents-and-tools/tool-use/code-execution-tool",
        files=(
            VendorFile("common/client.py", "common/client.py"),
            VendorFile("common/models.py", "common/models.py"),
            VendorFile("common/pricing.py", "common/pricing.py"),
        ),
        make_help="build .venv, install anthropic, write a file in your agent's sandbox and read it back from the reused container (~$0.05)",
        edit_surface=None,  # no single edit surface: the README explains adapting the workload
    ),
    "pdf-citations": BriefPlan(
        slug="pdf_citations",
        head_to_head=True,
        title='PDF citations',
        demo_kind="pdf_grounding",
        doc_url="https://platform.claude.com/docs/en/build-with-claude/citations",
        files=(
            VendorFile("common/client.py", "common/client.py"),
            VendorFile("common/models.py", "common/models.py"),
            VendorFile("common/pricing.py", "common/pricing.py"),
        ),
        make_help='build .venv, install anthropic, answer questions over a directly-supplied PDF and get a correct-page pointer for each answer (~$0.05)',
        from_assets=True,
        headline="# Deep-link every answer to the exact page of a user's PDF with Claude Citations",
        index_blurb='Answer questions over a directly-supplied PDF and get a verifiable page_location pointer (page number plus the quoted source text) for every answer, with zero resolver code.',
    ),
    "search-results": BriefPlan(
        slug="search_results",
        head_to_head=True,
        title='Inline RAG citations',
        demo_kind="byo_rag_grounding",
        doc_url="https://platform.claude.com/docs/en/build-with-claude/search-results",
        files=(
            VendorFile("common/client.py", "common/client.py"),
            VendorFile("common/models.py", "common/models.py"),
            VendorFile("common/pricing.py", "common/pricing.py"),
        ),
        make_help='search_results  Cite your own RAG chunks inline, resolver-free, with search_result blocks (~$0.05)',
        from_assets=True,
        headline='# Cite your own RAG chunks inline with Claude search_result content blocks',
        index_blurb='Cite the chunks your own retriever returned, inline and resolver-free, with a search_result_location block-span pointer and no hosted vector store.',
    ),
    "grounding-stack": BriefPlan(
        slug="grounding_stack",
        head_to_head=True,
        title='Grounding stack (text + PDF + RAG cited in one request)',
        demo_kind="grounding_stack",
        doc_url="https://platform.claude.com/docs/en/build-with-claude/citations",
        files=(
            VendorFile("common/client.py", "common/client.py"),
            VendorFile("common/models.py", "common/models.py"),
            VendorFile("common/pricing.py", "common/pricing.py"),
        ),
        make_help='grounding_stack  Cite text + PDF + RAG chunk in one request, one typed pointer each (~$0.01)',
        from_assets=True,
        headline='# Cite a text doc, a PDF, and a RAG chunk in one request with Claude Citations',
        index_blurb='Cite a plain-text note, a directly-supplied PDF, and a RAG chunk in one Claude request, each with its own typed pointer (char, page, search_result) and no vector store.',
    ),
    "web-citations": BriefPlan(
        slug="web_citations",
        head_to_head=True,
        title='Web search citations',
        demo_kind="web_grounding",
        doc_url="https://platform.claude.com/docs/en/agents-and-tools/tool-use/web-search-tool",
        files=(
            VendorFile("common/client.py", "common/client.py"),
            VendorFile("common/models.py", "common/models.py"),
            VendorFile("common/pricing.py", "common/pricing.py"),
        ),
        make_help='web_citations  Run the web-citation fidelity workload: every web claim comes back with the verbatim source quote (~$0.12)',
        from_assets=True,
        headline="# Verifiable web answers with Claude's web search citations",
        index_blurb="Claude's web search tool returns each web-grounded claim with the verbatim source quote attached, so a reader verifies the exact sentence in seconds instead of re-fetching the page.",
    ),
    "bulk-extended-output": BriefPlan(
        slug="bulk_output",
        head_to_head=True,
        title='Extended output',
        demo_kind="extended_output",
        doc_url="https://platform.claude.com/docs/en/build-with-claude/batch-processing",
        files=(
            VendorFile("common/client.py", "common/client.py"),
            VendorFile("common/models.py", "common/models.py"),
            VendorFile("common/pricing.py", "common/pricing.py"),
        ),
        make_help='bulk_output  the largest deliverable in one request with Claude extended output, live check (~$0.20)',
        from_assets=True,
        headline='# The largest deliverable in one request, with Claude extended output',
        index_blurb='One un-truncated deliverable per request above 128k output tokens, via the Message Batches API with the output-300k-2026-03-24 extended-output beta.',
    ),
    "exact-list-ledger": BriefPlan(
        slug="exact_ledger",
        head_to_head=True,
        title='Exact-list ledger',
        demo_kind="token_accounting",
        doc_url="https://platform.claude.com/docs/en/build-with-claude/context-editing",
        files=(
            VendorFile("common/client.py", "common/client.py"),
            VendorFile("common/models.py", "common/models.py"),
            VendorFile("common/pricing.py", "common/pricing.py"),
        ),
        make_help='build .venv, install anthropic, run the long-stream exact-list ledger agent with context editing and assert the win (~$0.17)',
        from_assets=True,
        headline='# Keep an exact running list across a long agent, with Claude context editing',
        index_blurb='A long tool-heavy agent keeps an exact running list while Claude context editing clears the bulky tool results in place, holding carried context flat and the bill down.',
    ),
    "cache-diagnostics": BriefPlan(
        slug="cache_diagnostics",
        title='Cache diagnostics',
        demo_kind="other",
        doc_url="https://platform.claude.com/docs/en/build-with-claude/cache-diagnostics",
        files=(
            VendorFile("common/client.py", "common/client.py"),
            VendorFile("common/models.py", "common/models.py"),
            VendorFile("common/pricing.py", "common/pricing.py"),
        ),
        make_help='cache_diagnostics  Name the silent prompt-cache-miss cause with a typed reason (~$0.02)',
        from_assets=True,
        headline='# Know why your prompt cache missed with Claude cache diagnostics',
        index_blurb='Claude cache diagnostics names the exact prefix surface that broke a prompt-cache hit (model, system, tools, or messages), turning a blind cache-miss hunt into a one-line typed answer.',
    ),
    "task-budgets": BriefPlan(
        slug="task_budgets",
        title='Task budgets',
        demo_kind="other",
        doc_url="https://platform.claude.com/docs/en/build-with-claude/task-budgets",
        files=(
            VendorFile("common/client.py", "common/client.py"),
            VendorFile("common/models.py", "common/models.py"),
            VendorFile("common/pricing.py", "common/pricing.py"),
        ),
        make_help='task_budgets   stop a budget-exhausted agent before the next tool call (~$0.01)',
        from_assets=True,
        headline='# Stop a budget-blown agent before it burns the next tool call, with Claude task budgets',
        index_blurb="Claude's task_budget gives an agent a server-side countdown for the whole loop, so it hands off cleanly before starting a tool call it cannot pay for.",
    ),
}

def _plan_for(edge_key: str) -> BriefPlan | None:
    return PLANS.get(edge_key)


# --------------------------------------------------------------------------- reading the committed truth


def _landscape_edges() -> tuple[list[dict], str]:
    """Every edge record the gate reads, plus a human label for where it came from. Reads the swept
    landscape/landscape.json when present, falls back to the committed scan.DIFFERENTIATORS seed leads on
    a fresh checkout. The seed leads are the claude-ahead, ranked differentiators, so on a fresh checkout
    the gate sees exactly the records a swept landscape would expose as leads."""
    f = ROOT / "landscape" / "landscape.json"
    if f.exists():
        try:
            land = json.loads(f.read_text())
            edges = land.get("edges", [])
            merged = scan.with_receipt_promoted_seed_edges(edges)
            suffix = " + receipt-promoted seeds" if len(merged) != len(edges) else ""
            return merged, f"landscape/landscape.json (as_of {land.get('as_of_date', '?')}){suffix}"
        except (json.JSONDecodeError, OSError):
            pass
    # Fresh checkout, or an unreadable landscape: the committed seed differentiators ARE the leads.
    return [scan.seed_edge_record(seed) for seed in scan.DIFFERENTIATORS], \
        "engine/scan.py DIFFERENTIATORS (committed seed, no landscape yet)"


def _find_edge(edge_key: str) -> tuple[dict | None, str]:
    """Find the edge record for a canonical edge key in the landscape or seed."""
    edges, src = _landscape_edges()
    wanted = {edge_key}
    plan = _plan_for(edge_key)
    if plan:
        wanted.add(plan.slug)
    for e in edges:
        if e.get("key") in wanted:
            return e, src
    return None, src


def _receipt_path(edge_key: str) -> pathlib.Path | None:
    """The data/last_<edge>.json receipt for this edge, if one is committed/present. Tries the edge key
    and the plan slug (the engine writes data/last_programmatic_tool_calling.json keyed on the short slug), returns the first
    that exists, else None. data/ is gitignored transient scratch, so a receipt is optional, but when it
    is present it gets a veto."""
    candidates = [edge_key]
    plan = _plan_for(edge_key)
    if plan:
        candidates.append(plan.slug)
    for key in candidates:
        p = ROOT / "data" / f"last_{key}.json"
        if p.exists():
            return p
    return None


def _receipt_is_claude_win(receipt: dict) -> bool:
    """Does the receipt indicate a Claude win? True when an explicit verdict says claude-ahead, OR a
    structured verdict marks promotable_edge, OR a passed/mode_b_correct flag is truthy. A receipt with
    an explicit non-win verdict, a promotable_edge of false, or a false passed/mode_b_correct, is NOT a
    win and vetoes the publish."""
    verdict = receipt.get("verdict")
    if isinstance(verdict, dict):
        # A structured verdict (the retention_resume demonstrator writes one): promotable_edge is the
        # win flag, with positive_signal as the fallback. A false flag still vetoes.
        if "promotable_edge" in verdict:
            return bool(verdict.get("promotable_edge"))
        if "positive_signal" in verdict:
            return bool(verdict.get("positive_signal"))
        return True
    if verdict is not None:
        return verdict == "claude-ahead"
    if "passed" in receipt:
        return bool(receipt.get("passed"))
    if "mode_b_correct" in receipt:
        return bool(receipt.get("mode_b_correct"))
    # No verdict signal in the receipt at all: it cannot disagree, so it does not veto.
    return True


def _committed_receipt(plan: BriefPlan) -> dict | None:
    """The SHIPPED numbers, parsed from the committed receipt-of-record edges/<folder>/sample.txt, the
    same file the receipt-drift gate (scripts/check_receipts.py) checks. This is the source of truth a
    published brief quotes, NOT the gitignored transient data/last_<edge>.json, which drifts to whatever
    the last local run happened to bill. So a republish keeps the brief's numbers identical to the
    committed receipt instead of following the latest scratch run. Returns None when no committed receipt
    exists yet (then the templates show 'run it yourself' with no fabricated number). token_accounting
    only: the grounding_resolution brief quotes no receipt numbers, so it never calls this."""
    folder = next((k for k, v in PLANS.items() if v is plan), plan.slug)
    s = ROOT / "edges" / folder / "sample.txt"
    if not s.exists():
        return None
    text = s.read_text()
    a = re.search(r"without programmatic tool calling\s+([\d,]+)", text)
    b = re.search(r"with programmatic tool calling\s+([\d,]+)", text)
    if not (a and b):
        a = re.search(r"Mode A:.*?([\d,]+)\s+\d+\s+(\S+)\s+\$[\d.]+", text)
        b = re.search(r"Mode B:.*?([\d,]+)\s+\d+\s+(\S+)\s+\$[\d.]+", text)
    if not (a and b):
        return None
    a_tok = int(a.group(1).replace(",", ""))
    b_tok = int(b.group(1).replace(",", ""))
    expected = re.search(r"Expected compact decision:\s*\n\s+([a-z0-9_,\s]+)", text)
    expected_answer = tuple(part.strip() for part in expected.group(1).split(",") if part.strip()) if expected else None
    return {
        "mode_a": {"billed_input": a_tok},
        "mode_b": {"billed_input": b_tok},
        "pct_input_reduction": round((1 - b_tok / a_tok) * 100, 2) if a_tok else 0.0,
        "expected_answer": expected_answer,
        "mode_a_correct": expected_answer is not None,
        "mode_b_correct": expected_answer is not None,
    }


def _committed_json_receipt(edge_key: str) -> dict | None:
    """Read a committed edges/<folder>/receipt.json when one exists."""
    plan = _plan_for(edge_key)
    folders = [edge_key, edge_key.replace("_", "-")]
    if plan:
        folders.extend(k for k, v in PLANS.items() if v is plan)
    for folder in dict.fromkeys(folders):
        p = ROOT / "edges" / folder / "receipt.json"
        if not p.exists():
            continue
        try:
            return json.loads(p.read_text())
        except (json.JSONDecodeError, OSError):
            return None
    return None


def _measurement_for_gate(edge_key: str, plan: BriefPlan, transient_receipt: dict | None) -> dict | None:
    """The measurement the value gate sees: transient receipt first, then committed JSON receipt, then
    the committed sample parser for older token-accounting briefs."""
    if transient_receipt and receipt_value_positive(transient_receipt):
        return transient_receipt
    return _committed_json_receipt(edge_key) or _committed_receipt(plan) or transient_receipt


def _adversarial_value_gate(edge: dict, measurement: dict | None):
    return value_confirmed(edge, measurement, require_receipt=True, require_adversarial=True)


# --------------------------------------------------------------------------- the verdict gate


@dataclass
class GateResult:
    ok: bool
    edge_key: str
    verdict: str
    lead_basis: str
    source: str
    reason: str
    edge: dict | None = None
    receipt_path: pathlib.Path | None = None
    receipt: dict | None = None


def verdict_gate(edge_key: str) -> GateResult:
    """The fail-closed gate. Returns ok=True only for a clean, measured, non-regime-bounded Claude win.

    Reads, in order: the landscape (or seed) edge record (verdict + lead_score + fair_comparison), the
    optional data/last_<edge>.json receipt, and the lead_basis. ANY failing check returns ok=False with
    a reason, and the caller writes nothing. Never raises on a missing edge: an unknown API key is a refusal,
    not a crash."""
    edge, source = _find_edge(edge_key)
    if edge is None:
        return GateResult(False, edge_key, "(no record)", "(none)", source,
                          f"no edge record for {edge_key!r} in {source}")

    verdict = edge.get("verdict", "(missing)")
    lead_score = edge.get("lead_score", edge.get("score", 0)) or 0
    fc = edge.get("fair_comparison") or {}
    lead_basis = fc.get("lead_basis", "(missing)")
    demo_kind = edge.get("demoKind") or edge.get("demo_kind") or demokind_for(edge.get("key", ""),
                                                                              edge.get("axis"))

    if demo_kind in PRIVATE_ONLY_DEMOKINDS:
        return GateResult(False, edge_key, verdict, lead_basis, source,
                          f"demoKind {demo_kind!r} is private-only and cannot publish", edge=edge)

    # 1) The landscape verdict must be a clean, ranked claude-ahead.
    if verdict != "claude-ahead":
        return GateResult(False, edge_key, verdict, lead_basis, source,
                          f"verdict is {verdict!r}, not 'claude-ahead'", edge=edge)
    if lead_score <= 0:
        return GateResult(False, edge_key, verdict, lead_basis, source,
                          f"lead_score is {lead_score}, not > 0 (a parity or held edge)", edge=edge)

    # 2) A regime-bounded edge never publishes: not the cost-model key, and not a lead_basis outside the
    #    publishable set (which refuses doc-grounded-parity and any held basis).
    if edge_key in REGIME_BOUNDED_KEYS or edge.get("key") in REGIME_BOUNDED_KEYS:
        return GateResult(False, edge_key, verdict, lead_basis, source,
                          "regime-bounded edge (cost-model): the lead flips on the next price change, "
                          "never a stable public win", edge=edge)
    if lead_basis not in PUBLISHABLE_LEAD_BASES:
        return GateResult(False, edge_key, verdict, lead_basis, source,
                          f"lead_basis is {lead_basis!r}, not one of {PUBLISHABLE_LEAD_BASES} "
                          "(regime-bounded or held); refused", edge=edge)

    # 3) A present receipt must AGREE that it is a Claude win, or it vetoes.
    rpath = _receipt_path(edge_key)
    receipt = None
    if rpath is not None:
        try:
            receipt = json.loads(rpath.read_text())
        except (json.JSONDecodeError, OSError) as exc:
            return GateResult(False, edge_key, verdict, lead_basis, source,
                              f"receipt {rpath.name} is present but unreadable ({exc}); refused fail-closed",
                              edge=edge, receipt_path=rpath)
        if not _receipt_is_claude_win(receipt):
            rv = receipt.get("verdict") or receipt.get("passed", receipt.get("mode_b_correct"))
            return GateResult(False, edge_key, verdict, lead_basis, source,
                              f"receipt {rpath.name} disagrees (verdict/passed={rv!r}); the receipt "
                              "vetoes the publish", edge=edge, receipt_path=rpath, receipt=receipt)

    # 4) A built brief plan must exist (we only publish edges we can vendor a runnable brief for).
    plan = _plan_for(edge_key)
    if plan is None:
        return GateResult(False, edge_key, verdict, lead_basis, source,
                          f"no vendor plan for {edge_key!r}: a runnable brief cannot be assembled yet",
                          edge=edge, receipt_path=rpath, receipt=receipt)

    # 5) The central value bar: measured value plus a clean adversarial overlay. A current KILLED
    #    verdict holds the edge even when old receipts still exist.
    measurement = _measurement_for_gate(edge_key, plan, receipt)
    value_gate = _adversarial_value_gate(edge, measurement)
    if not value_gate.ok:
        return GateResult(False, edge_key, verdict, lead_basis, source,
                          f"adversarial value gate failed: {value_gate.reason}",
                          edge=edge, receipt_path=rpath, receipt=receipt)

    return GateResult(True, edge_key, verdict, lead_basis, source,
                      "clean claude-ahead, ranked, non-regime-bounded, measured, adversarially confirmed",
                      edge=edge, receipt_path=rpath, receipt=receipt)


# --------------------------------------------------------------------------- vendoring (the import swap)

# The deterministic prefix swaps, applied to import lines only. A tuple of (pattern, replacement). The
# patterns are anchored at the start of a `from ... import` line so only an import is ever rewritten.
_IMPORT_SWAPS = (
    (re.compile(r"^from engine\.demonstrators\.([a-z_]+) import", re.MULTILINE), r"from .\1 import"),
    (re.compile(r"^from common\.([a-z_]+) import", re.MULTILINE), r"from .common.\1 import"),
    (re.compile(r"^import common\.([a-z_]+)", re.MULTILINE), r"from .common import \1"),
)

# After the swaps, any of these substrings remaining in a vendored file is a dangling import and a refusal.
_DANGLING = (
    re.compile(r"^from engine\.", re.MULTILINE),
    re.compile(r"^import engine\b", re.MULTILINE),
    re.compile(r"^from common\.", re.MULTILINE),
    re.compile(r"^import common\b", re.MULTILINE),
)


def _swap_imports(text: str) -> str:
    for pat, repl in _IMPORT_SWAPS:
        text = pat.sub(repl, text)
    return text


def _assert_no_dangling(text: str, label: str) -> None:
    """Refuse if a vendored file still imports outside its declared closure. A dangling `from engine.` or
    non-dot `from common.` in a shipped brief would not import on a fork, so it is a hard refusal."""
    for pat in _DANGLING:
        m = pat.search(text)
        if m:
            line = text[m.start():text.find("\n", m.start())]
            raise PublishRefused(
                f"vendored file {label} still has a dangling import after the prefix swap: {line.strip()!r}. "
                "A shipped brief must import only from its declared closure (stdlib, anthropic, or a sibling)."
            )


class PublishRefused(Exception):
    """Raised when the gate or the vendoring refuses. The caller turns it into a non-zero exit having
    written nothing (the brief dir is assembled in a temp dir and only moved into place on success)."""


# --------------------------------------------------------------------------- the generated brief files


# Programmatic tool calling is no longer generated from Python source strings here.
# Its public artifact lives in engine/public_hits_bundle and is copied by manifest.


# The self-contained citations corpus, written as the brief's docs/ edit surface. Plain text so a
# citation is a character range that resolves exactly. Lifted from the engine's edges/citations/demo.py
# CORPUS, one .txt per document, so a forker swaps their own .txt files in.
_CITATIONS_CORPUS = {
    "acme_sla.txt": (
        "Acme Cloud commits to a monthly uptime of 99.9 percent for all Standard plan "
        "customers. Enterprise plan customers receive a monthly uptime commitment of 99.99 "
        "percent. If monthly uptime falls below the committed level, the customer is eligible "
        "for a service credit equal to 10 percent of the monthly fee for each full hour of "
        "downtime. Support tickets from Enterprise customers receive a first response within 30 "
        "minutes, around the clock. Standard plan tickets receive a first response within one "
        "business day.\n"
    ),
    "acme_data_policy.txt": (
        "All customer data is encrypted at rest using AES-256 and in transit using TLS 1.3. "
        "Deleted records are retained in backups for 35 days before permanent erasure. Customer "
        "data is stored in the region selected at signup and is never replicated outside that "
        "region without written consent. Acme retains audit logs for two years. Personal data "
        "deletion requests are completed within 30 days of verification.\n"
    ),
    "acme_billing.txt": (
        "Acme bills monthly in advance on the first day of each billing cycle. Usage above the "
        "plan allowance is charged at 2 cents per additional API call. Annual plans are "
        "discounted 20 percent compared to monthly billing. A customer who cancels within 14 "
        "days of initial signup receives a full refund. After 14 days, fees are non-refundable "
        "except where required by law.\n"
    ),
}

# The 8 questions the citations brief answers, each with a single citable answer in the corpus above.
_CITATIONS_QUESTIONS = [
    "What is the monthly uptime commitment for the Enterprise plan?",
    "How is customer data encrypted in transit?",
    "How long are deleted records kept in backups before permanent erasure?",
    "What service credit applies when uptime falls below the committed level?",
    "What is the charge for usage above the plan allowance?",
    "Within how long must a personal data deletion request be completed?",
    "What refund does a customer get if they cancel within 14 days of signup?",
    "How quickly do Enterprise support tickets get a first response?",
]


def _cite_source(slug: str) -> str:
    """The generated citations run entry: the engine demonstrator's Claude Citations arm (the in-API
    char_location pointer, resolved against the source and asserted) plus a --check self-test. The DIY
    and competitor arms are stripped. Imports the flattened common/ package; anthropic is imported
    lazily in the run path so importing this module needs no SDK."""
    qlist = ",\n    ".join(json.dumps(q) for q in _CITATIONS_QUESTIONS)
    return f'''"""cite: answer questions over your own documents, get a verifiable pointer back for every answer.

The founder-facing artifact for the {slug} brief. It answers a set of questions over the plain-text
documents in {slug}/docs/*.txt with Claude's Citations feature on, and for every answer it checks that
the source pointer the API returned actually resolves: source[start_char_index:end_char_index] is
exactly the cited_text the API handed back. That is the whole promise, measured on a live call.

Set citations.enabled=true on each document block and Claude returns, for every claim it makes, a
structured pointer into the source: the document index, a character range (0-indexed, end exclusive),
and the verbatim cited_text at that range. The docs guarantee the pointer is valid and the cited_text
does not count toward output tokens. Source, re-fetched 2026-06-18:
https://platform.claude.com/docs/en/build-with-claude/citations

  python -m {slug}.cite            answer the questions and print the resolve rate and cost
  python -m {slug}.cite --check    the self-test: assert every returned pointer resolves, exit 1 if not
  python -m {slug}.cite --model sonnet   use Sonnet 4.6 instead of the default Haiku 4.5

This costs estimated $0.01 on Haiku 4.5. The model call is the only spend. anthropic is imported lazily,
inside the run path, so importing this module needs no SDK.
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

# Make the repo root importable when run as a file, not just as a module.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from .common.models import get  # noqa: E402  the verified id + price registry, anthropic-free
from .common.pricing import cost_usd  # noqa: E402  real usage object -> real dollars, anthropic-free

DOCS_DIR = Path(__file__).resolve().parent / "docs"

# Citations is supported on every active model except Haiku 3. The brief runs on Haiku 4.5 (the cheap
# tier) by default and offers Sonnet 4.6.
CITATION_MODELS = {{"haiku": "claude-haiku-4-5-20251001", "sonnet": "claude-sonnet-4-6"}}

QUESTIONS = [
    {qlist},
]


def load_corpus():
    """Load the plain-text documents in a stable order. Each is one citable source. Replace the .txt
    files in {slug}/docs/ with your own to run this over your documents."""
    rows = []
    for path in sorted(DOCS_DIR.glob("*.txt")):
        rows.append({{"title": path.stem, "text": path.read_text(encoding="utf-8")}})
    if not rows:
        raise SystemExit(f"No documents found in {{DOCS_DIR}}. Expected {slug}/docs/*.txt.")
    return rows


def _doc_blocks(corpus):
    return [
        {{"type": "document",
          "source": {{"type": "text", "media_type": "text/plain", "data": d["text"]}},
          "title": d["title"], "citations": {{"enabled": True}}}}
        for d in corpus
    ]


def fmt_usd(x: float) -> str:
    return f"${{x:,.2f}}"


def ask(client, model_id, corpus, question):
    """Ask one question with citations on, then resolve every char_location pointer it returned."""
    content = _doc_blocks(corpus) + [
        {{"type": "text", "text": question + " Answer in one sentence, grounded in the documents."}}
    ]
    t0 = time.perf_counter()
    msg = client.messages.create(model=model_id, max_tokens=400,
                                 messages=[{{"role": "user", "content": content}}])
    dt = time.perf_counter() - t0
    cites, answer_parts = [], []
    for block in msg.content:
        if getattr(block, "type", None) != "text":
            continue
        answer_parts.append(block.text)
        for c in (getattr(block, "citations", None) or []):
            if getattr(c, "type", None) == "char_location":
                cites.append(c)
    # The guarantee, checked: source[start:end] == cited_text, on the right doc.
    resolved = sum(1 for c in cites
                   if 0 <= c.document_index < len(corpus)
                   and corpus[c.document_index]["text"][c.start_char_index:c.end_char_index] == c.cited_text)
    return {{
        "question": question, "answer": "".join(answer_parts).strip(),
        "n_citations": len(cites), "n_resolved": resolved,
        "cited_doc": corpus[cites[0].document_index]["title"] if cites else "",
        "output_tokens": getattr(msg.usage, "output_tokens", 0) or 0,
        "cost": cost_usd(model_id, msg.usage), "latency_s": dt,
    }}


def run(client, model_key, corpus, questions, *, progress=True):
    model_id = get(model_key).id
    rows = []
    for i, q in enumerate(questions, 1):
        r = ask(client, model_id, corpus, q)
        rows.append(r)
        if progress:
            print(f"      [{{i}}/{{len(questions)}}] {{r['n_resolved']}}/{{r['n_citations']}} pointers resolve  "
                  f"{{r['latency_s']:.1f}}s", flush=True)
    return {{
        "model_key": model_key, "model_id": model_id, "rows": rows, "questions": len(questions),
        "answered_with_citation": sum(1 for r in rows if r["n_citations"] > 0),
        "total_citations": sum(r["n_citations"] for r in rows),
        "total_resolved": sum(r["n_resolved"] for r in rows),
        "cost": sum(r["cost"] for r in rows),
        "output_tokens": sum(r["output_tokens"] for r in rows),
        "time": sum(r["latency_s"] for r in rows),
    }}


def print_table(result):
    print(f"\\n  {{'question':<58}}{{'doc':>10}}{{'pointer':>10}}")
    print("  " + "-" * 84)
    for r in result["rows"]:
        q = (r["question"][:55] + "...") if len(r["question"]) > 56 else r["question"]
        ptr = f"{{r['n_resolved']}}/{{r['n_citations']}}" if r["n_citations"] else "none"
        print(f"  {{q:<58}}{{r['cited_doc']:>10}}{{ptr:>10}}")
    n = result["questions"]
    print()
    print(f"  {{result['total_resolved']}}/{{result['total_citations']}} source pointers resolve "
          f"(source[start:end] == cited_text), across {{result['answered_with_citation']}}/{{n}} answers")
    print(f"  that carried a citation. The API extracts the pointer and guarantees it, the cited_text is")
    print(f"  free of output tokens, and your code checks it holds. Live cost {{fmt_usd(result['cost'])}} on "
          f"{{get(result['model_key']).label}}, {{result['time']:.0f}}s.\\n")


def cmd_run(model_key):
    from .common.client import get_client  # lazy: anthropic only imported when we actually call
    corpus = load_corpus()
    label = get(model_key).label
    print(f"\\n  Citations: {{len(QUESTIONS)}} questions over {{len(corpus)}} of your own documents "
          f"({slug}/docs/*.txt), on {{label}}.")
    print(f"  Citations on, char_location pointers, and the grader resolves every pointer the run returns.")
    print(f"  Upfront: estimated $0.01 and roughly 30 seconds using your API key. The model call is the only spend.\\n")
    client = get_client()
    print_table(run(client, model_key, corpus, QUESTIONS))
    return 0


def cmd_check(model_key):
    """The self-test: assert every returned pointer resolves. A pointer that does not resolve fails."""
    from .common.client import get_client  # lazy
    corpus = load_corpus()
    print(f"\\n  --check: answering {{len(QUESTIONS)}} questions on {{get(model_key).label}} and asserting "
          f"every returned char_location pointer resolves. Estimated $0.01.\\n")
    client = get_client()
    result = run(client, model_key, corpus, QUESTIONS)
    print_table(result)
    problems = []
    if result["total_citations"] == 0:
        problems.append("no citations were returned at all")
    if result["total_resolved"] != result["total_citations"]:
        problems.append(f"{{result['total_citations'] - result['total_resolved']}} of "
                        f"{{result['total_citations']}} pointers did not resolve")
    if result["answered_with_citation"] != result["questions"]:
        problems.append(f"only {{result['answered_with_citation']}}/{{result['questions']}} answers carried a citation")
    if problems:
        print("  CHECK FAILED:")
        for p in problems:
            print(f"    - {{p}}")
        return 1
    print(f"  CHECK PASSED: all {{result['total_resolved']}} pointers resolve across "
          f"{{result['questions']}}/{{result['questions']}} answers. Now drop your own .txt files into "
          f"{slug}/docs/ and rerun.\\n")
    return 0


def main() -> int:
    p = argparse.ArgumentParser(
        description="Answer questions over your own documents with Citations on and verify every pointer.")
    p.add_argument("--model", default="haiku", choices=sorted(CITATION_MODELS),
                   help="haiku (default, the cheap tier) or sonnet")
    p.add_argument("--check", action="store_true", help="self-test: assert every returned pointer resolves")
    a = p.parse_args()
    return cmd_check(a.model) if a.check else cmd_run(a.model)


if __name__ == "__main__":
    raise SystemExit(main())
'''


def _codeexec_run_source(slug: str) -> str:
    """The generated run entry for the code-execution-state brief: write a unique value to /tmp/state.txt in a
    fresh container, capture container.id, then read it back from the REUSED container on a separate
    request, plus a --check self-test. The Claude side runs by default on one dependency. The comparison
    gate (--compare / COMPARE=1) adds the OpenAI and Gemini arms from the sibling compare.py. Imports the
    flattened common/ package; anthropic is imported lazily so importing this module needs no SDK."""
    return f'''"""run: write a file in your agent's sandbox, then read it back from the reused container.

The founder-facing artifact for the {slug} brief. A multi-step agent that runs code needs its sandbox to
keep state between turns. Claude's code execution sandbox keeps its container and its files across
separate Messages API requests: save the container id returned by the first response, pass it as
container=<id> on the next request, and a file written in turn 1 is there in turn 2. Containers live 30 days. Source,
re-fetched 2026-06-22: https://platform.claude.com/docs/en/agents-and-tools/tool-use/code-execution-tool

  python -m {slug}.run            write a value, then read it back from the reused container
  python -m {slug}.run --check    the self-test: ASSERT the value reads back from the reused container
  python -m {slug}.run --model opus    use Opus 4.8 instead of the default Sonnet 4.6
  python -m {slug}.run --compare  also run the OpenAI and Gemini arms and print the full head-to-head

This costs estimated $0.05 on Sonnet 4.6. The model calls are the only spend, the code runs server-side in
Anthropic's sandbox. anthropic is imported lazily, inside the run path, so importing this module needs no
SDK. The comparison arms (compare.py) need OPENAI_API_KEY, GEMINI_API_KEY, and requirements-compare.txt.
"""

from __future__ import annotations

import argparse
import os
import sys
import time
from pathlib import Path

# Make the repo root importable when run as a file, not just as a module.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from .common.models import get  # noqa: E402  the verified id + price registry, anthropic-free
from .common.pricing import cost_usd  # noqa: E402  real usage object -> real dollars, anthropic-free

# This receipt stays pinned to the header/tool pair it measured. The current docs list
# code_execution_20250825 for file operations and same-container reuse, while programmatic tool calling uses
# code_execution_20260120 because allowed_callers runs tools from inside the sandbox.
CODE_EXEC_BETA = "code-execution-2025-08-25"
CODE_EXEC_TOOL = "code_execution_20250825"
MODELS = {{"sonnet": "claude-sonnet-4-6", "opus": "claude-opus-4-8"}}

# The comparison gate default. The generator bakes this per surface: the public brief ships it OFF, so
# the Claude side runs alone on one dependency, and --compare (make code_execution_state COMPARE=1)
# reproduces the OpenAI and Gemini head-to-head. A private both-directions checkout ships it ON.
COMPARE_DEFAULT = {{compare_default}}


def _nonce() -> str:
    return f"NONCE{{int(time.time())}}{{os.urandom(2).hex()}}"


def _text(resp) -> str:
    return "".join(b.text for b in resp.content if getattr(b, "type", None) == "text")


def write_and_reread(client, model_key: str) -> dict:
    """Write a unique value to /tmp/state.txt in a fresh container, then read it back from the REUSED
    container on a second, separate request. The container id is the mechanism: save it from the
    first response and pass it as container=<id> on the next request."""
    model_id = get(model_key).id
    nonce = _nonce()
    tools = [{{"type": CODE_EXEC_TOOL, "name": "code_execution"}}]

    r1 = client.beta.messages.create(
        model=model_id, max_tokens=1024, betas=[CODE_EXEC_BETA], tools=tools,
        messages=[{{"role": "user", "content":
                   f"Run python: write the exact text {{nonce}} to /tmp/state.txt, then print done."}}])
    cost = cost_usd(model_key, r1.usage)
    container_id = getattr(getattr(r1, "container", None), "id", None)

    read_back = False
    if container_id:
        r2 = client.beta.messages.create(
            model=model_id, max_tokens=1024, betas=[CODE_EXEC_BETA], container=container_id, tools=tools,
            messages=[{{"role": "user", "content": "Run python: print the contents of /tmp/state.txt"}}])
        cost += cost_usd(model_key, r2.usage)
        read_back = nonce in _text(r2)

    return {{"model_key": model_key, "nonce": nonce, "container_id": container_id,
            "read_back": read_back, "cost": cost}}


def fmt_usd(x: float) -> str:
    return f"${{x:,.2f}}"


def print_table(result: dict) -> None:
    cid = result["container_id"] or "(none returned)"
    short = (cid[:22] + "...") if len(cid) > 25 else cid
    back = "read back, matches" if result["read_back"] else "not read back"
    print()
    print("  step                                              result")
    print("  " + "-" * 64)
    print("  write the value to /tmp/state.txt (request 1)     done")
    print(f"  reuse container {{short:<34}}{{back}}")
    print("  " + "-" * 64)
    print()
    print("  The file written in request 1 was read back from the SAME container in request 2.")
    print("  Save the returned container id and pass container=<id> on the next request.")
    print(f"  Live cost {{fmt_usd(result['cost'])}} on {{get(result['model_key']).label}}.")
    print()


def _maybe_compare(model_key: str, result: dict, compare_on: bool, idle_minutes: int) -> None:
    """When the comparison gate is on, run the OpenAI and Gemini arms and print the full head-to-head.
    Imported lazily, so the default Claude-only run never touches the comparison code or its SDKs."""
    if not compare_on:
        return
    from .compare import append_comparison  # lazy: the comparison SDKs load only here
    append_comparison(model_key, result, idle_minutes=idle_minutes)


def cmd_run(model_key: str, compare_on: bool = False, idle_minutes: int = 0) -> int:
    from .common.client import get_client  # lazy: anthropic only imported when we actually call

    print(f"\\n  Code execution state: write a file in your agent's sandbox, then read it back from the")
    print(f"  reused container on a separate request, on {{get(model_key).label}}.")
    print(f"  Upfront: estimated $0.05 and roughly 40 seconds using your API key. The model calls are the only spend,")
    print(f"  the code runs server-side in Anthropic's sandbox.\\n")
    client = get_client()
    result = write_and_reread(client, model_key)
    print_table(result)
    _maybe_compare(model_key, result, compare_on, idle_minutes)
    return 0


def cmd_check(model_key: str, compare_on: bool = False, idle_minutes: int = 0) -> int:
    """The self-test: assert the value written in request 1 reads back from the REUSED container in
    request 2. No container id, or no read-back, is a failure."""
    from .common.client import get_client  # lazy

    print(f"\\n  --check: writing a value in one request and asserting it reads back from the reused")
    print(f"  container in a separate request, on {{get(model_key).label}}. Estimated $0.05.\\n")
    client = get_client()
    result = write_and_reread(client, model_key)
    print_table(result)
    _maybe_compare(model_key, result, compare_on, idle_minutes)
    if not result["container_id"]:
        print("  CHECK FAILED: no container id was returned to reuse.\\n")
        return 1
    if not result["read_back"]:
        print("  CHECK FAILED: the value did not read back from the reused container.\\n")
        return 1
    print("  CHECK PASSED: the file persisted across two separate requests on the same container.")
    print("  Containers live 30 days, so the state is there even after your user steps away.\\n")
    return 0


def main() -> int:
    p = argparse.ArgumentParser(
        description="Write a file in the code-execution sandbox and read it back from the reused container.")
    p.add_argument("--model", default="sonnet", choices=sorted(MODELS),
                   help="sonnet (default) or opus")
    p.add_argument("--check", action="store_true",
                   help="self-test: assert the value reads back from the reused container")
    p.add_argument("--compare", dest="compare", action="store_true", default=None,
                   help="also run the OpenAI and Gemini arms and print the full head-to-head table "
                        "(needs OPENAI_API_KEY, GEMINI_API_KEY, and requirements-compare.txt)")
    p.add_argument("--no-compare", dest="compare", action="store_false",
                   help="run only the Claude side (the public-brief default)")
    p.add_argument("--idle-minutes", type=int, default=0,
                   help="with --compare, wait this many minutes, then re-read each container to reproduce "
                        "the idle-survival result live (OpenAI expires after 20 minutes idle)")
    a = p.parse_args()
    compare_on = COMPARE_DEFAULT if a.compare is None else a.compare
    if a.check:
        return cmd_check(a.model, compare_on, a.idle_minutes)
    return cmd_run(a.model, compare_on, a.idle_minutes)


if __name__ == "__main__":
    raise SystemExit(main())
'''


def _codeexec_compare_source(slug: str) -> str:
    """The generated comparison arm for the code-execution-state brief: the OpenAI and Gemini code
    sandboxes run the same write-then-reread, behind the gate option. Best to best, each vendor's
    strongest sandbox. Imports are lazy, so importing this module needs no comparison SDK; a missing key
    or SDK skips that arm with a clear note. Built as a plain string (slug substituted) so the dict and
    f-string braces in the body need no escaping."""
    body = '''"""compare: reproduce the container-durability head-to-head against OpenAI and Gemini.

The default brief runs the Claude side alone on one dependency. Set OPENAI_API_KEY and GEMINI_API_KEY,
install the optional comparison SDKs (pip install -r requirements-compare.txt), and run
`make {slug} COMPARE=1` to reproduce the whole table using your own API keys, not just the Claude side.

Best to best, the same write-then-reread on each vendor's strongest code sandbox:
  - Claude code execution reuses its container by id across requests, and containers live 30 days.
  - OpenAI code_interpreter reuses a warm container by id. The dated comparison run recorded an
    expired-container error after the idle wait, consistent with the documented 20-minute idle expiry.
  - Gemini code execution exposes no reusable container handle in the tested setup.
Sources, re-fetched 2026-06-19:
  - OpenAI code interpreter: https://developers.openai.com/api/docs/guides/tools-code-interpreter
  - Gemini code execution: https://ai.google.dev/gemini-api/docs/code-execution

Every SDK import is lazy. A missing API key or SDK skips that arm with a clear note and never fakes a row.
By default the live arms show the warm reuse and Gemini's lack of a reusable container, and the
dated run records the idle result. Add --idle-minutes 21 to reproduce the idle re-read live (the run
waits, then re-reads each container).
"""

from __future__ import annotations

import os
import time

from .common.compare_clients import COMPARE_DEPS_HINT, gemini_cost, get_gemini_client, get_openai_client, openai_cost
from .common.models import get

OPENAI_MODEL = "gpt-top"    # gpt-5.5, code interpreter
GEMINI_MODEL = "gem-flash"  # gemini-3.5-flash, code execution


def _nonce(tag):
    return "NONCE" + tag + str(int(time.time())) + os.urandom(2).hex()


def _openai_container_id(resp):
    for it in (getattr(resp, "output", None) or []):
        if getattr(it, "type", None) == "code_interpreter_call":
            return getattr(it, "container_id", None) or getattr(it, "container", None)
    return None


def _openai_arm(idle_minutes):
    """Write a nonce to /tmp/state.txt in an OpenAI code_interpreter container, warm-read it back, then
    (with --idle-minutes) wait and re-read to reproduce the idle result live."""
    m = get(OPENAI_MODEL)
    client = get_openai_client()
    if client is None:
        return {"label": "OpenAI (" + m.id + ")", "skipped": "set OPENAI_API_KEY to run this arm"}
    nonce = _nonce("OAI")
    cost = 0.0
    r = client.responses.create(
        model=m.id, max_output_tokens=2048,
        tools=[{"type": "code_interpreter", "container": {"type": "auto"}}],
        input="Use the python tool: write the exact text " + nonce + " to /tmp/state.txt, then print done.")
    cost += openai_cost(OPENAI_MODEL, r.usage)
    cid = _openai_container_id(r)
    warm = False
    if cid:
        r2 = client.responses.create(
            model=m.id, max_output_tokens=2048,
            tools=[{"type": "code_interpreter", "container": cid}],
            input="Use the python tool: print the contents of /tmp/state.txt")
        cost += openai_cost(OPENAI_MODEL, r2.usage)
        warm = nonce in (getattr(r2, "output_text", "") or "")
    idle = None
    if idle_minutes > 0 and cid:
        time.sleep(idle_minutes * 60)
        try:
            r3 = client.responses.create(
                model=m.id, max_output_tokens=2048,
                tools=[{"type": "code_interpreter", "container": cid}],
                input="Use the python tool: print the contents of /tmp/state.txt, or print NOTFOUND if missing.")
            cost += openai_cost(OPENAI_MODEL, r3.usage)
            idle = nonce in (getattr(r3, "output_text", "") or "")
        except Exception:  # noqa: BLE001  the documented outcome after 20 min idle: the container is gone
            idle = False
    return {"label": "OpenAI (" + m.id + ")", "warm": warm, "idle": idle, "cost": cost}


def _gemini_arm():
    """Gemini has no reusable container: write in call 1, then a FRESH call 2 cannot see the file."""
    m = get(GEMINI_MODEL)
    client = get_gemini_client()
    if client is None:
        return {"label": "Gemini (" + m.id + ")", "skipped": "set GEMINI_API_KEY to run this arm"}
    from google.genai import types

    nonce = _nonce("GEM")
    tool = types.Tool(code_execution=types.ToolCodeExecution())
    cfg = types.GenerateContentConfig(tools=[tool], max_output_tokens=1024)
    cost = 0.0
    r1 = client.models.generate_content(
        model=m.id, contents="Write the exact text " + nonce + " to /tmp/state.txt using python, then print done.", config=cfg)
    cost += gemini_cost(GEMINI_MODEL, getattr(r1, "usage_metadata", None))
    r2 = client.models.generate_content(
        model=m.id, contents="Using python, print the contents of /tmp/state.txt, or print NOTFOUND if it is missing.", config=cfg)
    cost += gemini_cost(GEMINI_MODEL, getattr(r2, "usage_metadata", None))
    persisted = nonce in (getattr(r2, "text", None) or "")
    return {"label": "Gemini (" + m.id + ")", "persisted": persisted, "cost": cost}


def _run_arm(fn, *args):
    """Run one competitor arm, turning any failure into a skipped row, so --compare never crashes."""
    try:
        return fn(*args)
    except SystemExit as e:
        return {"skipped": str(e)}
    except Exception as e:  # noqa: BLE001
        return {"skipped": type(e).__name__ + ": " + str(e)[:80]}


def _claude_idle_reread(model_key, claude_result, idle_minutes):
    """Re-read Claude's container after the same idle, to show the file survives live. Returns a bool or
    None when the id or nonce is missing or the call fails."""
    cid = claude_result.get("container_id")
    nonce = claude_result.get("nonce")
    if not cid or not nonce:
        return None
    from .common.client import get_client
    from .run import CODE_EXEC_BETA, CODE_EXEC_TOOL

    client = get_client()
    try:
        r = client.beta.messages.create(
            model=get(model_key).id, max_tokens=1024, betas=[CODE_EXEC_BETA], container=cid,
            tools=[{"type": CODE_EXEC_TOOL, "name": "code_execution"}],
            messages=[{"role": "user", "content":
                       "Run python: print the contents of /tmp/state.txt, or print NOTFOUND if missing."}])
        txt = "".join(b.text for b in r.content if getattr(b, "type", None) == "text")
        return nonce in txt
    except Exception:  # noqa: BLE001
        return None


def append_comparison(model_key, claude_result, idle_minutes=0):
    """Run the OpenAI and Gemini sandboxes on the same write-then-reread and print the head-to-head."""
    short = get(model_key).label.replace("Claude ", "")
    print("  Reproducing the head-to-head: container durability across a write-then-reread.")
    print("  OpenAI and Gemini run their strongest code sandbox. " + COMPARE_DEPS_HINT + ".")
    if idle_minutes > 0:
        print("  Waiting " + str(idle_minutes) + " minutes idle, then re-reading each container live.\\n")
    else:
        print("  (Add --idle-minutes 21 to reproduce the idle expiry live.)\\n")

    gem = _run_arm(_gemini_arm)
    oai = _run_arm(_openai_arm, idle_minutes)

    if idle_minutes > 0:
        claude_idle = _claude_idle_reread(model_key, claude_result, idle_minutes)
        claude_cell = "read back" if (claude_idle or (claude_idle is None and claude_result.get("read_back"))) else "see run output above"
        rows = [("Claude (" + short + ")", claude_cell)]
        if "skipped" in oai:
            rows.append((oai.get("label", "OpenAI"), "skipped: " + oai["skipped"]))
        else:
            rows.append((oai["label"], "read back" if oai.get("idle") else "container expired"))
        if "skipped" in gem:
            rows.append((gem.get("label", "Gemini"), "skipped: " + gem["skipped"]))
        else:
            rows.append((gem["label"], "no reusable container"))
        header = "reread after " + str(idle_minutes) + " minutes idle"
    else:
        rows = [("Claude (" + short + ")", "reused by id, 30-day container life")]
        if "skipped" in oai:
            rows.append((oai.get("label", "OpenAI"), "skipped: " + oai["skipped"]))
        else:
            rows.append((oai["label"], "reused while warm, expires after 20 min idle"))
        if "skipped" in gem:
            rows.append((gem.get("label", "Gemini"), "skipped: " + gem["skipped"]))
        else:
            rows.append((gem["label"], "no reusable container, file gone next call"))
        header = "container reuse and idle durability"

    print("  " + "platform".ljust(22) + header)
    print("  " + "-" * 70)
    for label, cell in rows:
        print("  " + label.ljust(22) + cell)
    print("  " + "-" * 70)
    print()
    print("  Claude's sandbox keeps your agent's files between requests and across a long idle, where")
    print("  The dated comparison run records OpenAI returning an expired-container error after")
    print("  the idle wait, and Gemini exposing no reusable container handle in the tested setup.")
    if idle_minutes == 0:
        print("  Measured idle survival (2026-06-19): Claude read the file back after a 31-minute idle.")
    ran = [a for a in (oai, gem) if "skipped" not in a]
    if ran:
        print("  Competitor arms this run: $" + format(sum(a["cost"] for a in ran), ",.2f") +
              " across " + str(len(ran)) + " of 2 (OpenAI, Gemini).")
    print()
'''
    return body.replace("{slug}", slug)


def _codeexec_sample_source() -> str:
    """The committed receipt snapshot the demo gif replays (cat by demo.tape). Wins-only, Claude-only,
    deterministic, no competitor named. Shows the value written in one request read back from the reused
    container, and the measured 31-minute-idle durability."""
    return (
        "\n  Code execution state: your agent's sandbox keeps its files between requests.\n\n"
        "  Workload: write a unique value to /tmp/state.txt, capture the container id, then read it\n"
        "  back from the REUSED container on a separate request. Same container, a later call.\n\n"
        "  step                                            result\n"
        "  --------------------------------------------------------------------\n"
        "  write the value to /tmp/state.txt (request 1)   done\n"
        "  read it back from the reused container (req 2)   read back, matches\n"
        "  re-read after a 31-minute idle                   read back (30-day container life)\n"
        "  --------------------------------------------------------------------\n\n"
        "  -> the file written in one request is there in the next, and survives a long idle.\n"
        "     Save the returned container id and pass container=<id> on the next request.\n\n"
        '  The change: betas=["code-execution-2025-08-25"], add the code_execution tool, and carry\n'
        "  the container id between calls.\n\n"
        "  Runnable code and the full brief: code_execution_state/README.md\n"
    )


def _demo_tape_source(plan: BriefPlan) -> str:
    """The VHS tape for the brief's demo.gif. It shadows `make` with a function that cats the committed
    sample.txt, so `make gif` replays the receipt for $0 (no API call, deterministic). Generated here, so
    a republish reproduces it, and the gif binary is rendered from this tape by `make gif` (vhs + ffmpeg)."""
    slug = plan.slug
    _dims = {"citations": (1240, 820), "code_execution_state": (1200, 720)}
    width, height = _dims.get(slug, (1200, 720) if plan.from_assets else (1200, 640))
    # The gif opens with the brief's own value title (the README's first line), so the gif and the
    # README always lead with the same value, and a republish keeps the two in lockstep.
    headline_src = _read_bundle(plan, "README.md") if plan.public_bundle else _read_asset(plan, "README.md")
    headline = headline_src.splitlines()[0].strip()
    return (
        f"# VHS tape for the {slug} brief gif (https://github.com/charmbracelet/vhs).\n"
        f"# Regenerate from the repo root with:  make gif    (needs vhs and ffmpeg).\n"
        f"# It replays the committed receipt ({slug}/sample.txt) for $0, so the gif is deterministic.\n"
        f"# A republish regenerates this tape, and the gif binary is rendered from it by make gif.\n"
        f"Output {slug}/demo.gif\n\n"
        f"Set FontSize 16\nSet Width {width}\nSet Height {height}\nSet Padding 18\n\n"
        f"Hide\n"
        f'Type "make() {{ cat {slug}/sample.txt; }}"\nEnter\n'
        f'Type "clear"\nEnter\n'
        f"Show\n\n"
        f'Type "{headline}"\nEnter\nSleep 1200ms\n'
        f'Type "make {slug}"\nEnter\nSleep 3s\n'
    )


def _citations_sample_source() -> str:
    """The committed citations receipt snapshot the demo gif replays. Built from the same questions the
    brief ships, so it is deterministic and matches what a clean live run resolves (every pointer)."""
    docs = ["acme_sla", "acme_dat...", "acme_dat...", "acme_sla",
            "acme_bil...", "acme_dat...", "acme_bil...", "acme_sla"]
    n = len(_CITATIONS_QUESTIONS)
    rows = ""
    for q, d in zip(_CITATIONS_QUESTIONS, docs):
        qt = (q[:52] + "...") if len(q) > 52 else q
        rows += f"  {qt:<55}{d:<13}1/1\n"
    enabled = '  Turn it on: "citations": {"enabled": True} on each document.\n'
    return (
        "\n  Citations: a verifiable source pointer for every answer.\n\n"
        f"  {n} questions over 3 of your own documents (citations/docs/*.txt), on a live Claude call.\n"
        "  Citations on, char_location pointers back, the grader resolves every pointer the run returns.\n\n"
        "  question                                                  doc          pointer\n"
        "  ------------------------------------------------------------------------------\n"
        f"{rows}"
        "  ------------------------------------------------------------------------------\n\n"
        f"  {n}/{n} source pointers resolve (source[start:end] == cited_text), across {n}/{n} answers.\n"
        "  The API extracts the pointer and guarantees it, the cited_text is free of output\n"
        "  tokens, and your own code checks it holds.\n\n"
        f"{enabled}"
        "  Runnable code and the full brief: citations/README.md\n"
    )


def _sample_source(plan: BriefPlan, receipt: dict | None) -> str:
    """The committed receipt snapshot that the demo gif replays (cat by demo.tape). Wins-only, honest,
    deterministic. The token_accounting brief shows the billed-input table and same-answer check;
    grounding_resolution shows the per-pointer table."""
    if plan.from_assets:
        return _read_asset(plan, "sample.txt")
    if plan.public_bundle:
        return _read_bundle(plan, "sample.txt")
    if plan.slug == "code_execution_state":
        return _codeexec_sample_source()
    if plan.slug == "citations":
        return _citations_sample_source()
    raise PublishRefused(f"no sample source for brief slug {plan.slug!r}")


def _provenance_source(plan: BriefPlan, gate: GateResult, command: str) -> str:
    """The PROVENANCE stamp: exactly which committed engine state produced this brief, so a stranger can
    trace it. No model attribution. Records the edge key, demoKind, the verdict and source the gate read,
    the receipt path and its date, the source doc URL and date, the engine git SHA, and the command."""
    sha = _engine_sha()
    rpath = gate.receipt_path
    receipt_line = "(none committed; data/ is gitignored transient scratch)"
    if rpath is not None:
        rdate = gate.receipt.get("as_of_date") if gate.receipt else None
        receipt_line = f"data/{rpath.name}" + (f" (as_of {rdate})" if rdate else "")
    return f"""# Provenance

This brief is generated from the committed truth of the claude-feature-radar by `make publish-brief`,
not hand-written: the files come from the engine's manifest-owned public bundle or from the declared
per-edge generator path. The state below records which engine state produced the public artifact.
Regenerating from a different engine state changes this stamp.

- edge key: {gate.edge_key}
- demoKind: {plan.demo_kind}
- verdict read by the gate: {gate.verdict} (lead_basis {gate.lead_basis})
- gate source: {gate.source}
- receipt: {receipt_line}
- source doc: {plan.doc_url} (re-fetched 2026-06-18)
- engine git SHA: {sha}
- generating command: {command}
- generated: {date.today().isoformat()}

The verdict gate refused to publish unless this edge read as a clean, ranked, non-regime-bounded
claude-ahead win in the engine's own landscape, and any present receipt agreed.
"""


def _engine_sha() -> str:
    """The engine's current git SHA, for the provenance stamp. Read-only `git rev-parse`, no network, no
    write. Returns '(unknown)' if git is unavailable, never raises (provenance is a stamp, not a gate)."""
    try:
        out = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True, timeout=10)
        return out.stdout.strip() or "(unknown)"
    except Exception:  # noqa: BLE001
        return "(unknown)"


# --------------------------------------------------------------------------- idempotent root appends


def _ensure_makefile_entry(makefile: pathlib.Path, plan: BriefPlan) -> bool:
    """Idempotently add the brief's make target to the briefs-root Makefile. Returns True if it appended,
    False if the entry was already present. Never duplicates: it keys on the target name."""
    text = makefile.read_text() if makefile.exists() else ""
    run_module = plan.run_module or (
        "run" if plan.from_assets else {"citations": "cite", "code_execution_state": "run"}.get(plan.slug, "run")
    )
    if plan.head_to_head:
        # The comparison gate: `make <slug>` runs the Claude side alone, `make <slug> COMPARE=1` installs
        # the optional comparison SDKs and adds --compare, so the full OpenAI and Gemini head-to-head
        # reproduces. COMPARE is unset by default, so the default founder run stays one command, one
        # dependency, Claude side. $(if $(COMPARE),...) expands to nothing when COMPARE is unset.
        recipe = (f"\t$(if $(COMPARE),$(PIP) install --quiet -r requirements-compare.txt)\n"
                  f"\t$(PY) -m {plan.slug}.{run_module} $(if $(COMPARE),--compare)")
    else:
        recipe = f"\t$(PY) -m {plan.slug}.{run_module}"
    # Refresh an existing target's recipe (its run module may have been renamed on republish), so a
    # republished brief never leaves make pointed at a deleted module.
    block_re = re.compile(rf"^{re.escape(plan.slug)}:.*\n(?:[ \t].*\n)*", re.MULTILINE)
    if block_re.search(text):
        refreshed = block_re.sub(f"{plan.slug}: $(VENV)/.installed\n{recipe}\n", text, count=1)
        makefile.write_text(refreshed)
        return refreshed != text
    block = (
        f"\n# {plan.title}: {plan.make_help}\n"
        f"{plan.slug}: $(VENV)/.installed\n"
        f"{recipe}\n"
    )
    # Add the target to the .PHONY line if one exists and does not already name it.
    def _add_phony(m):
        names = m.group(1).split()
        if plan.slug not in names:
            names.append(plan.slug)
        return ".PHONY: " + " ".join(names)

    if re.search(r"^\.PHONY:", text, re.MULTILINE):
        text = re.sub(r"^\.PHONY:(.*)$", _add_phony, text, count=1, flags=re.MULTILINE)
    text = text.rstrip("\n") + "\n" + block
    makefile.write_text(text)
    return True


def _ensure_readme_entry(readme: pathlib.Path, plan: BriefPlan) -> bool:
    """Idempotently add a one-line entry for the brief to the briefs-root README. Returns True if it
    appended. Keys on the slug link, so a second publish of the same edge is a no-op."""
    text = readme.read_text() if readme.exists() else ""
    link = f"({plan.slug}/README.md)"
    # The run cost lives once, in plan.make_help, so the index entry can never drift from the make
    # target's own stated cost (the citations brief is the single-key $0.01 run, not the engine's
    # $0.06 cross-vendor sweep, and that distinction is exactly what kept drifting).
    mcost = re.search(r"\$([\d.]+)\)", plan.make_help)
    run_cost = mcost.group(1) if mcost else "?"
    cost_phrase = f"`make {plan.slug}` (estimated ${run_cost})"
    if link in text:
        # Refresh the run-cost in an existing entry so a stale figure cannot survive a republish.
        refreshed = re.sub(rf"`make {re.escape(plan.slug)}` \(about \$[\d.]+\)", cost_phrase, text, count=1)
        if refreshed != text:
            readme.write_text(refreshed)
        return refreshed != text
    if plan.from_assets and plan.index_blurb:
        blurb = plan.index_blurb
    elif plan.slug == "code_execution_state":
        blurb = ("Keep a multi-step agent's sandbox state between turns by reusing the code-execution "
                 "container, so a file written in one request is there in the next.")
    elif plan.slug == "citations":
        blurb = ("Answer questions over your own documents and get a verifiable source pointer for "
                 "every answer, resolved in your own code.")
    else:
        blurb = ("Cut the token bill on a fan-out task by running your tool in a code sandbox and "
                 "filtering the records before they reach the model.")
    entry = (
        f"- [**{plan.slug}**]({plan.slug}/README.md): {plan.title}. {blurb} "
        f"{cost_phrase}.\n"
    )
    # Insert under a "## Briefs" heading if present, else append at the end.
    m = re.search(r"^## Briefs\s*\n", text, re.MULTILINE)
    if m:
        # Append after the last existing list item under the Briefs heading.
        start = m.end()
        nxt = re.search(r"\n## ", text[start:])
        end = start + nxt.start() if nxt else len(text)
        section = text[start:end].rstrip("\n")
        text = text[:start] + section + "\n" + entry + text[end:]
    else:
        text = text.rstrip("\n") + "\n\n## Briefs\n\n" + entry
    readme.write_text(text)
    return True


# --------------------------------------------------------------------------- data-driven asset briefs

ASSETS_ROOT = ROOT / "engine" / "brief_assets"


def _assets_dir(plan: BriefPlan) -> pathlib.Path:
    """Where a from_assets brief's committed content (README.md, run.py, sample.txt, email.md) lives."""
    return ASSETS_ROOT / plan.slug


def _sub(text: str, plan: BriefPlan) -> str:
    """Substitute the brief placeholders into an asset file. Single-source for the slug, title, and doc
    URL so a brief's content cannot drift from its plan."""
    return (text.replace("{slug}", plan.slug)
                .replace("{title}", plan.title)
                .replace("{doc_url}", plan.doc_url))


def _read_asset(plan: BriefPlan, name: str) -> str:
    """Read one committed asset file for a from_assets brief, with placeholders substituted."""
    return _sub((_assets_dir(plan) / name).read_text(), plan)


def _read_bundle(plan: BriefPlan, name: str) -> str:
    """Read one file from a manifest-owned public artifact bundle."""
    path = ROOT / "engine" / "public_hits_bundle" / plan.slug / name
    return path.read_text(encoding="utf-8")


# --------------------------------------------------------------------------- the generator


def _vendor_files(plan: BriefPlan, brief_dir: pathlib.Path) -> None:
    """Copy each declared engine file into the brief dir, flattening common/ to a local common/ package
    and rewriting import lines by the deterministic prefix swap. Refuses on any dangling import."""
    (brief_dir / "common").mkdir(parents=True, exist_ok=True)
    (brief_dir / "common" / "__init__.py").write_text("")
    files = list(plan.files)
    if plan.head_to_head:
        # The comparison gate ships the lazy OpenAI + Gemini clients into common/, alongside the
        # client/models/pricing trio. compare_clients.py uses same-package relative imports (.client,
        # .pricing) like the rest of common/, so the prefix swap is a no-op and the dangling check passes.
        files.append(VendorFile("common/compare_clients.py", "common/compare_clients.py"))
    for vf in files:
        src = ROOT / vf.src
        text = src.read_text()
        swapped = _swap_imports(text)
        if vf.src == "common/client.py":
            swapped = swapped.replace(
                "pathlib.Path(__file__).resolve().parent.parent",
                "pathlib.Path(__file__).resolve().parents[2]",
            )
        _assert_no_dangling(swapped, vf.dst)
        dst = brief_dir / vf.dst
        dst.parent.mkdir(parents=True, exist_ok=True)
        dst.write_text(swapped)


def _apply_compare_default(text: str, compare_default: bool) -> str:
    """Bake the comparison-gate default into a generated run entry. The run.py templates of the
    head-to-head briefs carry a literal `{compare_default}`, replaced here with the per-surface bool:
    False for the public hits brief (Claude side by default, COMPARE=1 to reproduce the full table),
    True for a private both-directions checkout (always full). A template without the marker is left
    untouched, so this is safe to call on every run entry."""
    return text.replace("{compare_default}", "True" if compare_default else "False")


def _assemble_brief(plan: BriefPlan, gate: GateResult, command: str, staging: pathlib.Path,
                    compare_default: bool = False) -> None:
    """Build the whole brief into a staging dir (so a failure leaves nothing behind), then the caller
    moves it into place atomically. The edit surface and run entry differ by edge, so the body
    dispatches on the plan slug.

    compare_default sets the head-to-head briefs' comparison-gate default: False on the public hits
    brief (Claude side by default), True on a private both-directions checkout (always full)."""
    brief_dir = staging
    brief_dir.mkdir(parents=True, exist_ok=True)

    if plan.public_bundle:
        try:
            copy_artifact(plan.slug, brief_dir)
        except PublicHitsPublishError as exc:
            raise PublishRefused(str(exc)) from exc
    else:
        _vendor_files(plan, brief_dir)
        (brief_dir / "__init__.py").write_text("")

    if plan.public_bundle:
        pass
    elif plan.from_assets:
        # Data-driven brief: the run entry and README are committed under engine/brief_assets/<slug>/.
        run_src = _apply_compare_default(_read_asset(plan, "run.py"), compare_default)
        _assert_no_dangling(run_src, "run.py")  # the shipped run entry must import only from its closure
        (brief_dir / "run.py").write_text(run_src)
        (brief_dir / "README.md").write_text(_read_asset(plan, "README.md"))
        if plan.head_to_head:
            # The comparison arm: OpenAI + Gemini on the same workload, behind the gate option.
            compare_src = _read_asset(plan, "compare.py")
            _assert_no_dangling(compare_src, "compare.py")
            (brief_dir / "compare.py").write_text(compare_src)
    elif plan.slug == "citations":
        # The grounding_resolution brief: a docs/ corpus as the edit surface, cite.py as the run.
        docs = brief_dir / plan.edit_surface
        docs.mkdir(parents=True, exist_ok=True)
        for name, text in _CITATIONS_CORPUS.items():
            (docs / name).write_text(text)
        run_src = _cite_source(plan.slug)
        _assert_no_dangling(run_src, "cite.py")
        (brief_dir / "cite.py").write_text(run_src)
        (brief_dir / "README.md").write_text(_read_asset(plan, "README.md"))
    elif plan.slug == "code_execution_state":
        # The retention_resume brief: no edit surface, run.py writes a value to the container and reads
        # it back from the reused container on a separate request. Head-to-head, so it ships compare.py too.
        run_src = _apply_compare_default(_codeexec_run_source(plan.slug), compare_default)
        _assert_no_dangling(run_src, "run.py")
        (brief_dir / "run.py").write_text(run_src)
        (brief_dir / "README.md").write_text(_read_asset(plan, "README.md"))
        compare_src = _codeexec_compare_source(plan.slug)
        _assert_no_dangling(compare_src, "compare.py")
        (brief_dir / "compare.py").write_text(compare_src)
    else:  # pragma: no cover - a plan with no assembler is a programming error, not a publish path
        raise PublishRefused(f"no assembler for brief slug {plan.slug!r}")

    if not plan.public_bundle:
        # The demo gif's source: a generated tape that replays a generated, honest, wins-only receipt
        # snapshot for $0. `make gif` renders the binary from the tape, so the whole demo regenerates and
        # nothing about the gif is hand-written or lost on a republish.
        (brief_dir / "sample.txt").write_text(_sample_source(plan, _committed_receipt(plan)))
        (brief_dir / "demo.tape").write_text(_demo_tape_source(plan))

    (brief_dir / "PROVENANCE.md").write_text(_provenance_source(plan, gate, command))


def publish(edge_key: str, briefs_root: pathlib.Path, command: str, compare_default: bool = False) -> int:
    """The end-to-end publish. Runs the gate, refuses fail-closed on any failure (writing nothing), and
    otherwise assembles the brief in a temp dir, moves it into place, makes the idempotent root appends,
    and writes the founder email to the ENGINE repo. Returns a process exit code.

    compare_default sets a head-to-head brief's comparison-gate default: False (the public hits brief,
    Claude side by default) or True (a private both-directions checkout, always full)."""
    if not briefs_root.exists():
        print(f"  REFUSED: briefs root {briefs_root} does not exist. Pass --briefs-root=<path> to an "
              "existing checkout. Wrote nothing.")
        return 2

    gate = verdict_gate(edge_key)
    if not gate.ok:
        print(f"\n  REFUSED to publish edge {gate.edge_key!r}.")
        print(f"    verdict read : {gate.verdict}")
        print(f"    lead_basis   : {gate.lead_basis}")
        print(f"    source       : {gate.source}")
        print(f"    reason       : {gate.reason}")
        print("    wrote nothing (no partial brief dir).\n")
        return 1

    plan = _plan_for(edge_key)
    assert plan is not None  # the gate already verified a plan exists
    brief_dir = briefs_root / plan.slug

    # Assemble in a temp staging dir next to the target, so a refusal mid-vendor leaves nothing behind.
    staging = briefs_root / f".{plan.slug}.staging"
    if staging.exists():
        _rmtree(staging)
    try:
        _assemble_brief(plan, gate, command, staging, compare_default)
    except PublishRefused as exc:
        _rmtree(staging)
        print(f"\n  REFUSED to publish edge {gate.edge_key!r}: {exc}")
        print("    wrote nothing (no partial brief dir).\n")
        return 1

    # Success: move the staged brief into place (replacing any prior copy), then the idempotent appends.
    if brief_dir.exists():
        _rmtree(brief_dir)
    staging.rename(brief_dir)

    made_mk = _ensure_makefile_entry(briefs_root / "Makefile", plan)
    made_rd = _ensure_readme_entry(briefs_root / "README.md", plan)

    # Render the brief's demo.gif from its tape NOW, so a publish ALWAYS reproduces the gif in lockstep
    # with the brief, never a stale or missing one. The tape replays the committed sample.txt for $0
    # (no API call), so the gif stays deterministic and free.
    gif_status = _render_gif(briefs_root, plan.slug)

    # The full founder email is the engine's working draft, kept here under emails/.
    emails_dir = ROOT / "emails"
    emails_dir.mkdir(exist_ok=True)
    email_path = emails_dir / f"{plan.slug}_FOUNDER_EMAIL.md"
    # Every brief's prose (README + email) lives in engine/brief_assets/<slug>/, including the three
    # briefs whose run code is still generated, so all 11 share one source of truth for the copy.
    email_src = _read_asset(plan, "email.md")
    email_path.write_text(email_src)
    # This publisher writes only the engine's working draft, not the public hits repo.

    files = sorted(p.relative_to(briefs_root) for p in brief_dir.rglob("*") if p.is_file())
    print(f"\n  PUBLISHED brief {plan.slug!r} for edge {gate.edge_key!r} ({plan.demo_kind})")
    print(f"    verdict      : {gate.verdict} (lead_basis {gate.lead_basis})")
    print(f"    source       : {gate.source}")
    print(f"    brief dir    : {brief_dir}")
    for f in files:
        print(f"      + {f}")
    print(f"    Makefile     : {'appended ' + plan.slug + ' target' if made_mk else 'entry already present'}")
    print(f"    README.md    : {'appended ' + plan.slug + ' entry' if made_rd else 'entry already present'}")
    print(f"    demo.gif     : {gif_status}")
    print(f"    founder email: {email_path.relative_to(ROOT)} (engine repo only, never the public repo)")
    print("    no model call, no spend, no git, no send.\n")
    return 0


def _render_gif(briefs_root: pathlib.Path, slug: str) -> str:
    """Render <slug>/demo.gif from <slug>/demo.tape so every publish reproduces the gif in lockstep
    with the brief, never a stale or missing one. The tape replays the committed sample.txt for $0 (no
    API call). Scans the tape and sample for key material first and refuses to render on a hit, and
    skips with a clear note if vhs is not installed, so a publish never hard-fails on a missing renderer."""
    import shutil
    import subprocess
    brief = briefs_root / slug
    tape, sample = brief / "demo.tape", brief / "sample.txt"
    key = re.compile(r"sk-ant-|sk-proj-|AIza[0-9A-Za-z_-]{8}|xox[baprs]-|ghp_")
    for f in (tape, sample):
        if f.exists() and key.search(f.read_text(errors="ignore")):
            return f"NOT rendered (key material in {f.name})"
    if shutil.which("vhs") is None:
        return "SKIPPED (install vhs + ffmpeg, then re-publish)"
    subprocess.run(["vhs", f"{slug}/demo.tape"], cwd=str(briefs_root), capture_output=True, text=True)
    gif = brief / "demo.gif"
    return "rendered" if gif.exists() and gif.stat().st_size > 1000 else "render FAILED"


def _rmtree(path: pathlib.Path) -> None:
    import shutil
    shutil.rmtree(path, ignore_errors=True)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        description="Generate a self-contained public brief for a VERIFIED Claude-win edge (offline, $0).")
    p.add_argument("--edge", required=True, help="the edge key, e.g. programmatic-tool-calling")
    p.add_argument("--briefs-root", default=None,
                   help="the public hits repo root (default: ../claude-feature-hits relative to the engine)")
    p.add_argument("--compare-default", choices=("off", "on"), default="off",
                   help="a head-to-head brief's comparison-gate default. off (the public hits brief: the "
                        "Claude side runs by default, COMPARE=1 reproduces the full table); on (a private "
                        "both-directions checkout: the full OpenAI and Gemini head-to-head always runs)")
    a = p.parse_args(argv)

    briefs_root = (pathlib.Path(a.briefs_root).resolve() if a.briefs_root
                   else (ROOT.parent / "claude-feature-hits"))
    compare_default = a.compare_default == "on"
    command = f"make publish-brief EDGE={a.edge}"
    if a.briefs_root:
        command += f" BRIEFS_ROOT={a.briefs_root}"
    if compare_default:
        command += " COMPARE_DEFAULT=on"
    return publish(a.edge, briefs_root, command, compare_default)


if __name__ == "__main__":
    raise SystemExit(main())
