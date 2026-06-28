#!/usr/bin/env python3
"""One entry point for the engine. Use the Makefile, or:

    python run.py demo [--quick|--full]   the runnable proof for the current gap
    python run.py ledger                  the exact-list long-stream edge
    python run.py edges                    sweep the live docs, diff, rank, persist (no API call, $0)
    python run.py check-freshness          fail if source hashes changed from the pinned landscape
    python run.py freshness-report         write a PR-ready freshness report into state/outbox
    python run.py resolve-freshness        rerun mapped stale workloads and classify promote/hold/miss
    python run.py cadence [--dry-run]      the unattended engine: sweep, dispatch, draft to outbox ($0)
    python run.py coverage                 per-demoKind, what is built vs adapt vs build (no API call)
    python run.py managed [--apply]        the Tier-2 monthly resumable runtime (wired, $0 without --apply)
    python run.py security                 the private security/admin source-ledger receipt ($0)
    python run.py scan                     the candidate gaps, grounded in both sides' docs
    python run.py verify                   the skeptic pass: keep only what survives
    python run.py combine                  generate combination edges, skeptic-test, persist survivors
    python run.py draft                    draft the founder email from the measured receipt
    python run.py brief                    print the latest sourced brief
"""

import pathlib
import sys


def _brief():
    briefs = sorted((pathlib.Path(__file__).resolve().parent / "briefs").glob("*.md"))
    print(briefs[-1].read_text() if briefs else "no briefs yet")


def main():
    cmd = sys.argv[1] if len(sys.argv) > 1 else "demo"
    sys.argv = [sys.argv[0]] + sys.argv[2:]  # pass the rest through to the subcommand
    if cmd == "demo":
        from engine.demo import main as m; m()
    elif cmd in ("longhorizon-compare", "lhc"):
        from engine.longhorizon_compare import main as m; m()
    elif cmd in ("ledger", "exact-list-ledger"):
        from engine.ledger_compare import main as m; m()
    elif cmd == "compare":
        from engine.compare import main as m; m()
    elif cmd == "alert":
        from engine.product_alert import main as m; m()
    elif cmd == "sweep":
        from engine.sweep import main as m; m()
    elif cmd == "edges":
        from engine.sweep_edges import main as m; m()
    elif cmd == "check-freshness":
        from engine.freshness import main as m; raise SystemExit(m())
    elif cmd == "freshness-report":
        from engine.freshness import main as m; raise SystemExit(m(["--write-report", "--no-fail"]))
    elif cmd == "resolve-freshness":
        from engine.freshness_resolve import main as m; raise SystemExit(m())
    elif cmd == "cadence":
        from engine.cadence import main as m; raise SystemExit(m())
    elif cmd == "coverage":
        from engine.coverage import main as m; raise SystemExit(m())
    elif cmd == "managed":
        from engine.managed import main as m; raise SystemExit(m())
    elif cmd in ("other", "parity-gated"):
        from engine.demonstrators.other_parity_gated import main as m; raise SystemExit(m())
    elif cmd in ("dynamic-web", "dynamic-web-filtering"):
        from engine.demonstrators.dynamic_web_filtering import main as m; raise SystemExit(m())
    elif cmd in ("task-budget", "task-budgets"):
        from engine.demonstrators.task_budgets import main as m; raise SystemExit(m())
    elif cmd in ("cache-diagnostics", "cache-diagnostic"):
        from engine.demonstrators.cache_diagnostics import main as m; raise SystemExit(m())
    elif cmd in ("fast-mode", "fast_mode"):
        from engine.demonstrators.fast_mode import main as m; raise SystemExit(m())
    elif cmd in ("pdf-citations", "pdf_citations"):
        from engine.demonstrators.pdf_citations import main as m; raise SystemExit(m())
    elif cmd in ("search-results", "search_results"):
        from engine.demonstrators.search_results_grounding import main as m; raise SystemExit(m())
    elif cmd in ("grounding-stack", "grounding_stack"):
        from engine.demonstrators.grounding_stack import main as m; raise SystemExit(m())
    elif cmd in ("citations-paraphrase", "paraphrase", "paraphrase-resolution"):
        from engine.demonstrators.paraphrase_resolution import main as m; raise SystemExit(m())
    elif cmd in ("web-citations", "web_citations"):
        from engine.demonstrators.web_citations import main as m; raise SystemExit(m())
    elif cmd in ("bulk-output", "bulk-extended-output", "bulk_extended_output"):
        from engine.demonstrators.bulk_extended_output import main as m; raise SystemExit(m())
    elif cmd in ("advisor", "advisor-routing", "advisor_routing"):
        from engine.demonstrators.advisor_routing import main as m; raise SystemExit(m())
    elif cmd in ("code-execution-state", "code_execution_state"):
        from engine.demonstrators.code_execution_state import main as m; raise SystemExit(m())
    elif cmd == "programmatic-tool-calling-cache-context":
        from engine.demonstrators.programmatic_tool_calling_cache_context import main as m; raise SystemExit(m())
    elif cmd in ("security", "security-posture", "security_posture"):
        from engine.demonstrators.security_posture import main as m; raise SystemExit(m())
    elif cmd in ("eval", "eval-quality"):
        from engine.demonstrators.eval_quality import main as m; m()
    elif cmd == "scan":
        from engine.scan import main as m; m()
    elif cmd == "verify":
        from engine.verify import main as m; m()
    elif cmd in ("combine", "combinations"):
        from engine.combine import main as m; m()
    elif cmd in ("draft", "email", "draft-email"):
        from engine.draft_email import main as m; m()
    elif cmd == "brief":
        _brief()
    else:
        print(__doc__)
        sys.exit(2)


if __name__ == "__main__":
    main()
