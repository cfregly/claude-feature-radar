"""Find out why a prompt-cache read missed, with Claude cache diagnostics.

Your cached prefix stopped hitting and the only signal is cache_read_input_tokens
dropping to zero. Claude cache diagnostics compares two consecutive requests and
returns a typed cache_miss_reason that names exactly what changed: the model, the
system prompt, the tools, or the message history. No more guessing.

Usage:
  python run.py            # one live run: name the changed prefix surface, print the table
  python run.py --check    # self-test: assert the API names system_changed (about $0.02)

Cost: about $0.02 for --check on the 2026-06-19 run.
Doc:  https://platform.claude.com/docs/en/build-with-claude/cache-diagnostics
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from .common.models import get  # noqa: E402,F401  (registry id and price source of truth)
from .common.pricing import cost_usd  # noqa: E402

CLAUDE_MODEL = "claude-haiku-4-5-20251001"
BETA_HEADER = "cache-diagnosis-2026-04-07"
DOC = "https://platform.claude.com/docs/en/build-with-claude/cache-diagnostics"


def _system(prefix: str, repeats: int) -> str:
    return "You are a terse cache diagnostics probe. " + (f"{prefix} alpha beta gamma. " * repeats)


def _probe(model: str, repeats: int) -> dict:
    from .common.client import get_client

    client = get_client()
    base = _system("stable-prefix", repeats)
    changed = _system("changed-prefix", repeats)

    def call(system: str, previous_id: str | None):
        return client.beta.messages.create(
            model=model,
            max_tokens=16,
            cache_control={"type": "ephemeral"},
            system=system,
            messages=[{"role": "user", "content": "Reply ok."}],
            diagnostics={"previous_message_id": previous_id},  # add this
            betas=[BETA_HEADER],                                # add this
            timeout=60.0,
        )

    start = time.perf_counter()
    first = call(base, None)
    second = call(changed, first.id)
    latency = time.perf_counter() - start

    reason = getattr(getattr(second, "diagnostics", None), "cache_miss_reason", None)
    observed = getattr(reason, "type", "") if reason is not None else ""
    missed = getattr(reason, "cache_missed_input_tokens", 0) or 0
    cost = cost_usd(model, first.usage) + cost_usd(model, second.usage)
    return {
        "model": model,
        "miss_reason": observed,
        "missed_tokens": int(missed),
        "cost_usd": cost,
        "latency_s": latency,
    }


def _print_table(r: dict) -> None:
    print(f"\n  Claude cache diagnostics, live run. cost ${r['cost_usd']:.4f}, {r['latency_s']:.1f}s\n")
    print("  field             value")
    print("  ----------------------------------------")
    print(f"  model             {r['model']}")
    print(f"  miss reason       {r['miss_reason'] or '-'}")
    print(f"  missed tokens     {r['missed_tokens']:,}")
    print(f"  cost              ${r['cost_usd']:.4f}")
    print(f"  wall time         {r['latency_s']:.1f}s")
    print()


def cmd_run(args) -> int:
    r = _probe(args.model, args.repeats)
    _print_table(r)
    print(f"  Claude named the changed prefix surface: {r['miss_reason']!r}.")
    print(f"  Doc: {DOC}\n")
    return 0


def cmd_check(args) -> int:
    r = _probe(args.model, args.repeats)
    _print_table(r)
    assert r["miss_reason"] == "system_changed", (
        f"expected system_changed, got {r['miss_reason']!r}"
    )
    assert r["missed_tokens"] > 0, "expected a positive missed-input-token estimate"
    print("  CHECK PASSED: Claude named the changed surface (system_changed) with a token estimate.\n")
    return 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Claude cache diagnostics: name the silent cache-miss cause.")
    parser.add_argument("--check", action="store_true", help="self-test the win invariant")
    parser.add_argument("--model", default=CLAUDE_MODEL)
    parser.add_argument("--repeats", type=int, default=850, help="prefix length knob")
    args = parser.parse_args(argv)
    return cmd_check(args) if args.check else cmd_run(args)


if __name__ == "__main__":
    raise SystemExit(main())
