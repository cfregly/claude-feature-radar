# Your agent gets more expensive the longer it runs. On Claude it does not have to.

A runnable proof of one current gap between Claude and the other two big model platforms, picked
and re-checked against the live docs by the small engine in this repo. The gap right now: a
long-running agent on Claude can hold its per-turn cost roughly flat, where on the others it
climbs with every step. You see it on your own key in about two minutes.

This is not a slide. `make demo` runs a real agent twice and prints the cost of each, measured
from the token usage the API returns.

## See it

The same task on the same model, one step at a time, the way a real long-horizon agent works:
read a document, reason, read the next one. The only difference is whether the managed Claude
features are turned on.

```
input tokens per turn, 32-document audit, Claude Haiku 4.5

 turn   baseline   managed
    0        450     1,590
    4      4,807     4,015
    8      9,150     4,432
   12     13,492     4,911
   16     17,835     5,337
   20     22,178     5,696
   24     26,520     6,122
   28     30,863     6,553
   32     35,206     6,987      baseline is still climbing, managed is bounded
```

`baseline` re-sends the whole growing transcript every turn. `managed` clears stale tool results
and keeps what it needs in memory, so the context stays small. Both agents returned the same
correct answer.

| | baseline | managed | |
|---|--:|--:|---|
| total cost (same task) | $0.59863 | $0.28742 | **2.08x cheaper** |
| peak input tokens / turn | 35,206 | 8,505 | **76% smaller** |
| final answer | 11 | 11 | both correct (true count 11) |

Numbers from one real run, captured in [`sample_output.txt`](sample_output.txt). Re-running shifts
them by a fraction of a cent. That is the point of measuring instead of asserting.

And it is a floor, not a ceiling. `baseline` grows linearly with the agent's length and `managed`
stays bounded, so the longer the agent runs, the wider the gap.

## Run it

```bash
git clone <this-repo> && cd claude-competitive-engine
make setup                 # venv + one dependency (anthropic)
cp .env.example .env        # paste your key from console.anthropic.com
make demo                   # the 32-document run above, about $0.90 and ~2 minutes
```

`make demo-quick` is a 10-document version for about $0.10 if you just want to watch the curve
bend. Every dollar figure it prints comes from the API `usage` object, priced by the verified
table in [`common/models.py`](common/models.py).

## The problem it solves

An agent that runs for more than a few steps accumulates tool results in its context. Every turn,
the whole transcript is re-sent and re-billed as input. A 40-step agent pays for its early steps
forty times. This is the quiet tax on every long-running agent, and it grows with exactly the
thing you want more of: how much work the agent does on its own.

Your options on the other platforms:

- **Competitor A** added server-side compaction, which summarizes the old turns. That shrinks the
  bill, but a summary is lossy, and it has no built-in memory the model itself writes to.
- **Competitor B** offers a managed memory service, but you trigger it yourself, and it has no
  managed server-side context trimming at all. You hand-roll the trimming.

## What Claude does

Two request-level features, no extra infrastructure:

- **Context editing** clears the oldest tool results out of the context server-side, in place,
  and tells the model it happened. It clears, it does not summarize, so nothing is silently
  rewritten. ([docs](https://platform.claude.com/docs/en/build-with-claude/context-editing))
- **The memory tool** lets the model itself write durable notes to a file store and read them
  back, so the facts it needs survive the clearing.
  ([docs](https://platform.claude.com/docs/en/agents-and-tools/tool-use/memory-tool))

The pair is the point. Editing keeps the context cheap. Memory keeps the agent correct. In the
run above the managed agent did *more* work than the baseline (it wrote to memory along the way)
and still cost less than half, because each turn's context was bounded.

## Why this is the gap, and not the obvious ones

The engine in this repo checked the easy claims first and threw them out, because a founder who
has used all three platforms would throw them out too:

- "Only Claude has a managed agent runtime." False. Both others ship one.
- "Only Claude has agent memory." False. One competitor has had a managed memory service since
  late 2025.
- "Only Claude does server-side context management." False. One competitor shipped server-side
  compaction in early 2026.

What survives is narrow and specific, which is why it holds up: Claude is the only one of the
three that exposes **memory as a tool the model itself drives** *and* pairs it with **selective
server-side context editing that clears stale tool results rather than summarizing them**. That
exact pair is what keeps a long agent both cheap and correct. The dated, sourced version of this
comparison, with links to each competitor's own docs, is in
[`briefs/2026-06-17-context-editing-and-memory.md`](briefs/2026-06-17-context-editing-and-memory.md).

## This is one output of an engine

The gap above was not hand-picked. It was selected by re-reading Claude's and the competitors'
live docs, scoring the candidate gaps, and keeping only the one that survives a skeptic. The
platforms ship every month, so a hard-coded "Claude has X, they do not" rots fast. The engine
re-runs and re-verifies, and when a competitor closes a gap it says so and moves to the next one.

- [`engine/demo.py`](engine/demo.py) is the runnable proof for the current gap.
- [`engine/scan.py`](engine/scan.py) gathers the candidate gaps and grounds each side in its own docs.
- [`engine/verify.py`](engine/verify.py) is the skeptic pass that kills the overstated framings.
- [`engine/draft_email.py`](engine/draft_email.py) turns the surviving gap into a founder email.

## Every number is a receipt

- Prices live once in [`common/models.py`](common/models.py), verified 2026-06-17 against the live
  pricing page and cited in [`docs/VERIFIED_FACTS.md`](docs/VERIFIED_FACTS.md).
- Costs come from the `usage` object the API returns, priced by [`common/pricing.py`](common/pricing.py).
- Context editing and the memory tool are in beta. The beta header and exact parameter shapes are
  recorded in [`docs/VERIFIED_FACTS.md`](docs/VERIFIED_FACTS.md), checked against a live call.

## Layout

```
engine/demo.py        the runnable proof: a long agent, with and without the managed features
engine/memory_backend.py  the client side of the memory tool, sandboxed file ops
engine/scan.py        gather candidate gaps, ground each side in its own live docs
engine/verify.py      the skeptic pass: keep only the gap that survives
engine/draft_email.py compose the founder email from the surviving gap
common/               the shared client, the verified model and price registry, the cost math
briefs/               one dated, sourced brief per run: the gap and the evidence
docs/VERIFIED_FACTS.md  the cited source of truth for prices and the beta parameters
sample_output.txt     a captured real run
```

MIT licensed. Fork it, point it at your own agent, and watch your own cost curve.
