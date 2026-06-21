# Edge: Citations, Claude vs the other models on grounding a user's own documents

Part of [claude-feature-radar](../../README.md). Each vendor reads a user's own documents and must return a citation pointer INTO them with its real citation tool: Claude inline `citations`, OpenAI `file_search`, Gemini `File Search`. No string matching, each reads what its own API returns.

## What It Is

A product that answers over a user's own documents (a contract, a report, the app's wiki) needs to deep-link each answer to the exact source so a person can verify before acting. With `citations: {"enabled": true}` on the supplied documents, Claude attaches a pointer whose `cited_text` is the verbatim source span the API extracted, guaranteed to resolve, with zero resolver code, the quote free of output tokens, and no copy of the user's data leaving the request. The competitors' citation tools cannot cite a directly-supplied document at all: they require uploading it to a hosted vector store first.

## The Measured Proof

Run: `make citations-paraphrase`, 2026-06-19, 6 questions over 3 user documents. Claude runs Sonnet, the competitors run their frontier tier (run the stronger competitor before a correctness claim).

| arm | citation tool | pointer granularity | resolves | cites right doc | hosted objects (copies of the user's data) | cost |
|---|---|:---:|:---:|:---:|:---:|---:|
| claude citations:sonnet | Claude Citations (inline) | char-span | 6/6 | 6/6 | 0 | $0.02 |
| openai file_search:gpt-top | OpenAI file_search | file-level | 6/6 | 6/6 | 4 | $0.07 |
| gemini File Search:gem-pro | Gemini File Search | chunk-level | 6/6 | 6/6 | 4 | $0.02 |

Claude returns a structured, API-guaranteed-to-resolve **char-span** pointer into the user's directly-supplied documents with **zero hosted objects**, so the data never leaves the request. OpenAI `file_search` and Gemini `File Search` **cannot cite a directly-supplied document**: they require uploading it to a hosted vector store first (4/4 hosted objects, 8 in total, a third-party copy of the user's data), and even then the citation is file-level (OpenAI) or chunk-level (Gemini), never a guaranteed char span into the source. Verified against the vendors' live docs on 2026-06-19. Because this is an API-surface gap, it holds at the competitors' frontier tier, it is not a model contest.

Verdict: `promotable_edge: true`.

Full receipt: [`sample.txt`](sample.txt). Machine receipt: [`receipt.json`](receipt.json).

## Honest Scope

- The win is feature vs feature and is an API-surface gap (the competitors cannot return a structured, guaranteed-resolve pointer into a directly-supplied document without a hosted store), so it survives their frontier models.
- The competitors CAN cite their own content through a hosted vector store. That hosted path, and its file/chunk granularity and persisted objects, is also measured in the [search-results](../search-results/README.md), [pdf-citations](../pdf-citations/README.md), and [grounding-stack](../grounding-stack/README.md) edges.
- Citations cannot be combined with Structured Outputs. The two return a 400 together, so a grounded answer here is free text.

## Run It Yourself

```bash
git clone https://github.com/cfregly/claude-feature-radar && cd claude-feature-radar
make setup
make compare-deps
cp .env.example .env   # paste ANTHROPIC_API_KEY, OPENAI_API_KEY, and GEMINI_API_KEY
make citations-paraphrase   # about $0.12, the competitor arms create and delete a hosted store
```

Sources:

- Claude citations: https://platform.claude.com/docs/en/build-with-claude/citations
- OpenAI file search: https://developers.openai.com/api/docs/guides/tools-file-search
- Gemini file search: https://ai.google.dev/gemini-api/docs/file-search
