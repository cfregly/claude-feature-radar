# CLAUDE.md

Conventions for any agent or person working in this repo.

## Use Chris Fregly's voice for every outbound surface

Read `CHRIS_FREGLY_VOICE.md` before writing or editing any founder email, product email, brief,
README CTA, generated outbox draft, or public-facing copy in this repo.

The voice is builder-to-builder: warm, direct, concrete, measured, first-person, and code-backed.
Keep the thinking pattern from public talks and writing, but remove transcript filler. No ums, uhs,
repeated starts, or throat-clearing. Start with the founder's workload, name the pain in their terms,
show the Claude feature and the one code change, then give the receipt and the exact next command.

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

When a doc names a newer tool version, model, beta header, parameter, or response field, verify the
whole chain before classifying the edge: current docs, latest package-manager SDK version, installed
SDK generated schema, raw API acceptance, and any documented or plausible beta header. If docs,
SDK, and runtime disagree, the discrepancy is a first-class receipt item. Hold the edge until the
live API accepts the exact subfeature and the workload proves value.

Fast mode has a separate org-level rate-limit pool. A `0 fast mode input tokens per minute` error
cannot be fixed in this repo or by changing the Messages request. Request fast-mode access or a
fast-mode rate-limit increase through the Anthropic account path, confirm it on the Claude Console
Limits page or with the Rate Limits API, then run `make fast-mode` for the receipt.

## Beta, alpha, and experimental edges are fair game, and often the anchor
A capability being beta, alpha, or experimental is never a reason to drop it from the search or the
pitch. The newest Claude surfaces are frequently where the genuine edge lives, so when a beta or alpha
feature is the sharpest verified differentiator, anchor on it and lead with it. Label the maturity
plainly, name the doc and the date and any beta header it needs, and let the grounding rule carry it.
The "compare best to best" rule already puts alpha and beta on the table for both sides. This makes it
explicit: a stated beta caveat is part of an honest pitch, not a reason to look away from the edge.
Many of the headline Claude API surfaces (the Files, Skills, Agents, Sessions, and Environments APIs)
are beta today, checked 2026-06-17, and that is exactly what a founder building this quarter wants.

## Measure and document cost, time, model, and why
Every run records, from real calls: total cost, wall-clock time, the exact model id on each side,
and the reason for each choice. Put the why in a comment next to the choice (why this model, why
this task shape, why this feature is on). No silent knobs. A reader sees, in the code and in the
receipt, exactly what ran, what it cost, how long it took, and why.

## Model tier tracks stakes, not cost
Pick the model tier by stakes times reasoning difficulty times volume, never "default to cheap". The
seats that decide what is true and what ships run on the top tier with adaptive thinking on: the
skeptic pass (`engine/verify.py`), the founder email (`engine/draft_email.py`), and the product-team
note (`engine/product_alert.py`) all run Opus with `request_kwargs("opus", effort="high",
adaptive_thinking=True)`. Extraction that the API already guarantees runs on Sonnet, like the
Citations grounding loop (`engine/cite_facts.py`), where thinking would add latency across many calls
for no judgment gain. The deterministic discovery loop stays a $0 pass with no model call. Almost
nothing here runs on Haiku, and the one place it does is a benchmark arm that races Claude's cheap
tier against the competitor's equivalent cheap tier, tier-matched on purpose, never a judgment call.
Haiku cannot take the effort knob or adaptive thinking, so it is wrong for any seat whose job is to
think. The judgment calls are low-volume, so the top tier costs pennies and a lenient skeptic costs
the whole asset. When in doubt, go up a tier.

## Lead with what the result is worth to the reader
Every result this repo puts in front of a reader (the benchmark table, the founder email, the
README, the product note) says what it means for that reader before it says how it was made. A
number is not a finding, and a mechanism is not a value. "Claude held its context flat at 3k tokens
instead of 36k" is a mechanism: it says what the feature does, not what the reader gets. "With the
memory tool and the prompt held constant in both runs and only context editing toggled, the
editing-off agent crashed at the 200k context window and the editing-on agent finished the same job
for $0.35" is a finding, because the reader can see what they get. Lead with the
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
  measured at scale. The fix, [`edges/context-editing/demo.py`](edges/context-editing/demo.py), runs the agent with
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
- Search below the feature name. A wedge is often a subfeature, not the headline capability. Break a
  surface into parameters, modes, beta headers, response fields, billing behavior, lifecycle rules,
  failure modes, and where it sits inside an agent loop. Do not call "web search", "files", "tools",
  "agents", "caching", or "code execution" parity until the subfeatures have been compared. The
  current web-search lesson is the rule: generic web search is parity, but pre-context dynamic
  filtering plus result-block exclusion may still be a real candidate edge.
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

## Understand the mechanism, then find the workload where the edge appears
Before you claim OR dismiss a feature, understand how it actually works: what the API does under the
hood, what the competitor's nearest equivalent does, and exactly where each one breaks. That
understanding is the creative engine of this repo. A naive head-to-head on a toy task usually shows
parity, because the task never stresses the thing the feature is good at. Knowing the mechanism is
what lets you design a REAL workload where the difference shows up as a number a founder would feel.
- Learn the mechanism on both sides. Claude's context editing clears tool results in place, OpenAI's
  compaction summarizes them (and can drop a detail), Gemini carries the full window (and pays for
  it). Those are different failure modes, and the difference only appears under load.
- Find the workload where it bites, and make the workload explicit. Name the real scenario (a long
  tool-heavy agent, 40k-token-per-call payloads, a many-document answer), say why it exercises the
  mechanism, and which founder situation it maps to. A reader must see exactly what was tested and
  why it is realistic, never a black-box "Claude wins."
- Surface the real-world edges, do not dismiss them. Reliability under a long context, finishing a
  long-horizon job, correctness under load, cost at scale: these are the edges a founder actually
  lives with, and a toy benchmark hides them. If the naive test shows parity, push the workload
  toward the real condition before concluding there is no edge.
- This is validation, not spin. Working through the mechanism vets the feature, you learn its limits,
  where it loses, and the exact condition for its win. Getting creative means finding the genuine
  real-world condition where the edge exists, never manufacturing a rigged one. The comparison stays
  best-to-best and the workload stays honest and stated.

## Compare features at subfeature depth
The comparison unit is the smallest meaningful mechanism that changes builder value. Do not compare
feature labels when the implementation details differ. Compare the exact subfeature, the exact knob,
and the exact output the developer receives.

- For every candidate, write the subfeature claim before writing the benchmark: what changes in the
  API call, what the model sees, what the client receives, and which tokens, latency, correctness, or
  reliability number should move.
- Compare the competitor's closest subfeature, not just the competitor's headline feature. If the
  competitor has the umbrella capability but lacks the specific mode, field, or lifecycle behavior,
  record the candidate as parity-gated and test it.
- Do not bury the subfeature in private notes. If it survives, the public artifact must explain the
  subfeature in public-reader language with public docs and a receipt, so a reader can understand the
  wedge without access to this workspace or any internal repo.
- Treat positive subfeature signal as a candidate, not an edge. A receipt like `make dynamic-web` can
  prove that Claude exercises a mechanism and the closest competitor docs lack the exact subfeature.
  It still does not ship until the receipt shows `promotable_edge: true`, as `make task-budget` did
  only after the tool-loop workload proved a founder-value win against the best competitor
  configuration.
- Resolve docs/SDK/runtime discrepancies at this same subfeature depth. A docs-new parameter that the
  latest SDK schema lacks, or that raw HTTP rejects, is not an edge yet. Record the latest SDK version,
  accepted tool tags, rejected variants, and beta-header attempts so the next run starts from evidence.

## Check subfeatures AND combinations of features and subfeatures
A single feature can read as parity while a COMBINATION of features (or subfeatures) is a real edge.
The search is three-dimensional, not one: the feature, the subfeature one layer down, and the
combination of two or more features or subfeatures stacked on one workload. Run all three before
calling parity.

- Enumerate combinations on purpose. For every workload, ask which Claude features compose and whether
  the stack compounds a value a founder prices: prompt caching plus the Batch API plus extended output,
  programmatic tool calling plus code execution plus dynamic web filtering, the memory tool plus context
  editing plus the 1M window, Citations plus PDF support plus tool-returned search results, the advisor
  tool plus the effort knob. The compounding is the candidate, even when each part alone is parity.
- Compare against the competitor's BEST achievable combination, not a single competitor feature. The
  honest question is whether OpenAI or Gemini can assemble an equivalent stack on the same workload, in
  the same request count, with the same guarantees. A Claude combination is an edge only when the
  competitor's best combination cannot match it on cost, speed, reliability, correctness, or glue code.
- Watch for combinations that CONFLICT, and record them. Some Claude features are mutually exclusive.
  Citations returns a 400 with structured outputs, search results is incompatible with structured
  outputs, and context editing clear_tool_uses is not fully compatible with advisor blocks. A conflict is
  a first-class finding: it bounds which stacks are real and stops a benchmark that cannot run.
- Attribute the win to the combination, not a part. Toggle the stack against the best single feature
  and against the competitor's best stack, so the receipt shows the combination is what moved the
  number, the same isolate-one-variable discipline applied to the stack as a unit.
- A combination still ships only at `promotable_edge: true`: the measured workload proved a
  founder-value win against the best competitor configuration, combination against combination.

## Put the workload, cost, and time on every outbound surface
The internal receipt is recorded above. What ships to a reader carries the same facts, up front, in
the reader's words, never buried:
- **The workload.** What ran: the task, the agent shape (how many steps, which tools), the exact
  model id on each side, the prompt complexity, the features turned on, and the assumptions a
  founder's own task would change.
- **The cost and the time.** The dollar cost and wall-clock time of the run, and the cost and time
  for the reader to reproduce it using their own API keys, stated before they commit, not discovered
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

## Name the founder use case and the Claude features on the email and the README
Every founder email and the README hero is written for one reader, a founder building a real product
over their users' own work (contracts, charts, tickets, research, support docs, a long-running agent).
Name that use case and the workload behind it before anything else, then name the Claude Developer
Platform and Claude Agent SDK features that serve it: Citations for the verifiable per-character
pointer into the user's own document, the memory tool and context editing for the long-horizon job,
prompt caching, the model tiers, and whichever verified differentiator the search surfaced this run.
Name the feature, then show what the founder gets from it on that workload, measured against the
competitor at its best. A feature name is not a value.

## Persist every synthesis to a committed file, never re-derive it from a transcript
A run that fans out (the audit, a review panel) writes its synthesis to a file: the structured
`engine/scan.py` and the committed `landscape/landscape.json`, plus the verified brief in `briefs/`
(written locally, the analytical both-directions briefs stay internal), never only a workflow transcript or
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

## The cadence runs on its own, and the gate is the boundary
This is a recurring engine, not a one-shot. On a cadence (a weekly cheap sweep, an optional monthly
deep run) it sweeps the live docs, diffs against the last run, ranks by value times genuine lead,
drafts a fresh email for the newest uncovered edge, and writes the brief, the changelog, and the
coverage ledger. That whole chain is measurement and drafting, so it runs unattended. The boundary is
fixed in code in [`engine/gate.py`](engine/gate.py) and `engine.gate.audit()` proves nothing crossed
it on a schedule.

The operator command for the loop is `make grind`. It runs the $0 cadence, prints coverage, then runs
the full offline CI gate. It does not spend credits and it does not run live proofs. When the loop
surfaces a candidate, run the named live target explicitly, promote only on a receipt with
`promotable_edge: true`, then run `make grind` again so the landscape, coverage ledger, and docs stay
current.

The loop has two tiers, matched to the gate. Tier 1 is `make grind`: the $0 fire-and-forget spine
(sweep, rank, draft to the inert outbox, coverage, offline gate), safe to run on a tight schedule
forever because nothing in it spends, sends, or pushes. Tier 2 is `make grind-deep`: tier 1 plus the
two creative judgment seats that DO spend, the Opus skeptic (`make verify`) and the combinatorial
generator (`make combine`, which proposes new feature stacks and skeptic-tests them against the
competitor's best counter-stack). Run tier 2 on a slower cadence under a spend cap. The split is the
gate: the cheap recurring discovery stays unattended, the paid reasoning is an explicit, budgeted pass.

To make it truly fire-and-forget, a scheduler invokes `make grind` (tier 1) often and `make grind-deep`
(tier 2) on a slower cadence. The scheduler is operator-side and is NOT committed here (a host cron
entry, a Claude Code routine, or a Managed Agents scheduled deployment that fires the cadence on a cron
and is itself a paid ASK-tier runtime). The repo's job is to expose one clean entrypoint per tier and to
make the gate hold no matter how often the scheduler fires, so an unattended run can never cross the
send, push, or spend boundary even if it is triggered every hour.

- **ALWAYS, unattended.** Fetch the docs, diff, rank, draft into the inert `state/outbox/`, write the
  brief and the CHANGELOG, update the coverage ledger. All reversible, all internal, nothing leaves
  the repo and nothing spends credits. The sweep is stdlib HTTP fetches, so the discovery loop needs
  no key and costs nothing.
- **ASK, waits for you.** Run a credit-spending benchmark (the PTC grid, compare, longhorizon,
  citations), scaffold or refresh an `edges/<key>/` bundle, raise the per-run spend cap. These change
  the repo or the bill, so they run only on an explicit token, never twice for the same edge without a
  fresh one.
- **NEVER on a schedule, by design.** Send mail in your name, post in public, push a remote, or spend
  past the cap. The boundary is the absence of the capability in the unattended path, not a flag that
  could be flipped. The outbox holds inert files and no send transport is wired into the cadence.

A blocked or failed doc fetch is recorded as status `unknown`, never as competitor-absence, so the
engine can never manufacture a false Claude lead. The losing and parity cells stay in the ranking.
The offline gate test in `tests/test_gate.py` asserts `audit()` flags any outward or non-always action
and runs in CI with no key and no network.

## The discovery loop is stdlib fetch, diff, rank, persist, for $0
`make edges` (`engine/sweep_edges.py`) is the cheap heart of the cadence. It fetches every URL in the
committed `engine/sources_registry.py` with a stdlib `urllib` conditional GET (ETag and Last-Modified,
no new dependency), writes a dated `sources/<vendor>_<key>_<date>.txt` in the same header format
`engine/cite_facts.py` consumes, normalizes each page to a best-effort capability record, diffs against
`landscape/landscape.json`, ranks by value times genuine lead, and persists the overwritten
`landscape/landscape.json` baseline as the one tracked durable artifact. The `landscape/CHANGELOG-<date>.md`
delta and the regenerated `briefs/<date>-edge-landscape.md` are written locally and gitignored, as
internal both-directions analysis that never ships on the public surface. No model call, no benchmark, no spend. The optional
Claude `--normalize` pass on changed pages only is deferred, so the default loop stays $0.
- The deterministic normalizer is best-effort, and it is honest about its limits. A maturity it cannot
  read off the feature line is recorded `unverified`, never asserted `ga` off page navigation, and an
  `unverified` maturity on either side is parity, never a manufactured behind. The raw snapshot is
  always kept so `cite_facts.py` grounds the real claim. An absence-of-evidence lead (`lead_score` 2)
  stands only when every relevant competitor source actually fetched. If one did not, the edge is held
  `never-evaluated`, not pitched.
- `engine/scan.py`'s constants are now the committed seed and fallback, not the live truth.
  `scan.current_edges()` reads `landscape/landscape.json` when present and falls back to the constants
  on a fresh checkout, and `verify.py` and `draft_email.py` read it so the skeptic pass and the
  drafter follow the live ranking. A built edge still carries its vetted, measured seed claim.

## Fan out only on a wide, independent search space
The engine is not a heavyweight parallel pipeline by default. The discovery loop above is a single
deterministic pass (stdlib fetch, diff, rank, persist, for $0), and the skeptic pass in
[`engine/verify.py`](engine/verify.py) is one model call over all candidates at once, not a fleet. A
fan-out (the whole-surface audit, a review panel, a multi-lane sweep) is earned by a wide,
independent search space, not taken by default. Managed Agents is a capability this engine measures
and may anchor an edge on, never the machinery that runs the engine, so do not confuse the feature
compared with the engine used.

Fan out when:
- The search space is wide and independent: many subfeatures or many competitor surfaces swept at
  once, each lane blind to the others.
- The run is a thorough audit where coverage matters more than cost.
- A finding can fail multiple ways and wants diverse skeptic lenses, not one.

Stay inline and sequential when:
- Grounding a single claim against the live docs. That is one fetch. Fanning out wastes tokens and
  adds nothing.
- Verifying one edge against its primary source. That is close, sequential reading, because the
  rigor comes from reading one source carefully, not skimming ten.
- The fan-out cost is not justified by a real win in coverage or confidence.

The rule of thumb: parallel processing is earned by a wide, independent search space, not taken by
default. "Find the global edge", "Ground every Claude and competitor claim", and "Compare features
at subfeature depth" above are about depth and grounding, and most of that work is inline and
sequential. The heavy machinery comes out only when the work genuinely decomposes into independent
lanes.

## State survives a clone, data does not
There are two state roots, and the split matters. `data/` is gitignored transient scratch (per-run
benchmark receipts, the last run's JSON), rewritten every run. `state/` and `landscape/` are committed
and durable. The diff baseline (`landscape/landscape.json`) and the coverage ledger
(`state/coverage.jsonl`) must survive a clone, or "diff against the last run" and "never repeat an edge
to the same reader" break on a fresh checkout. Anything that must persist across runs lives under
`state/` or `landscape/`, never under gitignored `data/`. See [`state/README.md`](state/README.md).

## One command, one dependency
The core runs with a single `make` target and nothing but `anthropic` installed. The OpenAI
comparison adds exactly one optional dependency (`openai`), declared in `requirements-compare.txt`.
The offline tests add `pytest`, a dev-only dependency the CI installs.

## Clean prose
No em-dashes or en-dashes, no semicolons in prose, no buzzwords. Say the thing plainly.

## Show the wins-only comparison, name competitors as dated evidence
The founder email and the brief README show the Claude vs OpenAI vs Gemini comparison when a real,
sourced, dated head-to-head receipt exists, because the comparison is what a founder prices. It is
dated evidence, never a swipe, and it stays wins-only: show only the axis where Claude leads, never a
Claude negative and never a tie stated as a concession. When the edge is a capability gap or a
within-Claude result with no head-to-head number, state the honest capability line and show no
competitor table, never a fabricated competitor number. The both-directions losses stay in the
private analysis and the product-team note, never on the founder surface.

## Keep it forkable
Cloned and edited by a stranger. No secrets in git (`.env` is ignored), no machine-specific
paths, no references to anything outside this repo. Assume a public reader has only this repo, the
generated public brief, and public URLs. They do not have this private parent workspace, private
receipts, private plans, or any internal repository. Any instruction, claim, source, or reproduction
path needed to understand the edge must ship inside the public repo or link to a public source.

## The public surface shows only wins, the internal analysis stays honest both ways

The both-directions honesty in this file (surface where Claude ties or loses, write the product-team alert) governs the internal analysis and the reviewer, not the founder-facing surface. Public assets, meaning the founder emails, the briefs, and the landing README a founder clones, show only verified Claude wins and never expose a Claude negative. No "Claude got it wrong" baseline, no "where Claude loses on price or speed". Reframe any benefit that has an unflattering flip side as the positive, so programmatic tool calling gives exact totals because the math runs in code, never "the model got it wrong without it". The losing and parity cells stay in the internal brief and the product alert, never in the founder's inbox.

Speak the founder's language on every founder-facing word. Explain every term a founder would not parse on a glance (fan out, tool use, rollups, allowed_callers, rows to code). Lead with the value a founder prices, which is cost, speed, reliability, and accuracy. Write cost as a concrete dollar figure like $0.06. Label every table column in plain terms with the key number where a quick scan expects it, and keep it warm. The founder emails are saved as .md, here in the engine repo under emails/, and are never committed to the public hits repo.

## Founder email and brief checklist (every email, every brief, the README CTA landing)

A founder-facing piece is not done until it passes this, read cold as a busy YC founder with five seconds to spare:
- Open warm and personal to the reader, who is a YC founder. A quick genuine congrats, then get to the point, adapted to the specific feature.
- State the PROBLEM first in the founder's own terms (what it costs them in dollars, latency, or maintenance), then present the feature as the SOLUTION.
- Show the real, minimal CODE that makes the difference, in Python, with the one or two changed lines marked. Code-forward beats prose.
- Include the current official documentation link, fetched and verified live per the grounding rule, the latest URL.
- Label every table column in the reader's terms (with the feature versus without it, the abbreviation defined on first use), and make every cell say what it means.
- Abbreviate the value plainly. Write "28% cheaper", not "6,828 which is 28% lower".
- Never imply a Claude negative, even softly. A line like "your totals come out exact every time" implies they might not today, which is a Claude negative, so cut it.
- Voice: warm, concise, scannable, casual and punchy, a friend and fellow builder, never sleazy sales or marketing.
- One reproduce path, one or two commands, about a minute, the cost as a dollar figure like $0.06.
- Deslop-clean, and run the gate before it ships.
- Crisp over chatty. Cut every word that does not earn its place. Warm and casual is good, but never at the expense of clean grammar or smooth reading. Read it aloud, and if a line is awkward, fix it.
- Make the run-it-on-your-own-data path explicit: name the one file to edit and the one command to re-run, never a vague "swap in your tool".
- Sign reusable engine-generated drafts neutrally as the sender, a name placeholder and "Building
  with Claude". The exception is the curated take-home email packet, where the assignment explicitly
  asks for the Applied AI, Startups role at Anthropic. Keep that role language only in the submission
  emails and Google Doc, not in public repos or generic engine templates. A warm sign-off may carry
  one emoji.
- Do not editorialize about a feature's maturity. Mention beta or a required beta header only when the founder must act on it (they have to set the header). For a GA feature, never write "it is GA" or "no beta header", it is noise. Get to the value.
- The subject line must clear spam filters: no money-and-urgency trigger words (cut, save, free, cheap, discount, guarantee, a dollar sign). Keep the subject warm, personal, and specific to the feature, a genuine note to the reader, for example "Congrats on YC! A cool Claude feature to help you build".
- Write in the first person as a builder sharing your own run ("I measured", "using my API key").
  Generic engine drafts never claim to speak for Anthropic. The submission email packet may use the
  Applied AI, Startups role because the prompt explicitly asks for it. Open with a plain, concrete line
  (a "quick tip"), never a vague filler like "quick one".
- The reader is a startup founder (a YC batch), so use a startup-native example (plan limits, usage metering, churn, signups, logs, MRR, cohorts), never a generic enterprise scenario like employee expenses. Carry one example all the way through: the problem, the code, the table, and the tool name all use the same scenario.
- Every word fights for its place. Cut anything that does not earn its spot, the same every-word-earns-its-place standard. If a word or a line can come out without losing meaning or punch, it comes out.
