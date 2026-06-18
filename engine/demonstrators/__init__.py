"""demonstrators: one plugin per demoKind, each proving an edge through the same interface.

The package holds the Demonstrator protocol and the standard dataclasses (engine/demonstrators/base.py),
the registry and dispatcher (engine/demonstrators/registry.py), and one demonstrator module per
demoKind. The three built edges (PTC, Citations, context editing) implement the interface in
edges/<key>/demo.py and register here.

The shared/ subpackage carries the backends every demonstrator plugs into, lifted from the A and B
harnesses in Phase 3: the no-Docker sandbox executor (shared/sandbox.py), the per-demo platform
telemetry (shared/platform.py), and the program.md spec parser for budgeted kinds (shared/spec.py).
The cross-vendor competitor arm runs through common/runner.py call() and engine/providers/.
"""
