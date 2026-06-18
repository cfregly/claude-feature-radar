# CLAUDE.md

Conventions for any agent or person working in this repo.

## Numbers are receipts
Every dollar figure, latency, and token count comes from a real API call, never from memory.
The price table lives once in `common/models.py`, verified in `docs/VERIFIED_FACTS.md`. If you
quote a number, it must be reproducible by re-running the module that prints it. The demo
measures its own cost curve. It does not quote a figure from a blog.

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

## Scrutinize every outbound communication
Anything destined for someone outside this repo (the founder email above all, and any product-team
alert) is the highest-stakes surface. Before it ships it gets a hard review pass: every claim is
sourced and not overstated, the comparison behind it is best-to-best and fair, the reproduction is
one command with clear key placement and an upfront cost, and the prose is deslop-clean. When in
doubt, weaken the claim. An overstated outbound message is worse than no message.

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
