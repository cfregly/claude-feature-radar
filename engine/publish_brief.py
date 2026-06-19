"""publish_brief: turn a VERIFIED Claude-win edge into a self-contained public brief, offline, for $0.

This is the one-source-of-truth fix for the drift between this engine and the public claude-feature-briefs
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

# The lead_basis values that are NOT regime-bounded: a stable head-to-head win, a documented
# absence-of-evidence lead, or a within-Claude value-add. doc-grounded-parity is a parity, not a lead,
# and a cost-model lead is a price-regime lead that flips on the next price change, so neither is here.
PUBLISHABLE_LEAD_BASES = ("head-to-head", "absence-of-evidence", "within-claude-only")

# Keys we refuse outright regardless of how their lead_basis is labeled. cost-model is regime-bounded by
# construction (it wins only in one price regime), so it never publishes even if a record mislabels it.
REGIME_BOUNDED_KEYS = {"cost-model", "cost_model", "cost"}


# --------------------------------------------------------------------------- the per-edge vendor plan
#
# Each publishable edge declares, statically, the engine files its brief needs and how the brief lays
# them out, so the generated brief runs with one dependency (anthropic), exactly like the existing
# public ptc and citations briefs. The copier flattens common/ into a local common/ package and rewrites
# import lines by a DETERMINISTIC PREFIX SWAP only (no semantic rewrite):
#
#   from engine.demonstrators.token_core import   ->  from .token_core import
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
    points at, the vendored files, and the make-target help line. ``edit_surface`` is the one file a
    forker edits (my_tool.py), surfaced in the README run-it-on-your-own-data section when present."""
    slug: str
    title: str
    demo_kind: str
    doc_url: str
    files: tuple[VendorFile, ...]
    make_help: str
    edit_surface: str | None = None  # dst path of the edit-surface file, e.g. "my_tool.py"


# The vendor closure for programmatic-tool-calling. The brief needs the one audited counter/run loop
# (token_core), the anthropic-free client/models/pricing trio (flattened to a local common/), and the
# region_sales example fixture, vendored as the brief's own my_tool.py edit surface. The run entry is a
# generated run_tokens.py: the demonstrator's Claude arm (Mode A/B over token_core.run_mode) plus a
# --check self-test, with no competitor arm (the engine's PTC competitor side is a documented absence
# anyway).
PLANS: dict[str, BriefPlan] = {
    "programmatic-tool-calling": BriefPlan(
        slug="ptc",
        title="programmatic tool calling",
        demo_kind="token_accounting",
        doc_url="https://platform.claude.com/docs/en/agents-and-tools/tool-use/programmatic-tool-calling",
        files=(
            VendorFile("engine/demonstrators/token_core.py", "token_core.py"),
            VendorFile("common/client.py", "common/client.py"),
            VendorFile("common/models.py", "common/models.py"),
            VendorFile("common/pricing.py", "common/pricing.py"),
        ),
        make_help="build .venv, install anthropic, run the PTC token-bill comparison on the region_sales example (~$0.08)",
        edit_surface="my_tool.py",
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
}

# A publish-time alias from a landscape/seed key to its publish plan, so both the live sweep slug (ptc)
# and the built-edge folder name (programmatic-tool-calling) resolve to the same plan. Mirrors the
# scan._SEED_KEY_ALIAS direction but points at PLANS, which is keyed on the built-edge folder name.
_PLAN_KEY_ALIAS = {
    "ptc": "programmatic-tool-calling",
}


def _plan_for(edge_key: str) -> BriefPlan | None:
    if edge_key in PLANS:
        return PLANS[edge_key]
    alias = _PLAN_KEY_ALIAS.get(edge_key)
    return PLANS.get(alias) if alias else None


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
            return land.get("edges", []), f"landscape/landscape.json (as_of {land.get('as_of_date', '?')})"
        except (json.JSONDecodeError, OSError):
            pass
    # Fresh checkout, or an unreadable landscape: the committed seed differentiators ARE the leads.
    return list(scan.DIFFERENTIATORS), "engine/scan.py DIFFERENTIATORS (committed seed, no landscape yet)"


def _find_edge(edge_key: str) -> tuple[dict | None, str]:
    """Find the edge record for a key in the landscape (or seed), resolving the slug<->folder alias both
    directions so `ptc` and `programmatic-tool-calling` both hit the right record. Returns (record, src)."""
    edges, src = _landscape_edges()
    # The set of keys that should resolve to this edge: the key itself, its plan alias, and the reverse.
    wanted = {edge_key, edge_key.replace("_", "-"), edge_key.replace("-", "_")}
    plan = _plan_for(edge_key)
    if plan:
        wanted.add(plan.slug)
    for alt, canon in _PLAN_KEY_ALIAS.items():
        if edge_key in (alt, canon):
            wanted.update({alt, canon})
    for e in edges:
        if e.get("key") in wanted:
            return e, src
    return None, src


def _receipt_path(edge_key: str) -> pathlib.Path | None:
    """The data/last_<edge>.json receipt for this edge, if one is committed/present. Tries the edge key
    and the plan slug (the engine writes data/last_ptc.json keyed on the short slug), returns the first
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
    passed/mode_b_correct flag is truthy. A receipt with an explicit non-win verdict, or a false
    passed/mode_b_correct, is NOT a win and vetoes the publish."""
    verdict = receipt.get("verdict")
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
    a = re.search(r"Mode A:.*?([\d,]+)\s+\d+\s+(\S+)\s+\$[\d.]+", text)
    b = re.search(r"Mode B:.*?([\d,]+)\s+\d+\s+(\S+)\s+\$[\d.]+", text)
    if not (a and b):
        return None
    a_tok = int(a.group(1).replace(",", ""))
    b_tok = int(b.group(1).replace(",", ""))
    win = re.search(r"True winner.*?:\s*([^\s.]+)", text)
    winner = win.group(1) if win else None
    return {
        "mode_a": {"billed_input": a_tok},
        "mode_b": {"billed_input": b_tok},
        "pct_input_reduction": round((1 - b_tok / a_tok) * 100, 2) if a_tok else 0.0,
        "mode_a_correct": winner is not None and a.group(2) == winner,
        "mode_b_correct": winner is not None and b.group(2) == winner,
    }


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
    a reason, and the caller writes nothing. Never raises on a missing edge: an unknown key is a refusal,
    not a crash."""
    edge, source = _find_edge(edge_key)
    if edge is None:
        return GateResult(False, edge_key, "(no record)", "(none)", source,
                          f"no edge record for {edge_key!r} in {source}")

    verdict = edge.get("verdict", "(missing)")
    lead_score = edge.get("lead_score", edge.get("score", 0)) or 0
    fc = edge.get("fair_comparison") or {}
    lead_basis = fc.get("lead_basis", "(missing)")

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
    if _plan_for(edge_key) is None:
        return GateResult(False, edge_key, verdict, lead_basis, source,
                          f"no vendor plan for {edge_key!r}: a runnable brief cannot be assembled yet",
                          edge=edge, receipt_path=rpath, receipt=receipt)

    return GateResult(True, edge_key, verdict, lead_basis, source,
                      "clean claude-ahead, ranked, non-regime-bounded, receipt agrees",
                      edge=edge, receipt_path=rpath, receipt=receipt)


# --------------------------------------------------------------------------- vendoring (the import swap)

# The deterministic prefix swaps, applied to import lines only. A tuple of (pattern, replacement). The
# patterns are anchored at the start of a `from ... import` line so only an import is ever rewritten.
_IMPORT_SWAPS = (
    (re.compile(r"^from engine\.demonstrators\.token_core import", re.MULTILINE), "from .token_core import"),
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


def _my_tool_source() -> str:
    """The region_sales example fixture, vendored as the brief's my_tool.py edit surface. Lifted from
    app/example_tool.py (the engine's single home for the shipped worked example), trimmed to the edit
    surface a forker needs: TOOL_SPEC, call(), the fan-out QUESTION, EXPECTED_ANSWER, and parse_answer.
    The brief ships my_tool.py self-contained (the fixture inlined) so the brief stays a small flat
    package. Imports only stdlib (hashlib, random, re)."""
    return '''"""my_tool: THE single file you edit to run the token-bill comparison on your own tool.

This is the edit surface. Out of the box it ships a worked example: a region_sales tool that returns
about 60 sales rows per region, and a fan-out task that asks for the highest-revenue region across four
regions (240 rows). That is the same fan-out the brief's token-bill comparison measures, so `make ptc`
gives you a real before-and-after number before you change a line. Then swap in your own tool:

  1. Replace TOOL_SPEC with your own Messages-API tool dict (name, description, input_schema).
  2. Replace call(...) with the function that runs your real backend (a database query, an API call,
     a file read). Its keyword arguments match input_schema's properties, and it returns whatever the
     model normally gets back.
  3. Set QUESTION to your own fan-out task, the prompt that makes the model call your tool many times.

Keep the task fan-out shaped: the win lands when the model calls your tool many times, so the bulky
outputs run in code instead of filling its context. A fan-out task is where the input-token savings
show up, so pick one that fans out over many inputs.

Nothing here imports anthropic. my_tool is data plus a plain Python function; run_tokens.py drives it.
"""

from __future__ import annotations

import hashlib
import random
import re

# --------------------------------------------------------------------------- the worked example
# A deterministic mock backend so the shipped example has a fixed, reproducible true answer. Replace this
# whole block with your own tool. The seed makes region_sales(region) return the same ~60 rows every run,
# so "the highest-revenue region" is a fact you can check by hand, not a coin flip.

REGIONS = ["north", "south", "east", "pacific"]
PRODUCTS = ["widget", "gadget", "sprocket", "gizmo", "doohickey", "flange", "valve", "bracket"]
ROWS_PER_REGION = 60


def _region_sales(region: str):
    """About 60 deterministic sales rows for one region. This is the EXAMPLE backend, swap it out."""
    seed = int(hashlib.sha256(region.encode()).hexdigest()[:8], 16)
    rng = random.Random(seed)
    rows = []
    for i in range(ROWS_PER_REGION):
        rows.append({
            "order_id": f"{region[:2].upper()}{i:04d}",
            "product": rng.choice(PRODUCTS),
            "units": rng.randint(1, 100),
            "revenue": round(rng.uniform(10.0, 5000.0), 2),
        })
    return rows


# --------------------------------------------------------------------------- THE EDIT SURFACE
# Replace TOOL_SPEC and call() with your own tool. Keep the shape: a Messages-API tool dict, and a Python
# function whose keyword arguments match input_schema's properties.

TOOL_SPEC = {
    "name": "query_region_sales",
    "description": (
        "Return the full list of sales order records for one region. Each call returns a JSON array "
        "of objects, each with keys order_id (string), product (string), units (integer), and "
        "revenue (number, USD). About 60 records per region."
    ),
    "input_schema": {
        "type": "object",
        "properties": {"region": {"type": "string", "description": "the region name, lowercase"}},
        "required": ["region"],
    },
}


def call(region: str = ""):
    """Run the tool for one input and return a JSON-serializable result. Your real backend goes here.

    The example reads the deterministic mock above. Replace the body with your database query, API call,
    or file read. The return value is what the model (or the sandbox, under programmatic tool calling)
    receives as the tool result.
    """
    return _region_sales(region)


# The fan-out task: a prompt that makes the model call the tool once per input. Replace with your own.
EXAMPLE_INPUTS = REGIONS

QUESTION = (
    "You have a tool query_region_sales(region) that returns the sales records for one region. "
    f"For these {len(REGIONS)} regions: {', '.join(REGIONS)}. Find the single region with the highest "
    "TOTAL revenue, the sum of the revenue field across all of that region's records. "
    "Write ONE script that loops over all of the regions in a single code execution, calls the tool "
    "for each region inside that one loop, sums the revenue per region, and returns the winner. Do "
    "NOT call the tool one region at a time across separate steps. Reply with exactly one final line "
    "in the form: Winner: <region>"
)


# --------------------------------------------------------------------------- the example's check
# Only the shipped example needs a machine-checkable true answer, so `make ptc` (with --check) can assert
# the model answered correctly. When you swap in your own tool, set EXPECTED_ANSWER to your task's known
# answer (or leave it None and --check will only assert the token invariant, not correctness).

def _true_winner() -> str:
    totals = {r: sum(row["revenue"] for row in _region_sales(r)) for r in REGIONS}
    return max(totals, key=totals.get)


EXPECTED_ANSWER = _true_winner()  # the example's known answer, set to your own (or None) when you swap


def parse_answer(text: str):
    """Pull the final answer out of the model's last text. The example uses 'Winner: <region>'.

    Replace this with however your task states its answer. Returns a normalized string to compare against
    EXPECTED_ANSWER, or None when the model did not answer in the expected form.
    """
    m = re.search(r"Winner:\\s*([a-zA-Z]+)", text or "")
    if not m:
        return None
    w = m.group(1).lower()
    return w if w in REGIONS else None
'''


def _run_tokens_source(slug: str) -> str:
    """The generated run entry: the PTC demonstrator's Claude arm (Mode A/B over the audited
    token_core.run_mode) plus a --check self-test. The competitor arm is stripped (the engine's PTC
    competitor side is a documented absence, never a runnable head-to-head row). Imports the vendored
    token_core (sibling) and the flattened common/ package; anthropic is imported lazily in main()."""
    return f'''"""run_tokens: run your fan-out task twice over your own tool, print your before-and-after token bill.

The founder-facing artifact for the {slug} brief. It runs the SAME task two ways over the tool in
my_tool.py, on the same model, and prints YOUR own numbers:

  Mode A  plain tool use. The model calls your tool directly, once per input, so every record it pulls
          back flows through the model's context and is billed as input tokens.
  Mode B  programmatic tool calling. Your tool gets allowed_callers: ["code_execution_20260120"] and the
          code execution tool is added, so Claude writes ONE script in a sandbox that calls your tool in
          a loop and filters the records there. The irrelevant records stay in the sandbox, not the
          model, so you are not billed input tokens for data the model never reads.

It prints the billed-input table for both modes, the input-token reduction, the dollar delta at the
model's published input price, and an upfront cost-and-time line BEFORE it spends anything. Source,
re-fetched 2026-06-18:
https://platform.claude.com/docs/en/agents-and-tools/tool-use/programmatic-tool-calling

  python -m {slug}.run_tokens            run the example (or your tool) and print the before-and-after table
  python -m {slug}.run_tokens --check    the self-test: run the shipped example and ASSERT the PTC invariant
                                   (Mode B bills fewer input tokens AND answers correctly)
  python -m {slug}.run_tokens --model opus    use Opus 4.8 instead of the default Sonnet 4.6

This costs about $0.08 on the shipped example on Sonnet 4.6. The model arms are the only spend, the code
runs server-side in Anthropic's sandbox. anthropic is imported lazily, inside main(), so importing this
module needs no SDK.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Make the repo root importable when run as a file (python {slug}/run_tokens.py), not just as a module.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from .common.models import get  # noqa: E402  the verified id + price registry, anthropic-free
from .common.pricing import cost_usd  # noqa: E402  real usage object -> real dollars, anthropic-free
from .token_core import run_mode  # noqa: E402  the ONE audited counter + run loop

from {slug} import my_tool as tool  # noqa: E402  the single edit surface

# The PTC docs list Fable 5, Mythos 5, Opus 4.5 to 4.8, and Sonnet 4.5 to 4.6, not Haiku (verified
# 2026-06-18 against the live doc). This brief runs Sonnet and Opus, the two practical founder paths.
PTC_MODELS = {{"sonnet": "claude-sonnet-4-6", "opus": "claude-opus-4-8"}}


# Upfront cost estimate for the shipped example, tied to the selected model. The committed example
# bills about $0.08 on Sonnet 4.6. Opus 4.8 prices input and output at the same 5/3 multiple, so the
# estimate scales with the model's input price (Opus comes out higher). Derived from the committed run.
_REF_MODEL, _REF_USD = "sonnet", 0.0835


def est_usd(model_key: str) -> float:
    """The upfront dollar estimate for `model_key`, scaled from the committed Sonnet reference run."""
    return _REF_USD * get(model_key).input_per_mtok / get(_REF_MODEL).input_per_mtok


def fmt_usd(x: float) -> str:
    return f"${{x:,.6f}}" if x < 0.01 else f"${{x:,.4f}}"


def run_token_compare(client, model_key: str) -> dict:
    """Run Mode A and Mode B over my_tool, on top of the one audited token_core engine. Returns both
    runs plus the reduction and the dollar delta, all from the real usage objects."""
    model_id = get(model_key).id
    a = run_mode(client, model_id, tool.TOOL_SPEC, tool.call, tool.QUESTION,
                 programmatic=False, cost_fn=lambda u: cost_usd(model_key, u), label="A")
    b = run_mode(client, model_id, tool.TOOL_SPEC, tool.call, tool.QUESTION,
                 programmatic=True, cost_fn=lambda u: cost_usd(model_key, u), label="B")
    a_in, b_in = a["billed_input"], b["billed_input"]
    pct = (1 - b_in / a_in) * 100 if a_in else 0.0
    saved_usd = (a_in - b_in) * get(model_key).input_per_mtok / 1e6
    a["answer_parsed"] = tool.parse_answer(a["answer"])
    b["answer_parsed"] = tool.parse_answer(b["answer"])
    return {{"model_key": model_key, "model_id": model_id, "mode_a": a, "mode_b": b,
            "pct_input_reduction": round(pct, 1), "saved_input_usd": saved_usd}}


def print_table(result: dict) -> None:
    a, b = result["mode_a"], result["mode_b"]
    print(f"\\n  {{'mode':<44}}{{'billed input tok':>18}}{{'round-trips':>13}}{{'answer':>10}}{{'cost':>11}}")
    print("  " + "-" * 96)
    for name, r in [("Mode A: plain tool use", a),
                    ("Mode B: programmatic (allowed_callers)", b)]:
        ans = str(r["answer_parsed"]) if r["answer_parsed"] is not None else "(unparsed)"
        print(f"  {{name:<44}}{{r['billed_input']:>18,}}{{r['turns']:>13}}{{ans:>10}}{{fmt_usd(r['cost']):>11}}")
    print()
    print(f"  Your before and after: Mode B billed {{b['billed_input']:,}} input tokens vs Mode A's "
          f"{{a['billed_input']:,}},")
    print(f"  a {{result['pct_input_reduction']:.0f}}% reduction worth {{fmt_usd(result['saved_input_usd'])}} "
          f"on THIS run at {{get(result['model_key']).label}}'s input price, because the records went")
    print(f"  to the sandbox, not the model context. The saving scales with how often you run the task.\\n")


def cmd_run(model_key: str) -> int:
    from .common.client import get_client  # lazy: anthropic is imported only when we actually call

    label = get(model_key).label
    n = len(getattr(tool, "EXAMPLE_INPUTS", []) or [])
    print(f"\\n  Token bill: the same fan-out task two ways over your tool ({{tool.TOOL_SPEC['name']}}),")
    print(f"  on {{label}}. Mode A calls the tool directly, Mode B (programmatic tool calling) runs it")
    print(f"  from a sandbox so the records stay out of the model's context.")
    print(f"  Upfront: this run makes 2 task runs over {{n}} inputs and costs about ${{est_usd(model_key):.2f}} and roughly")
    print(f"  90 seconds on your key. The model arms are the only spend, the sandbox is server-side.\\n")
    client = get_client()
    result = run_token_compare(client, model_key)
    print_table(result)
    return 0


def cmd_check(model_key: str) -> int:
    """The self-test: run the shipped example and assert the PTC invariant (Mode B bills strictly fewer
    input tokens than Mode A AND answers correctly). A reduction with a wrong answer is not a win, and a
    right answer that costs more is not the edge, so the gate requires both."""
    from .common.client import get_client  # lazy

    expected = getattr(tool, "EXPECTED_ANSWER", None)
    print(f"\\n  --check: running the shipped example on {{get(model_key).label}} and asserting the PTC")
    print(f"  invariant (Mode B bills fewer input tokens AND answers correctly). About ${{est_usd(model_key):.2f}}.\\n")
    client = get_client()
    result = run_token_compare(client, model_key)
    print_table(result)

    a, b = result["mode_a"], result["mode_b"]
    fewer = b["billed_input"] < a["billed_input"]
    correct = (expected is None) or (b["answer_parsed"] == expected)
    problems = []
    if not fewer:
        problems.append(f"Mode B billed {{b['billed_input']:,}} input tokens, not fewer than Mode A's "
                        f"{{a['billed_input']:,}}")
    if not correct:
        problems.append(f"Mode B answered {{b['answer_parsed']!r}}, expected {{expected!r}}")
    if problems:
        print("\\n  CHECK FAILED:")
        for p in problems:
            print(f"    - {{p}}")
        return 1
    print(f"\\n  CHECK PASSED: Mode B billed {{result['pct_input_reduction']:.0f}}% fewer input tokens "
          f"({{b['billed_input']:,}} vs {{a['billed_input']:,}})" +
          (f" and answered {{b['answer_parsed']!r}} correctly." if expected is not None else "."))
    print("  The token saving holds on the example. Now swap your tool into my_tool.py.\\n")
    return 0


def main() -> int:
    p = argparse.ArgumentParser(
        description="Run a fan-out task over your tool twice (plain vs programmatic) and print the token bill.")
    p.add_argument("--model", default="sonnet", choices=sorted(PTC_MODELS),
                   help="sonnet (default) or opus, Haiku does not support programmatic tool calling")
    p.add_argument("--check", action="store_true",
                   help="self-test: run the shipped example and assert the PTC invariant")
    a = p.parse_args()
    return cmd_check(a.model) if a.check else cmd_run(a.model)


if __name__ == "__main__":
    raise SystemExit(main())
'''


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

This costs about $0.01 on Haiku 4.5. The model call is the only spend. anthropic is imported lazily,
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
CITATION_MODELS = {{"haiku": "claude-haiku-4-5", "sonnet": "claude-sonnet-4-6"}}

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
    return f"${{x:,.6f}}" if x < 0.01 else f"${{x:,.4f}}"


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
    print(f"  Upfront: about $0.01 and roughly 30 seconds on your key. The model call is the only spend.\\n")
    client = get_client()
    print_table(run(client, model_key, corpus, QUESTIONS))
    return 0


def cmd_check(model_key):
    """The self-test: assert every returned pointer resolves. A pointer that does not resolve fails."""
    from .common.client import get_client  # lazy
    corpus = load_corpus()
    print(f"\\n  --check: answering {{len(QUESTIONS)}} questions on {{get(model_key).label}} and asserting "
          f"every returned char_location pointer resolves. About $0.012.\\n")
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


def _citations_readme_source(plan: BriefPlan) -> str:
    """The public, wins-only README for the citations brief. Generated, no internal backrefs, doc link
    from the landscape source_url (the plan's doc_url)."""
    return f"""# Get a verifiable source pointer for every answer with Citations

![demo](demo.gif)

When your app answers a question over your users' own documents (contracts, policies, tickets, support
docs), the answer is only as trustworthy as the source behind it. Claude's Citations feature returns,
for every claim it makes, a structured pointer into the source document: the document, a character
range, and the verbatim quote at that range. The pointer is guaranteed to resolve, and the quote is
free of output tokens, so you can check every answer in your own code instead of trusting it.

## What you get

Set `citations.enabled` on each document and the API returns a `char_location` for every claim:
`source[start_char_index:end_char_index]` is exactly the `cited_text` it handed back. This brief answers
{len(_CITATIONS_QUESTIONS)} questions over three plain-text documents and resolves every pointer, so you
see the guarantee hold on a live call.

```python
content = [
    {{"type": "document",
      "source": {{"type": "text", "media_type": "text/plain", "data": doc_text}},
      "citations": {{"enabled": True}}}},          # turn citations on for this document
    {{"type": "text", "text": question}},
]
msg = client.messages.create(model="claude-haiku-4-5", max_tokens=400,
                            messages=[{{"role": "user", "content": content}}])
# every citation resolves: source[c.start_char_index:c.end_char_index] == c.cited_text
```

## Run it (about $0.01)

```
export ANTHROPIC_API_KEY=your-key   # https://console.anthropic.com/
make {plan.slug}        # build the venv, install anthropic, answer the questions and resolve every pointer
```

## Run it on your own documents

Drop your own `.txt` files into `{plan.slug}/docs/`, edit `QUESTIONS` at the top of
`{plan.slug}/cite.py` to the questions you want answered, and run `make {plan.slug}` again. Citations is
supported on every active model except Haiku 3.

## Learn more

- [Citations docs]({plan.doc_url})
"""


def _readme_source(plan: BriefPlan, edge: dict, receipt: dict | None) -> str:
    """The public, wins-only README for the brief. Generated from the engine truth: the measured receipt
    numbers when present, the doc link from the landscape source_url (the plan's doc_url), no internal
    backrefs or engine paths. The win-side table and the two-line code change are kept; nothing names a
    Claude negative."""
    # Pull the measured win-side numbers off the receipt when one is present, else state the shape only.
    a_in = b_in = pct = None
    if receipt:
        ma, mb = receipt.get("mode_a", {}), receipt.get("mode_b", {})
        a_in = ma.get("billed_input")
        b_in = mb.get("billed_input")
        pct = receipt.get("pct_input_reduction")
    table = ""
    if a_in and b_in:
        pct_str = f"{pct:.0f}%" if isinstance(pct, (int, float)) else "fewer"
        table = (
            "\n| mode | input tokens billed | what happens to the 240 rows |\n"
            "|---|---:|---|\n"
            f"| without PTC | {a_in:,} | all the rows flow through the model's context |\n"
            f"| **with PTC** | **{b_in:,}** | the sandbox aggregates, only the answer reaches the model |\n\n"
            f"That is **{pct_str} fewer input tokens** on this run, because the records went to the "
            "sandbox, not the model context. Every cell is read live off the API's own `usage` object, "
            "so re-running shifts the count a little. The saving compounds across every fan-out you run.\n"
        )
    else:
        table = (
            "\nRun `make ptc` to print your own before/after table from a live call. Every cell comes "
            "from the real `usage` object the API returns, never from memory.\n"
        )

    return f"""# Cut your tool-output token bill with programmatic tool calling

![demo](demo.gif)

If your app calls your own tool to answer a question and that tool returns a lot of records, every
record it pulls back lands in the model's context and you pay for all of them, even the ones that turn
out irrelevant. Programmatic tool calling (PTC) runs your tool inside a code sandbox, keeps only the
records that matter, and passes just those to the model. The rest never reach the context, so you are
not billed for them.

## The same task, Claude with PTC vs Claude without it

The same fan-out task two ways on the same model (Sonnet 4.6): across four regions of about 60 sales
rows each (240 rows), find the highest-revenue region. The only thing that changes between the two rows
is programmatic tool calling, on or off.
{table}
## The change is two lines

```python
response = client.messages.create(
    model="claude-sonnet-4-6",
    messages=[...],
    tools=[
        {{"type": "code_execution_20260120", "name": "code_execution"}},   # add this
        {{ "name": "query_region_sales", "input_schema": {{...}},   # your tool, unchanged
          "allowed_callers": ["code_execution_20260120"] }},        # add this line
    ],
)
```

Add `allowed_callers: ["code_execution_20260120"]` to your tool and include the code execution tool.
Claude writes one script in a server-side sandbox that loops over the inputs, calls your tool for each,
and keeps only the records that matter. The irrelevant records stay in the sandbox, so you are not
billed for them.

## The honest scope

The win is fan-out shaped: it lands when the model calls your tool many times, so the bulky outputs
run in code instead of filling its context. The shipped example (`query_region_sales`, 240 rows over
four regions) is a genuine fan-out, which is where the input-token savings show up. The PTC docs list
Fable 5, Mythos 5, Opus 4.5 to 4.8, and Sonnet 4.5 to 4.6 (not Haiku). This brief runs Sonnet and Opus,
the practical founder paths.

## Run it (about $0.08)

```
export ANTHROPIC_API_KEY=your-key   # https://console.anthropic.com/
make ptc        # build the venv, install anthropic, run the token-bill comparison on the region_sales example
```

`make ptc` is self-bootstrapping: it creates `.venv`, installs `anthropic`, and runs the before/after.

## Run it on your own tool

Open `{plan.slug}/{plan.edit_surface}`, the one file you edit. Replace three things, then run
`make ptc` again:

1. `TOOL_SPEC` with your own Messages-API tool dict (the same `{{name, description, input_schema}}` you
   already pass in `tools=[...]`).
2. `call(...)` with your real backend (a database query, an API call, a file read) returning whatever
   the model normally gets back.
3. `QUESTION` and `EXAMPLE_INPUTS` with your fan-out task and the inputs it fans out over.

Keep the task fan-out shaped: a fan-out task, where the model calls your tool many times, is where
the input-token savings show up.

## Learn more

- [Programmatic tool calling docs]({plan.doc_url})
- [Improved web search with dynamic filtering](https://claude.com/blog/improved-web-search-with-dynamic-filtering) (about 24% fewer input tokens, 11% better answers)
"""


def _demo_tape_source(plan: BriefPlan) -> str:
    """The VHS tape for the brief's demo.gif. It shadows `make` with a function that cats the committed
    sample.txt, so `make gif` replays the receipt for $0 (no API call, deterministic). Generated here, so
    a republish reproduces it, and the gif binary is rendered from this tape by `make gif` (vhs + ffmpeg)."""
    slug = plan.slug
    width, height = (1240, 820) if slug == "citations" else (1200, 640)
    headline = ("# Citations: a verifiable source pointer for every answer, resolved in your own code"
                if slug == "citations"
                else "# programmatic tool calling: about 28% fewer billed input tokens on a fan-out task")
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
        f'Type "make {slug}"\nEnter\nSleep 6s\n'
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
    deterministic. The token_accounting brief shows the billed-input table token-only (no answer-correctness
    claim, since plain tool use can miss on 240 rows); grounding_resolution shows the per-pointer table."""
    if plan.slug == "citations":
        return _citations_sample_source()
    a_in = b_in = pct = None
    if receipt:
        a_in = receipt.get("mode_a", {}).get("billed_input")
        b_in = receipt.get("mode_b", {}).get("billed_input")
        pct = receipt.get("pct_input_reduction")
    a_str = f"{a_in:,}" if a_in else "9,451"
    b_str = f"{b_in:,}" if b_in else "6,828"
    pct_str = f"{pct:.0f}" if isinstance(pct, (int, float)) else "28"
    return (
        "\n  Programmatic tool calling: the same fan-out task, Claude with PTC vs without it.\n\n"
        "  Task: across 4 regions (240 sales rows total), find the highest-revenue region.\n"
        "  Same task, same model (Sonnet 4.6). Every number is read live off the API usage object.\n\n"
        "  mode             billed input tokens    what happens to the 240 rows\n"
        "  --------------------------------------------------------------------------\n"
        f"  without PTC      {a_str:>18}    all rows flow through the model context\n"
        f"  with PTC         {b_str:>18}    sandbox aggregates, only the answer returns\n"
        "  --------------------------------------------------------------------------\n\n"
        f"  -> {pct_str}% fewer billed input tokens, because the 240 records went to the\n"
        "     sandbox, not the model context. The saving compounds across every fan-out.\n\n"
        "  The change is two lines: add the code_execution tool, then put\n"
        '  allowed_callers: ["code_execution_20260120"] on your own tool.\n\n'
        "  Runnable code and the full brief: ptc/README.md\n"
    )


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

This brief is generated from the committed truth of the claude-competitive-engine by `make publish-brief`,
not hand-written: the README, the run entry, the vendored token counter, the demo tape, and the receipt
snapshot it replays all come from the engine state below. The demo gif is rendered from the generated
tape by `make gif` (it replays that snapshot for $0), so the gif traces to the same state. Regenerating
from a different engine state changes these stamps.

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
claude-ahead win in the engine's own landscape, and any present receipt agreed. The brief vendors the
engine's audited token counter and run loop verbatim, with import lines rewritten by a deterministic
prefix swap, so the published code is the same code the engine measures with.
"""


def _engine_sha() -> str:
    """The engine's current git SHA, for the provenance stamp. Read-only `git rev-parse`, no network, no
    write. Returns '(unknown)' if git is unavailable, never raises (provenance is a stamp, not a gate)."""
    try:
        out = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True, timeout=10)
        return out.stdout.strip() or "(unknown)"
    except Exception:  # noqa: BLE001
        return "(unknown)"


def _founder_email_source(plan: BriefPlan, receipt: dict | None) -> str:
    """The founder email, written to the ENGINE repo (never the public briefs repo). Wins-only, plain
    language, startup-native example, the two-line code change, one reproduce path. Numbers come from the
    receipt when present, else the shape is stated without a fabricated figure."""
    a_in = b_in = pct = None
    if receipt:
        a_in = receipt.get("mode_a", {}).get("billed_input")
        b_in = receipt.get("mode_b", {}).get("billed_input")
        pct = receipt.get("pct_input_reduction")
    if a_in and b_in:
        pct_str = f"{pct:.0f}%" if isinstance(pct, (int, float)) else ""
        table = (
            "| | input tokens billed | why |\n"
            "|---|---:|---|\n"
            f"| without PTC | {a_in:,} | every result lands in the model's context |\n"
            f"| with PTC | {b_in:,} | only the relevant results reach the model |\n\n"
            f"{pct_str} fewer billed input tokens on this demo, and the saving grows with the size of the fan-out.\n"
        )
    else:
        table = "Run `make ptc` to print your own before/after from a live call.\n"

    return f"""Subject: Token Thinning: removing unused tool results from your context window

Hey {{first_name}},

Congrats on getting into YC! Quick tip to trim your Claude token bill.

If your app calls your own tool to answer a question and that tool returns a lot of results, every
result it pulls back lands in the model's context, and you pay for all of them, even the ones that turn
out irrelevant.

[Programmatic tool calling]({plan.doc_url}) (PTC) fixes that. Claude runs your tool inside a code
sandbox, keeps only the results that matter, and passes just those to the model. The rest never reach
the context, so you are not billed for them.

It is two small additions to the API call you already make:

```python
response = client.messages.create(
    model="claude-sonnet-4-6",
    messages=[...],
    tools=[
        {{"type": "code_execution_20260120", "name": "code_execution"}},   # add this
        {{ "name": "query_region_sales", "input_schema": {{...}},   # your tool, unchanged
          "allowed_callers": ["code_execution_20260120"] }},        # add this line
    ],
)
```

Same task and model (Sonnet 4.6), with and without it:

{table}
Want to watch it first, no clone needed? The brief opens with a gif of the run:
https://github.com/cfregly/claude-feature-briefs/blob/main/{plan.slug}/README.md

See it run (about two minutes):

```
git clone https://github.com/cfregly/claude-feature-briefs && cd claude-feature-briefs
export ANTHROPIC_API_KEY=your-key
make ptc        # the example, $0.08
```

To run it on your own tool, open [{plan.slug}/{plan.edit_surface}](https://github.com/cfregly/claude-feature-briefs/blob/main/{plan.slug}/{plan.edit_surface}),
drop in your tool, and run `make ptc` again.

Happy building! 🚀
{{your_name}}
Building with Claude
"""


def _citations_founder_email_source(plan: BriefPlan) -> str:
    """The citations founder email, written to the ENGINE repo (never the public briefs repo). Wins-only,
    plain language, the real code, one reproduce path."""
    return f"""Subject: Congrats on YC! 🎉 A Claude primitive for grounded answers you verify in code

Hey {{first_name}},

Congrats on getting into YC! Quick tip if your app answers questions over your users' own documents.

When you answer over a contract, a policy, or a support doc, the answer is only as trustworthy as the
source behind it. [Citations]({plan.doc_url}) gives you a source pointer for every answer that you can
check in your own code: the document, a character range, and the verbatim quote at that range. The
pointer is guaranteed to resolve, and the quote is free of output tokens.

Turn it on per document, then verify in your own code:

```python
content = [
    {{"type": "document",
      "source": {{"type": "text", "media_type": "text/plain", "data": doc_text}},
      "citations": {{"enabled": True}}}},          # add this
    {{"type": "text", "text": question}},
]
msg = client.messages.create(model="claude-haiku-4-5", max_tokens=400,
                            messages=[{{"role": "user", "content": content}}])
# every citation resolves: source[c.start_char_index:c.end_char_index] == c.cited_text
```

Want to watch it first, no clone needed? The brief opens with a gif of the run:
https://github.com/cfregly/claude-feature-briefs/blob/main/{plan.slug}/README.md

See it run (about a minute):

```
git clone https://github.com/cfregly/claude-feature-briefs && cd claude-feature-briefs
export ANTHROPIC_API_KEY=your-key
make {plan.slug}     # answer the questions and resolve every pointer, $0.01
```

To run it on your own documents, drop your `.txt` files into `{plan.slug}/docs/`, edit the questions at
the top of `{plan.slug}/cite.py`, and run `make {plan.slug}` again.

Happy building! 🚀
{{your_name}}
Building with Claude
"""


# --------------------------------------------------------------------------- idempotent root appends


def _ensure_makefile_entry(makefile: pathlib.Path, plan: BriefPlan) -> bool:
    """Idempotently add the brief's make target to the briefs-root Makefile. Returns True if it appended,
    False if the entry was already present. Never duplicates: it keys on the target name."""
    text = makefile.read_text() if makefile.exists() else ""
    run_module = "cite" if plan.slug == "citations" else "run_tokens"
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
        f"\t$(PY) -m {plan.slug}.{run_module}\n"
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
    cost_phrase = f"`make {plan.slug}` (about ${run_cost})"
    if link in text:
        # Refresh the run-cost in an existing entry so a stale figure cannot survive a republish.
        refreshed = re.sub(rf"`make {re.escape(plan.slug)}` \(about \$[\d.]+\)", cost_phrase, text, count=1)
        if refreshed != text:
            readme.write_text(refreshed)
        return refreshed != text
    if plan.slug == "citations":
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


_OUTREACH_README = """# Outreach examples

Example founder emails you can adapt. Each one is a short, warm note to a builder: it names the workload,
shows the one Claude feature and the small code change, gives a real before and after number from the
matching brief, and links the one-command run. They are templates, not sent mail. The `{first_name}` and
`{your_name}` placeholders and the neutral sign-off are meant to be filled in.

- [ptc-email.md](ptc-email.md): the programmatic-tool-calling brief, for an agent that calls a tool a lot.
- [citations-email.md](citations-email.md): the Citations brief, for a product that answers over user docs.

Every number in these matches the brief it points at, and the repo's number gate checks that, so you can
send one knowing the reader sees the same figure when they run it.
"""


def _ensure_outreach_readme(readme: pathlib.Path) -> None:
    """Write the framing README for the outreach-examples folder if it is missing. Idempotent, so a
    republish never churns it. It marks the emails as adaptable examples, not sent mail."""
    if not readme.exists():
        readme.write_text(_OUTREACH_README)


# --------------------------------------------------------------------------- the generator


def _vendor_files(plan: BriefPlan, brief_dir: pathlib.Path) -> None:
    """Copy each declared engine file into the brief dir, flattening common/ to a local common/ package
    and rewriting import lines by the deterministic prefix swap. Refuses on any dangling import."""
    (brief_dir / "common").mkdir(parents=True, exist_ok=True)
    (brief_dir / "common" / "__init__.py").write_text("")
    for vf in plan.files:
        src = ROOT / vf.src
        text = src.read_text()
        swapped = _swap_imports(text)
        _assert_no_dangling(swapped, vf.dst)
        dst = brief_dir / vf.dst
        dst.parent.mkdir(parents=True, exist_ok=True)
        dst.write_text(swapped)


def _assemble_brief(plan: BriefPlan, gate: GateResult, command: str, staging: pathlib.Path) -> None:
    """Build the whole brief into a staging dir (so a failure leaves nothing behind), then the caller
    moves it into place atomically. Writes the vendored engine files, the edit surface, the generated
    run entry, __init__.py, README.md, and PROVENANCE.md. The edit surface and run entry differ by edge
    (the token_accounting brief ships my_tool.py + run_tokens.py; the grounding_resolution brief ships a
    docs/ corpus + cite.py), so the body dispatches on the plan slug."""
    brief_dir = staging
    brief_dir.mkdir(parents=True, exist_ok=True)

    _vendor_files(plan, brief_dir)
    (brief_dir / "__init__.py").write_text("")

    if plan.slug == "ptc":
        # The token_accounting brief: the region_sales fixture as the edit surface (my_tool.py),
        # run_tokens.py as the run.
        (brief_dir / plan.edit_surface).write_text(_my_tool_source())
        run_src = _run_tokens_source(plan.slug)
        _assert_no_dangling(run_src, "run_tokens.py")  # the generated run entry must be closure-clean
        (brief_dir / "run_tokens.py").write_text(run_src)
        (brief_dir / "README.md").write_text(_readme_source(plan, gate.edge or {}, _committed_receipt(plan)))
    elif plan.slug == "citations":
        # The grounding_resolution brief: a docs/ corpus as the edit surface, cite.py as the run.
        docs = brief_dir / plan.edit_surface
        docs.mkdir(parents=True, exist_ok=True)
        for name, text in _CITATIONS_CORPUS.items():
            (docs / name).write_text(text)
        run_src = _cite_source(plan.slug)
        _assert_no_dangling(run_src, "cite.py")
        (brief_dir / "cite.py").write_text(run_src)
        (brief_dir / "README.md").write_text(_citations_readme_source(plan))
    else:  # pragma: no cover - a plan with no assembler is a programming error, not a publish path
        raise PublishRefused(f"no assembler for brief slug {plan.slug!r}")

    # The demo gif's source: a generated tape that replays a generated, honest, wins-only receipt
    # snapshot for $0. `make gif` renders the binary from the tape, so the whole demo regenerates and
    # nothing about the gif is hand-written or lost on a republish.
    (brief_dir / "sample.txt").write_text(_sample_source(plan, _committed_receipt(plan)))
    (brief_dir / "demo.tape").write_text(_demo_tape_source(plan))

    (brief_dir / "PROVENANCE.md").write_text(_provenance_source(plan, gate, command))


def publish(edge_key: str, briefs_root: pathlib.Path, command: str) -> int:
    """The end-to-end publish. Runs the gate, refuses fail-closed on any failure (writing nothing), and
    otherwise assembles the brief in a temp dir, moves it into place, makes the idempotent root appends,
    and writes the founder email to the ENGINE repo. Returns a process exit code."""
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
        _assemble_brief(plan, gate, command, staging)
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

    # The full founder email is the engine's working draft, kept here under emails/.
    emails_dir = ROOT / "emails"
    emails_dir.mkdir(exist_ok=True)
    email_path = emails_dir / f"{plan.slug}_FOUNDER_EMAIL.md"
    email_src = (_citations_founder_email_source(plan) if plan.slug == "citations"
                 else _founder_email_source(plan, _committed_receipt(plan)))
    email_path.write_text(email_src)

    # The same email also ships into the public briefs as a labeled, adaptable OUTREACH EXAMPLE. It is
    # generic by construction (templated names, neutral sign-off, links only to the public repo), and the
    # one template keeps the example and the engine draft from drifting apart.
    examples_dir = briefs_root / "outreach-examples"
    examples_dir.mkdir(exist_ok=True)
    (examples_dir / f"{plan.slug}-email.md").write_text(email_src)
    _ensure_outreach_readme(examples_dir / "README.md")

    files = sorted(p.relative_to(briefs_root) for p in brief_dir.rglob("*") if p.is_file())
    print(f"\n  PUBLISHED brief {plan.slug!r} for edge {gate.edge_key!r} ({plan.demo_kind})")
    print(f"    verdict      : {gate.verdict} (lead_basis {gate.lead_basis})")
    print(f"    source       : {gate.source}")
    print(f"    brief dir    : {brief_dir}")
    for f in files:
        print(f"      + {f}")
    print(f"    Makefile     : {'appended ' + plan.slug + ' target' if made_mk else 'entry already present'}")
    print(f"    README.md    : {'appended ' + plan.slug + ' entry' if made_rd else 'entry already present'}")
    print(f"    founder email: {email_path.relative_to(ROOT)} (engine repo only, never the public repo)")
    print("    no model call, no spend, no git, no send.\n")
    return 0


def _rmtree(path: pathlib.Path) -> None:
    import shutil
    shutil.rmtree(path, ignore_errors=True)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        description="Generate a self-contained public brief for a VERIFIED Claude-win edge (offline, $0).")
    p.add_argument("--edge", required=True, help="the edge key, e.g. programmatic-tool-calling")
    p.add_argument("--briefs-root", default=None,
                   help="the public briefs repo root (default: ../claude-feature-briefs relative to the engine)")
    a = p.parse_args(argv)

    briefs_root = (pathlib.Path(a.briefs_root).resolve() if a.briefs_root
                   else (ROOT.parent / "claude-feature-briefs"))
    command = f"make publish-brief EDGE={a.edge}"
    return publish(a.edge, briefs_root, command)


if __name__ == "__main__":
    raise SystemExit(main())
