"""demonstrators: one plugin per demoKind, each proving an edge through the same interface.

The package holds the Demonstrator protocol and the standard dataclasses (engine/demonstrators/base.py),
the registry and dispatcher (engine/demonstrators/registry.py), and one demonstrator module per
demoKind. The three built edges (PTC, Citations, context editing) implement the interface in
edges/<key>/demo.py and register here.
"""
