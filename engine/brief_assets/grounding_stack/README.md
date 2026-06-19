# Cite a text doc, a PDF, and a RAG chunk in one request with Claude Citations

![demo](demo.gif)

Your doc-QA agent answers over mixed sources at once: a plain-text note, a PDF the user just uploaded, and a chunk your own retriever pulled from their wiki. Users want to trust the answer, which means a pointer back to where each fact came from. Claude Citations gives you that in one `client.messages.create` call. Turn citations on for each source and Claude returns a typed pointer per source: a character range for the text, a page range for the PDF, and a chunk span for the RAG result.

## What you get

One request carrying all three sources and a three-part question came back with every part answered and a pointer into each source: `char_location` for the text, `page_location` for the PDF, and `search_result_location` for the chunk, all in the same response. No vector store to stand up, no upload-and-index step, and no copy of the user's data kept anywhere. The cited text rides along for free, it does not count against your output tokens. Measured on 2026-06-19: 3 of 3 sources cited in one request on Claude Haiku 4.5 for $0.0101.

```python
content = [
    {"type": "document", "source": {"type": "text", "media_type": "text/plain", "data": text_note},
     "citations": {"enabled": True}},                                              # add this
    {"type": "document", "source": {"type": "base64", "media_type": "application/pdf", "data": pdf_b64},
     "citations": {"enabled": True}},                                              # add this
    {"type": "search_result", "source": "kb://chunk", "title": "Rate limits",
     "content": [{"type": "text", "text": rag_chunk}], "citations": {"enabled": True}},  # add this
    {"type": "text", "text": question},
]
r = client.messages.create(model="claude-haiku-4-5", max_tokens=600,
                           messages=[{"role": "user", "content": content}])
```

## Run it (about $0.01)

```bash
make grounding_stack
```

## Run it on your own sources

Edit `grounding_stack/run.py`: swap `TEXT_FACT`, the PDF the demo builds, and `CHUNK_FACT` for your own note, PDF, and retriever chunk, then re-run:

```bash
python grounding_stack/run.py --check
```

## Learn more

Claude Citations: https://platform.claude.com/docs/en/build-with-claude/citations
