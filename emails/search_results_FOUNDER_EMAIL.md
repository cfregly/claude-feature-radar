Subject: Congrats on YC! Inline citations for your retriever chunks

Hey {first_name},

Congrats on the batch. Quick builder tip from running retrieval-augmented generation over private data: you can keep your retriever yours and still get clean inline citations.

Here is the workload I keep hitting. You already run your own retrieval (pgvector, your own embeddings) and your answers need to deep-link to the exact passage they came from, so a user can click and verify. The common path ships those passages into a second hosted vector store, which means a copy of your users' data to manage and a coarse file-level pointer back.

Claude has a cleaner route. Pass the chunks your retriever already returned straight into the request as search_result blocks with citations turned on. Claude answers and cites them inline, no second store.

```python
blocks = [{"type": "search_result", "source": "your-retriever",
           "title": "your chunk title",
           "content": [...],
           "citations": {"enabled": True}}]   # add this line: makes each chunk citable
content = blocks + [{"type": "text", "text": question}]  # add this line: ask over the chunks inline
```

I measured it over a small question set across my own chunks: Claude cited 5/5 inline with a block-range pointer (which chunk, which block) and 0 persisted objects. Live cost was $0.01.

Here is the same run head-to-head, citing your own inline RAG chunks (RAG = your retriever feeds Claude the passages):

| Platform | Citation pointer | Objects you store |
|----------|------------------|-------------------|
| Claude   | block-range (chunk + block) | 0 persisted |
| OpenAI   | file/chunk-level | 6 persisted |
| Gemini   | file/chunk-level | 6 persisted |

Cost to reproduce the Claude side is about $0.01 and it runs in about a minute. One clone, one command:

```bash
git clone https://github.com/cfregly/claude-feature-hits && cd claude-feature-hits
export ANTHROPIC_API_KEY=your-api-key
make search_results
```

Full brief, demo GIF, code, and sample output: https://github.com/cfregly/claude-feature-hits/tree/main/search_results

Docs: https://platform.claude.com/docs/en/build-with-claude/search-results

Want the whole table, not just the Claude side? Set `OPENAI_API_KEY` and `GEMINI_API_KEY` too and run `make search_results COMPARE=1`. It runs Claude, OpenAI, and Gemini side by side on the same chunks, so you see Claude cite inline with zero stored objects while the others stand up a hosted store, about $0.05 using your API keys.

To run it on your own data, edit `search_results/run.py` with your retriever's chunks and questions, then run `make search_results` again.

If you reply with the bottleneck you are working through, I can point you to the closest Claude pattern.

Happy building,

--Chris Fregly
Building with Claude
