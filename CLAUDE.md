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
number is not a finding. "OpenAI ran this agent cheaper, and Claude held its context flat at about
3k tokens with no eviction code to write" is a finding, because the reader can see what they get.
Lead with the so-what: what the reader can now do, decide, build, or stop building. If a result
carries no worth to the reader, cut it or say plainly why it still matters to them.

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
