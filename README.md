# Build on Claude when your product has to show its work, with a citation that points to the exact sentence and actually resolves.

A live competitive engine. It sweeps the whole Claude Developer Platform, runs fair best-to-best
benchmarks against OpenAI and Google Gemini, and reports honestly, including where Claude loses on
cost and speed. The edge it surfaces this month, measured not asserted: **Citations**, a
guaranteed-valid pointer into your user's own document, against the workaround the other platforms
force you into. It re-checks every claim against the live docs each run, because the platforms ship
monthly and a hard-coded claim rots in weeks.

![Citations demo: every approach resolves 8 of 8 on clean text, but only Claude resolves the pointer in the API, guaranteed and free of output tokens, with no resolver code to write](docs/demo.gif)

*The committed receipt from a real `make citations` run. You run the same thing on your own keys.*

**What you get, measured.** A verifiable citation into your user's own document that the API
guarantees, with zero resolver code and the quote free of output tokens. Claude's Citations feature
(GA, no beta header) returns each claim with a char or page pointer plus the verbatim quote,
extracted by the API so it cannot point at the wrong text. No competitor ships a document-pointer
primitive, so without it you build the resolver yourself. Here is the honest comparison:

```bash
git clone <this-repo> && cd claude-competitive-engine
make setup && make compare-deps   # core deps, then the OpenAI + Gemini SDKs, all into the same venv
cp .env.example .env              # paste your Anthropic, OpenAI, and Gemini keys (the file says where)
make citations                    # the verifiable-pointer benchmark on your own keys, about six cents
```

## The measured proof (honest, including the part that is not flattering)

The same 8 questions over a set of your own documents. The realistic DIY path without the feature is
to ask the model for the verbatim quote and resolve it yourself with `source.find(quote)`, not to ask
the model for a character offset (a tokenizer cannot count characters, and an earlier version of this
benchmark that did was a strawman a scrutiny panel caught). The grader checks that each citation
resolves to the real source text.

| approach | resolves | who resolves it | quote free of output tokens | output tokens | cost |
|---|:--:|:--:|:--:|--:|--:|
| **Claude Haiku 4.5 + Citations** | **8/8** (guaranteed) | the API | yes | 308 | $0.011 |
| Claude Haiku 4.5, DIY str.find | 8/8 | your code | no | 586 | $0.006 |
| OpenAI gpt-5.4-mini, DIY str.find | 8/8 | your code | no | 391 | $0.004 |
| Gemini gemini-3.5-flash, DIY str.find | 8/8 | your code | no | 3,466 | $0.036 |

**The honest read.** On clean text the DIY bolt-on resolves just as well (8/8), because the model
quotes verbatim and `find` locates it. So the edge is not "the others cannot cite." The edge is
narrower and real: Claude resolves the pointer in the API, guaranteed by construction (the DIY `find`
returns nothing the moment the model paraphrases, which it will on a messy real PDF), the quote is
free of output tokens (308 versus 586), and you write zero resolver code. **Citations is not the
cheapest arm in raw dollars** (it adds input tokens for chunking, so it cost more than the OpenAI DIY
path here), so we never claim "cheaper." The win is the guarantee, the zero code, and the fact that
no competitor ships the primitive at all. Full receipt in
[`sample_citations.txt`](sample_citations.txt).

## Why it is a real edge, not a rigged demo

No competitor exposes a pointer into a user-supplied document. OpenAI's citations annotate web-search
URLs, and Gemini returns web grounding metadata. Neither gives you a char or page range into the
document you uploaded. Verified against the live docs on 2026-06-17
([Anthropic citations doc](https://platform.claude.com/docs/en/build-with-claude/citations)). The
docs say it plainly: `cited_text` "does not count towards output tokens" and citations "are
guaranteed to contain valid pointers to the provided documents." For a contract-review,
clinical-summary, financial-research, or support-over-docs product, the click-through to the exact
sentence is the trust layer, and it is the whole product. One caveat we carry, not hide: Citations
cannot be combined with Structured Outputs on the same document (the API returns a 400). The full
sourced audit is in [`briefs/2026-06-17-platform-edge.md`](briefs/2026-06-17-platform-edge.md).

## Second pillar: the longest autonomous jobs

If you build long-running agents, there is a second, independent reason. On METR's task time-horizon,
the neutral referee rather than a vendor chart, the top released Claude model runs the longest
autonomous jobs of any model, about 1.9x the next best before reliability drops to half (Claude about
12 hours, Gemini 3.1 Pro about 6.4, GPT-5.2 about 5.9). Claude does not lead the headline coding
boards, so this is the one place "finishes long jobs" survives a skeptic on neutral data. The sourced
reconciliation is in [`briefs/2026-06-17-agentic-landscape.md`](briefs/2026-06-17-agentic-landscape.md).
Be honest about scale: `make longhorizon-compare` runs the same heavy task across all three vendors,
and at 8 reports of 40k tokens every one finishes correctly (a tie, Claude just carries the least
context). The METR gap opens only at much longer horizons than a cheap demo reaches, which is exactly
why the independent referee, not our own short run, is the evidence. `make longhorizon` is the
runnable Claude-side view of the bounding mechanism.

## The credibility layer: Claude is not the cheapest, and we prove it

The anchor is not cost or speed, because a fair benchmark showed Claude does not win them. The same
32-step tool agent, all three at full strength, OpenAI on the Responses API with compaction and
caching, Gemini with implicit caching, Claude with context editing and memory and caching:

| platform | cost | time | correct |
|---|--:|--:|:--:|
| OpenAI gpt-5.4-mini | **$0.046** | **42.5s** | no (9 vs 11) |
| Gemini gemini-3.5-flash | $0.374 | 42.6s | yes (11) |
| Claude Haiku 4.5 (context editing on) | $0.124 | 58.4s | no (10 vs 11) |
| Claude Haiku 4.5 (off) | $0.120 | 50.1s | yes (11) |

OpenAI is cheapest and fastest. On this noisy counting task both OpenAI and Claude-with-editing
miscounted, while Gemini and plain Claude got it right. We report it exactly as it ran, which is the
point: this is the credibility layer, not the pitch. Claude is not the cheapest or the fastest, so we
anchor on what it genuinely leads. Full receipt in [`sample_compare.txt`](sample_compare.txt), the
variant sweep in [`sample_sweep.txt`](sample_sweep.txt), and the confounds we caught to keep it
apples-to-apples in [`docs/FINDINGS.md`](docs/FINDINGS.md).

## This is an engine, not a one-off

```
make scan        # the ranked, verified gaps from the live-docs sweep
make verify      # a skeptic pass that refutes the overstated ones
make citations         # THE ANCHOR: the verifiable-pointer benchmark, all three vendors
make compare           # the fair cost/speed/correctness benchmark (the credibility layer)
make longhorizon       # the Claude-side bounding mechanism
make longhorizon-compare # the cross-vendor long task (a tie at affordable scale, honestly)
make draft       # the founder email, from the verified anchor
make alert       # the product-team email, when a competitor is ahead
```

Re-run it any week. It is packaged as a skill ([`SKILL.md`](SKILL.md)) so a founder can run the same
analysis themselves, which is the point: do not trust the pitch, reproduce it. The edge moves monthly,
so the engine searches the whole platform surface every time rather than caching a winner.

## Where Claude loses (the honest other direction)

Raw price and speed, the coding-agent leaderboards (GPT-5.5 leads Terminal-Bench and BrowseComp),
cache retention (Gemini arbitrary TTL, OpenAI 24h, vs Claude 5m/1h), and the Structured-Outputs
incompatibility with Citations. The full product-team note is
[`PRODUCT_EMAIL.md`](PRODUCT_EMAIL.md). Honesty runs both ways.

## Every number is a receipt

Prices live once in [`common/models.py`](common/models.py), verified in
[`docs/VERIFIED_FACTS.md`](docs/VERIFIED_FACTS.md). Costs come from the API `usage` object. Beta
features are labeled beta. Competitor claims trace to the competitor's own docs, dated, in the briefs.
Nothing is quoted from memory.

## Layout

```
engine/citations.py   THE ANCHOR: verifiable source pointers vs prompt-for-quotes, all three vendors
engine/compare.py     the fair cost/speed/correctness benchmark (the credibility layer)
engine/sweep.py       the variant sweep that makes the compare result trustworthy
engine/longhorizon.py the runnable long-horizon proof
engine/openai_arm.py  the OpenAI arm: Responses API, compaction + caching
engine/gemini_arm.py  the Gemini arm: implicit caching
engine/scan.py / verify.py / draft_email.py / product_alert.py   the gap engine and the two emails
common/               the verified model + price registry and the cost math
briefs/               the dated, sourced competitive picture
docs/                 VERIFIED_FACTS.md and FINDINGS.md
```

MIT licensed. Re-run it any week. The edge moves, and so does this.
