"""Per-demo feature telemetry: make the Claude platform surfaces a run leans on visible at runtime.

Widened to the surfaces this engine's
demonstrators exercise. Each feature prints a one-line marker to stderr the first time it fires, so a
run teaches what it leans on instead of using it silently. A demonstrator's receipt() reads
exercised() (or exercised_keys()) so its "what this teaches about the platform" line is grounded in
what actually ran, not asserted.

Stdlib only, no SDK. exercised() and summary() give the end-of-run recap.
"""

from __future__ import annotations

import sys

# The platform surfaces this engine exercises, in the rough order they tend to fire. The first block
# is the cross-cutting set; the second names the surfaces specific demonstrators in this engine prove.
FEATURES = {
    "tools": "forced tool use (structured output, no parsing)",
    "cache": "prompt caching (shared prefix cached across cases)",
    "cost": "token-based cost accounting",
    "tiers": "model tiers (Haiku, Sonnet, Opus, Fable)",
    "parallel": "parallel fan-out (concurrent Claude calls)",
    "panel": "judge panel (independent votes)",
    "managed": "Managed Agents (hosted sandbox, beta)",
    # engine-specific edge surfaces
    "programmatic_tool_calling": "programmatic tool calling (allowed_callers keeps tool outputs out of context)",
    "code_execution": "code execution sandbox (server-side, beta)",
    "citations": "Citations (verifiable per-character source pointer)",
    "context_editing": "context editing (in-place tool-result clearing)",
    "memory": "the memory tool (durable state across a clear or kill)",
    "effort": "the model-gated reasoning effort knob",
    "thinking": "adaptive extended thinking",
}

_seen: set[str] = set()


def used(key: str, detail: str = "") -> None:
    """Mark a feature as exercised and print it once."""
    if key in _seen:
        return
    _seen.add(key)
    label = FEATURES.get(key, key)
    extra = f", {detail}" if detail else ""
    print(f"[platform] {label}{extra}", file=sys.stderr)


def reset() -> None:
    """Clear the seen set. Useful between independent demonstrator runs and in tests."""
    _seen.clear()


def exercised_keys() -> list[str]:
    """The feature KEYS that fired this run, in FEATURES order (stable for a receipt field)."""
    return [k for k in FEATURES if k in _seen]


def exercised() -> list[str]:
    """The human labels for the features that fired this run."""
    return [FEATURES[k] for k in exercised_keys()]


def summary() -> str:
    names = exercised()
    return "Platform features exercised: " + (", ".join(names) if names else "none")
