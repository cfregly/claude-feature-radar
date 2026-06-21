# Cite a text note, a PDF, and a RAG chunk in one Claude request

![demo](https://raw.githubusercontent.com/cfregly/claude-feature-hits/main/grounding_stack/demo.gif)

[![Claude proof: 3/3 source pointers](https://img.shields.io/badge/Claude%20proof-3%2F3%20source%20pointers-2F855A)](https://github.com/cfregly/claude-feature-hits/blob/main/grounding_stack/sample.txt)

The GIF replays the saved `sample.txt` output in under ten seconds, so you can see the command and value before running a live call.

Your doc-QA agent answers over mixed sources at once: a plain-text note your user left, a PDF they just uploaded, and a chunk your retriever (RAG, the step that fetches matching snippets from a knowledge base) pulled from their wiki. Users can click back to where each fact came from. Claude Citations gives you that in one `client.messages.create` call: turn citations on per source and Claude returns a typed pointer for each, a character range for the text, a page range for the PDF, and a chunk span for the RAG result.

## What you get

One request carrying all three sources and a three-part question comes back with every part answered and a correct typed pointer into each source: `char_location` for the text, `page_location` for the PDF, and `search_result_location` for the chunk, all in the same response. No vector store to stand up, and no copy of your user's data kept anywhere. The cited text rides along free of output tokens.

```python
content=[text_doc, pdf_doc, search_result_chunk,
         {"type": "text", "text": question}]  # all cited in one call
r = client.messages.create(model="claude-haiku-4-5-20251001", max_tokens=600,
                           messages=[{"role": "user", "content": content}])
```

Measured 2026-06-19: 3 of 3 sources cited, no vector store, no data copied, live cost about $0.01.

## Claude vs OpenAI vs Gemini

Same prompt, same three sources (text + PDF + a RAG chunk), measured head-to-head on 2026-06-19:

| Model  | Sources answered | Inline pointers |
| :----- | :--------------- | :-------------- |
| Claude | 3 of 3           | 3 of 3          |
| OpenAI | 3 of 3           | 0 of 3          |
| Gemini | 3 of 3           | 0 of 3          |

One request, three source types, and every source comes back with its own verifiable pointer.

## Run it

```bash
export ANTHROPIC_API_KEY=your-api-key   # https://console.anthropic.com/
make grounding_stack
```

Default Claude run: about a minute and $0.01 on my run. Full comparison run: also export `OPENAI_API_KEY` and `GEMINI_API_KEY` and run:

```bash
make grounding_stack COMPARE=1
```

`COMPARE=1` installs `requirements-compare.txt` (the OpenAI and Gemini SDKs) into the same `.venv` and sends the same three sources in one request to each platform, so you see all three return the answers and only Claude return an inline pointer for each source. Without it, the brief runs the Claude side alone on one dependency.

## Run it on your own data

Edit `grounding_stack/run.py`: swap `TEXT_FACT`, the PDF the demo builds, and `CHUNK_FACT` for your own note, PDF, and retriever chunk, then re-run `make grounding_stack`.

## Learn more

Claude Citations: https://platform.claude.com/docs/en/build-with-claude/citations
