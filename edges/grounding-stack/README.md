# Edge: Grounding stack, three mixed sources cited in one request

Part of [claude-feature-radar](../../README.md). This is a measured COMBINATION edge: the single-source
grounding wins (citations, pdf-citations, search-results) stacked into one request over mixed sources.

## What It Is

A doc-QA agent often answers over more than one kind of source at once: a plain-text note, a PDF the
user just uploaded, and a chunk the app's own retriever returned. In one `client.messages.create` call
you can supply all three with `citations: {"enabled": true}`, and Claude cites each with the location
type that fits it:

- inline plain-text document → `char_location` (character range)
- a directly-supplied PDF → `page_location` (page range)
- a developer-supplied RAG chunk (`search_result`) → `search_result_location` (chunk + block span)

Each pointer carries the verbatim quote free of output tokens, guaranteed to resolve, with no hosted
vector store, no upload or index step, no persisted copy of the user's data, and no resolver code.

## The Measured Proof

Run: `make grounding-stack`, 2026-06-19, one request per arm carrying the same three inline sources and
a three-part question (one fact unique to each source).

| arm | answered | source types cited in one request | hosted objects | cost |
|---|:---:|:---:|:---:|---:|
| Claude Haiku 4.5 | 3/3 | 3/3 (char + page + search_result) | 0 | $0.0102 |
| OpenAI GPT-5.4 inline | 3/3 | 0/3 | 0 | $0.0028 |
| Gemini 3.5 Flash inline | 3/3 | 0/3 | 0 | $0.0094 |

All three answered every part correctly. Only Claude returned a pointer into the supplied content, and
it returned all three location types in one response. On the one-request inline path, OpenAI and Gemini
returned no pointer into the inline sources. Machine receipt: [`receipt.json`](receipt.json).

## Honest Scope

- This is the one-request, inline, mixed-source path. The win is citing all three source types in one
  call with zero hosted objects and a typed pointer per source.
- The competitors can cite their own content through a hosted file-search vector store. That path is
  measured separately in the [`search-results`](../search-results/README.md) edge: it is file or
  chunk-level, needs six persisted objects, and cannot cite a directly-supplied PDF. Gemini's file
  search also cannot combine with another tool in the same call.
- Citations cannot be combined with structured outputs (the API returns a 400), so the grounded answer
  here is free text. A workload that also needs strict JSON must choose.

## Run It Yourself

```bash
git clone https://github.com/cfregly/claude-feature-radar && cd claude-feature-radar
make setup
make compare-deps
cp .env.example .env   # paste ANTHROPIC_API_KEY, OPENAI_API_KEY, and GEMINI_API_KEY
make grounding-stack   # cents-scale
```

`make grounding-stack` writes the latest local machine receipt to `data/last_grounding_stack.json`.

Sources, fetched 2026-06-19:

- Claude citations: https://platform.claude.com/docs/en/build-with-claude/citations
- Claude search results: https://platform.claude.com/docs/en/build-with-claude/search-results
- Claude PDF support: https://platform.claude.com/docs/en/build-with-claude/pdf-support
- OpenAI file search: https://developers.openai.com/api/docs/guides/tools-file-search
- Gemini file search: https://ai.google.dev/gemini-api/docs/file-search
