"""Offline tests for the paraphrase-resolution citation edge gate.

No key, no network, no model call: synthetic ArmResult rows drive the deterministic score gate. The
gate is the headline of this demonstrator, so these tests pin exactly when it promotes and when it
holds: Claude must resolve every paraphrased answer's pointer by guarantee with zero hosted objects and
an inline-PDF pointer, every cross-vendor DIY arm must run, and the DIY path must silently drop under
paraphrase. They also confirm the Demonstrator interface routes through the base honesty contract.
"""

from engine.demonstrators import paraphrase_resolution as pr
from engine.demonstrators.base import Verdict

N = 8         # questions
N_PDF = 2     # of which are PDF questions


def _claude(*, answered=N, resolved=N, cited=N, source_correct=N, persisted=0, pdf_resolved=N_PDF):
    return pr.ArmResult(name="claude+citations:sonnet", provider="anthropic", model="claude-sonnet-4-6",
                        mechanism="API citations", asked=N, answered=answered, cited=cited,
                        resolved=resolved, source_correct=source_correct, pdf_asked=N_PDF,
                        pdf_pointer_resolved=pdf_resolved, persisted_objects=persisted, output_tokens=300)


def _diy(provider, *, resolved, cited=N, ran=True, errors=None):
    name = {"anthropic": "claude DIY:sonnet", "openai": "openai DIY:gpt-mid",
            "gemini": "gemini DIY:gem-flash"}[provider]
    return pr.ArmResult(name=name, provider=provider, model=f"{provider}-model",
                        mechanism="DIY str.find", ran=ran, asked=N, answered=N, cited=cited,
                        resolved=resolved, pdf_asked=N_PDF, output_tokens=560, errors=errors or [])


def _run(arms):
    return pr.ParaRun(arms=arms, n_questions=N, n_pdf=N_PDF, total_cost=0.06)


def test_promotes_when_claude_resolves_all_and_diy_drops_under_paraphrase():
    run = _run([
        _claude(),
        _diy("anthropic", resolved=3),   # within-Claude DIY baseline, drops on paraphrase
        _diy("openai", resolved=2),      # cross-vendor DIY, drops
        _diy("gemini", resolved=2),      # cross-vendor DIY, drops
    ])
    v = pr.score_run(run)
    assert v["positive_signal"] is True
    assert v["promotable_edge"] is True
    assert v["claude_guaranteed_resolve"] is True
    assert v["claude_grounded_correct_source"] == f"{N}/{N}"
    assert v["claude_no_hosted_store"] is True
    assert v["claude_cites_inline_pdf_under_paraphrase"] is True
    assert v["competitor_diy_drop_total"] > 0


def test_blocks_when_claude_drops_a_pointer():
    run = _run([
        _claude(resolved=N - 1, source_correct=N - 1),   # one pointer did not resolve, breaks the guarantee
        _diy("openai", resolved=2),
        _diy("gemini", resolved=2),
    ])
    v = pr.score_run(run)
    assert v["promotable_edge"] is False
    assert any("ground every answer in the expected source" in r for r in v["why_not_promotable"])


def test_blocks_when_claude_grounds_the_wrong_source():
    # The pointers all resolve, but one lands in the wrong document, so the answer is not grounded in
    # the expected source: the robust correctness gate holds the edge even though resolution looks clean.
    run = _run([
        _claude(source_correct=N - 1),
        _diy("openai", resolved=2),
        _diy("gemini", resolved=2),
    ])
    v = pr.score_run(run)
    assert v["promotable_edge"] is False
    assert any("expected source" in r for r in v["why_not_promotable"])


def test_blocks_when_diy_does_not_drop_under_paraphrase():
    # If the DIY arms resolved every paraphrased pointer, the paraphrase gap is not measured, so the
    # edge must not promote on this run.
    run = _run([
        _claude(),
        _diy("openai", resolved=N),
        _diy("gemini", resolved=N),
    ])
    v = pr.score_run(run)
    assert v["promotable_edge"] is False
    assert any("no silent drop under paraphrase" in r for r in v["why_not_promotable"])


def test_blocks_when_a_cross_vendor_arm_did_not_run():
    run = _run([
        _claude(),
        _diy("openai", resolved=2),
        _diy("gemini", resolved=0, ran=False, errors=["GEMINI_API_KEY absent"]),
    ])
    v = pr.score_run(run)
    assert v["promotable_edge"] is False
    assert v["all_competitors_ran"] is False


def test_blocks_when_claude_pointer_needs_a_hosted_store():
    run = _run([
        _claude(persisted=1),            # a persisted/hosted object means it is not the no-store path
        _diy("openai", resolved=2),
        _diy("gemini", resolved=2),
    ])
    v = pr.score_run(run)
    assert v["promotable_edge"] is False
    assert v["claude_no_hosted_store"] is False


def test_blocks_when_claude_cannot_cite_the_inline_pdf():
    run = _run([
        _claude(pdf_resolved=N_PDF - 1),  # an inline-PDF page pointer did not resolve
        _diy("openai", resolved=2),
        _diy("gemini", resolved=2),
    ])
    v = pr.score_run(run)
    assert v["promotable_edge"] is False
    assert v["claude_cites_inline_pdf_under_paraphrase"] is False


def test_interface_score_routes_claude_ahead_only_when_every_cross_vendor_arm_ran():
    # The Demonstrator.score() must return claude-ahead only with every cross-vendor DIY arm run, and
    # the receipt must route through the base honesty contract (never-evaluated otherwise).
    demo = pr.ParaphraseResolutionDemonstrator()
    run = _run([
        _claude(),
        _diy("anthropic", resolved=3),
        _diy("openai", resolved=2),
        _diy("gemini", resolved=2),
    ])
    spec = {"_run": run}
    claude = demo.run_claude_arm({}, spec)
    competitors = demo.run_competitor_arms({}, spec)
    verdict = demo.score(claude, competitors, spec)
    assert verdict.verdict == "claude-ahead"
    edge = {"key": "citations", "axis": "grounding", "demoKind": "grounding_resolution",
            "fair_comparison": {"lead_basis": "head-to-head"}, "claim": "x"}
    receipt = demo.receipt(edge, claude, competitors, verdict, spec)
    assert receipt.verdict == "claude-ahead"     # all cross-vendor arms ran, so the contract lets it stand
    assert receipt.demo_kind == "grounding_resolution"
    assert receipt.fairness.get("lead_basis") == "head-to-head"


def test_interface_holds_when_a_cross_vendor_arm_is_absent():
    demo = pr.ParaphraseResolutionDemonstrator()
    run = _run([
        _claude(),
        _diy("openai", resolved=2),
        _diy("gemini", resolved=0, ran=False, errors=["key absent"]),
    ])
    spec = {"_run": run}
    claude = demo.run_claude_arm({}, spec)
    competitors = demo.run_competitor_arms({}, spec)
    verdict = demo.score(claude, competitors, spec)
    # Claude resolved all, but a cross-vendor arm did not run, so the verdict is held, never pitched.
    assert verdict.verdict in ("never-evaluated", "within-claude-only")
    assert isinstance(verdict, Verdict)
