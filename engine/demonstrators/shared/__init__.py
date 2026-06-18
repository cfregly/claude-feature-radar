"""shared: the backends every demonstrator plugs into, lifted from the A and B harnesses.

  sandbox.py   run model-generated code against a problem's tests in a no-Docker sandboxed
               subprocess (timeout, new session, resource limits). Ported from
               ship-on-claude edges/cost-and-effort/grader.py.
  platform.py  per-demo feature telemetry: each Claude surface a run leans on prints one marker
               the first time it fires, so a Receipt's "what this teaches about the platform" is
               runtime-grounded. Ported from claude-overnight overnight/platform.py.
  spec.py      parse a budgeted demonstrator's program.md into the model search space, decoding
               bounds, and the spend or wall-clock budget. Ported from claude-overnight
               overnight/spec.py.

All three are stdlib only and import no SDK, so they load with the offline core and run in the
mocked tests with no key.
"""
