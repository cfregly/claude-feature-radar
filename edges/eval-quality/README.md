# Edge: eval quality, which model and effort do you actually need on your own cases

Part of [claude-competitive-engine](../../README.md). The question this answers for a founder
deciding which tier to build on: on a labeled coding slice, which (model, effort) cell clears the bar
for the least money, measured on a HELD-OUT split so the win is not an overfit, and cross-checked by a
judge panel so the execution grade is not silently too trusting. On one-shot coding the frontier ties,
so the deciding factor is cost, and this demonstrator puts real dollars on every cell.

**On the shipped slice the measured verdict is parity, and that is the finding.** Every model tied at
100% on the held-out split, so no model leads on correctness, and the cheapest Claude tier (Haiku at
$0.0037) matched the entire frontier field. That is a cost-axis result, not a capability lead, so this
bundle leads with the honest read, not a Claude pitch.

## What it measures, and the three things that make it fair

A labeled coding slice, each task a stdin/stdout program graded by EXECUTION against hidden tests in a
sandboxed subprocess (no Docker, the same posture as the official LiveCodeBench runner). The harness
sweeps the SAME slice across every model x every effort level the model supports.

1. **The gate is the test suite, run identically on every arm.** A cell's pass rate is a measured K/N
   from running the generated program, never a rubric. Claude through `output_config.effort`, OpenAI
   through `reasoning_effort`, Gemini through `thinking_level`, all routed through one provider-blind
   call so the loop never branches on the vendor.

2. **The believable number is the held-out test split.** The slice carries a dev split and a disjoint
   held-out test split. Every cell is scored on both, and the headline is the held-out number, because
   a dev-only number can be an artifact of tuning against the cases you measured. A cell that wins on
   dev but not test is flagged as exactly that (the overfit guard).

3. **A judge panel cross-checks the execution grade.** With `--judge` on, each execution-passed
   program is re-graded by a panel of judges (the writer is never the grader: a Claude answer is judged
   by a different Claude tier, a competitor answer by Claude), and the receipt reports code-vs-judge
   agreement. Disagreement is the signal that the execution grade is too trusting on a task. The
   execution test is still the gate, and the judge is the cross-check.

## The measured result (the receipt)

8 tasks (4 dev, 4 held-out test) x 7 models x two effort levels, judge panel on. Full output in
[`sample.txt`](sample.txt).

| model | effort | held-out | suite $ | judge agree |
|---|:--:|:--:|--:|:--:|
| **Claude Haiku 4.5** | (none) | **100% (4/4)** | $0.0037 | 100% |
| Claude Sonnet 4.6 | low | 100% (4/4) | $0.0082 | 100% |
| GPT-5.4 | low | 100% (4/4) | $0.0107 | 100% |
| Claude Opus 4.8 | low | 100% (4/4) | $0.0173 | 100% |
| GPT-5.5 | low | 100% (4/4) | $0.0272 | 100% |
| Gemini 3.5 Flash | low | 100% (4/4) | $0.0356 | 100% |
| Gemini 3.1 Pro | high | 100% (4/4) | $0.1252 | 100% |

Total spend this run: $0.4285, every number off the API `usage` object.

**The honest read.** Every model tied at 100% on the held-out split, so this slice does not separate
the field on correctness. The finding is the cost spread: Claude Haiku resolved the held-out set for
$0.0037, and Gemini 3.1 Pro at high effort resolved the same set for $0.1252, about 33x more. Paying
for the bigger cell bought cost, not capability. The judge panel agreed with every execution-passed
program, so the grade is not too trusting here. The verdict is parity, reported exactly as it ran.

## Where the tiers actually separate (the harder slice)

A saturated slice hides the difference, so the demonstrator ships a harder one. Run `EVAL_LCB=1 make
eval` to pull a pinned LiveCodeBench hard slice at run time. On that slice the cells stop tying: Claude
Haiku resolved 40%, and Claude Sonnet at LOW effort scored 60% overall but 0% on the held-out hard
problem (the overfit signal the dev number alone would have hidden), while Sonnet at HIGH effort and
both Opus cells reached 100%. So on hard work the effort knob and the tier earn their cost, the
opposite of the saturated built-in slice. That partial LCB run is in [`sample.txt`](sample.txt), and
its Gemini and GPT-5.5 arms did not run, so it corroborates the separation, it is not a full
cross-vendor verdict.

## Scope and what would change the number

A small labeled slice, graded by exact-match execution on deterministic single-answer programs. The
result moves with the slice (a saturated slice ties, a hard slice separates), the effort levels, and
the model versions, so re-run it on your own cases before quoting it. Point the harness at your own
benchmark with `EVAL_TASKS=path/to/your.jsonl make eval`, where each JSONL line is
`{"name":..., "prompt":..., "tests":[[stdin, expected], ...], "difficulty":..., "split":...}`.

## Run it yourself

```bash
git clone https://github.com/cfregly/claude-competitive-engine && cd claude-competitive-engine
make setup && make compare-deps   # core deps, then openai, google-genai (datasets only for EVAL_LCB)
cp .env.example .env              # paste your Anthropic, OpenAI, and Gemini keys
make eval-smoke                   # a cents-scale Claude-only smoke (Haiku + Sonnet, low effort)
make eval                         # the full cross-vendor grid on your own keys, about $3-4
make eval-judge                   # the same grid with the judge-panel cross-check on
```

`run.py eval` is the same entry point. The grader runs model-generated programs against the hidden
tests in a sandboxed subprocess (no Docker, the same posture as the official LiveCodeBench runner), so
run it on a machine you do not mind exposing to arbitrary generated code.

See [`PRODUCT_EMAIL.md`](PRODUCT_EMAIL.md) for the honest other direction (the parity read that ships
for this run) and the cost-axis methodology: how to find out which tier you are overpaying for on
your own cases.
