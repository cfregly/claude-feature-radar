"""providers: the cross-vendor callers every demonstrator's competitor arm runs through.

Ported from ship-on-claude common/openai_provider.py and common/gemini_provider.py, the
provider-blind, access-probing layer a Demonstrator's competitor arm runs through. It is the
single-call demonstrator path. The stateful multi-turn chain agents in engine/openai_arm.py and
engine/gemini_arm.py stay the backend for the legacy long-horizon comparison (compare, sweep,
longhorizon_compare), so the committed receipts do not move. Each provider here exposes three
functions:

  get_<vendor>_client()   a client, or None when the key is unset (the run stays Claude only).
  call_<vendor>()         one timed call, returning the harness receipt dict (text, token counts,
                          latency, truncated), never a faked row.
  available_models()      an access probe: a real tiny call to each candidate, reporting which the
                          key can reach, so an access-gated tier is unavailable, never absent.

Every SDK import is lazy, inside the function that needs it, so importing this package, or the
engine.demonstrators that build on it, costs nothing but the stdlib and never pulls openai or
google-genai. The one-command, one-dependency core (anthropic only) is preserved on purpose.
"""
