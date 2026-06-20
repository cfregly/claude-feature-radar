Subject: Congrats on YC! A Claude trick for deep-linking answers to a user's PDF

Hey {first_name},

Congrats on the batch. Quick tip from a build I ran this week.

If your product answers questions over a PDF your user just uploaded (a contract, a report, a policy), the answer is only useful when they can verify it. That means pointing them at the exact page it came from. The usual way to get there is glue code you do not want to own: write your own page resolver, or push every uploaded file into a hosted vector store before you can ask a single question. That is latency and plumbing on what should be an upload-and-ask flow.

Claude Citations does it on the PDF you hand it directly in the request. Send the file as a base64 document block and turn citations on. Two lines:

```python
doc = {
    "type": "document",
    "source": {"type": "base64", "media_type": "application/pdf", "data": pdf_b64},  # the PDF, supplied directly
    "citations": {"enabled": True},                                                  # turn on page pointers
}
```

Every answer comes back with a `page_location` pointer: the page number plus the quoted source text. The quote rides for free (it does not count toward your output tokens), so the page pointer adds nothing to the bill.

On my key, over a five-page agreement PDF with five questions, Claude answered every question and returned a page pointer that resolved to the correct page every time. That run cost $0.046.

I ran the same five questions on the other two big models. Here is the head-to-head on the page pointer:

| Model | Page pointer to the right page |
| --- | --- |
| Claude | 5/5 |
| OpenAI (gpt-5.4) | 0/5 |
| Gemini (3.5-flash) | 0/5 |

Only Claude hands back a page pointer on a PDF you supply directly, so your user gets a one-click jump to the source.

Reproduce it in about a minute for $0.05. One clone, one command:

```
git clone https://github.com/cfregly/claude-feature-hits && cd claude-feature-hits
make pdf_citations
```

To run it on your own data, open `pdf_citations/run.py` and swap the sample pages and questions for your document and the questions your users ask. Your PDF needs extractable text, since the page pointers come from the text Claude reads.

Happy building
{your_name}
Building with Claude
