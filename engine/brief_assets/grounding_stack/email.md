Subject: Congrats on YC! Trustworthy doc-QA answers in one Claude call

Hey {first_name},

Congrats on the batch. Quick builder tip from my own testing, in case you are wiring up doc-QA over your users' files.

A real answer usually pulls from more than one kind of source at once: a plain-text note your user left, a PDF they just uploaded, and a chunk your retriever (RAG, the step that fetches matching snippets from a knowledge base) found in their wiki. Your users only trust the answer when they can click back to where each fact came from. Stitching that together by hand means a vector store, an index step, and your own glue code to map an answer back to its source.

Claude Citations does it in one request. Turn citations on per source and Claude hands back a typed pointer for each: a character range for the text, a page range for the PDF, and a chunk span for the RAG result.

```python
content = [text_doc, pdf_doc, search_result_chunk,
           {"type": "text", "text": question}]  # all cited in one call
r = client.messages.create(model="claude-haiku-4-5", max_tokens=600,
                           messages=[{"role": "user", "content": content}])
```

On my key, one request mixing all three sources answered every part and returned a correct typed pointer into each one (char, page, and chunk) in the same response. No vector store, no copy of your user's data, and the cited text rides along free of output tokens. Live cost $0.010.

I ran the same prompt head-to-head on 2026-06-19:

| Model  | Sources answered | Inline pointers |
| :----- | :--------------- | :-------------- |
| Claude | 3 of 3           | 3 of 3          |
| OpenAI | 3 of 3           | 0 of 3          |
| Gemini | 3 of 3           | 0 of 3          |

Three citation modes in one request is the combination edge: every source comes back with its own verifiable pointer.

Reproduce it in about a minute for $0.010. One clone, one command:

    git clone https://github.com/cfregly/claude-feature-hits && cd claude-feature-hits
    make grounding_stack

To run it on your own sources, edit `grounding_stack/run.py`: swap in your note, your PDF, and one retriever chunk, then re-run.

Happy building!
{your_name}
Building with Claude
