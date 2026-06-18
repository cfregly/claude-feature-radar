# Founder email: agentic coding (the conditional framing, NOT the one that ships this run)

This run is claude-behind on the slice, so the email that ships is the product-team note. This file is
the founder framing the methodology supports, and it is honest that on this run the slice did not go
Claude's way. It is here to show the engine applied to this edge, not to pitch a number that lost.

---

**Subject:** A coding-model head-to-head you can run yourself in one command, no Docker, no trust required

Hey {first_name},

If you are choosing which model to build a coding product on (an agent that reads a repo, understands
an issue, and writes a patch that passes the tests), the only number worth anything is the one you ran
yourself. So instead of a chart, here is a head-to-head you can reproduce on your own keys.

It runs a curated slice of SWE-bench Verified (real GitHub issues from flask and pylint) agentically:
each model proposes a patch, the harness grades it against the real tests locally with no Docker, and
on a miss it feeds the exact failure back and lets the model try again, up to three rounds. The grader
proves itself first by resolving every human gold patch, and the loop is identical for every provider,
the same accumulated history forwarded to Claude, OpenAI, and Gemini, so nobody gets an unfair turn.

I will be straight about my own run, because the whole point is that you do not have to trust me. On
this four-instance slice, with the symmetric loop, GPT-5.5 resolved all four (including two hard pylint
issues rated 1 to 4 hours to fix by hand) and the Claude models resolved two of four, tied with the
rest of the field. So on THIS slice, run THIS way, Claude was not the winner, and I am not going to
pretend otherwise. The headline SWE-bench Verified leaderboard, the full 500-instance one, still shows
Claude leading at scale, and you should weigh that, but my small slice went the other way and I am
showing you the receipt.

So why build on Claude? Not on this slice. The edges where I measured Claude genuinely ahead are
elsewhere, and they are in the same repo with the same run-it-yourself receipts:

- Programmatic tool calling cut billed input tokens by about 28% on a fan-out task, where no competitor
  keeps your own tool outputs out of the model's context (`make ptc`).
- Citations returns a guaranteed-valid, per-character source pointer into your user's own document,
  free of output tokens, with zero resolver code (`make citations`).
- On METR's independent task time-horizon (the neutral referee, not a vendor chart), the top released
  Claude model runs the longest autonomous jobs of any model, about 1.9x the next best.

{repo_link}

Run the coding head-to-head yourself: `make setup`, `make compare-deps` (this one pulls in the dataset
and grading tools), `uv` on PATH, paste three keys into `.env`, then `make validate` (proves the
grader, no model spend) and `make agentic` (about $4 to $5). Every number is read off the real API
usage object, and the slice is small and pure-Python on purpose so it runs fast and honest.

The reason I am sending you a benchmark that did not flatter Claude is the reason to trust the rest:
this engine reports both directions, so when it tells you Claude wins an edge, that claim survived the
same scrutiny this one failed.

Go build,

{your_name}
Building with Claude

---

### Why it is built this way (not part of the email)

- **It does not pitch a loss as a win.** The measured slice went to GPT-5.5, so the email says so. The
  engine's honesty rule is that an overstated claim in a founder's inbox is worse than no claim, so the
  agentic-coding edge is not the anchor this run. It is the credibility proof that the engine reports
  both directions.
- **The symmetric loop is disclosed as the reason the result differs.** An earlier asymmetric run had
  Claude at 4/4, and forwarding the full history to every provider changed it. The email and the
  product-team note both name that, so a reader who saw the old number is not confused.
- **The real anchors are the genuinely Claude-ahead edges.** PTC, Citations, and the METR time-horizon
  carry their own measured receipts in this repo, so the founder is pointed at the edges that survived.
- **Every number is a receipt.** The 2/4 and 4/4, the $5.46 total, and the gold-patch validation all
  come from `make validate` and `make agentic` (`edges/agentic-coding/sample.txt`), not from memory.
