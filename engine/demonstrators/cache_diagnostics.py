"""cache_diagnostics: live validation for cache-miss root-cause observability.

This is a measured edge when all arms run. It tests the narrow subfeature found in the
2026-06-19 sweep: Claude cache diagnostics can compare consecutive cached requests and report the
first prompt-prefix divergence as a typed cache_miss_reason, while the closest OpenAI and Gemini cache
surfaces expose cache token counts but no per-request miss reason.
"""

from __future__ import annotations

import argparse
import json
import os
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from common.client import get_client, load_env, repo_root
from common.pricing import cost_breakdown, cost_from_buckets

DATE = "2026-06-19"
CLAUDE_SOURCE = "https://platform.claude.com/docs/en/build-with-claude/cache-diagnostics"
OPENAI_SOURCE = "https://developers.openai.com/api/docs/guides/prompt-caching"
GEMINI_SOURCE = "https://ai.google.dev/gemini-api/docs/caching"

ROOT_CAUSE_TYPES = (
    "model_changed",
    "system_changed",
    "tools_changed",
    "messages_changed",
)


@dataclass
class ArmResult:
    provider: str
    model: str
    ran: bool
    root_cause_known: bool = False
    miss_reason_type: str = ""
    missed_input_tokens: int = 0
    cache_signal_present: bool = False
    cache_read_tokens: int = 0
    cache_write_tokens: int = 0
    cached_tokens: int = 0
    prompt_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0
    cost_usd: float = 0.0
    latency_s: float = 0.0
    diagnostic_fields: list[str] = field(default_factory=list)
    variant_results: list[dict] = field(default_factory=list)
    note: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


def _system(prefix: str, repeats: int) -> str:
    # Long enough to exercise all three vendors' prompt-cache usage paths.
    return "You are a terse cache diagnostics probe. " + (f"{prefix} alpha beta gamma. " * repeats)


def _keys(obj: Any) -> list[str]:
    found: set[str] = set()
    if isinstance(obj, dict):
        for key, value in obj.items():
            found.add(str(key))
            found.update(_keys(value))
    elif isinstance(obj, list):
        for item in obj:
            found.update(_keys(item))
    return sorted(found)


def _diagnostic_keys(obj: Any) -> list[str]:
    return [
        key for key in _keys(obj)
        if "diagnostic" in key.lower() or "miss_reason" in key.lower() or "cache_miss" in key.lower()
    ]


def _usage_buckets(model: str, message) -> dict:
    usage = message.usage
    cache_creation = getattr(usage, "cache_creation_input_tokens", 0) or 0
    cache_read = getattr(usage, "cache_read_input_tokens", 0) or 0
    prompt = getattr(usage, "input_tokens", 0) or 0
    output = getattr(usage, "output_tokens", 0) or 0
    return {
        "model": model,
        "prompt_tokens": prompt,
        "cache_read_tokens": cache_read,
        "cache_write_tokens": cache_creation,
        "output_tokens": output,
        "total_tokens": prompt + cache_read + cache_creation + output,
        "cost_usd": cost_breakdown(model, usage).total,
    }


def _docs_equivalent_absent() -> dict:
    """Best-effort docs absence check for the exact cache-miss root-cause subfeature."""
    root = repo_root()
    sources = {
        "openai_prompt_caching": root / "sources" / "openai_prompt_caching_2026-06-19.txt",
        "gemini_caching": root / "sources" / "gemini_caching_2026-06-19.txt",
        "gemini_tokens": root / "sources" / "gemini_token_counting_2026-06-19.txt",
    }
    needles = (
        "cache_miss_reason",
        "cache miss reason",
        "where the prompt prefix diverged",
        "system_changed",
        "tools_changed",
        "messages_changed",
        "previous_message_id",
    )
    out = {}
    for name, path in sources.items():
        text = path.read_text(errors="replace").lower() if path.exists() else ""
        hits = [needle for needle in needles if needle in text]
        out[name] = {"path": str(path), "hits": hits, "equivalent_found": bool(hits)}
    return out


def run_claude_cache_diagnostics(model: str, repeats: int) -> ArmResult:
    client = get_client()
    base = _system("stable-prefix", repeats)
    changed = _system("changed-prefix", repeats)
    model_changed_target = "claude-sonnet-4-6" if model != "claude-sonnet-4-6" else "claude-opus-4-8"
    tool_a = {
        "name": "lookup_a",
        "description": "Lookup A.",
        "input_schema": {"type": "object", "properties": {"q": {"type": "string"}}, "required": ["q"]},
    }
    tool_b = {
        "name": "lookup_b",
        "description": "Lookup B.",
        "input_schema": {"type": "object", "properties": {"q": {"type": "string"}}, "required": ["q"]},
    }

    def call(model_id: str = model, *, system: str = base, messages: list[dict] | None = None,
             tools: list[dict] | None = None, previous_id: str | None = None):
        kwargs = {
            "model": model_id,
            "max_tokens": 16,
            "cache_control": {"type": "ephemeral"},
            "system": system,
            "messages": messages or [{"role": "user", "content": "Reply ok."}],
            "diagnostics": {"previous_message_id": previous_id},
            "betas": ["cache-diagnosis-2026-04-07"],
            "timeout": 60.0,
        }
        if tools is not None:
            kwargs["tools"] = tools
        return client.beta.messages.create(**kwargs)

    variant_specs = [
        {
            "expected": "system_changed",
            "first": {"model_id": model, "system": base},
            "second": {"model_id": model, "system": changed},
        },
        {
            "expected": "tools_changed",
            "first": {"model_id": model, "system": base, "tools": [tool_a]},
            "second": {"model_id": model, "system": base, "tools": [tool_b]},
        },
        {
            "expected": "messages_changed",
            "first": {
                "model_id": model,
                "system": base,
                "messages": [{"role": "user", "content": "Original cached conversation turn. Reply ok."}],
            },
            "second": {
                "model_id": model,
                "system": base,
                "messages": [{"role": "user", "content": "Changed cached conversation turn. Reply ok."}],
            },
        },
        {
            "expected": "model_changed",
            "first": {"model_id": model, "system": base},
            "second": {"model_id": model_changed_target, "system": base},
        },
    ]
    start = time.perf_counter()
    variant_results = []
    totals = {
        "cost_usd": 0.0,
        "cache_write_tokens": 0,
        "cache_read_tokens": 0,
        "prompt_tokens": 0,
        "output_tokens": 0,
        "total_tokens": 0,
    }
    try:
        for spec in variant_specs:
            first_kwargs = dict(spec["first"])
            second_kwargs = dict(spec["second"])
            first_model = first_kwargs.pop("model_id")
            second_model = second_kwargs.pop("model_id")
            first = call(first_model, previous_id=None, **first_kwargs)
            second = call(second_model, previous_id=first.id, **second_kwargs)
            reason = getattr(getattr(second, "diagnostics", None), "cache_miss_reason", None)
            observed = getattr(reason, "type", "") if reason is not None else ""
            missed = getattr(reason, "cache_missed_input_tokens", 0) or 0
            first_buckets = _usage_buckets(first_model, first)
            second_buckets = _usage_buckets(second_model, second)
            for buckets in (first_buckets, second_buckets):
                for key in totals:
                    totals[key] += buckets[key]
            variant_results.append({
                "expected": spec["expected"],
                "observed": observed,
                "matched": observed == spec["expected"] and missed > 0,
                "cache_missed_input_tokens": missed,
                "first_model": first_model,
                "second_model": second_model,
                "diagnostic_fields": _diagnostic_keys(second.model_dump() if hasattr(second, "model_dump") else {}),
                "first_usage": first_buckets,
                "second_usage": second_buckets,
            })
    except Exception as exc:  # noqa: BLE001 - live API state belongs in the receipt
        return ArmResult("claude", model, ran=False, note=f"{type(exc).__name__}: {str(exc)[:700]}")
    latency = time.perf_counter() - start
    matched = [v for v in variant_results if v["matched"]]
    primary = variant_results[0] if variant_results else {}
    all_reasons = [v["observed"] for v in variant_results if v["observed"]]
    root_cause_known = len(matched) == len(variant_specs)
    return ArmResult(
        provider="claude",
        model=model,
        ran=True,
        root_cause_known=root_cause_known,
        miss_reason_type=primary.get("observed", ""),
        missed_input_tokens=primary.get("cache_missed_input_tokens", 0),
        cache_signal_present=True,
        cache_read_tokens=int(totals["cache_read_tokens"]),
        cache_write_tokens=int(totals["cache_write_tokens"]),
        prompt_tokens=int(totals["prompt_tokens"]),
        output_tokens=int(totals["output_tokens"]),
        total_tokens=int(totals["total_tokens"]),
        cost_usd=totals["cost_usd"],
        latency_s=latency,
        diagnostic_fields=sorted({field for v in variant_results for field in v["diagnostic_fields"]}),
        variant_results=variant_results,
        note=(
            f"Claude identified all {len(matched)} documented cache-miss root-cause variants: "
            + ", ".join(all_reasons)
            if root_cause_known else "Claude ran, but not every documented cache_miss_reason variant matched"
        ),
    )


def run_openai_cache_probe(model: str, repeats: int) -> ArmResult:
    load_env()
    try:
        from openai import OpenAI
    except ImportError:
        return ArmResult("openai", model, ran=False, note="OpenAI SDK missing, run make compare-deps")
    base = _system("stable-prefix", repeats)
    changed = _system("changed-prefix", repeats)
    client = OpenAI()
    responses = []
    start = time.perf_counter()
    try:
        for instructions in (base, changed):
            responses.append(client.responses.create(
                model=model,
                instructions=instructions,
                input="Reply ok.",
                max_output_tokens=16,
                reasoning={"effort": "low"},
                prompt_cache_key="cache-diagnostics-edge",
                prompt_cache_retention="24h",
                timeout=60.0,
            ))
    except Exception as exc:  # noqa: BLE001
        return ArmResult("openai", model, ran=False, note=f"{type(exc).__name__}: {str(exc)[:700]}")
    latency = time.perf_counter() - start
    raw = [r.model_dump() if hasattr(r, "model_dump") else {} for r in responses]
    usage = [getattr(r, "usage", None) for r in responses]
    prompt_tokens = sum(getattr(u, "input_tokens", 0) or 0 for u in usage)
    output_tokens = sum(getattr(u, "output_tokens", 0) or 0 for u in usage)
    cached = sum(getattr(getattr(u, "input_tokens_details", None), "cached_tokens", 0) or 0 for u in usage)
    cost = sum(cost_from_buckets(model, fresh_input=(getattr(u, "input_tokens", 0) or 0) -
                                 (getattr(getattr(u, "input_tokens_details", None), "cached_tokens", 0) or 0),
                                 cached=getattr(getattr(u, "input_tokens_details", None), "cached_tokens", 0) or 0,
                                 output=getattr(u, "output_tokens", 0) or 0)
               for u in usage)
    diagnostic_fields = _diagnostic_keys(raw)
    return ArmResult(
        provider="openai",
        model=model,
        ran=True,
        root_cause_known=False,
        cache_signal_present=True,
        cached_tokens=cached,
        prompt_tokens=prompt_tokens,
        output_tokens=output_tokens,
        total_tokens=prompt_tokens + output_tokens,
        cost_usd=cost,
        latency_s=latency,
        diagnostic_fields=diagnostic_fields,
        note="OpenAI exposed cached token counts, but no per-request cache-miss root cause field",
    )


def run_gemini_cache_probe(model: str, repeats: int) -> ArmResult:
    load_env()
    try:
        from google import genai
        from google.genai import types
    except ImportError:
        return ArmResult("gemini", model, ran=False, note="Gemini SDK missing, run make compare-deps")
    if not os.environ.get("GEMINI_API_KEY"):
        return ArmResult("gemini", model, ran=False, note="GEMINI_API_KEY unset")
    client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
    prompts = [_system("stable-prefix", repeats) + "\nReply ok.", _system("changed-prefix", repeats) + "\nReply ok."]
    responses = []
    config = types.GenerateContentConfig(
        max_output_tokens=16,
        thinking_config=types.ThinkingConfig(thinking_budget=128),
    )
    start = time.perf_counter()
    try:
        for prompt in prompts:
            responses.append(client.models.generate_content(model=model, contents=prompt, config=config))
    except Exception as exc:  # noqa: BLE001
        return ArmResult("gemini", model, ran=False, note=f"{type(exc).__name__}: {str(exc)[:700]}")
    latency = time.perf_counter() - start
    usages = [getattr(resp, "usage_metadata", None) for resp in responses]
    prompt_tokens = sum(getattr(u, "prompt_token_count", 0) or 0 for u in usages)
    output_tokens = sum((getattr(u, "candidates_token_count", 0) or 0) +
                        (getattr(u, "thoughts_token_count", 0) or 0) for u in usages)
    cached = sum(getattr(u, "cached_content_token_count", 0) or 0 for u in usages)
    raw = [resp.model_dump() if hasattr(resp, "model_dump") else {} for resp in responses]
    cost = sum(cost_from_buckets(model, fresh_input=(getattr(u, "prompt_token_count", 0) or 0) -
                                 (getattr(u, "cached_content_token_count", 0) or 0),
                                 cached=getattr(u, "cached_content_token_count", 0) or 0,
                                 output=(getattr(u, "candidates_token_count", 0) or 0) +
                                 (getattr(u, "thoughts_token_count", 0) or 0))
               for u in usages)
    return ArmResult(
        provider="gemini",
        model=model,
        ran=True,
        root_cause_known=False,
        cache_signal_present=True,
        cached_tokens=cached,
        prompt_tokens=prompt_tokens,
        output_tokens=output_tokens,
        total_tokens=prompt_tokens + output_tokens,
        cost_usd=cost,
        latency_s=latency,
        diagnostic_fields=_diagnostic_keys(raw),
        note="Gemini exposed cache token counters or cache metadata, but no per-request cache-miss root cause field",
    )


def score(claude: ArmResult, competitors: list[ArmResult], docs_absence: dict) -> dict:
    competitor_equiv = any(v["equivalent_found"] for v in docs_absence.values())
    ran = [c for c in competitors if c.ran]
    all_competitors_ran = len(ran) == len(competitors) and len(ran) >= 2
    competitors_silent = all_competitors_ran and all(
        c.cache_signal_present and not c.root_cause_known and not c.diagnostic_fields for c in ran
    )
    positive = claude.ran and claude.root_cause_known and competitors_silent and not competitor_equiv
    promotable = positive
    candidates_without_diagnostics = len(ROOT_CAUSE_TYPES)
    candidates_with_diagnostics = 1 if claude.root_cause_known else candidates_without_diagnostics
    matched_variants = [
        v["observed"] for v in claude.variant_results
        if v.get("matched")
    ]
    return {
        "positive_signal": positive,
        "promotable_edge": promotable,
        "why_not_promotable": [] if promotable else [
            reason for reason, failed in [
                ("Claude did not return a concrete cache_miss_reason", not (claude.ran and claude.root_cause_known)),
                ("not every competitor cache arm ran", not all_competitors_ran),
                ("a competitor exposed cache-miss diagnostic fields", not competitors_silent),
                ("competitor docs show an exact cache-miss root-cause equivalent", competitor_equiv),
            ] if failed
        ],
        "measured_axis": ["observability", "root_cause_resolution"],
        "competitor_exact_subfeature_documented": competitor_equiv,
        "all_competitors_cache_arms_ran": all_competitors_ran,
        "competitors_exposed_no_miss_reason": competitors_silent,
        "root_cause_candidates_without_diagnostics": candidates_without_diagnostics,
        "root_cause_candidates_with_claude_diagnostics": candidates_with_diagnostics,
        "manual_suspects_eliminated": candidates_without_diagnostics - candidates_with_diagnostics,
        "claude_root_cause_variants_identified": matched_variants,
        "claude_root_cause_variant_count": len(matched_variants),
        "claude_root_cause_variant_total": len(ROOT_CAUSE_TYPES),
    }


def write_receipt(receipt: dict) -> Path:
    out = repo_root() / "data" / "last_cache_diagnostics.json"
    out.parent.mkdir(exist_ok=True)
    out.write_text(json.dumps(receipt, indent=2) + "\n")
    return out


def _fmt_usd(x: float) -> str:
    return f"${x:.4f}" if x >= 0.0001 else f"${x:.6f}"


def write_sample(receipt: dict) -> Path:
    out = repo_root() / "edges" / "cache-diagnostics" / "sample.txt"
    out.parent.mkdir(parents=True, exist_ok=True)
    arms = receipt["arms"]
    verdict = receipt["verdict"]
    lines = [
        "",
        "  Cache diagnostics workload: two long cached-prefix requests with one silent system-prefix change.",
        "  The client sees a cache miss. The question is whether the API says what changed.",
        "",
        "  Cache-miss root-cause head-to-head, one live run.",
        "",
        "  platform                              root cause known  miss reason       missed tok     cache signal     cost  wall time",
        "  ---------------------------------------------------------------------------------------------------------------",
    ]
    for arm in arms:
        reason = arm["miss_reason_type"] or "-"
        lines.append(
            f"  {arm['provider'] + ' ' + arm['model']:<38}"
            f"{'YES' if arm['root_cause_known'] else 'NO':>8}"
            f"{reason:>17}"
            f"{arm['missed_input_tokens']:>15,}"
            f"{'yes' if arm['cache_signal_present'] else 'no':>17}"
            f"{_fmt_usd(arm['cost_usd']):>9}"
            f"{arm['latency_s']:>10.1f}s"
        )
    lines.extend([
        "",
        "  Claude diagnostic variant coverage:",
    ])
    for variant in arms[0].get("variant_results", []):
        lines.append(
            f"    {variant['expected']:<18} -> {variant['observed'] or '-':<18} "
            f"matched={str(variant['matched']).lower()} missed={variant['cache_missed_input_tokens']:,}"
        )
    lines.extend([
        "",
        "  Verdict:",
        f"    positive_signal: {str(verdict['positive_signal']).lower()}",
        f"    promotable_edge: {str(verdict['promotable_edge']).lower()}",
        "",
        "  Honest reading:",
        f"  - Claude named {verdict['claude_root_cause_variant_count']}/{verdict['claude_root_cause_variant_total']} documented cache-break root causes.",
        "  - Claude estimated the missed input tokens for each typed miss reason.",
        "  - OpenAI and Gemini exposed cache token counters but no miss-reason field on this workload.",
        f"  - Claude reduced the manual suspect list from {verdict['root_cause_candidates_without_diagnostics']} to {verdict['root_cause_candidates_with_claude_diagnostics']}.",
        "  - The edge is observability, not cheaper inference on this two-call probe.",
        "",
        "  Reproduce:",
        "    make cache-diagnostics",
        "",
        "  Machine receipt:",
        "    data/last_cache_diagnostics.json",
    ])
    out.write_text("\n".join(lines) + "\n")
    return out


def write_edge_files(receipt: dict) -> None:
    edge = repo_root() / "edges" / "cache-diagnostics"
    edge.mkdir(parents=True, exist_ok=True)
    (edge / "receipt.json").write_text(json.dumps(receipt, indent=2) + "\n")
    write_sample(receipt)
    (edge / "demo.py").write_text(
        '"""cache-diagnostics: wrapper for the cache-miss root-cause edge."""\n\n'
        "from __future__ import annotations\n\n"
        "import pathlib as _pl\n"
        "import sys as _sys\n\n"
        "_sys.path.insert(0, str(_pl.Path(__file__).resolve().parents[2]))\n\n"
        "from engine.demonstrators.cache_diagnostics import main\n\n\n"
        'if __name__ == "__main__":\n'
        "    main()\n"
    )
    readme = edge / "README.md"
    claude = receipt["arms"][0]
    openai = receipt["arms"][1]
    gemini = receipt["arms"][2]
    verdict = receipt["verdict"]
    variant_rows = "\n".join(
        f"| `{v['expected']}` | `{v['observed'] or '-'}` | {'yes' if v['matched'] else 'no'} | {v['cache_missed_input_tokens']:,} |"
        for v in claude.get("variant_results", [])
    )
    readme.write_text(f"""# Edge: Cache diagnostics, root cause for silent cache misses

Part of [claude-feature-radar](../../README.md). This is a measured observability edge, not a claim
that Claude is cheaper on every cached prompt.

## What It Is

A long cached-prefix request is sent twice. The second request silently changes the system prefix, the
kind of bug a production app gets from timestamps, routing metadata, or non-deterministic schema
serialization. All three providers expose cache-related token counters. Claude additionally returns a
typed `diagnostics.cache_miss_reason`.

## The Measured Proof

Run: `make cache-diagnostics`, {receipt['date']}, same changed-prefix workload plus all documented
Claude cache-miss reason variants.

| arm | root cause known | miss reason | missed tokens | cost | wall time |
|---|:---:|---|---:|---:|---:|
| Claude Haiku 4.5 cache diagnostics | {'yes' if claude['root_cause_known'] else 'no'} | `{claude['miss_reason_type']}` | {claude['missed_input_tokens']:,} | {_fmt_usd(claude['cost_usd'])} | {claude['latency_s']:.1f}s |
| OpenAI GPT-5.5 prompt caching | {'yes' if openai['root_cause_known'] else 'no'} | none exposed | 0 | {_fmt_usd(openai['cost_usd'])} | {openai['latency_s']:.1f}s |
| Gemini 3.1 Pro cache counters | {'yes' if gemini['root_cause_known'] else 'no'} | none exposed | 0 | {_fmt_usd(gemini['cost_usd'])} | {gemini['latency_s']:.1f}s |

Claude identified {verdict['claude_root_cause_variant_count']}/{verdict['claude_root_cause_variant_total']} documented cache-miss reason variants:

| expected miss reason | observed miss reason | matched | missed tokens |
|---|---|:---:|---:|
{variant_rows}

Claude reduced the manual cache-miss suspect list from
{verdict['root_cause_candidates_without_diagnostics']} possible prompt-prefix surfaces to
{verdict['root_cause_candidates_with_claude_diagnostics']}: `system_changed`.

Full receipt: [`sample.txt`](sample.txt). Machine receipt: [`receipt.json`](receipt.json).

## Honest Scope

- This is an observability edge for debugging prompt-cache misses.
- The win is not lower cost on this probe. The win is that Claude names the changed prefix surface and
  estimates missed input tokens.
- OpenAI and Gemini still have prompt or context caching. Their closest live surfaces exposed cache
  counters, not a root-cause diagnostic field, on this workload.

## Run It Yourself

```bash
git clone https://github.com/cfregly/claude-feature-radar && cd claude-feature-radar
make setup
make compare-deps
cp .env.example .env   # paste ANTHROPIC_API_KEY, OPENAI_API_KEY, and GEMINI_API_KEY
make cache-diagnostics # full receipt, cents-scale on the 2026-06-19 run
```

`make cache-diagnostics` also writes the latest local machine receipt to
`data/last_cache_diagnostics.json`.

Sources:

- Claude cache diagnostics: {CLAUDE_SOURCE}
- OpenAI prompt caching: {OPENAI_SOURCE}
- Gemini context caching: {GEMINI_SOURCE}
""")


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="Validate the cache diagnostics edge. Writes data/last_cache_diagnostics.json."
    )
    parser.add_argument("--claude-model", default="claude-haiku-4-5-20251001")
    parser.add_argument("--openai-model", default="gpt-5.5")
    parser.add_argument("--gemini-model", default="gemini-3.1-pro-preview")
    parser.add_argument("--repeats", type=int, default=850)
    parser.add_argument("--skip-competitors", action="store_true")
    parser.add_argument("--emit-edge", action="store_true")
    args = parser.parse_args(argv)

    print("\n  cache_diagnostics: live root-cause observability validation.\n")
    docs_absence = _docs_equivalent_absent()
    print("  running Claude cache diagnostics ...", flush=True)
    claude = run_claude_cache_diagnostics(args.claude_model, args.repeats)
    competitors: list[ArmResult] = []
    if not args.skip_competitors:
        print("  running OpenAI prompt caching probe ...", flush=True)
        competitors.append(run_openai_cache_probe(args.openai_model, args.repeats))
        print("  running Gemini cache counter probe ...", flush=True)
        competitors.append(run_gemini_cache_probe(args.gemini_model, args.repeats))
    verdict = score(claude, competitors, docs_absence)
    receipt = {
        "date": DATE,
        "claim_under_test": (
            "Claude cache diagnostics returns a typed cache_miss_reason for a silent prompt-cache "
            "prefix change, while closest OpenAI and Gemini cache surfaces expose counters but no "
            "per-request miss reason."
        ),
        "sources": {
            "claude": CLAUDE_SOURCE,
            "openai": OPENAI_SOURCE,
            "gemini": GEMINI_SOURCE,
        },
        "config": {
            "changed_surface": "system",
            "repeats": args.repeats,
            "root_cause_types_considered": list(ROOT_CAUSE_TYPES),
        },
        "docs_absence_check": docs_absence,
        "arms": [claude.to_dict()] + [c.to_dict() for c in competitors],
        "verdict": verdict,
    }
    path = write_receipt(receipt)
    if args.emit_edge and verdict["promotable_edge"]:
        write_edge_files(receipt)

    print("\n  Result:")
    print(f"    positive_signal: {verdict['positive_signal']}")
    print(f"    promotable_edge: {verdict['promotable_edge']}")
    if verdict["why_not_promotable"]:
        print("    held because:")
        for reason in verdict["why_not_promotable"]:
            print(f"      - {reason}")
    print("\n  Arms:")
    for arm in [claude, *competitors]:
        ran = "ran" if arm.ran else "not-run"
        reason = arm.miss_reason_type or "-"
        print(
            f"    {arm.provider:<7} {ran:<7} model={arm.model} root_cause={arm.root_cause_known} "
            f"reason={reason} missed={arm.missed_input_tokens:,} "
            f"cost={_fmt_usd(arm.cost_usd)} latency={arm.latency_s:.1f}s"
        )
    print(f"\n  wrote {path.relative_to(repo_root())}")
    if args.emit_edge and verdict["promotable_edge"]:
        print("  wrote edges/cache-diagnostics/{README.md,demo.py,sample.txt,receipt.json}")
    print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
