# Confirmed Improvements

Status: mechanically checked, not externally confirmed.

This ledger names the promoted Claude feature proofs in this repo and the checks that keep them
honest. A promoted artifact is still a candidate until a skeptical builder runs it on a real
workflow against a baseline and records the result.

## Radar Boundary

`feature-radar` watches the moving surface. `feature-hits` only contains reproducible wins that have
a workload, baseline, eval, saved output, and skeptic gate. New Anthropic or competitor releases do
not update this ledger by themselves.

A release does not update the claim. A rerun updates the claim.

When radar source hashes, pricing, model availability, or competitor docs change, the freshness gate
writes a receipt-update report. The public artifact changes only after the relevant command is rerun
and the result is promoted, held, or moved to misses.

The auto-resolve path may open a review PR that promotes or archives artifacts after rerunning the
mapped workload. It does not merge the PR or treat missing keys, quota, timeouts, or unknown fetches
as evidence against a public claim.

## Promoted Proofs

| Artifact | Workload | Current receipt | Gate |
| --- | --- | --- | --- |
| `programmatic_tool_calling` | fan out across customer evidence rows, reduce to three at-risk accounts | 74% fewer billed input tokens in `programmatic_tool_calling/sample.txt` | reducer evals, trace evals, number checks, live `--check` |
| `programmatic_tool_calling_cache_context` | combine programmatic tool calling with prompt caching and a 1M-context cost model | 80.8% lower modeled token cost than GPT-5.5 best cache plus 1M and 36.0% lower than Gemini 3.5 Flash cache plus 1M in `programmatic_tool_calling_cache_context/sample.txt` | checked price table, live programmatic tool calling grounding, OpenAI and Gemini rows, trace gate |

## What Is Confirmed

- The promoted artifacts run through one-command Make targets.
- Every shipped number traces to a committed receipt, a checked cost model, or a live `--check` gate.
- `make ci` runs reducer evals, trace evals, public-surface checks, number reconciliation, secret
  scanning, import checks, compile checks, common-helper drift checks, and demo GIF contract checks
  without an API key.
- The live `make check` path runs all promoted default targets with `--check`.
- No accuracy or Operations artifact is promoted in this pass. Candidate artifacts stay in the radar
  and misses workflow until the current adversarial gate says the founder-valued result survives the
  strongest app-owned and cross-provider baselines.
- Every pillar has the same competition bar. A promoted claim names OpenAI and Gemini's strongest
  current path, then measures Claude against that path or against the app-owned orchestration stack
  the founder would otherwise maintain.
- Every promoted artifact has a `Dimension matrix` that covers Cost, Speed, Accuracy, Reliability,
  Operations, and Security, including rows that are explicitly not measured or not claimed.
- The public surface has explicit Cost, Speed, Accuracy, Reliability, Operations, and
  Security pillars. Empty pillars are placeholders, not implied wins.

## What Is Not Confirmed Yet

- The artifacts have not been externally confirmed to add value by an independent founder or
  builder.
- The cost reductions and accuracy wins are workload-specific, not universal platform claims.
- `programmatic_tool_calling_cache_context` has OpenAI GPT-5.5 and Gemini 3.5 Flash rows in its current receipt. It is not
  a claim against Gemini Flash-Lite unless someone proves Flash-Lite handles the same high-tool-call
  workload at equal quality.
- The all-in production cost still needs backend cost, latency, correctness, failure rate, and any
  code-execution runtime charge for the real workload.
- No Speed artifact is promoted in this pass. Speed needs a same-workload wall-clock, p50/p95,
  throughput, or streaming completion receipt.
- No reliability artifact is promoted in this pass.
- Managed Agents is an Operations candidate, not a promoted feature hit. It needs a same-workload
  comparison against a self-managed Claude loop, OpenAI's agent stack, and Gemini's agent stack before
  it can move into the promoted list.
- No Security artifact is promoted in this pass.

## Pinning Rule

Repos that point to this one should pin a commit or tag, not a moving branch. Move the pin only after
recording the old pin, new pin, commands run, what changed, and why the downstream recipe should
move.
