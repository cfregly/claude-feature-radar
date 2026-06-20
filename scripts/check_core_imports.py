"""One-dependency gate: the engine's core imports with anthropic alone.

The cross-vendor runner and the OpenAI and Gemini provider callers add imports that must stay
OPTIONAL: a new third-party dep (openai, google-genai) lives in
requirements-compare.txt, and the imported demonstrator code pulls those SDKs lazily, so the core
still runs with just anthropic installed. This gate proves it: it blocks openai and google-genai at
the import system, then imports every core module and registers the built demonstrators. A stray
top-level `import openai` anywhere on the core path makes this exit nonzero.

Stdlib only, no key, no network. Runs in CI right after `pip install anthropic` (the one dependency),
before pytest installs the dev extra.
"""

from __future__ import annotations

import importlib
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

# The optional comparison and MCP SDKs. Block them so any core module that imports one at load fails
# loudly. mcp is the optional server SDK (requirements-mcp.txt): the MCP logic layer engine.mcp_tools
# must import without it, so the server's gate boundary stays testable with anthropic alone.
BLOCKED = ("openai", "google", "google.genai", "mcp")


class _Blocker:
    def find_spec(self, name, path=None, target=None):
        if any(name == b or name.startswith(b + ".") for b in BLOCKED):
            raise ImportError(f"one-dependency gate blocked an optional SDK at import: {name}")
        return None


def main() -> int:
    sys.meta_path.insert(0, _Blocker())
    for mod in [m for m in list(sys.modules) if m.startswith(BLOCKED)]:
        del sys.modules[mod]

    core = [
        "common.client", "common.models", "common.pricing", "common.runner", "common.compare_clients",
        "engine.demokinds", "engine.gate", "engine.scan", "engine.sweep_edges",
        "engine.cite_facts", "engine.draft_email", "engine.product_alert", "engine.verify",
        "engine.publish_brief", "engine.mcp_tools",
        "engine.sources_registry", "engine.cadence", "engine.coverage", "engine.managed",
        "engine.demonstrators", "engine.demonstrators.base", "engine.demonstrators.registry",
        "engine.demonstrators.shared.sandbox", "engine.demonstrators.shared.platform",
        "engine.demonstrators.eval_quality", "engine.demonstrators.retention_resume",
        "engine.demonstrators.cost_model", "engine.demonstrators.other_parity_gated",
        "engine.providers.openai_provider", "engine.providers.gemini_provider",
    ]
    failed = []
    for mod in core:
        try:
            importlib.import_module(mod)
        except Exception as e:  # noqa: BLE001
            failed.append(f"{mod}: {type(e).__name__}: {e}")

    # The built demonstrators must still register with the SDKs blocked (their run_*_arm is lazy).
    try:
        from engine.demonstrators.registry import register_all
        reg = register_all()
        for kind in ("token_accounting", "grounding_resolution", "long_horizon_survival",
                     "eval_quality", "retention_resume", "cost", "other"):
            if kind not in reg:
                failed.append(f"built demonstrator for '{kind}' did not register with SDKs blocked")
    except Exception as e:  # noqa: BLE001
        failed.append(f"register_all: {type(e).__name__}: {e}")

    if failed:
        print("one-dependency gate: FAIL (a core module needs an optional SDK at import time)")
        for f in failed:
            print("  -", f)
        return 1
    print(f"one-dependency gate: clean ({len(core)} core modules import with anthropic alone)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
