# Edge: Citations, a verifiable per-character source pointer into your user's own document

Part of [claude-competitive-engine](../../README.md). This edge is GA today.

**What it is.** Turn on `citations: {"enabled": true}` per document and Claude returns each claim with
a structured pointer (a character range for text, a page range for a PDF) plus the verbatim quote,
extracted by the API. The pointer is guaranteed to resolve to real source text, and the quote is free
of output tokens. For a contract-review, clinical-summary, financial-research, or support-over-docs
product, the click-through to the exact sentence is the trust layer.

## The measured proof (honest, including the part that is not flattering)

The realistic DIY path without the feature is to ask the model for the verbatim quote and resolve it
yourself with `source.find(quote)`. Over 8 questions on 3 plain-text documents, the grader checks that
each citation resolves to the real source text:

| approach | resolves | who resolves it | quote free of output tokens | output tokens | cost |
|---|:--:|:--:|:--:|--:|--:|
| **Claude Haiku 4.5 + Citations** | **8/8** (guaranteed) | the API | yes | 308 | $0.011 |
| Claude Haiku 4.5, DIY str.find | 8/8 | your code | no | 586 | $0.006 |
| OpenAI gpt-5.4-mini, DIY str.find | 8/8 | your code | no | 391 | $0.004 |
| Gemini gemini-3.5-flash, DIY str.find | 8/8 | your code | no | 3,466 | $0.036 |

**The honest read.** On clean text the DIY bolt-on resolves just as well. The edge is not "the others
cannot cite." It is that Claude resolves the pointer in the API, guaranteed by construction (the DIY
`find` returns nothing the moment the model paraphrases, which it will on a messy real PDF), the quote
is free of output tokens, and you write zero resolver code. Citations is not the cheapest arm in raw
dollars, so we never claim "cheaper." Full receipt in [`sample.txt`](sample.txt).

## The precise edge, and where it is narrowing

No competitor exposes a per-character pointer into a user-supplied document with a guaranteed-valid,
output-token-free quote. The absolute "no competitor" claim is refuted: Google's Gemini File Search
(2026-05) returns a page-level pointer, and OpenAI cites its own output, not your source. So the
surviving lead is char granularity plus the guarantees, verified against the live docs on 2026-06-17
([Anthropic citations doc](https://platform.claude.com/docs/en/build-with-claude/citations),
[Gemini File Search](https://ai.google.dev/gemini-api/docs/file-search)). One hard caveat: Citations
cannot be combined with Structured Outputs on the same document (the API returns a 400).

## Run it yourself

```bash
git clone <this-repo> && cd claude-competitive-engine
make setup && make compare-deps   # core deps, then the OpenAI + Gemini SDKs, into the same venv
cp .env.example .env              # paste your Anthropic, OpenAI, and Gemini keys
make citations                    # this edge, on your own keys, about six cents
# or directly: python edges/citations/demo.py
```

Every number is read off the real API `usage` object. See [`FOUNDER_EMAIL.md`](FOUNDER_EMAIL.md) for
the pitch and [`PRODUCT_EMAIL.md`](PRODUCT_EMAIL.md) for the honest other direction.
