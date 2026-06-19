# Edge: the parity-gated long tail (held until a skeptic fails to break it)

Part of [claude-competitive-engine](../../README.md). This bundle is the engine's holding pen for the
narrow candidate edges that are NOT yet pitchable: a server-side fallback credit, a per-request
cache-miss-reason signal, and Claude Code as a programmable build surface. Each one is a plausible
Claude edge with no head-to-head evidence yet that a competitor lacks an equivalent. The engine's own
rule (verify both sides, then keep what survives) forbids pitching a lead a skeptic has not first failed
to break, so all three are **held never-evaluated and are never pitched** until their parity check
passes.

This bundle exists to make that honest state visible and auditable, not to sell anything. The deliverable
is the discipline: the engine names the candidate, names the exact competitor surface to check it
against, names the machine-checkable gate the thin proof would run, and then refuses to claim a win
until the skeptic pass survives.

## The three candidates, and why each is held

| candidate | axis | the Claude surface | the parity check it must survive | state |
|---|---|---|---|---|
| `fallback_credit` | correctness | server-side model fallback with a fallback credit, recover from a refusal by falling back inside a single call | confirm no competitor ships a named single-call server-side cross-model fallback with a credit (vs a client-side retry loop) | held (unchecked) |
| `cache_diagnostics` | observability | a per-request `cache_miss_reason` in the usage object, an explainer of why a cache read missed | confirm the OpenAI and Gemini usage objects surface no equivalent per-request miss reason | held (unchecked) |
| `build_velocity` | agentic-success | Claude Code as a programmable build surface (the `@claude` Action, plugins bundling skills, agents, hooks, and MCP) | time the issue-to-merged-PR loop against Codex CLI and Gemini CLI on the same repo, every headline primitive now has a competitor equivalent | held (unchecked) |

Full output in [`sample.txt`](sample.txt). It runs with no key and no network, and it spends nothing.

## How the parity gate works

The demonstrator for the `other` demoKind ([`engine/demonstrators/other_parity_gated.py`](../../engine/demonstrators/other_parity_gated.py))
implements one rule: `applicable()` returns False until the edge's recorded parity check reads
`survives`. While a candidate is unchecked or killed, the dispatcher files a precondition-unmet ASK
stub, the cadence surfaces "run the parity check for this candidate" to a human, and the edge stays out
of every brief and every email. The skeptic pass is the live `engine/verify.py` call, so it is not run
in the offline cadence or the tests, the recorded verdict is what flips the gate.

Only `survives` (the skeptic could not break the claim AND the competitor surface was fetched and shows
no named equivalent) unblocks a candidate, and even then the verdict it can reach is within-Claude
(the opt-in thin proof would measure the within-Claude value-add), never a head-to-head `claude-ahead`
off the parity gate alone. A `killed` verdict (the skeptic broke it, or a competitor ships a
near-equivalent) keeps the edge held as parity or behind, and that is the finding, written to the
product-team note rather than the founder email.

## Run it yourself

```bash
git clone <this-repo> && cd claude-competitive-engine
make parity-gated      # the $0 view of every held candidate and its parity check (no key, no spend)
```

`make parity-gated` needs nothing installed and spends nothing. The thin proofs that would spend a
credit (a live refusal to trigger the fallback, a deliberate cache miss, a headless Claude Code run)
are described and gated, not run here, the same opt-in shape as the live Managed Agents arm in the
retention edge. The surfaces are fast-moving, so re-ground each one against its live doc before any
parity check is recorded.

See [`PRODUCT_EMAIL.md`](PRODUCT_EMAIL.md) for the internal read: these are never-evaluated, here is
the parity check each one needs, and what would have to be true before any founder pitch.
