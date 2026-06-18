# program.md (template for a budgeted demonstrator)

This file is the spec front door for a budgeted demonstrator kind (eval_quality, agentic_grading).
You edit it, you do not edit code. The shared spec parser in
`engine/demonstrators/shared/spec.py` reads the fields below into the run's model search space, its
decoding bounds, and its spend cap. Copy this template into a budgeted demonstrator's
`edges/<key>/program.md` and fill it in. Missing or unparseable fields fall back to safe defaults,
so a half-written file still runs.

## Models in the search space

List the model ids the demonstrator may try, one comparison at a time. Each full Claude model id on
this page is picked up in first-seen order. Example search space:

- claude-haiku-4-5
- claude-sonnet-4-6
- claude-opus-4-8

## Decoding bounds

The parser reads a range in the form `<knob> in [lo, hi]`:

- temperature in [0.0, 0.7]
- max_tokens in [256, 2048]

## Budget

The spend cap and the stop conditions. The demonstrator stops at whichever bound it hits first, and
no demonstrator spends a credit until its estimate has been surfaced and approved by the gate.

- spend: 3.00
- iterations: 12
- wall clock: 60
