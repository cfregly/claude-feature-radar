# Cite your own RAG chunks inline with Claude search_result content blocks

![demo](demo.gif)

You run your own retriever over your users' data (support docs, contracts, billing rules) and you
want every answer to deep-link to the exact passage it came from. The usual path ships that data into
a hosted vector store, then hands back a coarse file-level pointer. With Claude you pass the chunks
your retriever already returned straight into the request as `search_result` content blocks. Claude
answers and cites them inline.

## What you get

Every answer comes back with a `search_result_location` pointer: which chunk, the block span inside
it, and the verbatim cited text, all resolver-free. No hosted store, no upload step, no third-party
copy of your users' data, no resolver code to write. Measured 2026-06-19 over five questions across
five chunks supplied inline: Claude answered 5 of 5, cited the correct source chunk 5 of 5, with a
block-span pointer, 0 hosted objects, for $0.0067 on Claude Haiku 4.5.

```python
# your retriever already returned these passages
blocks = [{"type": "search_result", "source": "kb://overage.txt", "title": "Overage billing",
           "content": [{"type": "text", "text": chunk_text}],
           "citations": {"enabled": True}}]              # add this: makes each chunk citable
content = blocks + [{"type": "text", "text": question}]   # add this: ask over the chunks inline
resp = client.messages.create(model="claude-haiku-4-5-20251001", max_tokens=512,
                              messages=[{"role": "user", "content": content}])
# resp carries search_result_location citations: search_result_index, start/end_block_index, cited_text
```

## Run it (about $0.05)

```bash
make search_results
```

## Run it on your own chunks

Edit `search_results/run.py`: replace the `CHUNKS` and `QUESTIONS` with your retriever's passages and
your questions. Then re-run:

```bash
python search_results/run.py
```

## Learn more

- Claude search results: https://platform.claude.com/docs/en/build-with-claude/search-results
