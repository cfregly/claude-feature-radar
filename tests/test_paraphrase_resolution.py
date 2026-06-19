"""Offline tests for the citations feature-vs-feature cross-vendor gate.

No key, no network, no model call: synthetic ArmResult rows drive the deterministic score gate. The
demonstrator pits Claude's inline citations against OpenAI file_search and Gemini File Search over a
user's own documents. The gate promotes only when Claude returns a resolving char-span into the supplied
documents with ZERO hosted objects while both competitors need a hosted store and return a coarser
file/chunk-level pointer. The tests pin exactly when it promotes and when it holds, and confirm the
Demonstrator interface routes through the base honesty contract.
"""

from engine.demonstrators import paraphrase_resolution as pr
from engine.demonstrators.base import Verdict

N = 6


def _arm(provider, *, pointer_kind, resolved=N, source_correct=N, persisted=0, ran=True, errors=None):
    name = {"anthropic": "claude citations:sonnet", "openai": "openai file_search:gpt-top",
            "gemini": "gemini File Search:gem-pro"}[provider]
    mech = {"anthropic": "inline citations", "openai": "hosted file_search",
            "gemini": "hosted File Search"}[provider]
    return pr.ArmResult(name=name, provider=provider, model=f"{provider}-m", mechanism=mech,
                        ran=ran, asked=N, cited=resolved, resolved=resolved, source_correct=source_correct,
                        persisted_objects=persisted, setup_calls=persisted, pointer_kind=pointer_kind,
                        errors=errors or [])


def _run(arms):
    return pr.ParaRun(arms=arms, n_questions=N, total_cost=0.15)


def test_promotes_when_claude_char_span_zero_objects_vs_hosted_competitors():
    run = _run([
        _arm("anthropic", pointer_kind="char-span", persisted=0),
        _arm("openai", pointer_kind="file-level", persisted=4),
        _arm("gemini", pointer_kind="chunk-level", persisted=4),
    ])
    v = pr.score_run(run)
    assert v["promotable_edge"] is True
    assert v["claude_char_span_into_supplied_docs"] is True
    assert v["claude_persisted_objects"] == 0
    assert v["competitor_total_persisted_objects"] == 8


def test_holds_if_a_competitor_cites_without_a_hosted_store():
    run = _run([
        _arm("anthropic", pointer_kind="char-span", persisted=0),
        _arm("openai", pointer_kind="file-level", persisted=0),   # no hosted store -> parity on data residency
        _arm("gemini", pointer_kind="chunk-level", persisted=4),
    ])
    v = pr.score_run(run)
    assert v["promotable_edge"] is False
    assert any("without a hosted store" in r for r in v["why_not_promotable"])


def test_holds_if_a_competitor_returns_a_char_span():
    run = _run([
        _arm("anthropic", pointer_kind="char-span", persisted=0),
        _arm("openai", pointer_kind="char-span", persisted=4),    # parity on granularity
        _arm("gemini", pointer_kind="chunk-level", persisted=4),
    ])
    v = pr.score_run(run)
    assert v["promotable_edge"] is False
    assert any("char-span pointer" in r for r in v["why_not_promotable"])


def test_holds_if_claude_needs_hosted_objects():
    run = _run([
        _arm("anthropic", pointer_kind="char-span", persisted=1),
        _arm("openai", pointer_kind="file-level", persisted=4),
        _arm("gemini", pointer_kind="chunk-level", persisted=4),
    ])
    v = pr.score_run(run)
    assert v["promotable_edge"] is False
    assert v["claude_char_span_into_supplied_docs"] is True   # the char span is fine; the hosted object is not


def test_holds_if_claude_does_not_ground_every_answer():
    run = _run([
        _arm("anthropic", pointer_kind="char-span", resolved=N - 1, source_correct=N - 1, persisted=0),
        _arm("openai", pointer_kind="file-level", persisted=4),
        _arm("gemini", pointer_kind="chunk-level", persisted=4),
    ])
    v = pr.score_run(run)
    assert v["promotable_edge"] is False
    assert any("resolving char-span" in r for r in v["why_not_promotable"])


def test_holds_if_a_competitor_arm_did_not_run():
    run = _run([
        _arm("anthropic", pointer_kind="char-span", persisted=0),
        _arm("openai", pointer_kind="file-level", persisted=4),
        _arm("gemini", pointer_kind="none", resolved=0, ran=False, errors=["setup failed"]),
    ])
    v = pr.score_run(run)
    assert v["promotable_edge"] is False
    assert v["all_competitors_ran"] is False


# ----- the Demonstrator interface routes through the base honesty contract -----

def test_interface_routes_claude_ahead_only_when_every_competitor_ran():
    demo = pr.CitationsVsStoresDemonstrator()
    run = _run([
        _arm("anthropic", pointer_kind="char-span", persisted=0),
        _arm("openai", pointer_kind="file-level", persisted=4),
        _arm("gemini", pointer_kind="chunk-level", persisted=4),
    ])
    spec = {"_run": run}
    claude = demo.run_claude_arm({}, spec)
    competitors = demo.run_competitor_arms({}, spec)
    verdict = demo.score(claude, competitors, spec)
    assert verdict.verdict == "claude-ahead"
    edge = {"key": "citations", "axis": "grounding", "demoKind": "grounding_resolution",
            "fair_comparison": {"lead_basis": "head-to-head"}, "claim": "x"}
    receipt = demo.receipt(edge, claude, competitors, verdict, spec)
    assert receipt.verdict == "claude-ahead"     # every competitor arm ran, so the contract lets it stand
    assert receipt.demo_kind == "grounding_resolution"
    assert receipt.fairness.get("lead_basis") == "head-to-head"


def test_interface_holds_when_a_competitor_arm_is_absent():
    demo = pr.CitationsVsStoresDemonstrator()
    run = _run([
        _arm("anthropic", pointer_kind="char-span", persisted=0),
        _arm("openai", pointer_kind="file-level", persisted=4),
        _arm("gemini", pointer_kind="none", resolved=0, ran=False, errors=["key absent"]),
    ])
    spec = {"_run": run}
    claude = demo.run_claude_arm({}, spec)
    competitors = demo.run_competitor_arms({}, spec)
    verdict = demo.score(claude, competitors, spec)
    assert verdict.verdict in ("never-evaluated", "within-claude-only")
    assert isinstance(verdict, Verdict)


# ----- the retained helpers the internal scale probe imports still work -----

def test_retained_probe_helpers_are_importable_and_work():
    assert pr.PARAPHRASE_RULE and pr.DIY_INSTRUCTIONS
    assert pr._parse_json('prefix {"a": 1} suffix') == {"a": 1}
    assert pr._parse_json("no json here") is None
    # _fold normalizes typography and whitespace for a tolerant substring check
    assert pr._fold("month’s  base") == pr._fold("month's base")
