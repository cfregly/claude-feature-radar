# Product-team email: eval quality, the honest parity read (this run ships this one)

This run is parity on correctness (every model tied on the held-out split), so this internal note is
what goes out, not a founder pitch. Same rigor as a founder email. The engine writes the product-team
note when a run is a tie or a loss, not a pitch built on a number that did not separate.

---

**Subject:** On a labeled coding slice every tier tied at 100%, so the eval edge is cost, not capability

To the Claude platform team,

I built a reproducible cost-x-effort eval grid into the competitive engine and ran it best-to-best
across all three vendors. The result on this slice is parity on correctness, and I want to flag both
the tie and what it does and does not let us claim.

The setup. A labeled coding slice (stdin/stdout programs with a deterministic single-value answer),
graded by EXECUTION against hidden tests in a sandboxed subprocess, no Docker. The slice carries a
disjoint dev and held-out test split, so the reported number is the split no cell was tuned against.
The grid sweeps every model tier x two effort levels (low and high), and a judge panel cross-checks
each execution-passed program with the writer never its own grader, so a too-trusting execution grade
would show up as a code-vs-judge disagreement.

The measured outcome (8 tasks, 4 held-out, 7 models, judge on, $0.4090 total off the usage object):

- Every model resolved the held-out split 4 of 4. Claude Haiku, Sonnet, and Opus, GPT-5.4 and GPT-5.5,
  and Gemini 3.5 Flash and 3.1 Pro. All tied at 100%.
- The cost spread was the only separation: Haiku at $0.0037 vs Gemini 3.1 Pro at high effort at $0.1252,
  about 33x, for the identical held-out result.
- The judge panel agreed with all but one execution-passed program (Gemini 3.1 Pro at high, 88%), so
  the execution grade is essentially not too trusting on this slice.

What this slice does NOT let us claim. It is saturated, so it does not separate the field on capability,
and we must not pitch a Claude eval-quality lead off it. I ran a harder slice too (a pinned
LiveCodeBench hard set, `EVAL_LCB=1`) and ran it complete cross-vendor. Execution pass rate barely separates even there: only Claude Haiku
(40%) and Claude Sonnet at LOW effort (80% overall, 50% on the held-out hard problem, the dev-vs-test
gap a single number would hide) fall short, every other cell passes 100%. What separates the field is
the judge panel: the Claude programs hold high judge agreement (Sonnet high 100%, Opus 80 to 100%)
while the competitor passing programs draw low agreement (GPT 0 to 50%, Gemini 20 to 60%), so several
competitor programs pass the tests but read as off-spec to an independent grader. With 5 problems and a
model judge, I am holding this as a corroborating pattern, not a cross-vendor verdict.

Why it matters for the pitch. The founder-facing value here is the cost-axis finding (the cheap tier
often clears the bar, so a team can stop overpaying), and the credibility is the held-out split plus
the judge cross-check. We should not lead with a Claude correctness lead on this slice, because there
is not one. The durable contribution is the methodology: a held-out overfit guard, an execution gate,
and a writer-is-never-the-grader judge panel, all runnable on a stranger's own JSONL. If we want an
eval-quality capability anchor, we need the full cross-vendor run on the hard slice, with credits to
finish it, and the number to hold.

To reproduce: `make setup`, `make compare-deps`, paste three keys into `.env`, then `make eval-smoke`
(cents) or `make eval` (about $3 to $4), and `EVAL_LCB=1 make eval` for the hard slice. The receipt is
`edges/eval-quality/sample.txt`.

{your_name}
