# Build your agent on Claude. Not because it is cheaper. Because of the part the others do not ship.

A live competitive engine and a fair benchmark. It runs the same agent on Claude and OpenAI (and
Gemini) at full strength, reports who actually wins on cost, speed, and correctness (often not
Claude), and then shows the one agent primitive Claude ships that the others do not. It re-checks
the claim against the live docs every run, because the platforms ship monthly and a hard-coded claim
rots in weeks.

Built on the Claude API and the Agent SDK. Run it on your own keys.

## The fair benchmark (we do not cheat)

The same 32-step tool-using agent, both platforms at full strength (OpenAI on the Responses API with
compaction and caching, Claude with context editing, memory, and caching):

| platform | cost | correct | peak context |
|---|--:|:--:|--:|
| OpenAI gpt-5.4-mini | **$0.046** | no (9 vs 11) | 19,331 |
| Claude Haiku 4.5 (best) | $0.153 | yes (11) | **3,035** |
| Claude Haiku 4.5 (baseline) | $0.123 | yes (11) | 3,989 |

**OpenAI is cheaper.** We say so here and in the founder email, because a founder can check, and
because saying it is what makes everything else believable. The cheap-tier correctness gap is not a
Claude advantage either: it is a model-quality artifact, and OpenAI's stronger model answers
correctly. Full receipt in [`sample_compare.txt`](sample_compare.txt), variant sweep in
[`sample_sweep.txt`](sample_sweep.txt), and every confound we had to fix to make the fight fair (a
prompt ambiguity, caching versus context editing, compaction losing the thread, the model-tier
check) is in [`docs/FINDINGS.md`](docs/FINDINGS.md).

## So why build on Claude: context editing

The reason is the agent primitives the others do not ship, verified by a hard skeptic pass. The
sharpest one for tool-heavy agents is **context editing**: it clears stale tool results out of the
context server-side, **in place**, replaced with a placeholder, with one beta header.

- OpenAI's tool-output trimmer is **client-side** (you wire it into your own process).
- OpenAI's server-side compaction **summarizes** (and loses detail).
- Gemini's in-place version is **realtime-API only**.

Claude is the only one shipping in-place clearing as a managed API feature on the standard tool-use
path. `make demo` shows it holding a long agent's context flat (peak around 3k tokens instead of
36k) while the agent stays correct.

Honest scope: context editing **bounds context**, it is not a raw dollar win when caching is on,
because clearing rewrites the cached prefix (see `docs/FINDINGS.md`). The win is a bounded context
and no eviction logic to build, not a cheaper bill. The other verified Claude-ahead primitives
(self-hosted sandboxes, the model-driven memory tool) are in
[`briefs/2026-06-17-verified-picture.md`](briefs/2026-06-17-verified-picture.md).

## Run it

```bash
git clone <this-repo> && cd claude-competitive-engine
make setup                              # venv + anthropic
pip install -r requirements-compare.txt # openai + google-genai, for the comparison
cp .env.example .env                    # paste the three keys (the file says where each goes)
make compare                            # the fair head-to-head on your keys, about a dollar
make demo                               # context editing holding the context flat
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
