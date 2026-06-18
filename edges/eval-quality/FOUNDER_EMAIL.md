# Founder email: eval quality (the cost-axis framing, the parity read this run supports)

This run is parity on correctness (every model tied on the held-out split), so the email does not pitch
a Claude capability lead. It pitches the thing the run actually measured: which tier you are overpaying
for on your own cases, and a one-command way to find out. It stays competitor-neutral, per the repo
convention, and points the founder at the genuinely Claude-ahead edges as the reasons to build.

---

**Subject:** Find out which model tier you are overpaying for, on your own cases, in one command

Hey {first_name},

If you are shipping a feature on Claude (a classifier, an extractor, a code helper, anything graded by
a real check), the question that decides your bill is which tier and how much reasoning effort you
actually need. Most teams default to the frontier model and never test whether the cheap tier already
clears their bar. So instead of a chart, here is a grid you can run on your own cases.

It sweeps your labeled slice across every model tier and every effort level, grades each one by
EXECUTION against your hidden tests (no rubric, no LLM-as-judge as the gate), and prints pass rate
against real dollars. Two things keep it honest. The headline number is a HELD-OUT test split, so a
cell that looks good only because it was tuned against the cases you measured gets caught (an overfit
guard built into the run). And a judge panel cross-checks each passing program, with the writer never
its own grader, so you can see if the execution grade is too trusting on any task.

I will be straight about my own run, because the point is that you do not trust me, you run it. On my
labeled slice every tier tied at 100% on the held-out split, Claude Haiku included, so no model led on
correctness. The finding was the cost: Haiku resolved the held-out set for less than half a cent, and
the most expensive frontier cell resolved the same set for about thirty times more. Paying for the
bigger model bought cost, not capability, on that slice. On a harder slice the tiers do separate (the
cheap tier hits its limit, and effort starts earning its tokens), which is the whole reason the grid
sweeps both, and you point it at YOUR cases to find where your own line sits.

So why build on Claude, if this run is a tie? Because the tie IS the value here (you can drop to the
cheap tier and stop overpaying), and the genuine capability leads are elsewhere in the same repo, each
with its own run-it-yourself receipt:

- Programmatic tool calling cut billed input tokens by about 28% on a fan-out task, where no competitor
  keeps your own tool outputs out of the model's context (`make ptc`).
- Citations returns a guaranteed-valid, per-character source pointer into your user's own document,
  free of output tokens, with zero resolver code (`make citations`).
- The model tiers (Haiku 4.5, Sonnet 4.6, Opus 4.8) and the model-gated effort knob are exactly what
  this grid lets you price against your own bar, so you ship the tier you need, not the one you assumed.

{repo_link}

Run it yourself: `make setup`, `make compare-deps`, paste your keys into `.env`, then `make eval-smoke`
for a cents-scale taste or `make eval` for the full cross-vendor grid (about $3 to $4). Point it at your
own benchmark with `EVAL_TASKS=your.jsonl`. Every dollar is read off the real API usage object, and the
held-out split is the number worth trusting.

The reason I am sending you a benchmark that did not crown Claude is the reason to trust the rest: this
engine reports the tie when it is a tie, so when it tells you Claude wins an edge, that claim survived
the same scrutiny.

Go build,

{your_name}
Building with Claude

---

### Why it is built this way (not part of the email)

- **It does not invent a capability lead.** The run was parity on correctness, so the email pitches the
  cost-axis finding (drop to the tier you need) and the grid that measures it, never a made-up Claude
  win. The honesty rule is that an overstated claim in a founder's inbox is worse than no claim.
- **The held-out split and the judge panel are the credibility, not decoration.** The believable number
  is the split no cell was tuned against, and the judge cross-check is how a reader knows the execution
  grade is not too trusting. Both are named because both are what make the receipt trustworthy.
- **The real anchors are the genuinely Claude-ahead edges.** PTC and Citations carry their own measured
  receipts in this repo, so the founder is pointed at the edges that survived a head-to-head, while the
  tier-and-effort grid is the tool that saves them money on whichever tier they land on.
- **Every number is a receipt.** The 100% held-out tie, the sub-half-cent Haiku cost, and the ~30x
  spread all come from `make eval` (`edges/eval-quality/sample.txt`), read off the usage object, not
  from memory.
