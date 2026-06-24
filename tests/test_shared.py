"""Offline tests for the shared cross-vendor infrastructure (runner, providers, sandbox, platform).

No key, no network, no real model call. Every provider call is driven through a fake client, the
no-key paths are exercised by clearing the env and pointing the loader at an empty .env, and the
sandbox runs trivial Python locally (the one thing that does spawn a subprocess, by design, since
that is the backend being tested). The contracts these protect:

  - the cross-vendor registry: every model row carries a provider, and the new request_kwargs and
    effort helpers drop knobs a model rejects (so a Claude request never 400s).
  - the provider-blind runner: call() dispatches on provider, and to_arm() sums the carried-context
    bucket correctly per vendor (Claude input + cache_read + cache_write, others the inclusive field).
  - the access probe: a competitor client is None when its key is absent, so a demonstrator marks
    that arm ran=False instead of faking a row. SDKs are imported lazily, never at module load.
  - the sandbox grader: a correct program passes, a wrong one fails, untrusted code runs in a
    subprocess with a timeout.
  - the platform telemetry and the program.md spec parser round-trip.
"""

import sys
import types
from dataclasses import dataclass

import pytest

from common import models as M
from common import runner as R
from engine.demonstrators.base import Arm
from engine.demonstrators.shared import platform as P
from engine.demonstrators.shared import sandbox as S


# ----- the merged cross-vendor model registry -----

def test_every_model_row_has_a_provider():
    for key, m in M.MODELS.items():
        assert m.provider in ("anthropic", "openai", "gemini"), f"{key} has provider {m.provider!r}"


def test_the_claude_rows_kept_their_committed_prices():
    # The merge must not move the prices the committed $0.06 citations receipt rides on.
    assert M.get("opus").input_per_mtok == 5.0 and M.get("opus").output_per_mtok == 25.0
    assert M.get("sonnet").input_per_mtok == 3.0 and M.get("sonnet").output_per_mtok == 15.0
    assert M.get("haiku").input_per_mtok == 1.0 and M.get("haiku").output_per_mtok == 5.0


def test_competitor_rows_resolve_by_id():
    assert M.get("gpt-5.4").provider == "openai"
    assert M.get("gemini-3.5-flash").provider == "gemini"


def test_request_kwargs_drops_effort_on_a_model_without_it():
    # Haiku rejects effort with a 400, so request_kwargs must omit it rather than send it.
    kw = M.request_kwargs("haiku", effort="low")
    assert "output_config" not in kw and kw["model"] == M.get("haiku").id


def test_request_kwargs_sends_effort_and_thinking_where_supported():
    kw = M.request_kwargs("opus", effort="low", adaptive_thinking=True)
    assert kw["output_config"] == {"effort": "low"}
    assert kw["thinking"] == {"type": "adaptive"}


def test_supports_effort_helpers():
    assert M.supports_effort("opus") is True
    assert M.supports_effort("haiku") is False
    assert M.supports_effort_level("sonnet", "max") is True
    assert M.supports_effort_level("sonnet", "xhigh") is False  # no xhigh on Sonnet 4.6
    assert M.supports_effort_level("gpt-top", "xhigh") is True


# ----- the provider-blind runner -----

class _Usage:
    def __init__(self, **kw):
        for k, v in kw.items():
            setattr(self, k, v)


class _Block:
    def __init__(self, text):
        self.type = "text"
        self.text = text


class _Msg:
    def __init__(self, text, usage, stop_reason="end_turn"):
        self.content = [_Block(text)]
        self.usage = usage
        self.stop_reason = stop_reason


class _FakeAnthropic:
    """Records the create() kwargs and returns a canned message, so call() runs with no SDK."""

    def __init__(self, usage):
        self._usage = usage
        self.seen = {}
        self.messages = self

    def create(self, **kwargs):
        self.seen = kwargs
        return _Msg("hello", self._usage, stop_reason=kwargs.get("_stop", "end_turn"))


def test_call_dispatches_anthropic_and_costs_from_real_usage():
    usage = _Usage(input_tokens=1000, output_tokens=200, cache_read_input_tokens=500,
                   cache_creation_input_tokens=0)
    client = _FakeAnthropic(usage)
    res = R.call(client, "haiku", [{"role": "user", "content": "hi"}], max_tokens=16)
    assert res.text == "hello"
    assert res.input_tokens == 1000 and res.cache_read_tokens == 500
    # cost is computed from the usage, not asserted: 1000 in + 200 out + 500 cache_read on Haiku
    assert res.cost_usd == pytest.approx(
        (1000 * 1.0 + 200 * 5.0 + 500 * 0.10) / 1e6, rel=1e-6
    )


def test_call_sends_effort_only_on_a_model_that_takes_it():
    client = _FakeAnthropic(_Usage(input_tokens=1, output_tokens=1))
    R.call(client, "haiku", [{"role": "user", "content": "hi"}], effort="low")
    assert "output_config" not in client.seen  # Haiku rejects effort, so call() must omit it
    R.call(client, "opus", [{"role": "user", "content": "hi"}], effort="low")
    assert client.seen.get("output_config") == {"effort": "low"}


def test_to_arm_sums_carried_context_per_vendor():
    # A Claude Result carries cache buckets, so ctx is input + cache_read + cache_write.
    claude = R.Result(model="claude-haiku-4-5-20251001", text="x", latency_s=0.1,
                      input_tokens=100, output_tokens=10, cache_read_tokens=40, cache_write_tokens=20,
                      thinking_tokens=0, cost=M_cost(100, 10), raw=None)
    arm = R.to_arm(claude)
    assert isinstance(arm, Arm)
    assert arm.provider == "anthropic"
    assert arm.ctx == 160  # 100 + 40 + 20

    # An OpenAI Result has the inclusive field in input_tokens, cache buckets at 0, so ctx == input.
    oai = R.Result(model="gpt-5.4", text="y", latency_s=0.1, input_tokens=300, output_tokens=10,
                   cache_read_tokens=0, cache_write_tokens=0, thinking_tokens=0,
                   cost=M_cost(300, 10, key="gpt-mid"), raw=None)
    arm2 = R.to_arm(oai)
    assert arm2.provider == "openai" and arm2.ctx == 300


def M_cost(in_tok, out_tok, key="haiku"):
    from common.pricing import cost_breakdown
    return cost_breakdown(key, _Usage(input_tokens=in_tok, output_tokens=out_tok))


# ----- the access probe: no key means None, never a faked client, and SDKs load lazily -----

def _empty_env(monkeypatch, tmp_path):
    """Point the loader at an empty .env and clear the keys, so the no-key path is real."""
    from common import client as C
    monkeypatch.setattr(C, "repo_root", lambda: tmp_path)  # an empty dir, no .env
    for var in ("OPENAI_API_KEY", "GEMINI_API_KEY", "ANTHROPIC_API_KEY"):
        monkeypatch.delenv(var, raising=False)


def test_openai_client_is_none_without_a_key(monkeypatch, tmp_path):
    _empty_env(monkeypatch, tmp_path)
    from engine.providers import openai_provider as O
    assert O.get_openai_client() is None  # no key, no client, no faked row


def test_gemini_client_is_none_without_a_key(monkeypatch, tmp_path):
    _empty_env(monkeypatch, tmp_path)
    from engine.providers import gemini_provider as G
    assert G.get_gemini_client() is None


def test_runner_competitor_clients_are_none_without_a_key(monkeypatch, tmp_path):
    _empty_env(monkeypatch, tmp_path)
    assert R.get_openai_client() is None
    assert R.get_gemini_client() is None


def test_available_models_reports_unavailable_without_a_key(monkeypatch, tmp_path):
    _empty_env(monkeypatch, tmp_path)
    from engine.providers import openai_provider as O
    probe = O.available_models()
    assert all(not v["available"] for v in probe.values())  # every tier unavailable, none faked


def test_provider_modules_do_not_import_sdks_at_load():
    # The lazy-import contract: importing the provider modules must not require openai or google-genai.
    # Simulate their absence and re-import; a top-level import would raise.
    import importlib
    for sdk in ("openai", "google", "google.genai"):
        sys.modules.pop(sdk, None)
    with _block_imports("openai", "google.genai"):
        for mod in ("engine.providers.openai_provider", "engine.providers.gemini_provider",
                    "common.runner"):
            sys.modules.pop(mod, None)
            importlib.import_module(mod)  # must not raise even with the SDKs blocked


class _block_imports:
    """A context manager that makes the named top-level packages unimportable, to prove a module does
    not import them at load time."""

    def __init__(self, *names):
        self.names = names
        self._finder = None

    def __enter__(self):
        blocked = self.names

        class _Blocker:
            def find_spec(self, name, path=None, target=None):
                if any(name == b or name.startswith(b + ".") for b in blocked):
                    raise ImportError(f"blocked for test: {name}")
                return None

        self._finder = _Blocker()
        sys.meta_path.insert(0, self._finder)
        return self

    def __exit__(self, *exc):
        sys.meta_path.remove(self._finder)
        return False


# ----- the no-Docker sandbox grader -----

def test_sandbox_grades_a_correct_program():
    code = "n = int(input())\nprint(2 * n)"
    ok, msg = S.grade(code, [("5\n", "10"), ("21\n", "42")])
    assert ok is True and msg == "pass"


def test_sandbox_fails_a_wrong_program():
    code = "n = int(input())\nprint(n)"  # prints n, not 2n
    ok, msg = S.grade(code, [("5\n", "10")])
    assert ok is False and "wrong answer" in msg


def test_sandbox_reports_no_code():
    ok, msg = S.grade("", [("5\n", "10")])
    assert ok is False and msg == "no code"


def test_sandbox_times_out_a_hanging_program():
    code = "while True:\n    pass"
    ok, msg = S.grade(code, [("", "")], timeout=1.0)
    assert ok is False and "timeout" in msg


def test_extract_code_takes_the_last_fenced_block():
    text = "first\n```python\nprint(1)\n```\nthen\n```python\nprint(2)\n```"
    assert S.extract_code(text) == "print(2)"


# ----- the platform telemetry -----

def test_platform_marks_a_feature_once_and_recaps():
    P.reset()
    P.used("citations")
    P.used("citations")  # second call is a no-op
    P.used("programmatic_tool_calling")
    assert P.exercised_keys() == ["programmatic_tool_calling", "citations"]  # FEATURES order, deduped
    assert "Citations" in P.summary() and "programmatic tool calling" in P.summary()


def test_platform_summary_is_none_when_nothing_fired():
    P.reset()
    assert P.summary().endswith("none")
