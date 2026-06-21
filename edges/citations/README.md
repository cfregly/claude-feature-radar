# Edge: Citations, a verifiable per-character source pointer into your user's own document

Part of [claude-feature-radar](../../README.md), the internal engine. This note is the internal
both-directions read, not founder copy. The wins-only founder brief is
[`claude-feature-hits/citations`](https://github.com/cfregly/claude-feature-hits). This edge needs
no beta header.

**What it is.** Turn on `citations: {"enabled": true}` per document and Claude returns each claim with
a structured pointer (a character range for text, a page range for a PDF) plus the verbatim quote,
extracted by the API. The pointer is guaranteed to resolve to real source text, and the quote is free
of output tokens. For a contract-review, clinical-summary, financial-research, or support-over-docs
product, the click-through to the exact sentence is the trust layer.

## The measured proof

Over 8 questions on 3 plain-text documents, the grader verifies the API's own offsets against the
source (`source[start:end] == cited_text`, the documented guarantee). This is verification of the
returned pointer, not a do-it-yourself string search.

| approach | resolves | who resolves it | quote free of output tokens | output tokens | cost |
|---|:--:|:--:|:--:|--:|--:|
| **Claude Haiku 4.5 + Citations** | **8/8** (guaranteed) | the API | yes | 305 | $0.01 |

**The honest read.** The value is the in-API guarantee, the verbatim quote free of output tokens, and
char granularity, with zero resolver code to own. It is a within-Claude value-add, measured on a single
arm. Citations is not the cheapest arm in raw dollars, so we never claim "cheaper." Full receipt in
[`sample.txt`](sample.txt).

## The precise edge, and where comparisons live

This single-arm edge proves Claude's own API guarantee for plain-text user documents: a structured
character-range pointer, a guaranteed-valid quoted span, and zero resolver code. It does not claim that
competitors lack hosted-search or custom-resolver paths. Where the task becomes a head-to-head
capability comparison, the sibling edges state the exact condition being tested: direct request inputs,
hosted stores, PDFs, returned RAG chunks, or mixed grounding:
[citations-paraphrase](../citations-paraphrase/README.md),
[pdf-citations](../pdf-citations/README.md), [search-results](../search-results/README.md), and
[grounding-stack](../grounding-stack/README.md). Sources:
[Anthropic citations doc](https://platform.claude.com/docs/en/build-with-claude/citations),
[Gemini File Search](https://ai.google.dev/gemini-api/docs/file-search),
[OpenAI file_search](https://developers.openai.com/api/docs/guides/tools-file-search). One hard caveat:
Citations cannot be combined with Structured Outputs on the same document (the API returns a 400).

## Run it yourself

```bash
git clone https://github.com/cfregly/claude-feature-radar && cd claude-feature-radar
make setup                        # core deps, the one dependency
cp .env.example .env              # paste your ANTHROPIC_API_KEY
make citations                    # this edge, using your own API key, about $0.01
# or directly: python edges/citations/demo.py
```

Every number is read off the real API `usage` object.
