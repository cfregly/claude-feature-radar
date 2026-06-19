# Deep-link every answer to the exact page of a user's PDF with Claude Citations

![demo](demo.gif)

Your product answers questions over a PDF your user just uploaded: a lease, a 10-K, an insurance policy, a vendor contract. The answer is only useful if the user can verify it, which means pointing them at the exact page it came from. Writing your own page resolver, or persisting every uploaded file into a hosted vector store first, is glue code you do not want to own.

## What you get

Send the PDF directly in the request as a base64 document block with citations enabled, and every answer comes back with a `page_location` citation: the page number plus the quoted source text. The pointer is guaranteed to resolve into the PDF you supplied, and the quote does not count toward your output tokens. No vector store to set up, no resolver to write. On a five-page agreement PDF with five questions, Claude answered all five and returned a correct-page pointer for all five (5 of 5), measured 2026-06-19 for $0.0458 on Claude Haiku 4.5.

```python
doc = {
    "type": "document",
    "source": {"type": "base64", "media_type": "application/pdf", "data": pdf_b64},  # add this: the PDF, supplied directly
    "citations": {"enabled": True},                                                  # add this
}
r = client.messages.create(model="claude-haiku-4-5-20251001", max_tokens=512,
    messages=[{"role": "user", "content": [doc, {"type": "text", "text": question}]}])
# each text block now carries citations with type page_location: start_page_number + cited_text
```

## Run it (about $0.02)

```
export ANTHROPIC_API_KEY=your-key   # https://console.anthropic.com/
make pdf_citations        # build the venv, install anthropic, answer questions over a PDF with a page pointer each
```

`make pdf_citations` is self-bootstrapping: it creates `.venv`, installs `anthropic`, and runs the self-test that asserts every answer points at the correct page.

## Run it on your own PDF

Open `pdf_citations/run.py`, the file you edit. Replace the `PAGES` sample and the `QUESTIONS` list with your own document and the questions your users ask, then run `python -m pdf_citations.run`. To point at a real PDF file instead of the generated sample, base64-encode its bytes and pass them as the document `source` data. Your PDF needs extractable text, since page citations are drawn from the text Claude extracts.

## Learn more

- [Citations docs](https://platform.claude.com/docs/en/build-with-claude/citations)
