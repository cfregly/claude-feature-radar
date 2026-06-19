"""app: the forkable "run it on your own tool, watch your token bill drop" artifact.

Three files, and you only edit one. `app/my_tool.py` is the single edit surface: replace its TOOL_SPEC,
call(), and fan-out task with your own tool, keep the shape, and `app/run_tokens.py` runs the same
fan-out task twice over it (plain tool use vs programmatic tool calling) and prints your own
before-and-after billed-input table. Out of the box `app/my_tool.py` ships as a working copy of the
worked example in `app/example_tool.py` (the region_sales fixture), so you can see a real number before
you touch anything.

  app/my_tool.py      the single edit surface, ships as a copy of the example so it runs out of the box
  app/run_tokens.py   the runner: drives my_tool through both modes and prints the token bill
  app/example_tool.py the shipped worked example (region_sales), the single home for the fixture

The token counter and the A/B run loop are imported from engine/demonstrators/token_core.py, the same
audited counter the repo's programmatic-tool-calling demo uses, so the app's number and the demo's
number are produced by one piece of code, never two.
"""
