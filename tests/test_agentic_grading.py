"""Offline tests for the agentic_grading demonstrator.

No key, no network, no Docker, no dataset download: every test drives the pure-Python pieces
(repair_patch, extract_patch, the salient-log compressor) directly, and the demonstrator interface
against a synthetic in-memory run, so the symmetric-loop fairness and the honesty contract are proven
without a model call. The dataset and grader (datasets + swebench + uv) are exercised live by
`make validate` and `make agentic`, which spend; these tests protect the logic those runs depend on.

What these tests protect:
  - the demonstrator registers under agentic_grading and declares its kind.
  - score() runs the SAME gate (resolved K/N off the real suite) and emits claude-ahead only when
    Claude strictly out-resolves every competitor arm that RAN.
  - the honesty contract: a claude-ahead score is downgraded to never-evaluated when a competitor arm
    did not run (an absent key), never shipped as an unproven lead.
  - parity on a tie and claude-behind when a competitor wins (the product-team direction).
  - repair_patch fixes a botched hunk header against the base file so a correct edit is not discarded.
  - the symmetric loop forwards the SAME accumulated history to every provider (the confound fix):
    the OpenAI and Gemini message normalizers carry every prior turn, not just the last.
"""

from engine.demonstrators import agentic_grading as ag
from engine.demonstrators.base import Arm, Verdict
from engine.demonstrators.registry import REGISTRY, register_all


# ----- registration -----

def test_agentic_grading_registers():
    register_all()
    demo = REGISTRY.get("agentic_grading")
    assert demo is not None
    assert demo.demo_kind == "agentic_grading"


def test_dispatch_routes_swebench_to_agentic_grading():
    from engine.demonstrators.registry import dispatch
    register_all()
    r = dispatch({"key": "swebench", "axis": "agentic-success"})
    assert r.covered is True
    assert r.demo_kind == "agentic_grading"
    assert r.estimate is not None and r.estimate.usd > 0   # it spends, so it is an ASK
    assert r.gate == "ask"
    assert r.estimate.command == "make agentic"


# ----- the score gate and the honesty contract -----

def _claude(resolved, n=4):
    return Arm(provider="anthropic", model="claude-opus-4-8", ran=True,
               metric={"resolved": resolved, "n": n, "k_of_n": f"{resolved}/{n}", "rounds_landed": []})


def _comp(provider, model, resolved, n=4, ran=True):
    return Arm(provider=provider, model=model, ran=ran,
               metric={"resolved": resolved, "n": n, "k_of_n": f"{resolved}/{n}", "rounds_landed": []} if ran else {})


def test_score_claude_ahead_when_it_out_resolves_every_competitor_that_ran():
    d = ag.AgenticGradingDemonstrator()
    claude = _claude(4)
    comps = [_comp("openai", "gpt-5.5", 1), _comp("gemini", "gemini-3.1-pro-preview", 1)]
    v = d.score(claude, comps, {})
    assert v.verdict == "claude-ahead"
    assert v.passed is True


def test_score_parity_on_a_tie():
    d = ag.AgenticGradingDemonstrator()
    v = d.score(_claude(2), [_comp("openai", "gpt-5.5", 2)], {})
    assert v.verdict == "parity"
    assert v.passed is False


def test_score_claude_behind_when_a_competitor_wins():
    d = ag.AgenticGradingDemonstrator()
    v = d.score(_claude(1), [_comp("openai", "gpt-5.5", 3)], {})
    assert v.verdict == "claude-behind"


def test_score_holds_at_never_evaluated_when_a_competitor_arm_did_not_run():
    # Claude out-resolves the arms that ran, but one competitor key was absent. score() proposes
    # claude-ahead, and the receipt honesty contract must downgrade it.
    d = ag.AgenticGradingDemonstrator()
    claude = _claude(4)
    comps = [_comp("openai", "gpt-5.5", 1), _comp("gemini", "gemini-3.1-pro-preview", 0, ran=False)]
    v = d.score(claude, comps, {})
    # the gate itself sees only the arms that ran, so it can read claude-ahead...
    assert v.verdict == "claude-ahead"
    # ...but the receipt downgrades because not every competitor arm ran.
    edge = {"key": "swebench", "axis": "agentic-success", "demoKind": "agentic_grading",
            "fair_comparison": {"lead_basis": "head-to-head"}, "claim": "agentic coding separates"}
    receipt = d.receipt(edge, claude, comps, v, {"estimate": {}})
    assert receipt.verdict == "never-evaluated"


def test_receipt_claude_ahead_stands_when_every_competitor_arm_ran():
    d = ag.AgenticGradingDemonstrator()
    claude = _claude(4)
    comps = [_comp("openai", "gpt-5.5", 1), _comp("gemini", "gemini-3.1-pro-preview", 2)]
    v = d.score(claude, comps, {})
    edge = {"key": "swebench", "axis": "agentic-success", "demoKind": "agentic_grading",
            "fair_comparison": {"lead_basis": "head-to-head"}, "claim": "x"}
    receipt = d.receipt(edge, claude, comps, v, {"estimate": {}})
    assert receipt.verdict == "claude-ahead"
    assert receipt.demo_kind == "agentic_grading"
    assert "task_shape" in receipt.workload
    # the per-arm K/N is carried so the table is reconstructable from the receipt.
    assert receipt.metric.get("per_arm")


# ----- repair_patch: a correct edit with a botched header is rescued -----

def test_repair_patch_fixes_a_botched_hunk_header():
    base = ["def f():", "    return 1", "", "def g():", "    return 2"]
    # The model got the edit right (return 1 -> return 10) but the @@ header line numbers are wrong.
    patch = (
        "--- a/m.py\n+++ b/m.py\n"
        "@@ -999,3 +999,3 @@\n"
        " def f():\n"
        "-    return 1\n"
        "+    return 10\n"
    )
    fixed = ag.repair_patch(patch, lambda p: base)
    # the header is recomputed to the real location (the 'def f()' block starts at line 1).
    assert "@@ -1,2 +1,2 @@" in fixed
    assert "+    return 10" in fixed


def test_extract_patch_pulls_the_diff_block():
    text = "Here is the fix:\n```diff\ndiff --git a/x b/x\n--- a/x\n+++ b/x\n@@ -1 +1 @@\n-a\n+b\n```\ndone"
    out = ag.extract_patch(text)
    assert out.startswith("diff --git a/x b/x")
    assert out.endswith("\n")


def test_salient_keeps_the_failure_lines():
    raw = "\n".join(["1 passed", "noise line", "FAILED test_thing - AssertionError", "more noise"])
    out = ag._salient(raw, ["test_thing"])
    assert "FAILED test_thing" in out
    assert "noise line" not in out


# ----- the symmetric loop: every provider gets the SAME accumulated history -----

def test_openai_normalizer_forwards_full_multi_turn_history():
    from engine.providers.openai_provider import _to_input
    messages = [
        {"role": "user", "content": "the issue"},
        {"role": "assistant", "content": "patch v1"},
        {"role": "user", "content": "the test failure"},
    ]
    out = _to_input(messages)
    # all three turns survive, not just the last: this is the confound fix.
    assert [m["role"] for m in out] == ["user", "assistant", "user"]
    assert out[0]["content"] == "the issue"
    assert out[-1]["content"] == "the test failure"
    # a plain string still maps to one user turn.
    assert _to_input("hello") == [{"role": "user", "content": "hello"}]


def test_gemini_normalizer_forwards_full_history_and_maps_assistant_to_model():
    # A tiny stand-in for google.genai.types so this runs with no SDK installed.
    class _Part:
        def __init__(self, text):
            self.text = text

    class _Content:
        def __init__(self, role, parts):
            self.role, self.parts = role, parts

    class _Types:
        Part = _Part
        Content = _Content

    from engine.providers.gemini_provider import _to_contents
    messages = [
        {"role": "user", "content": "issue"},
        {"role": "assistant", "content": "patch v1"},
        {"role": "user", "content": "failure"},
    ]
    out = _to_contents(messages, _Types)
    assert [c.role for c in out] == ["user", "model", "user"]   # assistant -> model, all turns kept
    assert out[0].parts[0].text == "issue"
    # a plain string passes straight through (Gemini accepts a raw string for one turn).
    assert _to_contents("hello", _Types) == "hello"


def test_runner_forwards_full_messages_to_competitor_providers(monkeypatch):
    # The runner's competitor paths must hand the WHOLE messages list to the provider caller, not just
    # the last turn. We capture what call_openai / call_gemini receive.
    import common.runner as runner

    seen = {}

    def fake_openai(client, prompt, effort, model_id, max_tokens):
        seen["openai"] = prompt
        return {"text": "ok", "input_tokens": 1, "output_tokens": 1, "latency_s": 0.0, "truncated": False}

    def fake_gemini(client, prompt, effort, model_id, max_tokens):
        seen["gemini"] = prompt
        return {"text": "ok", "input_tokens": 1, "output_tokens": 1, "latency_s": 0.0, "truncated": False}

    import engine.providers.openai_provider as op
    import engine.providers.gemini_provider as gp
    monkeypatch.setattr(op, "call_openai", fake_openai)
    monkeypatch.setattr(gp, "call_gemini", fake_gemini)

    messages = [{"role": "user", "content": "a"}, {"role": "assistant", "content": "b"},
                {"role": "user", "content": "c"}]
    runner.call(None, "gpt-top", messages, max_tokens=16)
    runner.call(None, "gem-pro", messages, max_tokens=16)
    # both providers received the full three-turn list, not messages[-1] only.
    assert isinstance(seen["openai"], list) and len(seen["openai"]) == 3
    assert isinstance(seen["gemini"], list) and len(seen["gemini"]) == 3
    assert seen["openai"][0]["content"] == "a"
    assert seen["gemini"][-1]["content"] == "c"
