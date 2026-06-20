# Deep-link every answer to the exact page of a user's PDF

![demo](demo.gif)

Your product answers questions over a PDF your user just uploaded: a lease, a 10-K, an insurance policy, a vendor contract. The answer is only useful when the user can verify it, which means pointing them at the exact page it came from. With Claude Citations you hand Claude the PDF directly in the request and every answer comes back with a page pointer, so there is no page resolver to write and no vector store to stand up first.

## What you get

Send the PDF as a base64 document block with citations enabled. Every answer comes back with a `page_location` citation: the page number plus the quoted source text. The pointer resolves into the PDF you supplied, and the quoted text does not count toward your output tokens, so the page pointer adds nothing to the bill. On a five-page agreement PDF with five questions, Claude answered every question and returned a page pointer that resolved to the correct page every time (5/5), for $0.046.

```python
doc = {
    "type": "document",
    "source": {"type": "base64", "media_type": "application/pdf", "data": pdf_b64},  # the PDF, supplied directly
    "citations": {"enabled": True},                                                  # turn on page pointers
}
r = client.messages.create(
    model="claude-haiku-4-5",
    max_tokens=512,
    messages=[{"role": "user", "content": [doc, {"type": "text", "text": question}]}],
)
# each text block now carries a page_location citation: start_page_number + cited_text
```

## The page pointer, head-to-head

Measured (2026-06-19), same five questions over the same directly-supplied PDF:

| Model | Page pointer to the right page |
| --- | --- |
| Claude | 5/5 |
| OpenAI (gpt-5.4) | 0/5 |
| Gemini (3.5-flash) | 0/5 |

Only Claude returns a page pointer on a PDF supplied directly in the request, so your user gets a one-click jump to the source.

## Run it (about $0.05)

```
export ANTHROPIC_API_KEY=your-key   # https://console.anthropic.com/
make pdf_citations                  # build the venv, install anthropic, answer questions over a PDF with a page pointer each
```

About a minute, $0.046 on my run. `make pdf_citations` is self-bootstrapping: it creates `.venv`, installs `anthropic`, and runs the self-test that asserts every answer points at the correct page.

To reproduce the whole table on your own keys, not just the Claude side:

```
export ANTHROPIC_API_KEY=your-key
export OPENAI_API_KEY=your-key
export GEMINI_API_KEY=your-key
make pdf_citations COMPARE=1        # installs the optional OpenAI and Gemini SDKs, runs all three arms
```

`COMPARE=1` installs `requirements-compare.txt` (the OpenAI and Gemini SDKs) into the same `.venv` and runs the same questions over the same PDF on each platform, so you see the page pointer come back from Claude and not from the others. Without it, the brief runs the Claude side alone on one dependency.

## Run it on your own data

Open `pdf_citations/run.py`, the one file you edit. Replace the sample pages and the questions list with your own document and the questions your users ask, then run `python -m pdf_citations.run`. Your PDF needs extractable text, since the page pointers come from the text Claude reads.

## Learn more

- [Citations docs](https://platform.claude.com/docs/en/build-with-claude/citations)
