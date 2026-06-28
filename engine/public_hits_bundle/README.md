# claude-feature-hits

Public, runnable Claude feature wins. The current surface is intentionally small: artifacts that run
from this repo, print their own receipts, and stay out unless the claim clears the fail-closed value
gate.

_Registry and source links rechecked 2026-06-24. Saved measurement receipts keep their artifact dates.
Costs and capabilities change, so re-check the linked docs before you rely on a number._

`feature-radar` watches the moving platform surface. This repo contains only reproducible wins. A
release does not update the claim. A rerun updates the claim.

## Current Promoted Artifacts

The current promoted public surface has two cost artifacts. Speed, Accuracy, Reliability,
Operations, and Security are tracked as pillars, but none has a promoted artifact in this pass. A
candidate stays out of this repo until the current radar gate says the founder-valued outcome
survives OpenAI and Gemini best-available baselines.

Across every pillar, the bar is OpenAI and Gemini best available. A promoted artifact must name the
strongest current OpenAI path and the strongest current Gemini path for the same workload. If that
path is an app-owned workaround, say so. If a receipt beats one competitor but not the other, scope
the claim to what the receipt proves instead of implying an all-provider win.

Every promoted artifact carries a `Dimension matrix`. The matrix must cover Cost, Speed, Accuracy,
Reliability, Operations, and Security. A dimension can say `not measured` or `not claimed`, but it
cannot be omitted.

**Cost**:

- [**programmatic_tool_calling**](https://github.com/cfregly/claude-feature-hits/tree/main/programmatic_tool_calling): cut the token bill on a fan-out task by running your tool in a code sandbox and filtering records before they reach the model. The live workload fans out across support tickets, product logs, usage metering, CRM notes, and compliance docs, then asks for one compact decision: the three customer accounts most likely to churn or block expansion. `make programmatic_tool_calling` (estimated $0.08 token/API cost).
- [**programmatic_tool_calling_cache_context**](https://github.com/cfregly/claude-feature-hits/tree/main/programmatic_tool_calling_cache_context): validate the committed 54,989 -> 14,299 programmatic-tool-calling receipt, then apply the checked model-token price table to a larger declared cache plus 1M-context workload: 700,000 stable-prefix tokens, 100 turns, 200,000 raw tool-output tokens per turn, 2,000 programmatic tool calling summary tokens per turn, and 300 output tokens per turn. Claude Sonnet 4.6 cache plus programmatic tool calling is $26.04 vs $135.55 for GPT-5.5 best cache plus 1M without programmatic tool calling and $40.67 for Gemini 3.5 Flash cache plus 1M without programmatic tool calling, saving $109.51 vs OpenAI and $14.63 vs Gemini, before any separate code-execution runtime charge. That is 80.8% lower than the OpenAI row and 36.0% lower than the Gemini row. `make programmatic_tool_calling_cache_context` ($0, no API call).

**Accuracy**:

- No promoted artifact yet. This pillar is reserved for source-grounding, citation, or extraction
  workloads that beat the strongest app-side resolver baseline, not just the easiest competitor
  integration path.

**Speed**:

- No promoted artifact yet. This pillar is reserved for same-workload wall-clock, p50/p95 latency, or
  throughput gains that survive OpenAI and Gemini best-available comparisons.

**Reliability**:

- No promoted artifact yet. This pillar is reserved for same-workload reliability gains that survive
  a competent app-side baseline and cross-provider comparison.

**Operations**:

- No promoted artifact yet. This pillar is reserved for measured reductions in orchestration code,
  state surfaces, retry paths, debug loops, cache risk, or test burden that survive the strongest
  app-owned and cross-provider baselines.

Managed Agents also belongs in Operations, but it is not promoted in this repo yet. The canonical
comparison lives in `feature-radar` as `make managed-agents-ops`. The standalone
[`claude-managed-agents`](https://github.com/cfregly/claude-managed-agents) repo remains a product
surface deep dive and smoke test. The latest radar comparison is mechanically vetted on the
ops-triage workload, but not ahead. The radar receipt now uses a formal Operations scorecard:
orchestration lines removed, state or cleanup components avoided, repeated failed-run teardown,
interruption resume behavior, time to first correct agent, and token/API cost from session usage when
the API exposes it.

**Security**:

- No promoted artifact yet. This pillar is reserved for a future candidate that clears the same
  fail-closed value gate and is appropriate to expose in this public repo.

Cost scope: promoted cost artifacts print token/API cost from usage objects or checked model-token
arithmetic. Cached-token buckets are included when present, with cache reads and cache writes priced
at their own rates. Because programmatic tool calling uses code execution, code-execution runtime can bill separately after
the monthly free allowance. At current pricing, one newly billed container has $0.0042 of
5-minute floor exposure at $0.05 per hour. Production COGS should add that line item before quoting
all-in savings. Cost artifacts still name OpenAI and Gemini best available. A cost win against
OpenAI alone is not a Gemini win.

Speed scope: promoted speed artifacts must print same-workload wall-clock time, p50/p95 latency,
batch throughput, or streaming completion time. Build speed and developer convenience are Operations
claims unless the artifact measures runtime behavior for the workload.

Accuracy scope: promoted accuracy artifacts must prove a founder-valued result on small fixtures
with known answers and compare against the strongest app-side workaround. A native pointer is not
enough by itself if a competent application resolver recreates the visible outcome.

Operations scope: promoted artifacts must quantify removed orchestration code, state surfaces, retry
paths, debug loops, cache risk, or test burden. Convenience alone is not enough. The comparison still
has to be competitive: name OpenAI and Gemini's strongest current path, then measure the provider
feature against that path or against the app-owned stack the founder would otherwise carry.
No Operations artifact is promoted in this pass because the latest radar gate did not find a current
candidate whose workload survived the strongest app-owned and cross-provider baselines.

Promotion difficulty: an easy candidate is easy to port, not easy to pass. It already has a small
self-contained workload, a positive receipt, a demo tape, and a narrow claim whose strongest baseline
is known. It still needs a clean adversarial gate. A hard candidate needs a new workload or a new
baseline because the current objection still recreates the founder-valued outcome.

Production gate: `make ci` includes reducer evals, trace evals, number checks, public-surface checks,
secret scanning, import checks, compile checks, common-helper drift checks, and demo GIF contract
checks. The `make check` path runs every promoted default target with `--check`. Only the live programmatic tool calling artifact spends API tokens. The programmatic tool calling check
also requires the expected caller path, an observed server-tool block, a code-execution container id,
and no fallback reason before treating the receipt as promotable.

## Clone and run

```
git clone https://github.com/cfregly/claude-feature-hits && cd claude-feature-hits
export ANTHROPIC_API_KEY=your-api-key
make programmatic_tool_calling
make programmatic_tool_calling_cache_context
```

Default targets are self-bootstrapping: the `make` target builds the venv, installs dependencies when
needed, runs the proof, and prints the measured result or checked model-token cost. Cache-context is
deterministic and does not require an API key.

## What Counts As A Win

Each artifact states the workload, runs the proof, and prints the measured result or checked cost
model. The repo stays small so the current wins are easy to inspect and rerun.

The founder runbook is narrow on purpose:

1. Build: pick one workload where the feature changes cost, accuracy, reliability, runtime,
   Operations burden, or glue code in a way your product can measure.
2. Test: run the feature path against OpenAI and Gemini best available for the same workload,
   including any app-side workaround that would be fair to own.
3. Avoid: do not use broad tools, raw customer payloads in logs, unsupported caller paths, or a claim
   without correctness, latency, fallback, and cost accounting.
4. Promote: move into this repo only when the receipt is positive and the current adversarial gate has
   no live `KILLED` verdict for the claim.

## Confirmed improvements ledger

[docs/confirmed-improvements.md](docs/confirmed-improvements.md) records the promoted proofs, their
receipts, what the gates confirm, and what still needs external builder proof before stronger value
claims.

## Startup credits

Building a startup on Claude? Apply to Claude for Startups before you run larger proofs. Eligible
founders can get startup credits and priority rate limits through the first-party Claude Console,
then use this repo to pick the blocker, run the proof, and measure the cost on their own key.

[Apply to Claude for Startups](https://claude.com/programs/startups)

## More refs

- [Claude quickstarts](https://github.com/anthropics/claude-quickstarts): the `customer-support-agent` quickstart is the RAG starter.
- [Claude Cookbook](https://platform.claude.com/cookbook/): runnable notebooks across the platform.
- [Anthropic Academy](https://www.anthropic.com/learn/build-with-claude): guided courses.
