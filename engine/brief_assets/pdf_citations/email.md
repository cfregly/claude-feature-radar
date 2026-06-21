Subject: Congrats on YC! Page-linked answers over user PDFs

Hey {first_name},

Congrats on the batch. Quick tip from a build I ran this week.

If your product answers questions over a PDF your user just uploaded (a contract, a report, a policy), the user needs a one-click jump to the page behind the answer. The usual way to get there is glue code you do not want to own: write your own page resolver, or push every uploaded file into a hosted vector store before you can ask a single question. That is latency and plumbing on what should be an upload-and-ask flow.

Claude Citations does it on the PDF you hand it directly in the request. Send the file as a base64 document block and turn citations on. Two lines:

```python
doc = {
    "type": "document",
    "source": {"type": "base64", "media_type": "application/pdf", "data": pdf_b64},  # the PDF, supplied directly
    "citations": {"enabled": True},                                                  # turn on page pointers
}
```

Every answer comes back with a `page_location` pointer: the page number plus the quoted source text. The quote rides for free (it does not count toward your output tokens), so the page pointer adds nothing to the bill.

Using my API key, over a five-page agreement PDF with five questions, Claude answered every question and returned a page pointer that resolved to the correct page every time. That run cost $0.05.

I ran the same five questions on the other two big models, without creating a hosted vector store or
file-search index first. Here is the direct-PDF head-to-head:

| Model | Correct page pointer on the direct-PDF path |
| --- | --- |
| Claude | 5/5 |
| OpenAI (gpt-5.4) | 0/5 |
| Gemini (3.5-flash) | 0/5 |

On this direct-request path, Claude hands back the page pointer in the same response, so your user gets a one-click jump to the source without a pre-upload step.

Reproduce it in about a minute for $0.05. One clone, one command:

```
git clone https://github.com/cfregly/claude-feature-hits && cd claude-feature-hits
export ANTHROPIC_API_KEY=your-api-key
make pdf_citations
```

Full brief, demo GIF, code, and sample output: https://github.com/cfregly/claude-feature-hits/tree/main/pdf_citations

Docs: https://platform.claude.com/docs/en/build-with-claude/citations

Want the whole table, not just the Claude side? Set `OPENAI_API_KEY` and `GEMINI_API_KEY` too and run `make pdf_citations COMPARE=1`. It runs Claude, OpenAI, and Gemini side by side on the same directly-supplied PDF, with no hosted file-search store, using your own API keys for a few cents.

To run it on your own data, open `pdf_citations/run.py` and swap the sample pages and questions for your document and the questions your users ask. Your PDF needs extractable text, since the page pointers come from the text Claude reads.

Happy building,
{your_name}
Building with Claude
