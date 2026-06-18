"""shared: the backends every demonstrator plugs into.

  sandbox.py   run model-generated code against a problem's tests in a no-Docker sandboxed
               subprocess (timeout, new session, resource limits).
  platform.py  per-demo feature telemetry: each Claude surface a run leans on prints one marker
               the first time it fires, so a Receipt's "what this teaches about the platform" is
               runtime-grounded.

Both are stdlib only and import no SDK, so they load with the offline core and run in the
mocked tests with no key.
"""
