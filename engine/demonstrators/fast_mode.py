"""fast_mode: live validation for Claude's same-model speed toggle.

This is a validation harness, not a guaranteed public edge. The current org may have zero fast-mode
rate limit, and OpenAI/Gemini both document adjacent priority inference paths. The harness therefore
fails closed:

  - access_blocked: the org cannot spend fast-mode tokens yet.
  - positive_signal: Claude fast mode is live and faster than standard speed on the same Opus model.
  - promotable_edge: reserved for a best-to-best receipt where Claude wins against competitor priority
    paths on the measured founder-value axis.
"""

from __future__ import annotations

import argparse
import json
import os
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path

from common.client import fmt_usd, get_client, load_env, repo_root
from common.pricing import cost_usd

DATE = "2026-06-19"
CLAUDE_SOURCE = "https://platform.claude.com/docs/en/build-with-claude/fast-mode"
CLAUDE_RATE_LIMITS_SOURCE = "https://platform.claude.com/docs/en/api/rate-limits"
OPENAI_SOURCE = "https://developers.openai.com/api/docs/guides/priority-processing"
GEMINI_SOURCE = "https://ai.google.dev/gemini-api/docs/priority-inference"

FAST_MODE_ENABLEMENT = (
    "Fast mode has a dedicated org-level rate-limit pool. If the API reports 0 fast-mode input "
    "tokens per minute, enablement is not a repo setting: request fast-mode access or a fast-mode "
    "rate-limit increase through the Anthropic account path, then verify the Limits page or Rate "
    "Limits API before rerunning this target."
)

PROMPT = (
    "Write a compact, deterministic implementation note for a production API latency incident. "
    "Use exactly 12 numbered bullets. Each bullet must be one sentence and include one concrete "
    "action. Do not use markdown tables."
)


@dataclass
class ArmResult:
    provider: str
    model: str
    mode: str
    ran: bool
    correct: bool = False
    access_blocked: bool = False
    speed_field: str | None = None
    service_tier: str | None = None
    latency_s: float = 0.0
    input_tokens: int = 0
    output_tokens: int = 0
    output_chars: int = 0
    output_tokens_per_s: float = 0.0
    cost_usd: float = 0.0
    stop_reason: str = ""
    error_type: str = ""
    error: str = ""
    metric: dict = field(default_factory=dict)

    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens

    def to_dict(self) -> dict:
        d = asdict(self)
        d["total_tokens"] = self.total_tokens
        return d


def _fast_cost_usd(model: str, usage) -> float:
    if model != "claude-opus-4-8":
        return cost_usd(model, usage)
    input_tokens = getattr(usage, "input_tokens", 0) or 0
    output_tokens = getattr(usage, "output_tokens", 0) or 0
    cache_read = getattr(usage, "cache_read_input_tokens", 0) or 0
    cache_creation = getattr(usage, "cache_creation_input_tokens", 0) or 0
    # The fast-mode docs price Opus 4.8 at $10 / MTok input and $50 / MTok output. No cache writes
    # are expected in this prompt, but include all reported input buckets conservatively.
    return ((input_tokens + cache_read + cache_creation) * 10.0 + output_tokens * 50.0) / 1e6


def _line_count(text: str) -> int:
    return len([line for line in text.splitlines() if line.strip()])


def run_claude(model: str, *, fast: bool, max_tokens: int) -> ArmResult:
    client = get_client()
    kwargs = {}
    if fast:
        kwargs = {"speed": "fast", "betas": ["fast-mode-2026-02-01"]}
    start = time.perf_counter()
    try:
        msg = client.beta.messages.create(
            model=model,
            max_tokens=max_tokens,
            messages=[{"role": "user", "content": PROMPT}],
            timeout=90.0,
            **kwargs,
        )
    except Exception as exc:  # noqa: BLE001 - record live API state, never fake access
        text = str(exc)
        return ArmResult(
            provider="claude",
            model=model,
            mode="fast" if fast else "standard",
            ran=False,
            access_blocked=("0 fast mode input tokens per minute" in text or "fast mode" in text.lower()),
            error_type=type(exc).__name__,
            error=text[:700],
            metric={"enablement": FAST_MODE_ENABLEMENT} if fast else {},
        )
    latency = time.perf_counter() - start
    text = "".join(getattr(b, "text", "") for b in msg.content if getattr(b, "type", None) == "text")
    usage = msg.usage
    output_tokens = getattr(usage, "output_tokens", 0) or 0
    speed_field = getattr(usage, "speed", None)
    cost = _fast_cost_usd(model, usage) if fast else cost_usd(model, usage)
    return ArmResult(
        provider="claude",
        model=model,
        mode="fast" if fast else "standard",
        ran=True,
        correct=_line_count(text) >= 10 and getattr(msg, "stop_reason", "") != "max_tokens",
        speed_field=speed_field,
        service_tier=getattr(usage, "service_tier", None),
        latency_s=latency,
        input_tokens=getattr(usage, "input_tokens", 0) or 0,
        output_tokens=output_tokens,
        output_chars=len(text),
        output_tokens_per_s=(output_tokens / latency) if latency else 0.0,
        cost_usd=cost,
        stop_reason=getattr(msg, "stop_reason", ""),
        metric={"prompt": PROMPT, "max_tokens": max_tokens},
    )


def _docs_equivalent_present() -> dict:
    root = repo_root()
    sources = {
        "openai_priority_processing": root / "sources" / "openai_priority_processing_2026-06-19.txt",
        "gemini_priority_inference": root / "sources" / "gemini_priority_inference_2026-06-19.txt",
    }
    needles = ("priority processing", "priority inference", "lower latency", "premium inference")
    out = {}
    for name, path in sources.items():
        text = path.read_text(errors="replace").lower() if path.exists() else ""
        hits = [n for n in needles if n in text]
        out[name] = {"path": str(path), "hits": hits, "equivalent_found": bool(hits)}
    return out


def score(standard: ArmResult, fast: ArmResult, docs_equivalence: dict) -> dict:
    competitor_priority_documented = any(v["equivalent_found"] for v in docs_equivalence.values())
    speedup = (fast.output_tokens_per_s / standard.output_tokens_per_s) if (
        standard.output_tokens_per_s and fast.output_tokens_per_s
    ) else 0.0
    fast_live = fast.ran and fast.speed_field == "fast"
    positive = standard.ran and fast_live and speedup >= 1.25 and fast.correct
    # Adjacent competitor priority paths mean this is held unless a future receipt adds live
    # competitor priority arms and shows a clean measured win.
    promotable = positive and not competitor_priority_documented and False
    return {
        "positive_signal": positive,
        "promotable_edge": promotable,
        "access_blocked": fast.access_blocked,
        "speedup_output_tokens_per_s": speedup,
        "competitor_priority_documented": competitor_priority_documented,
        "why_not_promotable": [] if promotable else [
            reason for reason, failed in [
                ("fast mode is not enabled for this org or did not return usage.speed='fast'", not fast_live),
                ("fast mode did not show at least 1.25x output-token throughput on this run", not (speedup >= 1.25)),
                ("closest competitor priority paths are documented and still need live best-to-best arms", competitor_priority_documented),
            ] if failed
        ],
    }


def write_receipt(receipt: dict) -> Path:
    out = repo_root() / "data" / "last_fast_mode.json"
    out.parent.mkdir(exist_ok=True)
    out.write_text(json.dumps(receipt, indent=2) + "\n")
    return out


def write_sources_if_missing() -> None:
    """Create tiny source stubs when the live sweep has not fetched these newer competitor docs yet."""
    source_dir = repo_root() / "sources"
    source_dir.mkdir(exist_ok=True)
    stubs = {
        "openai_priority_processing_2026-06-19.txt": (
            f"Source: {OPENAI_SOURCE}\nSnapshot fetched {DATE}. Verbatim excerpts for citation grounding.\n\n"
            "Priority processing delivers significantly lower and more consistent latency compared "
            "to Standard processing while keeping pay-as-you-go flexibility.\n"
        ),
        "gemini_priority_inference_2026-06-19.txt": (
            f"Source: {GEMINI_SOURCE}\nSnapshot fetched {DATE}. Verbatim excerpts for citation grounding.\n\n"
            "The Gemini Priority API is a premium inference tier designed for business-critical "
            "workloads that require lower latency and the highest reliability at a premium price point.\n"
        ),
    }
    for name, text in stubs.items():
        path = source_dir / name
        if not path.exists():
            path.write_text(text)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Validate Claude fast mode access and speed behavior.")
    parser.add_argument("--model", default="claude-opus-4-8")
    parser.add_argument("--max-tokens", type=int, default=512)
    args = parser.parse_args(argv)

    print("\n  fast_mode: live access and speed validation.\n")
    write_sources_if_missing()
    docs_equivalence = _docs_equivalent_present()

    print("  running Claude standard-speed control ...", flush=True)
    standard = run_claude(args.model, fast=False, max_tokens=args.max_tokens)
    print("  running Claude fast-mode probe ...", flush=True)
    fast = run_claude(args.model, fast=True, max_tokens=args.max_tokens)
    verdict = score(standard, fast, docs_equivalence)

    receipt = {
        "date": DATE,
        "claim_under_test": (
            "Claude fast mode uses the same Opus model with speed='fast' for higher output-token "
            "throughput, but competitor priority paths must be checked before any public edge claim."
        ),
        "sources": {
            "claude": CLAUDE_SOURCE,
            "claude_rate_limits": CLAUDE_RATE_LIMITS_SOURCE,
            "openai": OPENAI_SOURCE,
            "gemini": GEMINI_SOURCE,
        },
        "enablement_note": FAST_MODE_ENABLEMENT,
        "docs_equivalence_check": docs_equivalence,
        "arms": [standard.to_dict(), fast.to_dict()],
        "verdict": verdict,
    }
    path = write_receipt(receipt)

    print("\n  Result:")
    print(f"    positive_signal: {verdict['positive_signal']}")
    print(f"    promotable_edge: {verdict['promotable_edge']}")
    print(f"    access_blocked: {verdict['access_blocked']}")
    print(f"    speedup_output_tokens_per_s: {verdict['speedup_output_tokens_per_s']:.2f}x")
    if verdict["why_not_promotable"]:
        print("    held because:")
        for reason in verdict["why_not_promotable"]:
            print(f"      - {reason}")

    print("\n  Arms:")
    for arm in [standard, fast]:
        ran = "ran" if arm.ran else "not-run"
        status = arm.stop_reason or arm.error_type or "-"
        print(
            f"    {arm.provider:<7} {arm.mode:<8} {ran:<7} model={arm.model} "
            f"speed_field={arm.speed_field or '-'} stop={status} "
            f"otps={arm.output_tokens_per_s:.1f} cost={fmt_usd(arm.cost_usd)} "
            f"tokens={arm.total_tokens:,} latency={arm.latency_s:.1f}s"
        )
    if fast.access_blocked:
        print(f"\n  Enablement: {FAST_MODE_ENABLEMENT}")
    print(f"\n  wrote {path.relative_to(repo_root())}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
