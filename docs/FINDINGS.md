# Findings: the knobs, the confounds, and why we sweep before we trust

A fair cross-platform agent benchmark has many knobs, and several of them quietly decide the
result. These are the ones we found the hard way. Every one would have produced a false claim if we
had trusted a single run. The meta-lesson under all of them: apples to apples, or the number does not
ship. A number is not comparable until you have checked what it actually counts, and at what price,
on every side.

## 1. Prompt ambiguity (the "Answer: K" confound)

The task asked the agent to "reply with exactly `Answer: K`", meaning K as a placeholder for the
count. gpt-5.4-mini sometimes echoed the literal `K`, while Claude substituted the number, so the
correctness column read "Claude right, OpenAI wrong" for a reason that had nothing to do with the
platforms. Fix: an unambiguous format, "reply with `Answer: N`, replace N with the integer count,
for example `Answer: 7`". After the fix, all platforms returned the number. Lesson: a benchmark
prompt must be unambiguous, or it measures prompt-following, not the thing you think it measures.

## 2. Caching and context editing fight (the cost confound)

On Claude, prompt caching reads the stable prefix cheaply, but context editing clears stale tool
results in place, which rewrites that prefix and invalidates the cache. Measured on a 32-step chain:
the baseline with caching pulled hundreds of thousands of cache-read tokens, while the managed run
(context editing on) pulled far fewer, because clearing kept breaking the cache. So context editing
is NOT a cost win when caching is on. It is a context-size and context-limit tool. Lesson: a feature
that helps one metric (carried tokens) can hurt another (dollars), and you only see it by toggling
caching on AND off.

## 3. Compaction can lose the thread (the correctness confound)

OpenAI's server-side compaction summarizes older turns. On a sequential chain task that can
summarize away the state the agent needs to continue (the next pointer, the running count), so the
agent stops early or miscounts. But its other best config, no compaction with caching only, carries
the full context cheaply. Lesson: "use the competitor's best feature" is not one config, it is a
few, and you have to try each to find the competitor's real best.

## 4. Cross-vendor numbers are not directly comparable

Different tokenizers, different model tiers, different pricing. Compare the shape and the outcomes
(cost, time, correctness), name the model tier, and let a founder swap in their own task.

## 5. The correctness edge was a model-tier artifact

On a 32-step chain, Claude Haiku 4.5 returned the right count while OpenAI gpt-5.4-mini undercounted
(8 and 10 vs 11). It was tempting to call that "Claude is more reliable." It is not. OpenAI's
stronger model, gpt-5.4, returned the correct 11 on the same task. So the gap was Haiku 4.5 beating
gpt-5.4-mini at the cheap tier, not a platform property, and it disappears one tier up. Lesson:
before any correctness claim, run the competitor's stronger model too. A cheap-tier win is a
model-tier win, not a platform win.

## 6. The context-token metric was apples-to-oranges (the one that nearly shipped)

To compare carried context across vendors, we summed the wrong field. Claude's `input_tokens`
EXCLUDES cached tokens (cache_read is reported separately), while OpenAI's `input_tokens` and
Gemini's `prompt_token_count` INCLUDE them. So the peak-context column compared Claude's fresh tokens
(about 3k) against the others' full context (19k, 33k), and we nearly shipped "Claude carries 6x less
context." The true carried context is input plus cache_read on Claude, the total field on the others.
Corrected: Claude with context editing carries about 15k, OpenAI 19k, Gemini 33k, and Claude without
context editing 35k. Lesson: a token count is not comparable until you know exactly what it counts on
each side. Apples to apples, or the number does not ship.

## 7. Prices are verified, never assumed

A placeholder price for gemini-3.5-flash (input $0.30) made it look cheaper than Claude. The live
paid-tier price is $1.50 input and $9.00 output, so Gemini is actually pricier. Lesson: pull every
per-token price from the vendor's live pricing page and date it, before any dollar figure ships.

## 8. Citations: the edge is the guarantee and the no-store bundle, not char granularity

The skeptic refuted the citations edge as first stated: on clean text a model-emitted quote plus your
own `str.find` resolves 8 of 8 at char granularity on every vendor, so "the only API with a per-char
source pointer" overclaims. A live-docs dig (2026-06-19) confirmed it and found the real wedge. Two
parts were genuinely refuted: char-level granularity holds only for plain text (Claude PDFs are
page-level via `page_location`, the same coarseness as Gemini File Search `page_number`), and on clean
text the DIY path is parity. Three subfeatures survive. (1) The API guarantees every returned pointer
resolves to a real source span ("citations are guaranteed to contain valid pointers to the provided
documents"). The DIY quote-plus-find cannot, because a paraphrase makes `str.find` return -1 and the
citation is silently dropped, so the wedge is the guarantee, not recall. (2) `cited_text` is free of
output tokens and of input tokens on replay, which no competitor documents. (3) The global edge is the
one-request, no-hosted-store, mixed-source bundle: Claude cites a directly-supplied PDF plus
developer-supplied RAG chunks plus inline text in a single call with zero persisted objects, while
OpenAI (`file_citation`) and Gemini (File Search) both require a hosted vector store with upload and
index, neither cites a directly-supplied inline PDF, and Gemini File Search cannot be combined with
another tool in one call. Where Claude loses: Citations and Structured Outputs return a 400 together,
so a founder who needs strict-JSON grounded output cannot stack the two. The next demonstrator step is
a paraphrase-resolution arm, the case "not measured on clean text," to retire the objection directly.
Lesson: when a headline edge is refuted, the wedge is usually one subfeature deeper, not gone.

## What the benchmark is for

The benchmark is a credibility tool, not a sales pitch: a fair, exhaustive, best-to-best fight a
founder can run on their own keys. A toy task collapses every model into a cost-and-speed race that
decides nothing, so the engine pushes past it to find the genuine Claude-only capability, the edge an
audit can stand behind, and measures that.

## The current benchmark result

The latest run is in `../data/last_sweep.json`,
re-run with `make sweep`. Read it, do not quote it from here, because it changes as the platforms
ship.
