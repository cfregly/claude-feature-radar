"""my_tool: THE single file you edit to run the token-bill comparison on your own tool.

HOW TO RUN THIS ON YOUR OWN TOOL (3 steps):
  1. Replace TOOL_SPEC below with your own Messages-API tool dict (the same dict you already pass in
     tools=[...]): name, description, input_schema.
  2. Replace call(...) with the function that actually runs your tool. Its keyword arguments match
     input_schema's properties, and it returns whatever the model would normally get back (a list,
     dict, or string).
  3. Set QUESTION and EXAMPLE_INPUTS to your own fan-out task, the prompt that makes the model call
     your tool many times.
Then run `make app` to see your own before-and-after input tokens. Out of the box this file ships as
a working copy of the region_sales worked example, so `make app-check` works before you change
anything.

THE EDIT SURFACE, the five things you replace:

  TOOL_SPEC   a Messages-API tool dict: name, description, input_schema. The exact dict you already
              pass in `tools=[...]`. Copy yours in.
  call(...)   the Python that actually runs your tool. It takes the tool's input arguments as keyword
              arguments (matching input_schema's properties) and returns a JSON-serializable result
              (a list, a dict, a string). This is your real backend: a database query, an API call,
              a file read. Whatever the model would get back.
  QUESTION and EXAMPLE_INPUTS   the fan-out task: a prompt that makes the model call your tool many
              times, and the list of inputs it should fan out over. Programmatic tool calling pays off
              when the model calls a tool many times and the bulky outputs would otherwise flow
              through its context, so the task has to fan out. On a sequential single-call task the
              doc reports it is flat to about 8% more expensive, so a one-shot task is the wrong
              shape and the bill will not drop.
  EXPECTED_ANSWER and parse_answer   only the worked example needs a machine-checkable true answer,
              so `make app-check` can assert the model answered correctly. When you swap in your own
              tool, set EXPECTED_ANSWER to your task's known answer (or leave it None and --check will
              assert only the token invariant, not correctness), and replace parse_answer with however
              your task states its answer.

Out of the box this ships the worked example from app/example_tool.py: a region_sales tool that
returns about 60 sales rows per region, and a task that asks for the highest-revenue region across
four regions (240 rows). That is the same fan-out the repo's programmatic-tool-calling receipt
measures, so `python -m app.run_tokens --check` gives you a real before-and-after number before you
change a line. Then swap in your own.

Nothing here imports anthropic. my_tool is data plus a plain Python function. app/run_tokens.py
drives it.
"""

from __future__ import annotations

# This file ships as a working copy of the region_sales worked example so the app runs out of the box.
# Replace the five names below (and the import) with your own tool. The example backend lives in
# app/example_tool.py, the single home for the shipped fixture.
from app.example_tool import (  # noqa: F401  re-exported as the edit surface
    EXAMPLE_INPUTS,
    EXPECTED_ANSWER,
    QUESTION,
    TOOL_SPEC,
    parse_answer,
    region_sales as _region_sales,
)


def call(region: str = ""):
    """Run the tool for one input and return a JSON-serializable result. Your real backend goes here.

    The example reads the deterministic backend in app/example_tool.py. Replace the body with your
    database query, API call, or file read. The return value is what the model (or the sandbox, under
    programmatic tool calling) receives as the tool result.
    """
    return _region_sales(region)
