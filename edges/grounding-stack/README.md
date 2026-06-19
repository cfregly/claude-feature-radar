# Edge: Grounding stack, three mixed sources cited in one request

Part of [claude-feature-radar](../../README.md). This is a measured combination edge: the single-source grounding wins stacked into one request over mixed sources.

## What It Is

A doc-QA agent often answers over more than one kind of source at once: a plain-text note, a PDF the user just uploaded, and a chunk the app's own retriever returned. In one `client.messages.create` call you can supply all three with citations enabled, and Claude cites each with the location type that fits it: `char_location`, `page_location`, and `search_result_location`.

## The Measured Proof

Run: `make grounding-stack`, 2026-06-19, one request per arm carrying the same three inline sources and a three-part question.

| arm | answered | source types cited in one request | hosted objects | cost |
|---|:---:|:---:|:---:|---:|
| claude:haiku | 3/3 | 3/3 (char + page + search_result) | 0 | $0.0101 |
| openai:gpt-mid | 3/3 | 0/3 | 0 | $0.0028 |
| gemini:gem-flash | 3/3 | 0/3 | 0 | $0.0087 |

All three answered every part correctly. Only Claude returned a pointer into the supplied content, and it returned all three location types in one response. On the one-request inline path, OpenAI and Gemini returned no pointer into the inline sources.

Full receipt: [`sample.txt`](sample.txt). Machine receipt: [`receipt.json`](receipt.json).

## Honest Scope

- This is the one-request, inline, mixed-source path.
- The competitors can cite their own content through hosted file-search vector stores. That path is measured separately in the search-results edge.
- Citations cannot be combined with structured outputs, so the grounded answer here is free text.

## Run It Yourself

```bash
git clone https://github.com/cfregly/claude-feature-radar && cd claude-feature-radar
make setup
make compare-deps
cp .env.example .env   # paste ANTHROPIC_API_KEY, OPENAI_API_KEY, and GEMINI_API_KEY
make grounding-stack   # cents-scale
```

Sources:

- Claude citations: https://platform.claude.com/docs/en/build-with-claude/citations
- Claude search results: https://platform.claude.com/docs/en/build-with-claude/search-results
- Claude PDF support: https://platform.claude.com/docs/en/build-with-claude/pdf-support
- OpenAI file search: https://developers.openai.com/api/docs/guides/tools-file-search
- Gemini file search: https://ai.google.dev/gemini-api/docs/file-search
