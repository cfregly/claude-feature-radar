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


# ----- the HEADLINE cross-vendor feature gate: Claude citations vs OpenAI file_search vs Gemini File Search -----

NQ = 6


def _feat_arm(provider, *, pointer_kind, resolved=NQ, source_correct=NQ, persisted=0, ran=True, errors=None):
    name = {"anthropic": "claude citations:sonnet", "openai": "openai file_search:gpt-top",
            "gemini": "gemini File Search:gem-pro"}[provider]
    return {"name": name, "provider": provider, "model": f"{provider}-m", "mechanism": "x",
            "pointer_kind": pointer_kind, "resolved": f"{resolved}/{NQ}", "source_correct": f"{source_correct}/{NQ}",
            "persisted_objects": persisted, "setup_calls": persisted, "cost": 0.01, "errors": errors or [], "ran": ran}


def _feat(arms):
    return {"n_questions": NQ, "cost": 0.1, "skipped": [], "arms": arms}


def test_feature_comparison_promotes_when_claude_char_span_zero_objects_vs_hosted_competitors():
    feat = _feat([
        _feat_arm("anthropic", pointer_kind="char-span", persisted=0),
        _feat_arm("openai", pointer_kind="file-level", persisted=4),
        _feat_arm("gemini", pointer_kind="chunk-level", persisted=4),
    ])
    v = pr.score_feature_comparison(feat)
    assert v["promotable_edge"] is True
    assert v["claude_char_span_into_supplied_docs"] is True
    assert v["claude_persisted_objects"] == 0
    assert v["competitor_total_persisted_objects"] == 8


def test_feature_comparison_holds_if_a_competitor_cites_without_a_hosted_store():
    feat = _feat([
        _feat_arm("anthropic", pointer_kind="char-span", persisted=0),
        _feat_arm("openai", pointer_kind="file-level", persisted=0),   # no hosted store -> parity on data residency
        _feat_arm("gemini", pointer_kind="chunk-level", persisted=4),
    ])
    v = pr.score_feature_comparison(feat)
    assert v["promotable_edge"] is False
    assert any("without a hosted store" in r for r in v["why_not_promotable"])


def test_feature_comparison_holds_if_a_competitor_returns_a_char_span():
    feat = _feat([
        _feat_arm("anthropic", pointer_kind="char-span", persisted=0),
        _feat_arm("openai", pointer_kind="char-span", persisted=4),    # parity on granularity
        _feat_arm("gemini", pointer_kind="chunk-level", persisted=4),
    ])
    v = pr.score_feature_comparison(feat)
    assert v["promotable_edge"] is False
    assert any("char-span pointer" in r for r in v["why_not_promotable"])


def test_feature_comparison_holds_if_claude_needs_hosted_objects():
    feat = _feat([
        _feat_arm("anthropic", pointer_kind="char-span", persisted=1),
        _feat_arm("openai", pointer_kind="file-level", persisted=4),
        _feat_arm("gemini", pointer_kind="chunk-level", persisted=4),
    ])
    v = pr.score_feature_comparison(feat)
    assert v["promotable_edge"] is False


def test_feature_comparison_holds_if_a_competitor_arm_did_not_run():
    feat = _feat([
        _feat_arm("anthropic", pointer_kind="char-span", persisted=0),
        _feat_arm("openai", pointer_kind="file-level", persisted=4),
        _feat_arm("gemini", pointer_kind="none", resolved=0, ran=False, errors=["setup failed"]),
    ])
    v = pr.score_feature_comparison(feat)
    assert v["promotable_edge"] is False
    assert v["all_competitors_ran"] is False


def test_glue_grader_drops_line_wrapped_quote_naively_and_recovers_normalized():
    # The PDF glue-code teaching point: a verbatim quote carrying a PDF line-wrap newline fails the
    # developer's naive str.find but resolves after the one-line whitespace normalization.
    span = "monthly uptime commitment of 99.9 percent"
    assert pr.GLUE_CANON.find(span) != -1
    wrapped = span.replace(" commitment ", " commitment\n")     # a PDF line-wrap inside the span
    naive, norm = pr._grade_glue(wrapped)
    assert naive is False        # naive str.find drops it (silent -1)
    assert norm is True          # " ".join(quote.split()) recovers it
    # a span genuinely not in the document still fails both, so this is a real check, not loosened.
    assert pr._grade_glue("this sentence is nowhere in the agreement") == (False, False)


def test_deterministic_glue_example_drops_naive_and_resolves_normalized_and_guarantee():
    # The $0 teaching illustration must hold every run, independent of live model output: a PDF-wrapped
    # sentence drops the developer's naive str.find and resolves under whitespace normalization and the
    # API-grade guarantee.
    d = pr._deterministic_glue_example()
    assert d["rendered_spans_lines"] is True
    assert d["naive_resolves"] is False
    assert d["normalized_resolves"] is True
    assert d["guarantee_resolves"] is True


def test_glue_lines_render_the_teaching_table():
    glue = {"n_pdf_questions": 5, "naive_drop_total": 2, "cost": 0.1, "skipped": [], "arms": [
        {"name": "claude+citations:sonnet", "is_citations": True, "naive_resolved": "-",
         "normalized_resolved": "-", "guaranteed_resolved": "5/5", "naive_drops": 0, "errors": []},
        {"name": "openai DIY:gpt-top", "is_citations": False, "naive_resolved": "3/5",
         "normalized_resolved": "5/5", "guaranteed_resolved": "-", "naive_drops": 2, "errors": []},
    ]}
    lines = pr._glue_lines({"pdf_glue_demo": glue})
    body = "\n".join(lines)
    assert "PDF glue-code demo" in body
    assert "silently dropped 2" in body          # names the measured drop
    assert "resolved every quote by guarantee" in body
    # no glue section when the demo did not run (no keys)
    assert pr._glue_lines({"pdf_glue_demo": {}}) == []


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
