Subject: Congrats on YC! A Claude trick for trustworthy doc answers

Hey {first_name},

Congrats on the batch. If you are wiring up a doc-QA flow, one quick tip from my own
testing: keep each RAG chunk in its own source block instead of pasting them into one
blob, so the citation points at the exact chunk a user can click back to.

The problem I kept hitting: a real answer pulls from more than one kind of source at
once. A plain-text note, a PDF the user just uploaded, and a chunk your retriever found
in their wiki. Users only trust the answer when they can see where each fact came from,
and stitching that together usually means a vector store, an index step, and your own
glue code to map an answer back to a source.

Claude Citations does it in one request. You turn on citations per source and Claude
hands back a typed pointer for each: a character range for the text, a page range for the
PDF, and a chunk span for the RAG result.

```python
content = [
    {"type": "document", "source": {"type": "text", ...}, "citations": {"enabled": True}},   # add this
    {"type": "document", "source": {"type": "base64", ...}, "citations": {"enabled": True}},  # add this
    {"type": "search_result", "source": "kb://chunk", "content": [...],
     "citations": {"enabled": True}},                                                         # add this
]
```

On my key, one request with all three sources answered every part and returned a pointer
into each one (char, page, and chunk) in the same response. No vector store, no copy of
the user's data, and the cited text does not count against your output tokens. Measured
2026-06-19 on Claude Haiku 4.5 for $0.0101.

Demo and code: https://github.com/cfregly/claude-feature-hits/blob/main/grounding_stack/README.md

Run it in about a minute for roughly $0.01:

    make grounding_stack

To try it on your own sources, edit `grounding_stack/run.py`, swap in your note, your
PDF, and one of your retriever chunks, then re-run.

Happy building! 🚀
{your_name}
Building with Claude
