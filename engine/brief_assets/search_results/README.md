# Cite your own RAG chunks inline, no second vector store

![demo](demo.gif)

You already run your own retriever over your users' data (pgvector, your own embeddings) and you want every answer to deep-link to the exact passage it came from. The common path ships those passages into a second hosted vector store. With Claude you pass the chunks your retriever already returned straight into the request and get inline citations back, no second store.

## What you get

Pass each chunk as a `search_result` block with citations turned on. Claude answers and cites it inline with a block-range pointer (which chunk, which block), and you persist nothing new.

```python
blocks = [{"type": "search_result", "source": "your-retriever",
           "title": "your chunk title",
           "content": [...],
           "citations": {"enabled": True}}]   # add this line: makes each chunk citable
content = blocks + [{"type": "text", "text": question}]  # add this line: ask over the chunks inline
```

Measured over a small question set across my own chunks supplied inline: Claude cited 5/5 inline with a block-range pointer and 0 persisted objects, for $0.007.

## Claude vs OpenAI vs Gemini

Measured head-to-head, citing your own inline RAG chunks (RAG = your retriever feeds the model the passages):

| Platform | Citation pointer | Objects you store |
|----------|------------------|-------------------|
| Claude   | block-range (chunk + block) | 0 persisted |
| OpenAI   | file/chunk-level | 6 persisted |
| Gemini   | file/chunk-level | 6 persisted |

## Run it (about $0.05)

```bash
export ANTHROPIC_API_KEY=sk-ant-...
make search_results
```

Runs in about a minute. To reproduce the comparison, also set `OPENAI_API_KEY` and `GEMINI_API_KEY`.

## Run it on your own data

Edit `search_results/run.py`: replace the chunks and questions with your retriever's passages and your questions, then re-run `make search_results`.

## Learn more

- Claude search results: https://platform.claude.com/docs/en/build-with-claude/search-results
