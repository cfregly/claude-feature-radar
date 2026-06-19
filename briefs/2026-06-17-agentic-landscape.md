# Long-horizon autonomy, reconciled for a founder pitch (2026-06-17)

The pitch anchor under test: "the agent that finishes hard, long, tool-heavy jobs." This brief
reconciles the sourced long-horizon evidence into the honest picture, weighting the independent METR
referee above vendor self-reports. It names competitors because it is dated evidence, not a swipe.
Re-run before quoting, because this surface moves monthly.

## The honest headline

The one independent referee where Claude leads with a real margin and a citable data file is METR's
50% task time-horizon: the highest released Claude model holds the only is_sota flag and runs about
1.9x longer than the best non-Claude model before its reliability falls to 50%. That is the
defensible anchor for "finishes long jobs," and it is the place the long-horizon claim survives a
skeptic on neutral data.

## The anchor: METR 50% task time-horizon, Claude Opus 4.6 about 12 hr vs about 6.4 hr next-best

What it is: METR measures the length of task a frontier agent can finish autonomously at 50%
reliability, on a fixed task suite, scored by a neutral third party that is not a model vendor. It is
the closest thing to a referee-grade measure of "finishes long jobs" that exists.

### METR 50% task time-horizon, official data file
- Highest released model on the official YAML: Claude Opus 4.6 at P50 = 718.8 min, about 12.0 hr,
  is_sota true, release 2026-02-05. It is the only released model carrying is_sota true.
- Best non-Claude released models: Gemini 3.1 Pro at 384.1 min (about 6.4 hr, is_sota false) and
  GPT-5.2 at 352.2 min (about 5.9 hr). GPT-5.3-Codex is 349.5 min, GPT-5.4 is 341.7 min.
- Margin: Claude Opus 4.6 runs about 1.87x the best non-Claude model (Gemini 3.1 Pro) and about 2.04x
  GPT-5.2, on the same neutral data file.
- Source: https://metr.org/time-horizons/ (data
  https://metr.org/assets/benchmark_results_1_1.yaml), pulled 2026-06-17.

Why it survives the skeptic:
- It is independent. METR is not Anthropic, OpenAI, or Google. The number is read from METR's own
  published data file, not a vendor table.
- The margin is real, not a rounding tie. About 12.0 hr vs about 6.4 hr for the best non-Claude model
  is roughly 1.9x, not a coin-flip.
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

## Where Claude leads on vendor self-reports (lower weight, still useful)

These come from Anthropic's own Claude Opus 4.8 system card (2026-05-28,
https://www-cdn.anthropic.com/0b4915911bb0d19eca5b5ee635c80fef830a37ea.pdf) and Google's own table
where noted. A vendor reporting its own and a rival's score has an obvious incentive, so weight these
below the independent boards.
- OSWorld-Verified (computer use): Claude Opus 4.8 83.4% vs GPT-5.5 78.7% vs Gemini 3.1 Pro 76.2%
  (Anthropic card). OpenAI's own page shows GPT-5.5 78.7% vs Claude Opus 4.7 78.0%, an effective tie
  at the older Claude generation. So the lead is real on the newest models but narrow, not decisive.
- MCP Atlas (tool use): Claude Opus 4.7 79.1% leads on OpenAI's own table (GPT-5.5 75.3%, Gemini 3.1
  Pro 78.2%). Claude Opus 4.8 is 82.2% on Anthropic's card.

## The vendor "ran for N hours" claims are anecdotes, not the anchor

Both Anthropic and OpenAI publish single-run endurance demos. They are not benchmarks and are not
directly comparable, so do not present them as a head-to-head.
- Anthropic: Claude Sonnet 4.5 "maintaining focus for more than 30 hours on complex, multi-step
  tasks" (verbatim, https://www.anthropic.com/news/claude-sonnet-4-5, 2025-09-29). Note the 30+ hr
  claim is Sonnet 4.5, not Opus 4.5 (easy to conflate).
- OpenAI: GPT-5.3-Codex "ran for about 25 hours uninterrupted, used about 13M tokens, and generated
  about 30k lines of code" (verbatim,
  https://developers.openai.com/blog/run-long-horizon-tasks-with-codex, 2026-02-23).
- Google publishes no equivalent "ran for N hours" claim. Its long-horizon evidence is on other axes
  (Vending-Bench 2, APEX-Agents), which measure planning coherence.
These bracket the picture but do not settle the ranking. Use them only as color behind the METR
number, never as the proof.

## The recommended anchor and the one-liner

Anchor: Claude leads the only independent, referee-graded measure of long-horizon autonomy. On
METR's 50% task time-horizon, the published data file puts Claude Opus 4.6 at about 12 hours, the
only released model flagged top on the suite, about 1.9x the best non-Claude model (Gemini 3.1 Pro at
about 6.4 hr, GPT-5.2 at about 5.9 hr).

One-liner a founder feels: when the job is long enough that the other models quit halfway, Claude is
the one still working.

## The benchmark we run on our own keys to prove it

A founder will not take METR on faith, and METR's suite is near-saturated, so we run our own
long-horizon, tool-heavy job on our own keys and publish the receipts.

Task: a long, tool-heavy run with a machine-checkable success criterion, not a counting toy. The
runnable receipt is the context-editing long-horizon isolation (`make longhorizon`): a chain of large
incident reports drives the carried context past the window, and the run is repeated three times with
only context editing toggled. Record on every side, from real calls: pass or fail, wall-clock time,
dollar cost, and total tokens carried. The success gate is a real test of whether the run finishes
correctly at the window, not a rubric the model can game.

This is the right test because the success gate is a finish-or-fail check (not a rubric), it is long
and tool-heavy (it exercises the anchor, not a single API call), and it is reproducible by a founder
on their own keys from one command.

## Caveats that must travel with any quote from this brief

- METR Opus 4.6 about 12 hr is read from the data file with its is_sota flag. The about 14.5 hr live
  figure has a 6 to 98 hr CI and the suite is near-saturated. Never quote either as a precise number.
- The three Claude models in the system cards were benchmarked at different dates against different
  competitor generations and different benchmark versions. Do not place them on one chart.
- Vendor "ran for N hours" demos (Anthropic 30+ hr Sonnet 4.5, OpenAI about 25 hr Codex) are
  single-run anecdotes with no shared protocol and are not directly comparable.
- Competitor numbers on a vendor's own page (Anthropic's card, OpenAI's page, Google's table) carry
  an incentive bias. Re-verify each against the rival's primary source before it ships.
- The whole frontier moves monthly. Re-pull every data file and re-run our own benchmark before any
  number goes in front of a founder.
