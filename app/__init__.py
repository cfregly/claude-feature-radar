"""app: the forkable "run it on your own tool, watch your bill drop" artifact.

Two files, and you only edit one. `app/yourtool.py` is the single edit surface: replace its TOOL_SPEC
and call() with your own tool, keep the shape, and `app/billcut.py` runs the same fan-out task twice
over it (plain tool use vs programmatic tool calling) and prints your own before/after billed-input
table. Out of the box it ships a worked example so you can see a real number before you touch anything.

The token counter and the A/B run loop are imported from engine/demonstrators/token_core.py, the same
audited counter the repo's programmatic-tool-calling demo uses, so the app's number and the demo's
number are produced by one piece of code, never two.
"""
