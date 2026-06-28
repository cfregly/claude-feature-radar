"""Number-consistency gate for the promoted public surface.

This repo is intentionally small: promoted feature artifacts only. Held receipts and other
preflights live outside the public surface, so this gate checks only artifacts a founder can run from
this repo.
"""

from __future__ import annotations

import json
import pathlib
import re
import sys


ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
from artifact_manifest import active_slugs, load, removed_slugs  # noqa: E402

CANON_COST = {
    row.get("make_target", slug): str(row.get("cost_usd"))
    for slug, row in load().get("artifacts", {}).items()
    if row.get("status") == "active" and row.get("cost_usd")
}
CANON_COST["check"] = "0.08"

DIMENSIONS = ("Cost", "Speed", "Accuracy", "Reliability", "Operations", "Security")


def _read(rel: str) -> str:
    p = ROOT / rel
    return p.read_text(encoding="utf-8") if p.exists() else ""


def _need(rel: str, needle: str, fail: list[str], why: str) -> None:
    if needle not in _read(rel):
        fail.append(f"{rel}: missing {why}: {needle!r}")


def _close(a: str, b: str) -> bool:
    try:
        return abs(float(a) - float(b)) <= 0.015
    except ValueError:
        return a == b


def check_make_costs(fail: list[str]) -> None:
    cost_re = re.compile(r"make ([a-z][a-z0-9_-]*)\b[^\n]*?\$+([\d.]+)")
    surfaces = ["README.md", "Makefile"] + [str(p.relative_to(ROOT)) for p in sorted(ROOT.glob("*/README.md"))]
    for rel in surfaces:
        text = _read(rel)
        for m in cost_re.finditer(text):
            target, cost = m.group(1), m.group(2)
            want = CANON_COST.get(target)
            if want and not _close(cost, want):
                fail.append(f"{rel}: `make {target}` quotes ${cost}, canonical is ${want}")


def check_pillars(fail: list[str]) -> None:
    for pillar in DIMENSIONS:
        _need("README.md", f"**{pillar}**:", fail, f"{pillar} pillar")
    _need("README.md", "Dimension matrix", fail, "dimension matrix discipline")
    _need("README.md", "not measured", fail, "not measured dimension language")
    _need("README.md", "not claimed", fail, "not claimed dimension language")
    _need("README.md", "Promotion difficulty", fail, "candidate difficulty explanation")
    _need("README.md", "easy to port, not easy to pass", fail, "easy candidate definition")
    _need("README.md", "No promoted artifact yet", fail, "empty pillar language")


def check_dimension_matrices(fail: list[str]) -> None:
    for slug in active_slugs():
        rel = f"{slug}/README.md"
        _need(rel, "## Dimension matrix", fail, f"{slug} dimension matrix")
        for dimension in DIMENSIONS:
            _need(rel, f"| {dimension} |", fail, f"{slug} {dimension} dimension row")


def check_programmatic_tool_calling(fail: list[str]) -> None:
    sample = _read("programmatic_tool_calling/sample.txt")
    plain = re.search(r"without programmatic tool calling\s+([\d,]+)", sample)
    programmatic = re.search(r"with programmatic tool calling\s+([\d,]+)", sample)
    if not (plain and programmatic):
        fail.append("programmatic_tool_calling/sample.txt: cannot parse programmatic tool calling token rows")
        return

    plain_tokens, programmatic_tokens = plain.group(1), programmatic.group(1)
    pct = round((1 - int(programmatic_tokens.replace(",", "")) / int(plain_tokens.replace(",", ""))) * 100)
    for rel in ["README.md", "programmatic_tool_calling/README.md", "programmatic_tool_calling/sample.txt"]:
        text = _read(rel)
        for m in re.finditer(r"\b([69],\d{3})\b", text):
            if m.group(1) not in (plain_tokens, programmatic_tokens):
                fail.append(f"{rel}: token {m.group(1)} is not the receipt's {plain_tokens}/{programmatic_tokens}")
    _need("programmatic_tool_calling/README.md", f"{pct}% fewer input tokens", fail, "programmatic tool calling reduction")
    _need("programmatic_tool_calling/README.md", "## Reducer eval gate", fail, "programmatic tool calling reducer eval section")
    _need("programmatic_tool_calling/README.md", "scripts/check_reducer_contract.py", fail, "programmatic tool calling reducer eval gate")
    _need("programmatic_tool_calling/README.md", "scripts/check_trace_contract.py", fail, "programmatic tool calling trace eval gate")
    _need("programmatic_tool_calling/README.md", "expected caller path", fail, "programmatic tool calling README trace gate")
    _need("programmatic_tool_calling/README.md", "observed server-tool block", fail, "programmatic tool calling README server block gate")
    _need("programmatic_tool_calling/sample.txt", "Estimated token/API run cost: $0.08.", fail, "programmatic tool calling receipt cost")
    _need("programmatic_tool_calling/sample.txt", "Token/API dollars include weighted cache buckets", fail, "programmatic tool calling cache-bucket cost scope")
    _need("programmatic_tool_calling/sample.txt", "Code execution runtime can bill separately", fail, "programmatic tool calling runtime caveat")
    _need("programmatic_tool_calling/sample.txt", "$0.0042", fail, "programmatic tool calling code-execution runtime floor")
    _need("programmatic_tool_calling/sample.txt", "Trace summary:", fail, "programmatic tool calling trace summary")
    _need("programmatic_tool_calling/sample.txt", "caller_path=code_execution_20260120", fail, "programmatic tool calling code-execution caller trace")
    _need("programmatic_tool_calling/sample.txt", "raw_tool_bytes=", fail, "programmatic tool calling raw-byte trace")
    _need("programmatic_tool_calling/sample.txt", "final_bytes=", fail, "programmatic tool calling final-byte trace")
    _need("programmatic_tool_calling/sample.txt", "server_tool_blocks=", fail, "programmatic tool calling observed server-tool block trace")
    _need("programmatic_tool_calling/sample.txt", "caller_path_drift=False", fail, "programmatic tool calling caller-path drift trace")
    _need("programmatic_tool_calling/sample.txt", "Trace gate: PASS", fail, "programmatic tool calling trace gate pass")
    _need("programmatic_tool_calling/sample.txt", "correctness=True", fail, "programmatic tool calling correctness trace")

    try:
        receipt = json.loads((ROOT / "programmatic_tool_calling_cache_context" / "receipt.json").read_text(encoding="utf-8"))
        basis = receipt["basis"]["programmatic_tool_calling_receipt"]
    except Exception as exc:  # noqa: BLE001
        fail.append(f"programmatic_tool_calling_cache_context/receipt.json: cannot read programmatic tool calling basis: {exc}")
    else:
        plain_int = int(plain_tokens.replace(",", ""))
        programmatic_int = int(programmatic_tokens.replace(",", ""))
        pct_one_decimal = round((1 - programmatic_int / plain_int) * 100, 1)
        if basis["source"] != "programmatic_tool_calling/sample.txt":
            fail.append("programmatic_tool_calling_cache_context/receipt.json: programmatic tool calling basis must point to programmatic_tool_calling/sample.txt")
        if basis["plain_tool_use_billed_input_tokens"] != plain_int:
            fail.append("programmatic_tool_calling_cache_context/receipt.json: programmatic tool calling basis plain tokens do not match sample.txt")
        if basis["programmatic_tool_calling_billed_input_tokens"] != programmatic_int:
            fail.append("programmatic_tool_calling_cache_context/receipt.json: programmatic tool calling basis programmatic tokens do not match sample.txt")
        if basis["input_reduction_pct"] != pct_one_decimal:
            fail.append("programmatic_tool_calling_cache_context/receipt.json: programmatic tool calling basis reduction does not match sample.txt")

    for rel in ["programmatic_tool_calling/README.md", "programmatic_tool_calling/sample.txt"]:
        if re.search(r"(without programmatic tool calling|plain tool use)[^\n|]*\bcorrect\b", _read(rel)):
            fail.append(f"{rel}: claims plain tool use was correct")


def check_programmatic_tool_calling_cache_context(fail: list[str]) -> None:
    receipt_path = ROOT / "programmatic_tool_calling_cache_context" / "receipt.json"
    try:
        receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001
        fail.append(f"programmatic_tool_calling_cache_context/receipt.json: cannot read receipt: {exc}")
        return

    scenarios = receipt["scenarios"]
    cliff = receipt["cliff"]
    expected = {
        "claude_no_cache_no_programmatic": 270.45,
        "claude_cache_no_programmatic": 85.44,
        "openai_best_cache_1m_no_programmatic": 135.55,
        "gemini_best_cache_1m_no_programmatic": 40.67,
        "claude_cache_programmatic": 26.04,
    }
    for key, want in expected.items():
        got = scenarios[key]["total_usd"]
        if got != want:
            fail.append(f"programmatic_tool_calling_cache_context/receipt.json: {key} total {got}, expected {want}")

    if cliff["savings_vs_openai_best_cache_no_programmatic_usd"] != 109.51:
        fail.append("programmatic_tool_calling_cache_context/receipt.json: expected $109.51 GPT-5.5 savings")
    if cliff["reduction_vs_openai_best_cache_no_programmatic_pct"] != 80.8:
        fail.append("programmatic_tool_calling_cache_context/receipt.json: expected 80.8% GPT-5.5 reduction")
    if cliff["savings_vs_gemini_best_cache_no_programmatic_usd"] != 14.63:
        fail.append("programmatic_tool_calling_cache_context/receipt.json: expected $14.63 Gemini savings")
    if cliff["reduction_vs_gemini_best_cache_no_programmatic_pct"] != 36.0:
        fail.append("programmatic_tool_calling_cache_context/receipt.json: expected 36.0% Gemini reduction")

    for rel in ["README.md", "programmatic_tool_calling_cache_context/README.md", "programmatic_tool_calling_cache_context/sample.txt"]:
        for needle in ["$26.04", "$135.55", "$40.67", "$109.51", "$14.63", "80.8%", "36.0%"]:
            _need(rel, needle, fail, "programmatic tool calling cache-context cost cliff")
        _need(rel, "$0.0042", fail, "programmatic tool calling cache-context runtime floor scope")
    _need("programmatic_tool_calling_cache_context/README.md", "$0, no API call", fail, "programmatic tool calling cache-context deterministic run cost")
    _need("programmatic_tool_calling_cache_context/sample.txt", "does not call any model or require an API key", fail, "programmatic tool calling cache-context no API call")
    _need("programmatic_tool_calling_cache_context/sample.txt", "committed 74% basis", fail, "programmatic tool calling cache-context committed basis check")
    _need("programmatic_tool_calling_cache_context/compare_cache_context_programmatic.py", "validate_receipt", fail, "programmatic tool calling cache-context deterministic receipt validation")
    _need("programmatic_tool_calling_cache_context/receipt.json", "gemini_best_cache_1m_no_programmatic", fail, "programmatic tool calling cache-context Gemini scenario")
    _need("programmatic_tool_calling_cache_context/receipt.json", "competitor_best_stacks", fail, "programmatic tool calling cache-context multi-competitor basis")
    _need("README.md", "observed server-tool block", fail, "top-level programmatic tool calling trace gate")
    _need("programmatic_tool_calling_cache_context/compare_cache_context_programmatic.py", "CHECK PASSED", fail, "programmatic tool calling cache-context explicit check output")


def check_pdf_citations(fail: list[str]) -> None:
    for rel in ["README.md", "pdf_citations/README.md", "pdf_citations/sample.txt"]:
        _need(rel, "5/5", fail, "PDF citations 5/5 receipt")
        _need(rel, "page_location", fail, "PDF citations native page pointer")
    _need("README.md", "app-side page resolver workaround", fail, "PDF citations workaround disclosure")
    _need("pdf_citations/README.md", "App-side resolver workaround", fail, "PDF citations comparison baseline")
    _need("pdf_citations/sample.txt", "Strongest non-hosted workaround", fail, "PDF citations strongest workaround")
    _need("pdf_citations/sample.txt", "$0.05", fail, "PDF citations receipt cost")
    _need("pdf_citations/run.py", "COMPARE_DEFAULT = False", fail, "PDF citations opt-in comparison default")
    _need("pdf_citations/run.py", "page_location", fail, "PDF citations run pointer extraction")
    _need("pdf_citations/compare.py", "_app_side_resolver_workaround", fail, "PDF citations app-side resolver baseline")


def check_grounding_stack(fail: list[str]) -> None:
    for rel in ["README.md", "grounding_stack/README.md", "grounding_stack/sample.txt"]:
        _need(rel, "3/3", fail, "grounding stack 3/3 receipt")
    for rel in ["grounding_stack/README.md", "grounding_stack/run.py"]:
        _need(rel, "char_location", fail, "grounding stack char pointer")
        _need(rel, "page_location", fail, "grounding stack page pointer")
        _need(rel, "search_result_location", fail, "grounding stack search result pointer")
    _need("README.md", "app-side source-map resolver workaround", fail, "grounding stack workaround disclosure")
    _need("grounding_stack/README.md", "App-side source-map resolver", fail, "grounding stack comparison baseline")
    _need("grounding_stack/sample.txt", "Strongest non-hosted workaround", fail, "grounding stack strongest workaround")
    _need("grounding_stack/sample.txt", "$0.01", fail, "grounding stack receipt cost")
    _need("grounding_stack/run.py", "COMPARE_DEFAULT = False", fail, "grounding stack opt-in comparison default")
    _need("grounding_stack/run.py", "September", fail, "grounding stack neutral text fact")
    _need("grounding_stack/compare.py", "_app_source_map_workaround", fail, "grounding stack app-side resolver baseline")


def check_search_results(fail: list[str]) -> None:
    for rel in ["README.md", "search_results/README.md", "search_results/sample.txt"]:
        _need(rel, "24/24", fail, "search results 24/24 receipt")
        _need(rel, "40.4%", fail, "search results output-token reduction")
        _need(rel, "25.2%", fail, "search results cost reduction")
        _need(rel, "App JSON quote baseline", fail, "search results strongest app baseline")
    _need("README.md", "cited_text", fail, "search results cited_text metadata")
    _need("search_results/README.md", "$0.02", fail, "search results run cost")
    _need("search_results/README.md", "search_result_location", fail, "search results native pointer")
    _need("search_results/sample.txt", "$0.0056", fail, "search results native sample cost")
    _need("search_results/sample.txt", "$0.0075", fail, "search results baseline sample cost")
    _need("search_results/run.py", "COMPARE_DEFAULT = False", fail, "search results opt-in comparison default")
    _need("search_results/run.py", "MIN_OUTPUT_REDUCTION = 0.25", fail, "search results output threshold")
    _need("search_results/run.py", "MIN_COST_REDUCTION = 0.15", fail, "search results cost threshold")
    _need("search_results/run.py", "_run_app_quote_baseline", fail, "search results app JSON quote baseline")
    _need("search_results/compare.py", "_app_side_quote_resolver_workaround", fail, "search results optional comparison baseline")


def check_task_budgets(fail: list[str]) -> None:
    for rel in ["README.md", "task_budgets/README.md"]:
        _need(rel, "Operations", fail, "task budgets Operations framing")
        _need(rel, "app governor baseline", fail, "task budgets app baseline disclosure")
        _need(rel, "6 app-owned", fail, "task budgets replacement count")
        _need(rel, "2 request fields", fail, "task budgets native request-field count")
    _need("task_budgets/sample.txt", "Operations", fail, "task budgets Operations framing")
    _need("task_budgets/sample.txt", "app governor baseline", fail, "task budgets app baseline disclosure")
    _need("task_budgets/sample.txt", "app model-facing budget components replaced", fail, "task budgets replacement count")
    _need("task_budgets/sample.txt", "6 -> 2 request fields", fail, "task budgets native request-field count")
    _need("task_budgets/README.md", "What it replaces", fail, "task budgets replacement section")
    _need("task_budgets/README.md", "What it does not replace", fail, "task budgets remaining controls section")
    _need("task_budgets/sample.txt", "Gate passed: True", fail, "task budgets gate pass")
    _need("task_budgets/sample.txt", "Scope: this is an Operations win, not a reliability claim", fail, "task budgets scope caveat")
    _need("task_budgets/run.py", "REPLACED_BY_TASK_BUDGET", fail, "task budgets replacement ledger")
    _need("task_budgets/run.py", "STILL_APP_OWNED", fail, "task budgets remaining controls")
    _need("task_budgets/run.py", "app_governor_matches_visible_outcome", fail, "task budgets app baseline gate")


def check_removed_receipts(fail: list[str]) -> None:
    sec = "secur" + "ity"
    removed = set(removed_slugs()) | {
        "audit_" + "evidence_" + sec,
        "mcp_" + "authorization_" + sec,
        sec + "_claims_guard",
        "tool_" + "boundary_" + sec,
    }
    for slug in sorted(removed):
        if (ROOT / slug).exists():
            fail.append(f"{slug}/: removed receipt directory must not exist in feature-hits")
    forbidden_heading = "Held " + "Receipts"
    if forbidden_heading in _read("README.md"):
        fail.append("README.md: public feature-hits must not carry the removed-receipts section")


def main() -> None:
    fail: list[str] = []
    check_make_costs(fail)
    check_pillars(fail)
    check_dimension_matrices(fail)
    active = set(active_slugs())
    if "programmatic_tool_calling" in active:
        check_programmatic_tool_calling(fail)
    if "programmatic_tool_calling_cache_context" in active:
        check_programmatic_tool_calling_cache_context(fail)
    if "pdf_citations" in active:
        check_pdf_citations(fail)
    if "grounding_stack" in active:
        check_grounding_stack(fail)
    if "search_results" in active:
        check_search_results(fail)
    if "task_budgets" in active:
        check_task_budgets(fail)
    check_removed_receipts(fail)
    if fail:
        print("number gate: FAIL")
        for item in fail:
            print("  " + item)
        sys.exit(1)
    print("number gate: clean (promoted artifacts, receipts, and public claims)")


if __name__ == "__main__":
    main()
