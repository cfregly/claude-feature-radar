# Product-team email: agentic coding, the honest other direction (this run ships this one)

This run is claude-behind on the slice, so this is the email that goes out. Same rigor as a founder
email. The engine writes the product-team note when a competitor wins, not the pitch.

---

**Subject:** On a fair symmetric SWE-bench slice, GPT-5.5 resolved both hard instances and no Claude model did

To the Claude platform team,

I built a reproducible agentic-coding head-to-head into the competitive engine and ran it best-to-best.
The result on this slice is that GPT-5.5 is ahead, and I want to flag it cleanly because the way it
came out matters more than the single number.

The setup. A curated pure-Python slice of SWE-bench Verified (flask, pylint), 4 instances, graded
LOCALLY with no Docker (the swebench package's own per-instance env recipe rebuilt in a uv venv, scored
by the harness's own parser, so the verdict matches the public leaderboard). Each instance is solved
agentically: propose a patch, grade it against the real tests, feed the exact failure back, up to 3
rounds. The grader is proven first: all 4 human gold patches resolve locally, so a model patch gets a
real verdict.

The loop is symmetric, and that is the load-bearing part. Every provider gets the same accumulated
multi-turn history on every round (Claude, OpenAI, and Gemini all see the prior patches and the prior
test failures). An earlier version forwarded the full history only to Claude, which flattered Claude by
comparing a multi-turn Claude against a one-shot competitor. Once I removed that confound, the result
flipped.

The measured outcome (4 instances, up to 3 rounds, effort=medium, $5.46 total off the usage object):

- GPT-5.5: 4 of 4.
- Claude Opus 4.8: 2 of 4. Claude Sonnet 4.6: 2 of 4.
- GPT-5.4, Gemini 3.1 Pro, Gemini 3.5 Flash: 2 of 4 each.

The two easy instances tied the whole field at 6 of 6, so they decide nothing. The two HARD pylint
instances (rated 1 to 4 hours to fix by hand) are where it separates, and GPT-5.5 resolved BOTH while
no Claude model resolved either. GPT-5.5 landed those two on round 3, so it used the feedback loop to
get there, which is exactly the agentic-iteration ability we like to claim as a Claude strength.

What I am NOT saying. This is one small slice, not the 500-instance leaderboard, and the headline
SWE-bench Verified board still shows Claude leading at full scale, which I quote with its source rather
than this slice. The result can move with the instances chosen, the round budget, and the effort label.
But on a clean, fair, symmetric run it came out against us, and the honest move is to say so.

Why it matters for the pitch. We should not lead a founder email with agentic SWE-bench separation
based on a slice that, run symmetrically, goes the other way. The durable thing here is the
methodology: a no-Docker grader anyone can run, a symmetric loop, and a gold-patch self-test. If we
want to anchor on coding, we need a larger slice and the symmetric loop, and we need the number to hold.

To reproduce: `make setup`, `make compare-deps`, `uv` on PATH, paste three keys into `.env`, then
`make validate` and `make agentic`, about $4 to $5. The receipt is `edges/agentic-coding/sample.txt`.

{your_name}
