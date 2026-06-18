# Build on Claude when your product has to show its work, with a citation that points to the exact sentence and actually resolves.

A live competitive engine. It sweeps the whole Claude Developer Platform, runs fair best-to-best
benchmarks against OpenAI and Google Gemini, and reports honestly, including where Claude loses on
cost and speed. The edge it surfaces this month, measured not asserted: **Citations**, a
guaranteed-valid pointer into your user's own document, against the workaround the other platforms
force you into. It re-checks every claim against the live docs each run, because the platforms ship
monthly and a hard-coded claim rots in weeks.

![Citations demo: Claude resolves 8 of 8 source pointers, the prompt-for-quotes workaround resolves 0 of 8 on OpenAI, Gemini resolves 7 of 8 but at 148x the output tokens](docs/demo.gif)

*The committed receipt from a real `make citations` run. The grader is mechanical: does each returned
offset land on the exact source text. You run the same thing on your own keys.*

**What you get, measured.** A product that cites your user's own documents with a pointer that
resolves, every time. Claude's Citations feature (GA, no beta header) returns each claim with a
char or page pointer plus the verbatim quote, extracted by the API so it is guaranteed to resolve,
and the quote is free of output tokens. The workaround you would build without it (prompt the model
for a quote and offsets) is the only option on OpenAI and Google. Here is what that costs you:

```bash
git clone <this-repo> && cd claude-competitive-engine
make setup && make compare-deps   # core deps, then the OpenAI + Gemini SDKs, all into the same venv
cp .env.example .env              # paste your Anthropic, OpenAI, and Gemini keys (the file says where)
make citations                    # the verifiable-pointer benchmark on your own keys, about thirty cents
```

## The measured proof (we do not assert)

The same 8 questions over a set of your own documents, four ways. The grader checks one thing per
citation: does `source[start:end]` equal the quoted text. A pointer that resolves is one a user can
click and trust. A pointer that does not is a hallucinated citation.

| approach | pointer resolves | quotes verbatim | output tokens | cost |
|---|:--:|:--:|--:|--:|
| **Claude Haiku 4.5 + Citations** | **8/8** (guaranteed) | 8/8 | 308 | $0.011 |
| Claude Haiku 4.5, prompt-for-quotes | 0/8 | 8/8 | 715 | $0.007 |
| OpenAI gpt-5.4-mini, prompt-for-quotes | 0/8 | 8/8 | 448 | $0.005 |
| Gemini gemini-3.5-flash, prompt-for-quotes | 7/8 | 8/8 | 45,630 | $0.416 |

**The honest read.** The quoted text is correct everywhere (8/8 verbatim), so the differentiator is
the pointer. The prompt-for-quotes workaround returns offsets that point nowhere: 0/8 on OpenAI, and
0/8 even on Claude without the feature, so you cannot link to or verify them. Gemini can resolve 7/8,
but only by burning 45,630 output tokens against Claude's 308 (about 148x) and $0.42 against $0.011
(about 37x), because it brute-forces the character count with reasoning. Among the approaches that
actually resolve a pointer, Claude's Citations is the only one at 8/8 and by far the cheapest.
**Citations is not the cheapest arm in raw dollars** (it adds input tokens for chunking), so we never
claim "cheaper," only that the quotes are free of output tokens and that it is the only resolving
approach you would actually ship. Full receipt in [`sample_citations.txt`](sample_citations.txt).

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
reconciliation is in [`briefs/2026-06-17-agentic-landscape.md`](briefs/2026-06-17-agentic-landscape.md),
and `make longhorizon` is the runnable Claude-side proof (a long agent that finishes when its context
is bounded and fails when it is not).

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
make citations   # THE ANCHOR: the verifiable-pointer benchmark, all three vendors
make compare     # the fair cost/speed/correctness benchmark (the credibility layer)
make longhorizon # the runnable long-horizon proof
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
