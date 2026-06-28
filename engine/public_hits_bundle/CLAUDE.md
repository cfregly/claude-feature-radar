# CLAUDE.md

Conventions for anyone, person or agent, working in this repo. This repo stands alone. Read this first.

This is a set of short, runnable Claude feature artifacts. The root README is the current public
surface. A subdirectory is a current public win only when it is listed there.

## Every Artifact Runs In One Command

Each artifact is self-contained. `make <slug>` builds a local venv, installs the one dependency
(anthropic), and runs the live proof. State the cost and the time up front, before the reader commits.

## Every Number Is A Receipt

Each current promoted artifact shows what Claude does well on a real workload, with a measured
number. Every number on a page traces to that artifact's committed receipt and is reproduced by
running the artifact. Never quote a number you cannot reproduce. Re-running shifts token counts and
cents, so reproduce before you change a figure.

## Current-Win Standard

An artifact belongs on the public surface when the workload is concrete, the result is reproducible,
and the value is clear in founder terms: lower cost, faster runtime, higher reliability, better
accuracy, lower operations burden, or less glue code.

- Every artifact README keeps a `What you get` section that states the value plainly.
- Every artifact README keeps a `Dimension matrix` section covering Cost, Speed, Accuracy,
  Reliability, Operations, and Security. A dimension can say `not measured` or `not claimed`, but it
  cannot be omitted.
- Every claim ties to `sample.txt`, a source-backed local guard, or a dated comparison table.
- If a claim lacks measured value, it does not enter the promoted list. Rerun it on a better workload
  or move it out of this repo.
- `docs/confirmed-improvements.md` is the companion ledger. Keep it aligned with the promoted
  artifacts and their gates whenever a downstream repo pins this repo.

## Comparisons are fair, sourced, and dated

Every promoted artifact identifies the strongest OpenAI and Gemini path for the same workload. If the
competitor has a direct feature, compare against it. If the competitor path is app-owned orchestration,
compare against that app stack and say what the app still owns. A number comes from a real run on the
same workload on the date shown, or from the competitor's own public docs with that date. Never use a
competitor number that was not measured. The artifact reproduces the Claude side using your API key.
Compare best to best: each side runs its latest API and its strongest relevant option.

This applies to every pillar: Cost, Speed, Accuracy, Reliability, Operations, and Security. Do not treat
Operations as a lower bar. Do not treat "no exact matching field" as the end of the comparison. The
fair baseline is the strongest thing a competent OpenAI or Gemini builder would actually ship.

## Clean prose

No em-dashes, no en-dashes, no semicolons, no buzzwords. Say the thing plainly. Explain any term a
founder would not parse at a glance (fan-out, allowed_callers, RAG). `make ci` checks this without keys.

## No secrets

`.env` is gitignored. Never commit an API key. The CI gate and the gif build both scan for API key material
and fail on a hit.

## Voice

Founder-facing prose is warm, direct, first person, builder-to-builder. Lead with the workload, then
the feature, then the code, then the measured result, then the one command to reproduce.
