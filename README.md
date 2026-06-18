# Build your agent on Claude. Not because it is cheaper. Because of the part the others do not ship.

A live competitive engine and a fair benchmark. It runs the same agent on Claude and OpenAI (and
Gemini) at full strength, reports who actually wins on cost, speed, and correctness (often not
Claude), and then shows the one agent primitive Claude ships that the others do not. It re-checks
the claim against the live docs every run, because the platforms ship monthly and a hard-coded claim
rots in weeks.

![The fair three-way benchmark: OpenAI cheapest but wrong, Gemini correct but priciest, Claude correct and carrying the least context](docs/demo.gif)

*The committed receipt from a real `make compare` run. Carried context counts cached tokens on every
side, apples to apples. You run the same thing on your own keys.*

**What you get, measured.** A long agent that stays bounded, with no eviction code to write. On the
same 32-step tool-using agent at a 20k trim threshold, context editing drops Claude's carried context
(cached tokens included) from about 35,000 tokens to about 15,000. It clears stale tool results in
place, the one primitive only Claude ships. OpenAI's compaction summarizes them instead, and Gemini's
in-place trim is realtime-API only, so it carries about 33,000. It is not a free win: editing on ran
slower and cost a few percent more than off (clearing invalidates the cache), so you are buying
bounded context, not a cheaper bill. The fair benchmark is below, and you run it yourself.

```bash
git clone <this-repo> && cd claude-competitive-engine
make setup && make compare-deps   # core deps, then the OpenAI + Gemini SDKs, all into the same venv
cp .env.example .env              # paste your Anthropic, OpenAI, and Gemini keys (the file says where)
make compare                      # the fair three-way fight on your own keys, about a dollar
```

Built on the Claude API and the Agent SDK.

## The fair benchmark (we do not cheat)

The same 32-step tool-using agent, all three at full strength: OpenAI on the Responses API with
compaction and caching, Gemini with implicit caching, Claude with context editing, memory, and
caching. Carried context counts cached tokens on every side, apples to apples:

| platform | cost | correct | carried context |
|---|--:|:--:|--:|
| OpenAI gpt-5.4-mini | **$0.033** | no (8 vs 11) | 19,331 |
| Gemini gemini-3.5-flash | $0.414 | yes (11) | 32,638 |
| Claude Haiku 4.5 (context editing on) | $0.131 | yes (11) | **15,397** |
| Claude Haiku 4.5 (off) | $0.121 | yes (11) | 34,597 |

**The honest read.** OpenAI's cheap model is the cheapest but got the count wrong here (a cheap-tier
model-quality miss, its stronger model answers correctly). Gemini is correct but the priciest. Claude
is correct and mid-cost, and it carries the least context, because context editing takes it from
34,597 down to 15,397. **Claude is not the cheapest, and we say so.** Full receipt in
[`sample_compare.txt`](sample_compare.txt), the variant sweep in [`sample_sweep.txt`](sample_sweep.txt),
and every confound we caught to keep this apples-to-apples (a prompt ambiguity, caching versus context
editing, compaction losing the thread, the model-tier check, and the context-token metric itself) is
in [`docs/FINDINGS.md`](docs/FINDINGS.md).

## So why build on Claude: context editing

The reason is the agent primitives the others do not ship, verified by a hard skeptic pass. The
sharpest one for tool-heavy agents is **context editing**: it clears stale tool results out of the
context server-side, **in place**, replaced with a placeholder, with one beta header.

- OpenAI's tool-output trimmer is **client-side** (you wire it into your own process).
- OpenAI's server-side compaction **summarizes** (and loses detail).
- Gemini's in-place version is **realtime-API only**.

Claude is the only one shipping in-place clearing as a managed API feature on the standard tool-use
path. `make demo` shows it dropping a long agent's carried context from about 35k tokens to about
15k. Like any aggressive trim it can occasionally cost a count, which is why the repo measures
instead of asserting.

Honest scope: context editing **bounds context**, it is not a raw dollar win when caching is on,
because clearing rewrites the cached prefix (see `docs/FINDINGS.md`). The win is a bounded context
and no eviction logic to build, not a cheaper bill. The other verified Claude-ahead primitives
(self-hosted sandboxes, the model-driven memory tool) are in
[`briefs/2026-06-17-verified-picture.md`](briefs/2026-06-17-verified-picture.md).

## Run it

```bash
git clone <this-repo> && cd claude-competitive-engine
make setup            # venv + anthropic
make compare-deps     # openai + google-genai, into the SAME venv (for the comparison)
cp .env.example .env  # paste the three keys (the file says where each goes)
make compare          # the fair head-to-head on your keys, about a dollar
make demo             # context editing holding the context flat
```

## This is an engine, not a one-off

```
make scan      # the candidate gaps
make verify    # a skeptic pass that refutes the overstated ones
make compare   # the fair best-to-best benchmark
make draft     # the founder email, from the verified anchor
make alert     # the product-team email, when a competitor is ahead
```

Re-run it any week. It is packaged as a skill ([`SKILL.md`](SKILL.md)) so a founder can run the same
analysis themselves, which is the point: do not trust the pitch, reproduce it.

## Where Claude loses (the honest other direction)

Raw price, prompt-cache retention (Gemini arbitrary TTL, OpenAI 24h, vs Claude 5m/1h), the MCP
tunnel (OpenAI GA, Claude beta), and long-context billing. The full product-team note is
[`PRODUCT_EMAIL.md`](PRODUCT_EMAIL.md). Honesty runs both ways.

## Every number is a receipt

Prices live once in [`common/models.py`](common/models.py), verified in
[`docs/VERIFIED_FACTS.md`](docs/VERIFIED_FACTS.md). Costs come from the API `usage` object. Claude
features (context editing, memory) are beta, labeled as beta. Competitor claims trace to the
competitor's own docs, dated, in the brief. Nothing is quoted from memory.

## Layout

```
engine/demo.py        the Claude arm: a long chain agent, context editing + memory + caching
engine/openai_arm.py  the OpenAI arm: Responses API, compaction + caching
engine/gemini_arm.py  the Gemini arm: implicit caching (optional, free-tier rate-limited)
engine/compare.py     the three-way fair benchmark, outcomes a founder pays for
engine/sweep.py       the variant sweep that makes the result trustworthy
engine/scan.py / verify.py / draft_email.py / product_alert.py   the gap engine and the two emails
common/               the verified model + price registry and the cost math
briefs/               the dated, sourced competitive picture
docs/                 VERIFIED_FACTS.md and FINDINGS.md
```

MIT licensed. Re-run it any week. The gap moves, and so does this.
