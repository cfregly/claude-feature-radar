# Edge: Search results, resolver-free citations into your own RAG chunks

Part of [claude-feature-radar](../../README.md). This is a measured grounding edge for retrieval you run yourself: cite the chunks your own retriever returned, inline, with no hosted vector store.

## What It Is

Pass your retrieved passages as `search_result` content blocks with citations enabled. Claude returns each claim with a `search_result_location` citation: the chunk index, the block span inside that chunk, and the verbatim cited text. No hosted store, no upload, no indexing, no persisted copy of the user's data, and no resolver code.

## The Measured Proof

Run: `make search-results`, 2026-06-19, five questions over five developer-supplied chunks. Correct cite means the returned citation resolved to the chunk that actually holds the answer.

| arm | answered | correct cite | pointer kind | hosted objects | cost | wall time |
|---|:---:|:---:|:---:|:---:|---:|---:|
| claude:haiku | 5/5 | 5/5 | block-span | 0 | $0.01 | 4.5s |
| openai:gpt-mid | 5/5 | 5/5 | file-level | 6 | $0.03 | 19.8s |
| gemini:gem-flash | 5/5 | 5/5 | chunk-level | 6 | $0.02 | 26.5s |

All three cited the correct source. Claude did it inline, resolver-free, with a block-level pointer and zero persisted objects. OpenAI and Gemini each required a hosted vector store and returned a coarser file or chunk-level pointer.

Full receipt: [`sample.txt`](sample.txt). Machine receipt: [`receipt.json`](receipt.json).

## Honest Scope

- The win is inline, resolver-free citation into chunks you supply, with a block-level span and no hosted store.
- This is not a claim that competitors cannot cite at all. Through their hosted file-search stores they cited the correct source too.
- The cost gap is partly a model-tier choice. The edge is the citation mechanism and the absence of a persisted store, not the dollar figure.

## Run It Yourself

```bash
git clone https://github.com/cfregly/claude-feature-radar && cd claude-feature-radar
make setup
make compare-deps
cp .env.example .env   # paste ANTHROPIC_API_KEY, OPENAI_API_KEY, and GEMINI_API_KEY
make search-results    # cents-scale, creates and deletes competitor hosted stores
```

Sources:

- Claude search results: https://platform.claude.com/docs/en/build-with-claude/search-results
- Claude citations: https://platform.claude.com/docs/en/build-with-claude/citations
- OpenAI file search: https://developers.openai.com/api/docs/guides/tools-file-search
- Gemini file search: https://ai.google.dev/gemini-api/docs/file-search
