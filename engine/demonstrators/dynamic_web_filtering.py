"""dynamic_web_filtering: live subfeature validation for Claude web search/fetch.

This is a validation harness, not a public edge. It tests the narrow wedge found by the
2026-06-19 sweep: Claude can run web search from code execution and filter the results before the
final answer, while the newer response_inclusion version is currently docs-present but may be
access/API-shape blocked on a given key.

The output deliberately distinguishes:
  - positive_signal: Claude exercised the subfeature and competitor docs do not show an exact
    pre-context code-filtering equivalent.
  - promotable_edge: the stricter bar for generating a public edge bundle. This requires a live,
    correct, grounded, best-to-best comparison where Claude wins on the measured value axis.

No founder-facing edge is generated from this file unless promotable_edge is true.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path

from common.client import get_client, load_env, repo_root

DATE = "2026-06-19"
CLAUDE_SOURCE = "https://platform.claude.com/docs/en/agents-and-tools/tool-use/web-search-tool"
OPENAI_SOURCE = "https://developers.openai.com/api/docs/guides/tools-web-search"
GEMINI_SOURCE = "https://ai.google.dev/gemini-api/docs/google-search"

CLAUDE_PROMPT = (
    "Use web search and code execution, not memory. Search official public docs for Anthropic web "
    "search dynamic filtering. Use code execution to call web_search and filter to official "
    "Anthropic docs before the final answer. Return JSON only with keys dynamic_filtering_tool, "
    "code_required, urls. Keep concise."
)

COMPETITOR_PROMPT = (
    "Use live web search or grounding, not memory. Find the official Anthropic documentation page "
    "that states the web_search dynamic filtering version. Return JSON only with keys "
    "dynamic_filtering_tool, code_required, urls. Keep concise."
)

SDK_SCHEMA_NEEDLES = (
    "web_search_20260209",
    "web_search_20260318",
    "web_fetch_20260309",
    "web_fetch_20260318",
    "response_inclusion",
)

NEW_TOOL_BETA_CANDIDATES = (
    "web-search-2026-03-18",
    "web-search-20260318",
    "web-fetch-2026-03-18",
    "response-inclusion-2026-03-18",
    "code-execution-2026-05-21",
    "web-search-tool-2026-03-18",
    "web-search-tool-20260318",
)


@dataclass
class ArmResult:
    provider: str
    model: str
    ran: bool
    correct: bool = False
    grounded: bool = False
    dynamic_filtering_exercised: bool = False
    equivalent_subfeature_documented: bool = False
    latency_s: float = 0.0
    input_tokens: int = 0
    output_tokens: int = 0
    response_chars: int = 0
    text: str = ""
    parsed: dict = field(default_factory=dict)
    metric: dict = field(default_factory=dict)
    note: str = ""

    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens

    def to_dict(self) -> dict:
        d = asdict(self)
        d["total_tokens"] = self.total_tokens
        return d


def _extract_json(text: str) -> dict:
    match = re.search(r"\{.*\}", text or "", re.S)
    if not match:
        return {}
    try:
        return json.loads(match.group(0))
    except json.JSONDecodeError:
        return {}


def _answer_correct(text: str, parsed: dict) -> bool:
    blob = json.dumps(parsed) if parsed else text or ""
    return "web_search_20260209" in blob


def _sdk_schema_flags_from_text(text: str) -> dict:
    return {f"has_{needle}": needle in text for needle in SDK_SCHEMA_NEEDLES}


def probe_anthropic_sdk_schema() -> dict:
    """Record whether the installed SDK generated schema knows the docs-new tool shape."""
    try:
        import anthropic
    except ImportError as exc:
        return {"installed": False, "error_type": type(exc).__name__, "error": str(exc)}

    package_path = Path(anthropic.__file__).resolve().parent
    hits = {needle: [] for needle in SDK_SCHEMA_NEEDLES}
    for path in package_path.rglob("*.py"):
        try:
            text = path.read_text(errors="replace")
        except OSError:
            continue
        for needle in SDK_SCHEMA_NEEDLES:
            if needle in text:
                hits[needle].append(str(path.relative_to(package_path)))

    present_marker_text = "\n".join(needle for needle, paths in hits.items() if paths)
    flags = _sdk_schema_flags_from_text(present_marker_text)
    return {
        "installed": True,
        "installed_version": getattr(anthropic, "__version__", "unknown"),
        "package_path": str(package_path),
        **flags,
        "needle_hits": hits,
    }


def _docs_equivalent_absent() -> dict:
    """Best-effort docs absence check for the exact subfeature.

    This does not prove a measured win by itself. It only checks whether the fetched OpenAI/Gemini
    docs contain the specific phrases that would indicate pre-context code filtering or the
    Anthropic response_inclusion control.
    """
    root = repo_root()
    sources = {
        "openai": root / "sources" / "openai_web_search_tool_2026-06-19.txt",
        "gemini_search": root / "sources" / "gemini_google_search_2026-06-19.txt",
        "gemini_tools": root / "sources" / "gemini_tools_2026-06-19.txt",
    }
    needles = (
        "before they reach the context window",
        "dynamic filtering",
        "response_inclusion",
        "consumed search result blocks",
        "code to filter search results",
    )
    out = {}
    for name, path in sources.items():
        text = path.read_text(errors="replace").lower() if path.exists() else ""
        hits = [n for n in needles if n in text]
        out[name] = {"path": str(path), "hits": hits, "equivalent_found": bool(hits)}
    return out


def probe_claude_response_inclusion() -> dict:
    """Probe the docs-new response_inclusion tool version.

    The June 19 docs name web_search_20260318, but this key/API currently rejects that type in live
    calls. This probe captures that state explicitly so the edge cannot be promoted on docs alone.
    """
    client = get_client()
    try:
        client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=32,
            messages=[{"role": "user", "content": "Reply with ok."}],
            tools=[{
                "type": "web_search_20260318",
                "name": "web_search",
                "response_inclusion": "excluded",
                "max_uses": 1,
            }],
            timeout=30.0,
        )
        return {"available": True, "error_type": None, "error": None}
    except Exception as exc:  # noqa: BLE001 - report live API state, never hide it
        return {"available": False, "error_type": type(exc).__name__, "error": str(exc)[:900]}


def _tool_probe_cases() -> list[dict]:
    return [
        {
            "tool_type": "web_search_20260209",
            "tool_name": "web_search",
            "expected": "accepted",
            "extra": {"max_uses": 1},
            "subfeature": "dynamic filtering",
        },
        {
            "tool_type": "web_search_20260318",
            "tool_name": "web_search",
            "expected": "accepted if response_inclusion rollout matches docs",
            "extra": {"max_uses": 1, "response_inclusion": "excluded"},
            "subfeature": "response inclusion",
        },
        {
            "tool_type": "web_fetch_20260309",
            "tool_name": "web_fetch",
            "expected": "accepted",
            "extra": {},
            "subfeature": "dynamic filtering plus cache bypass",
        },
        {
            "tool_type": "web_fetch_20260318",
            "tool_name": "web_fetch",
            "expected": "accepted if response_inclusion rollout matches docs",
            "extra": {"response_inclusion": "excluded"},
            "subfeature": "response inclusion",
        },
    ]


def probe_tool_version_acceptance(model: str) -> dict:
    """Probe server-side tool tag acceptance through the public SDK."""
    client = get_client()
    out = {}
    for case in _tool_probe_cases():
        tool = {"type": case["tool_type"], "name": case["tool_name"], **case["extra"]}
        try:
            client.messages.create(
                model=model,
                max_tokens=8,
                messages=[{"role": "user", "content": "Reply ok."}],
                tools=[tool],
                timeout=30.0,
            )
            out[case["tool_type"]] = {
                "accepted": True,
                "expected": case["expected"],
                "subfeature": case["subfeature"],
                "error_type": None,
                "error": None,
            }
        except Exception as exc:  # noqa: BLE001 - record live API state
            out[case["tool_type"]] = {
                "accepted": False,
                "expected": case["expected"],
                "subfeature": case["subfeature"],
                "error_type": type(exc).__name__,
                "error": str(exc)[:900],
            }
    return out


def probe_raw_api_new_tool_tags(model: str) -> dict:
    """Probe the docs-new tool tags via raw HTTP so SDK runtime validation cannot explain failures."""
    load_env()
    if not os.environ.get("ANTHROPIC_API_KEY"):
        return {"ran": False, "note": "ANTHROPIC_API_KEY unset"}
    try:
        import httpx
    except ImportError as exc:
        return {"ran": False, "error_type": type(exc).__name__, "error": str(exc)}

    out = {"ran": True, "endpoint": "https://api.anthropic.com/v1/messages", "tools": {}}
    for case in _tool_probe_cases():
        if not case["tool_type"].endswith("20260318"):
            continue
        tool = {"type": case["tool_type"], "name": case["tool_name"], **case["extra"]}
        try:
            resp = httpx.post(
                "https://api.anthropic.com/v1/messages",
                headers={
                    "x-api-key": os.environ["ANTHROPIC_API_KEY"],
                    "anthropic-version": "2023-06-01",
                    "content-type": "application/json",
                },
                json={
                    "model": model,
                    "max_tokens": 8,
                    "messages": [{"role": "user", "content": "Reply ok."}],
                    "tools": [tool],
                },
                timeout=30.0,
            )
            try:
                body = resp.json()
            except ValueError:
                body = {"text": resp.text[:900]}
            out["tools"][case["tool_type"]] = {
                "accepted": 200 <= resp.status_code < 300,
                "status_code": resp.status_code,
                "error_type": (body.get("error") or {}).get("type") if isinstance(body, dict) else None,
                "error": json.dumps(body)[:900],
            }
        except Exception as exc:  # noqa: BLE001 - record live API state
            out["tools"][case["tool_type"]] = {
                "accepted": False,
                "status_code": None,
                "error_type": type(exc).__name__,
                "error": str(exc)[:900],
            }
    return out


def probe_beta_unlocks(model: str) -> dict:
    """Try plausible beta names so a missing header is not left as an untested explanation."""
    client = get_client()
    out = {}
    tool = {
        "type": "web_search_20260318",
        "name": "web_search",
        "max_uses": 1,
        "response_inclusion": "excluded",
    }
    for beta in NEW_TOOL_BETA_CANDIDATES:
        try:
            client.beta.messages.create(
                model=model,
                max_tokens=8,
                messages=[{"role": "user", "content": "Reply ok."}],
                tools=[tool],
                betas=[beta],
                timeout=30.0,
            )
            out[beta] = {"accepted": True, "error_type": None, "error": None}
        except Exception as exc:  # noqa: BLE001 - record live API state
            out[beta] = {"accepted": False, "error_type": type(exc).__name__, "error": str(exc)[:700]}
    return out


def summarize_new_tool_discrepancy(sdk_schema: dict, tool_acceptance: dict, raw_api: dict,
                                   beta_unlocks: dict) -> dict:
    sdk_has_new = bool(
        sdk_schema.get("has_web_search_20260318")
        and sdk_schema.get("has_web_fetch_20260318")
        and sdk_schema.get("has_response_inclusion")
    )
    sdk_has_dynamic = bool(
        sdk_schema.get("has_web_search_20260209") and sdk_schema.get("has_web_fetch_20260309")
    )
    server_accepts_new = bool(
        tool_acceptance.get("web_search_20260318", {}).get("accepted")
        and tool_acceptance.get("web_fetch_20260318", {}).get("accepted")
    )
    server_accepts_dynamic = bool(
        tool_acceptance.get("web_search_20260209", {}).get("accepted")
        and tool_acceptance.get("web_fetch_20260309", {}).get("accepted")
    )
    raw_accepts_new = bool(
        raw_api.get("tools", {}).get("web_search_20260318", {}).get("accepted")
        and raw_api.get("tools", {}).get("web_fetch_20260318", {}).get("accepted")
    )
    beta_unlock_found = any(v.get("accepted") for v in beta_unlocks.values())
    if server_accepts_new:
        conclusion = "docs-new response_inclusion tool tags are live for this key and endpoint"
    elif not sdk_has_new and not raw_accepts_new and not beta_unlock_found:
        conclusion = (
            "docs are ahead of the public generated SDK schema and this key's server-side accepted "
            "tool tags; use dynamic filtering versions, but do not pitch response_inclusion yet"
        )
    else:
        conclusion = "mixed rollout state; keep held until raw API and SDK schema agree with docs"
    return {
        "sdk_has_dynamic_filtering_tags": sdk_has_dynamic,
        "sdk_has_docs_new_response_inclusion_tags": sdk_has_new,
        "server_accepts_dynamic_filtering_tags": server_accepts_dynamic,
        "server_accepts_docs_new_response_inclusion_tags": server_accepts_new,
        "raw_api_accepts_docs_new_response_inclusion_tags": raw_accepts_new,
        "beta_header_unlock_found": beta_unlock_found,
        "conclusion": conclusion,
    }


def _claude_text(message) -> str:
    return "".join(getattr(b, "text", "") for b in message.content if getattr(b, "type", None) == "text")


def run_claude_dynamic(model: str) -> ArmResult:
    client = get_client()
    start = time.perf_counter()
    msg = client.messages.create(
        model=model,
        max_tokens=2048,
        messages=[{"role": "user", "content": CLAUDE_PROMPT}],
        tools=[
            {"type": "code_execution_20260521", "name": "code_execution"},
            {"type": "web_search_20260209", "name": "web_search", "max_uses": 4},
        ],
        timeout=120.0,
    )
    latency = time.perf_counter() - start
    text = _claude_text(msg)
    parsed = _extract_json(text)
    block_types = [getattr(b, "type", None) for b in msg.content]
    names = [getattr(b, "name", None) for b in msg.content]
    caller_types = []
    for b in msg.content:
        caller = getattr(b, "caller", None)
        if caller is not None:
            caller_types.append(getattr(caller, "type", ""))
    raw = msg.model_dump_json() if hasattr(msg, "model_dump_json") else str(msg)
    dynamic = (
        "code_execution" in names
        and "web_search_tool_result" in block_types
        and any("code_execution" in c for c in caller_types)
    )
    return ArmResult(
        provider="claude",
        model=model,
        ran=True,
        correct=_answer_correct(text, parsed),
        grounded="platform.claude.com/docs" in raw or "docs.anthropic.com" in raw,
        dynamic_filtering_exercised=dynamic,
        latency_s=latency,
        input_tokens=getattr(msg.usage, "input_tokens", 0) or 0,
        output_tokens=getattr(msg.usage, "output_tokens", 0) or 0,
        response_chars=len(raw),
        text=text,
        parsed=parsed,
        metric={"block_types": block_types, "names": names, "caller_types": caller_types},
        note="Claude web_search_20260209 called from code_execution and filtered before final answer"
        if dynamic else "Claude ran, but dynamic filtering was not observed in content blocks",
    )


def run_openai_web(model: str) -> ArmResult:
    load_env()
    try:
        from openai import OpenAI
    except ImportError:
        return ArmResult("openai", model, ran=False, note="OpenAI SDK missing, run make compare-deps")
    start = time.perf_counter()
    try:
        resp = OpenAI().responses.create(
            model=model,
            input=COMPETITOR_PROMPT,
            max_output_tokens=2048,
            reasoning={"effort": "low"},
            tools=[{"type": "web_search", "search_context_size": "low"}],
            include=["web_search_call.action.sources"],
            timeout=90.0,
        )
    except Exception as exc:  # noqa: BLE001
        return ArmResult("openai", model, ran=False, note=f"{type(exc).__name__}: {str(exc)[:500]}")
    latency = time.perf_counter() - start
    text = resp.output_text or ""
    parsed = _extract_json(text)
    raw = resp.model_dump_json() if hasattr(resp, "model_dump_json") else str(resp)
    return ArmResult(
        provider="openai",
        model=model,
        ran=True,
        correct=_answer_correct(text, parsed),
        grounded="platform.claude.com/docs" in raw or "docs.anthropic.com" in raw,
        dynamic_filtering_exercised=False,
        latency_s=latency,
        input_tokens=getattr(resp.usage, "input_tokens", 0) or 0,
        output_tokens=getattr(resp.usage, "output_tokens", 0) or 0,
        response_chars=len(raw),
        text=text,
        parsed=parsed,
        metric={"status": getattr(resp, "status", "")},
        note="OpenAI web_search ran at closest documented setting",
    )


def run_gemini_grounding(model: str) -> ArmResult:
    load_env()
    try:
        from google import genai
        from google.genai import types
    except ImportError:
        return ArmResult("gemini", model, ran=False, note="Gemini SDK missing, run make compare-deps")
    import os
    if not os.environ.get("GEMINI_API_KEY"):
        return ArmResult("gemini", model, ran=False, note="GEMINI_API_KEY unset")
    client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
    config = types.GenerateContentConfig(
        tools=[types.Tool(google_search=types.GoogleSearch())],
        max_output_tokens=1024,
        thinking_config=types.ThinkingConfig(thinking_level="low"),
    )
    start = time.perf_counter()
    try:
        resp = client.models.generate_content(model=model, contents=COMPETITOR_PROMPT, config=config)
    except Exception as exc:  # noqa: BLE001
        return ArmResult("gemini", model, ran=False, note=f"{type(exc).__name__}: {str(exc)[:500]}")
    latency = time.perf_counter() - start
    usage = getattr(resp, "usage_metadata", None)
    text = getattr(resp, "text", "") or ""
    parsed = _extract_json(text)
    grounding = getattr(resp.candidates[0], "grounding_metadata", None) if getattr(resp, "candidates", None) else None
    chunks = getattr(grounding, "grounding_chunks", None) or [] if grounding else []
    queries = getattr(grounding, "web_search_queries", None) or [] if grounding else []
    out = (getattr(usage, "candidates_token_count", 0) or 0) + (getattr(usage, "thoughts_token_count", 0) or 0)
    return ArmResult(
        provider="gemini",
        model=model,
        ran=True,
        correct=_answer_correct(text, parsed),
        grounded=bool(chunks),
        dynamic_filtering_exercised=False,
        latency_s=latency,
        input_tokens=getattr(usage, "prompt_token_count", 0) or 0,
        output_tokens=out,
        response_chars=len(str(resp)),
        text=text,
        parsed=parsed,
        metric={"grounding_chunks": len(chunks), "web_search_queries": list(queries)},
        note="Gemini Google Search grounding ran, grounded only if grounding_chunks are present",
    )


def score(claude: ArmResult, competitors: list[ArmResult], response_inclusion_probe: dict,
          docs_absence: dict) -> dict:
    competitor_equiv = any(v["equivalent_found"] for v in docs_absence.values())
    positive = (
        claude.ran
        and claude.correct
        and claude.grounded
        and claude.dynamic_filtering_exercised
        and not competitor_equiv
    )
    ran = [c for c in competitors if c.ran]
    grounded_correct = [c for c in ran if c.correct and c.grounded]
    all_competitors_grounded_correct = len(ran) >= 2 and len(grounded_correct) == len(ran)
    token_win = all_competitors_grounded_correct and claude.total_tokens < min(c.total_tokens for c in grounded_correct)
    promotable = positive and token_win
    return {
        "positive_signal": positive,
        "promotable_edge": promotable,
        "why_not_promotable": [] if promotable else [
            reason for reason, failed in [
                ("Claude dynamic filtering was not correct, grounded, and observed", not positive),
                ("not every competitor produced a grounded correct answer", not all_competitors_grounded_correct),
                ("Claude did not beat every grounded correct competitor on total tokens", not token_win),
            ] if failed
        ],
        "token_win_against_grounded_correct_competitors": token_win,
        "all_competitors_grounded_correct": all_competitors_grounded_correct,
        "response_inclusion_available": bool(response_inclusion_probe.get("available")),
        "competitor_exact_subfeature_documented": competitor_equiv,
        "grounded_correct_competitors": [c.provider for c in grounded_correct],
    }


def write_receipt(receipt: dict) -> Path:
    out = repo_root() / "data" / "last_dynamic_web_filtering.json"
    out.parent.mkdir(exist_ok=True)
    out.write_text(json.dumps(receipt, indent=2) + "\n")
    return out


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="Validate the dynamic web filtering subfeature. Writes data/last_dynamic_web_filtering.json."
    )
    parser.add_argument("--claude-model", default="claude-sonnet-4-6")
    parser.add_argument("--openai-model", default="gpt-5.5")
    parser.add_argument("--gemini-model", default="gemini-3.1-pro-preview")
    parser.add_argument("--skip-competitors", action="store_true")
    args = parser.parse_args(argv)

    print("\n  dynamic_web_filtering: live subfeature validation, not a public edge yet.\n")
    docs_absence = _docs_equivalent_absent()
    print("  checking installed Anthropic SDK generated schema ...", flush=True)
    sdk_schema = probe_anthropic_sdk_schema()
    print(f"    anthropic SDK: {sdk_schema.get('installed_version', 'missing')}", flush=True)
    print(
        f"    SDK has web_search_20260318: {sdk_schema.get('has_web_search_20260318')}",
        flush=True,
    )
    print("  probing server tool tag acceptance ...", flush=True)
    tool_acceptance = probe_tool_version_acceptance(args.claude_model)
    print(
        "    accepted tags: "
        + ", ".join(k for k, v in tool_acceptance.items() if v.get("accepted")),
        flush=True,
    )
    print("  probing docs-new tags through raw HTTP ...", flush=True)
    raw_api_probe = probe_raw_api_new_tool_tags(args.claude_model)
    print(
        "    raw API accepts web_search_20260318: "
        f"{raw_api_probe.get('tools', {}).get('web_search_20260318', {}).get('accepted')}",
        flush=True,
    )
    print("  probing plausible beta-header unlocks ...", flush=True)
    beta_unlocks = probe_beta_unlocks(args.claude_model)
    print(f"    beta unlock found: {any(v.get('accepted') for v in beta_unlocks.values())}", flush=True)
    print("  probing Claude response_inclusion version ...", flush=True)
    inclusion = probe_claude_response_inclusion()
    print(f"    response_inclusion available: {inclusion.get('available')}", flush=True)
    print("  running Claude dynamic filtering ...", flush=True)
    claude = run_claude_dynamic(args.claude_model)
    competitors: list[ArmResult] = []
    if not args.skip_competitors:
        print("  running OpenAI web_search ...", flush=True)
        competitors.append(run_openai_web(args.openai_model))
        print("  running Gemini Google Search grounding ...", flush=True)
        competitors.append(run_gemini_grounding(args.gemini_model))
    verdict = score(claude, competitors, inclusion, docs_absence)
    discrepancy = summarize_new_tool_discrepancy(sdk_schema, tool_acceptance, raw_api_probe, beta_unlocks)
    receipt = {
        "date": DATE,
        "claim_under_test": "Claude dynamic web filtering can run web search from code execution and filter results before final answer.",
        "sources": {
            "claude": CLAUDE_SOURCE,
            "openai": OPENAI_SOURCE,
            "gemini": GEMINI_SOURCE,
        },
        "sdk_runtime_probe": {
            "sdk_schema": sdk_schema,
            "tool_version_acceptance": tool_acceptance,
            "raw_api_new_tool_tags": raw_api_probe,
            "beta_unlocks": beta_unlocks,
            "discrepancy_resolution": discrepancy,
        },
        "response_inclusion_probe": inclusion,
        "docs_absence_check": docs_absence,
        "arms": [claude.to_dict()] + [c.to_dict() for c in competitors],
        "verdict": verdict,
    }
    path = write_receipt(receipt)

    print("\n  Result:")
    print(f"    positive_signal: {verdict['positive_signal']}")
    print(f"    promotable_edge: {verdict['promotable_edge']}")
    print(f"    discrepancy: {discrepancy['conclusion']}")
    if verdict["why_not_promotable"]:
        print("    held because:")
        for reason in verdict["why_not_promotable"]:
            print(f"      - {reason}")
    print("\n  Arms:")
    for arm in [claude, *competitors]:
        ran = "ran" if arm.ran else "not-run"
        print(
            f"    {arm.provider:<7} {ran:<7} model={arm.model} correct={arm.correct} "
            f"grounded={arm.grounded} dynamic={arm.dynamic_filtering_exercised} "
            f"tokens={arm.total_tokens:,} latency={arm.latency_s:.1f}s"
        )
    print(f"\n  wrote {path.relative_to(repo_root())}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
