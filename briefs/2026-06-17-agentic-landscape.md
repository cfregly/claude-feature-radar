# Agentic AI capability, reconciled for a founder pitch (2026-06-17)

The pitch anchor under test: "the agent that finishes hard, long, tool-heavy jobs." This brief
reconciles five sourced benchmark reports into the honest picture, weighting independent
leaderboards (SWE-bench, Terminal-Bench, METR) above vendor self-reports. It names competitors
because it is dated evidence, not a swipe. Re-run before quoting, because this surface moves monthly.

## The honest headline

On the independent coding leaderboards Claude does not lead. On the official SWE-bench Verified board
the top Claude entry ties at the ceiling and nothing is at or above 80%. On both Terminal-Bench
tracks GPT-5.5 is ahead or in a statistical tie. The one independent referee where Claude leads with
a real margin and a citable data file is METR's 50% task time-horizon: the highest released Claude
model holds the only is_sota flag and runs about 1.9x longer than the best non-Claude model before
its reliability falls to 50%. That is the defensible anchor for "finishes long jobs," and it is the
only place the long-horizon claim survives a skeptic on neutral data.

## What the independent boards actually say (weighted highest)

### SWE-bench Verified, official board (swebench.com)
- Claude 4.5 Opus leads the board at 79.2% (two agent scaffolds tied at the top, dated 2025-12-15 and
  2025-12-05). Gemini 3 Pro Preview is next at 77.4%. No GPT model appears in the top tier.
- The ceiling is 79.2% and NOTHING on the official board is at or above 80%. Every top entry is
  self-reported via S3 log submission and none carry an official verified flag.
- Do not put any 90%+ SWE-bench Verified number in the pitch. Aggregator claims of "Claude Mythos 5
  95.5%" and "Fable 5 95%" do not exist in the official data file and are fabricated.
- Source: https://www.swebench.com/ (data file
  https://raw.githubusercontent.com/SWE-bench/swe-bench.github.io/master/data/leaderboards.json),
  pulled 2026-06-17.

### Terminal-Bench 2.0, official (tbench.ai)
- Leader: NexAU-AHE + GPT-5.5 at 84.7% (2026-05-14). Top Claude entry is WOZCODE + Claude Opus 4.7 at
  80.2%, behind by about 4.5 points. Rankings are agent-harness plus model combos, not pure model
  scores, and the top spread sits inside the +/-2% error bars.
- Source: https://www.tbench.ai/leaderboard/terminal-bench/2.0, fetched 2026-06-17.

### Terminal-Bench 2.1, official (tbench.ai, harder suite, not comparable to 2.0)
- Leader: Codex CLI + GPT-5.5 at 83.4% (2026-05-01). Top Claude entry is Claude Code + Claude 5 Fable
  at 83.1% (2026-06-17), a statistical tie given +/-2 error bars. Claude Code + Claude Opus 4.8 is
  78.9% (2026-05-29).
- Source: https://www.tbench.ai/leaderboard/terminal-bench/2.1, fetched 2026-06-17.

### METR 50% task time-horizon, official data file (the anchor)
- Highest released model on the official YAML: Claude Opus 4.6 at P50 = 718.8 min, about 12.0 hr,
  is_sota true, release 2026-02-05. It is the only released model carrying is_sota true.
- Best non-Claude released models: Gemini 3.1 Pro at 384.1 min (about 6.4 hr, is_sota false) and
  GPT-5.2 at 352.2 min (about 5.9 hr). GPT-5.3-Codex is 349.5 min, GPT-5.4 is 341.7 min.
- Margin: Claude Opus 4.6 runs about 1.87x the best non-Claude model (Gemini 3.1 Pro) and about 2.04x
  GPT-5.2, on the same neutral data file.
- Source: https://metr.org/time-horizons/ (data
  https://metr.org/assets/benchmark_results_1_1.yaml), pulled 2026-06-17.

## The anchor: METR 50% task time-horizon, Claude Opus 4.6 about 12 hr vs about 6.4 hr next-best

What it is: METR measures the length of task a frontier agent can finish autonomously at 50%
reliability, on a fixed task suite, scored by a neutral third party that is not a model vendor. It is
the closest thing to a referee-grade measure of "finishes long jobs" that exists.

Why it survives the skeptic:
- It is independent. METR is not Anthropic, OpenAI, or Google. The number is read from METR's own
  published data file, not a vendor table.
- The margin is real, not a rounding tie. About 12.0 hr vs about 6.4 hr for the best non-Claude model
  is roughly 1.9x, not a coin-flip like the Terminal-Bench top spread.
- METR's `is_sota` data field marks the top released model on the suite, and only Claude Opus 4.6
  carries it. It is a single machine-readable claim, not a vendor adjective.

The honest caveats that must travel with this number, or the claim is an overclaim:
- METR's task suite is near-saturated at the top. The newer Claude Opus 4.6 live-leaderboard estimate
  of about 14.5 hr carries a 95% confidence interval of 6 to 98 hr (per the LessWrong community
  write-up of METR's measurements,
  https://www.lesswrong.com/posts/WacuyurbABwNv8ziq/estimating-metr-time-horizons-for-claude-opus-4-6-and-gpt-5,
  2026-02-20, and officechai 2026-02-21
  https://officechai.com/ai/exponential-progress-claude-opus-4-6-has-50-time-horizon-of-14-5-hours-on-metr-time-horizons-benchmark/).
  Quote the data-file figure (718.8 min, about 12.0 hr) with its is_sota flag, not the wide-interval
  14.5 hr live estimate, and never as a precise capability.
- A preview entry, claude_mythos_preview_early, shows 1044.8 min (about 17.4 hr) but EXCEEDS METR's
  stated 16-hr reliability ceiling and is a preview, so it is unreliable. Do not cite it.
- The doubling trend (METR's own framing) accelerated from about every 7 months in the original 2025
  finding (https://metr.org/blog/2025-03-19-measuring-ai-ability-to-complete-long-tasks/) to about
  131 days post-2023 and about 89 days since 2024 under TH1.1
  (https://metr.org/blog/2026-1-29-time-horizon-1-1/, 2026-01-29). State which figure you mean.
- The number measures one Claude model (Opus 4.6) on one suite. It is a model-and-suite result, not a
  blanket claim that every Claude beats every competitor at every long task.

## The vendor "ran for N hours" claims are anecdotes, not the anchor

Both Anthropic and OpenAI publish single-run endurance demos. They are not benchmarks and are not
directly comparable, so do not present them as a head-to-head.
- Anthropic: Claude Sonnet 4.5 "maintaining focus for more than 30 hours on complex, multi-step
  tasks" (verbatim, https://www.anthropic.com/news/claude-sonnet-4-5, 2025-09-29). Note the 30+ hr
  claim is Sonnet 4.5, not Opus 4.5 (easy to conflate).
- OpenAI: GPT-5.3-Codex "ran for about 25 hours uninterrupted, used about 13M tokens, and generated
  about 30k lines of code" (verbatim,
  https://developers.openai.com/blog/run-long-horizon-tasks-with-codex, 2026-02-23).
- Google publishes no equivalent "ran for N hours" coding claim. Its long-horizon evidence is on
  other axes (Vending-Bench 2, APEX-Agents), which measure planning coherence, not coding endurance.
These bracket the picture but do not settle the ranking. Use them only as color behind the METR
number, never as the proof.

## Where Claude leads on vendor self-reports (lower weight, still useful)

These come from Anthropic's own Claude Opus 4.8 system card (2026-05-28,
https://www-cdn.anthropic.com/0b4915911bb0d19eca5b5ee635c80fef830a37ea.pdf) and Google's own table
where noted. A vendor reporting its own and a rival's score has an obvious incentive, so weight these
below the independent boards.
- SWE-bench Pro: Claude Opus 4.8 69.2% vs GPT-5.5 58.6% vs Gemini 3.1 Pro 54.2% (Anthropic card).
  OpenAI's own page corroborates the direction, showing Claude Opus 4.7 64.3% ahead of GPT-5.5 58.6%
  (https://openai.com/index/introducing-gpt-5-5/, 2026-04-23). Caveat: OpenAI footnotes memorization
  evidence on this eval, so absolute numbers are suspect even though the ordering holds on both
  vendors' pages.
- OSWorld-Verified (computer use): Claude Opus 4.8 83.4% vs GPT-5.5 78.7% vs Gemini 3.1 Pro 76.2%
  (Anthropic card). OpenAI's own page shows GPT-5.5 78.7% vs Claude Opus 4.7 78.0%, an effective tie
  at the older Claude generation. So the lead is real on the newest models but narrow, not decisive.
- MCP Atlas (tool use): Claude Opus 4.7 79.1% leads on OpenAI's own table (GPT-5.5 75.3%, Gemini 3.1
  Pro 78.2%). Claude Opus 4.8 is 82.2% on Anthropic's card.

## Parity or behind, do not pitch as a Claude win

- SWE-bench Verified, headline coding: parity at best on the independent board (Claude 79.2% ties the
  ceiling, nothing at or above 80%). Anthropic's vendor card claims 88.6% for Opus 4.8, but OpenAI
  publishes no SWE-bench Verified figure for GPT-5.5 at all (it reports SWE-bench Pro instead), so a
  clean three-way head-to-head on Verified does not exist. Do not claim Claude leads SWE-bench
  Verified head-to-head.
- Terminal-Bench (both 2.0 and 2.1): behind or tied. GPT-5.5 leads 2.0 (84.7 vs 80.2) and edges 2.1
  (83.4 vs 83.1, a tie). Do not claim Claude leads Terminal-Bench.
- BrowseComp (agentic web search): GPT-5.5 Pro leads at 90.1%, Gemini 3.1 Pro 85.9% edges GPT-5.5
  84.4%, Claude Opus 4.7 trails at 79.3% (OpenAI's own table).
- tau-bench / tau2-bench for Opus 4.8: ABSENT from the Opus 4.8 system card (full 246-page search).
  Reported only for Sonnet 4.6 (Retail 91.7, Telecom 97.9). Do not attribute a tau-bench number to
  Opus 4.8.
- Raw price: OpenAI is cheaper on a fair benchmark (per this repo's own cost finding). The anchor is
  not price.

## The recommended anchor and the one-liner

Anchor: Claude leads the only independent, referee-graded measure of long-horizon autonomy. On
METR's 50% task time-horizon, the published data file puts Claude Opus 4.6 at about 12 hours, the
only released model flagged top on the suite, about 1.9x the best non-Claude model (Gemini 3.1 Pro at
about 6.4 hr, GPT-5.2 at about 5.9 hr).

One-liner a founder feels: when the job is long enough that the other models quit halfway, Claude is
the one still working.

## The benchmark we run on our own keys to prove it

A founder will not take METR on faith, and METR's suite is near-saturated, so we run our own
long-horizon, tool-heavy job across all three vendors on our own keys and publish the receipts.

Task: a real multi-step repository-repair job with a machine-checkable success criterion, not a
counting toy. Pick a public open-source Python repository at a known-failing commit (a real bug with
a real failing test in the project's own suite, the SWE-bench style but run live by us, not quoted
from a leaderboard). Give each agent the same harness: a working tree, shell and file-edit and
test-run tools, and one instruction, "make the failing test pass without breaking the rest of the
suite." Run the same job on Claude (claude-opus-4-8), OpenAI (GPT-5.5 via the Responses API with its
tool loop), and Gemini (the latest Gemini with tool use), each with its full agent stack on, caching
and parallel tool use included, so it is best-to-best.

Success criterion, verifiable and identical on every side: the target test goes from fail to pass AND
the rest of the project's suite stays green, checked by running the suite, not by reading the model's
self-report. Record on every side, from real calls: pass or fail, number of tool-call steps to
resolution, wall-clock time, dollar cost, and total tokens carried. To make it a LONG-horizon test
and not a one-shot, chain three to five such repairs in a single session against an accumulating
context, so the score is "how many of N independent bugs did it finish in one run before it lost the
thread," which is exactly the time-horizon axis METR measures, now reproduced on our keys with a
hard pass/fail gate. The number that ships is "Claude finished K of N, the next vendor finished J of
N, here is the cost and time for each and the one command to reproduce it."

This is the right test because the success gate is a test suite (not a rubric the model can game), it
is long and tool-heavy (it exercises the anchor, not a single API call), it is best-to-best (each
vendor runs its latest model and full stack), and it is reproducible by a founder on their own keys
from one command.

## Caveats that must travel with any quote from this brief

- METR Opus 4.6 about 12 hr is read from the data file with its is_sota flag. The about 14.5 hr live
  figure has a 6 to 98 hr CI and the suite is near-saturated. Never quote either as a precise number.
- Every SWE-bench Verified top entry is self-reported, not independently verified, and the official
  ceiling is 79.2%. No 90%+ Verified number is real.
- Terminal-Bench rankings are harness-plus-model combos and the top spreads are inside the error
  bars. Claude does not lead Terminal-Bench on either track.
- The three Claude models in the system cards were benchmarked at different dates against different
  competitor generations and different benchmark versions. Do not place them on one chart.
- Vendor "ran for N hours" demos (Anthropic 30+ hr Sonnet 4.5, OpenAI about 25 hr Codex) are
  single-run anecdotes with no shared protocol and are not directly comparable.
- Competitor numbers on a vendor's own page (Anthropic's card, OpenAI's page, Google's table) carry
  an incentive bias. Re-verify each against the rival's primary source before it ships.
- The whole frontier moves monthly. Re-pull every data file and re-run our own benchmark before any
  number goes in front of a founder.
