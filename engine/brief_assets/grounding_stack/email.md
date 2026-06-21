Subject: Congrats on YC! One request for mixed-source doc QA

Hey {first_name},

Congrats on the batch. Quick builder tip from my own testing, in case you are wiring up doc-QA over your users' files.

A real answer usually pulls from more than one kind of source at once: a plain-text note your user left, a PDF they just uploaded, and a chunk your retriever (RAG, the step that fetches matching snippets from a knowledge base) found in their wiki. Your users can click back to where each fact came from. Stitching that together by hand means a vector store, an index step, and your own glue code to map an answer back to its source.

Claude Citations does it in one request. Turn citations on per source and Claude hands back a typed pointer for each: a character range for the text, a page range for the PDF, and a chunk span for the RAG result.

```python
content = [text_doc, pdf_doc, search_result_chunk,
           {"type": "text", "text": question}]  # all cited in one call
r = client.messages.create(model="claude-haiku-4-5-20251001", max_tokens=600,
                           messages=[{"role": "user", "content": content}])
```

Using my API key, one request mixing all three sources answered every part and returned a correct typed pointer into each one (char, page, and chunk) in the same response. No vector store, no copy of your user's data, and the cited text rides along free of output tokens. Live cost about $0.01.

I ran the same prompt head-to-head on 2026-06-19:

| Model  | Sources answered | Inline pointers |
| :----- | :--------------- | :-------------- |
| Claude | 3 of 3           | 3 of 3          |
| OpenAI | 3 of 3           | 0 of 3          |
| Gemini | 3 of 3           | 0 of 3          |

One request, three source types, and every source comes back with its own verifiable pointer.

Reproduce it in about a minute for $0.01. One clone, one command:

```bash
git clone https://github.com/cfregly/claude-feature-hits && cd claude-feature-hits
export ANTHROPIC_API_KEY=your-api-key
make grounding_stack
```

Full brief, demo GIF, code, and sample output: https://github.com/cfregly/claude-feature-hits/tree/main/grounding_stack

Docs: https://platform.claude.com/docs/en/build-with-claude/citations

Want the whole table, not just the Claude side? Set `OPENAI_API_KEY` and `GEMINI_API_KEY` too and run `make grounding_stack COMPARE=1`. It runs Claude, OpenAI, and Gemini side by side on the same three sources, so you see all three answer and only Claude return an inline pointer for each, using your own API keys for a few cents.

To run it on your own sources, edit `grounding_stack/run.py`: swap in your note, your PDF, and one retriever chunk, then re-run.

Happy building,
{your_name}
Building with Claude
