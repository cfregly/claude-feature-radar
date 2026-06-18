# CLAUDE.md

Conventions for any agent or person working in this repo.

## Numbers are receipts
Every dollar figure, latency, and token count comes from a real API call, never from memory.
The price table lives once in `common/models.py`, verified in `docs/VERIFIED_FACTS.md`. If you
quote a number, it must be reproducible by re-running the module that prints it. The demo
measures its own cost curve. It does not quote a figure from a blog.

## Apples to apples, or the number does not ship
Every cross-vendor number must count the same thing on every side, verified, before a reader sees it.
The traps that already bit this repo, all caught in `docs/FINDINGS.md`:
- **Token fields differ.** Claude's `input_tokens` EXCLUDES cached tokens (cache_read is reported
  separately), while OpenAI's `input_tokens` and Gemini's `prompt_token_count` INCLUDE them. Carried
  context is input plus cache_read on Claude, the total field on the others. Never compare the raw
  `input_tokens` across vendors.
- **Prices are pulled live, never assumed.** Every per-token price comes from the vendor's current
  pricing page, dated. A placeholder once made a competitor look four times cheaper than it was.
- **Cost depends on the caching config.** Caching changes the bill and interacts with context editing
  (clearing invalidates the cache). Report the config, and toggle caching on AND off to see it.
- **A cheap-tier win is a model-tier win.** Run the competitor's stronger model before any
  correctness or quality claim.
- **An unambiguous prompt, or you measure prompt-following.** A placeholder like `Answer: K` gets
  echoed literally by some models.
When a number cannot be made apples to apples, say so and drop it. Credibility is the whole asset.

## Carried context is every input bucket, not input plus cache_read
True carried context on Claude is `input_tokens + cache_read_input_tokens + cache_creation_input_tokens`,
the write bucket included. The three are disjoint and sum to the prompt the model actually processed.
Counting only input plus cache_read reads the context as about 1 token on a cold turn or the turn
right after context editing clears, because almost the whole prefix is a write then, which silently
undercounts the context exactly when a long-horizon claim depends on it. The per-turn `ctx` in
[`engine/demo.py`](engine/demo.py) sums all three. See [`docs/VERIFIED_FACTS.md`](docs/VERIFIED_FACTS.md).

## Ground every Claude and competitor claim
Every claim about a Claude feature, parameter, price, or limit traces to a page on
docs.claude.com, cited in `docs/VERIFIED_FACTS.md`. Every claim about a competitor traces to
that competitor's own public docs, dated. Anything you cannot verify is marked unverified, not
guessed. The platform ships monthly, so verify against the live doc, not memory.

## Verify both sides, then keep what survives
The engine finds a real capability gap, not a winning argument. It checks the Claude side and
the competitor side and throws out any framing that does not survive a skeptic. An overstated
claim in a founder's inbox is worse than no claim.

## Compare best to best, latest to latest
Every comparison uses each platform's LATEST API and ALL of its best features, including alpha and
beta, on both sides. Never handicap a competitor to make Claude look better, and never handicap
Claude either. Concretely: no older API when a newer one exists (use OpenAI's Responses API, not
Chat Completions), never disable a competitor's caching, compaction, or parallel execution, and
turn Claude's full stack on too (context editing, memory, caching). The comparison exists to find
the truth, not to win an argument. If our best loses to their best on cost, speed, or quality, that
is the finding: report it plainly and write the product-team alert below. A rigged win destroys the
founder trust this whole repo is built to earn.

## Measure and document cost, time, model, and why
Every run records, from real calls: total cost, wall-clock time, the exact model id on each side,
and the reason for each choice. Put the why in a comment next to the choice (why this model, why
this task shape, why this feature is on). No silent knobs. A reader sees, in the code and in the
receipt, exactly what ran, what it cost, how long it took, and why.

## Lead with what the result is worth to the reader
Every result this repo puts in front of a reader (the benchmark table, the founder email, the
README, the product note) says what it means for that reader before it says how it was made. A
number is not a finding, and a mechanism is not a value. "Claude held its context flat at 3k tokens
instead of 36k" is a mechanism: it says what the feature does, not what the reader gets. "With the
memory tool and the prompt held constant in both runs and only context editing toggled, the
editing-off agent crashed at the 200k context window and the editing-on agent finished the same job
for about thirty-five cents" is a finding, because the reader can see what they get. Lead with the
so-what: what the reader can now do, decide, build, or stop building. If a result carries no worth to
the reader, cut it.

## A mechanism is not a value, and a feature is measured where it bites
The trap this repo fell into, and the critique that fixed it: it showed context editing holding a
short agent at 3k tokens instead of 36k and called that the benefit. Holding context smaller is a
MECHANISM. The value is a measured change in what a founder pays for, cost, speed, correctness, or
reliability, and at that size there was none (the window is 200k to 1M), with the meter even showing
the managed run cost slightly MORE because clearing rewrites the cached prefix. The claim had no
so-what and should never have shipped.
- State the value as a measured number, or do not claim it.
- Measure the feature in the regime where it bites. A feature that only pays off at scale is
  measured at scale. The fix, [`engine/longhorizon.py`](engine/longhorizon.py), runs the agent with
  large payloads until the carried context exceeds the window, where context editing has a real,
  measured effect (the run finishes instead of the API erroring), not asserted from a mechanism.
- Isolate one variable, or you cannot attribute the win. The first version of that benchmark moved
  four things at once (the memory tool, context editing, a beta header, and a strategy-bearing
  prompt) and credited context editing for a correct answer that the memory tool actually produced.
  A confounded A/B measures the bundle, not the feature. Hold everything else constant and toggle
  exactly the one feature whose value you claim. Here the memory tool and the prompt are on in both
  arms and only context editing differs, so the reliability win is attributable to it alone.

## Find the global edge, not a local minimum
The deeper trap, the one that produced the mechanism above: the engine locked onto the first thing it
could measure as Claude-only (context editing) on a toy task (count the URGENT reports in a chain),
and a toy collapses every model to a cost-and-speed race Claude does not win, so the only thing left
standing was a plumbing primitive that, run honestly, miscounted. That is a local minimum. The edge
is global, and it can come from anywhere on the platform.
- Search the WHOLE surface. The anchor can be any capability across the Claude Developer Platform: an
  API primitive (prompt caching, the Batch API, the memory tool, code execution, citations, extended
  thinking, the 1M-token window), the Agent SDK, Agent Skills, MCP, Claude Code, or an economics
  lever. Do not stop at the first measurable Claude-only feature.
- Rank by value times genuine lead. Score every differentiator by how much a founder building a
  product cares, times how clearly Claude leads after the live competitor-parity check, and anchor on
  the global maximum, not the easiest thing to measure. Drop anything a competitor already matches.
- Pick the task that exercises the edge. A toy task hides the edge and surfaces a cost-and-speed race
  instead. Choose a real job where the edge decides the outcome, then measure it.
- The edge moves. Re-run the whole search as the platform ships monthly. Today's global maximum is
  next quarter's parity, so the engine searches every time, it does not cache a winner.
- Search and rank FIRST, then build. Sweep the surface and rank by value times lead before you build
  a benchmark or write a line of the email, never anchor on the first thing you can measure and rank
  afterward.
- Any genuine, measured value-add is a valid anchor, even a narrow one. A specific task type is fine
  to highlight when the edge is real on an axis a founder pays for (cost, speed, reliability,
  long-running, correctness). Do not dismiss a niche win for being niche, and do not inflate a
  broad-sounding claim that does not measure. The ranking sets the emphasis, it does not gate whether
  a real edge may be used.
- Measure the edge against the COMPETITOR, not just against Claude without the feature. "Claude with
  the feature beats Claude without it" proves the feature does something, it does not prove a
  competitive edge. An edge is real only when it is measured head-to-head against OpenAI and Gemini at
  their best on the same task, or grounded in a capability they verifiably do not ship. A
  feature-on-versus-off result is a within-Claude value-add, label it as exactly that until the
  cross-vendor arm is run.

## Put the workload, cost, and time on every outbound surface
The internal receipt is recorded above. What ships to a reader carries the same facts, up front, in
the reader's words, never buried:
- **The workload.** What ran: the task, the agent shape (how many steps, which tools), the exact
  model id on each side, the prompt complexity, the features turned on, and the assumptions a
  founder's own task would change.
- **The cost and the time.** The dollar cost and wall-clock time of the run, and the cost and time
  for the reader to reproduce it on their own keys, stated before they commit, not discovered
  halfway in.
- **The receipt.** Where each number comes from, so the reader can check it instead of trusting it.
A result or an email that hides its workload, its cost, or its reproduction cost and time is not
done.

## Review from the reader's point of view, always
Every review of an outbound surface (the founder email above all, the README, any result table) is
done as the person who receives it, not the person who built it. Read it cold as a busy founder and
answer their questions in order: what is this, what do I get, what does it cost me in money and
minutes to check, why should I believe you, what do I do next. The outbound-scrutiny panel below
carries a dedicated reader-point-of-view reviewer whose only job is to read as that founder and flag
anything that fails those questions. A claim that is true but does not answer "so what, for me" is
rewritten until it does.

## Persist every synthesis to a committed file, never re-derive it from a transcript
A run that fans out (the audit, a review panel) writes its synthesis to a committed file: the
verified brief in `briefs/` and the structured `engine/scan.py`, never only a workflow transcript or
a truncated return value. The next step reads the file. This keeps a result from being lost to a
truncated log, and lets a stranger see exactly what the audit concluded.

## Scrutinize every outbound communication, always, with an adversarial panel
Anything destined for someone outside this repo (the founder email above all, and the product-team
email) is the highest-stakes surface. It NEVER ships without a final outbound-scrutiny pass: an
adversarial review panel whose job is to find a single overclaim. The panel checks every claim
against the verified brief and the live benchmark, confirms the comparison is best-to-best and fair,
confirms the reproduction is one command with clear key placement and an upfront cost and time,
confirms the result states its workload and what it is worth to the reader, confirms the email opens
with a measurable, true, Claude-favorable hook, and confirms the prose is deslop-clean. One seat on
the panel reads only from the receiver's point of view, cold, as a busy founder, and flags anything
that fails what is this, what do I get, what does it cost me to check, why believe you, what next.
If any reviewer flags an overclaim, weaken it before sending. This pass is mandatory on every run,
not optional. An overstated outbound message is worse than no message.

## Ship a reproducible bundle every run
Each run drops a self-contained, dated bundle a stranger can reproduce. It contains BOTH our code
and the competitor's code, the receipts (cost, time, answers), a clear note on where to put each
API key, the exact cost and time to reproduce, and the constraints and assumptions (task shape,
prompt complexity, model tier) so a founder who swaps in their own prompt knows what will change.
The email links the bundle. Easy and transparent to reproduce is the product.

## If a competitor wins, tell the product team
When a fair run shows a competitor cheaper, faster, or better, that is signal, not failure. The
engine writes an internal product-team email with the reproduction bundle, the same way it writes
the founder email when Claude wins. Honesty runs in both directions.

## One command, one dependency
The core runs with a single `make` target and nothing but `anthropic` installed. The OpenAI
comparison adds exactly one optional dependency (`openai`), declared in `requirements-compare.txt`.

## Clean prose
No em-dashes or en-dashes, no semicolons in prose, no buzzwords. Say the thing plainly.

## Keep the email competitor-neutral, name competitors only as evidence
The founder email names no competitor, and the README hero stays neutral. The README comparison
section and the brief may name a competitor when it is a real, sourced, runnable comparison (the
OpenAI arm runs against OpenAI's published API and prices), because there it is dated evidence,
not a swipe.

## Keep it forkable
Cloned and edited by a stranger. No secrets in git (`.env` is ignored), no machine-specific
paths, no references to anything outside this repo.
