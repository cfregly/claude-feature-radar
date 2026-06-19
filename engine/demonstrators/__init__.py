"""demonstrators: one plugin per demoKind, each proving an edge through the same interface.

The package holds the Demonstrator protocol and the standard dataclasses (engine/demonstrators/base.py),
the registry and dispatcher (engine/demonstrators/registry.py), and one demonstrator module per
demoKind. Three edges (programmatic tool calling, citations, context editing) ship a runnable
edges/<key>/demo.py; the rest (eval quality, cost model, retention/resume, and the parity-gated long
tail) live as modules under engine/demonstrators/. All register here.

The shared/ subpackage carries the backends every demonstrator plugs into: the no-Docker sandbox
executor (shared/sandbox.py) and the per-demo platform telemetry (shared/platform.py). The
cross-vendor competitor arm runs through common/runner.py call() and engine/providers/.
"""
