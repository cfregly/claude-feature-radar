Subject: Congrats on YC! A Claude trick for citing a user's PDF

Hey {first_name},

Congrats on the batch. Quick tip from a build I ran this week: if you answer questions over a user's uploaded PDF, point them at the exact page the answer came from. People trust an answer they can verify in one click, and that one detail makes the feature feel real.

The problem is the plumbing. To deep-link an answer to its source page, you usually write your own page resolver, or you persist every uploaded file into a hosted vector store before you can ask anything. That is glue code and latency you do not want on an upload-and-ask flow.

Claude Citations does it on the PDF you hand it directly in the request. Send the file as a base64 document block and turn citations on, two lines:

```python
doc = {"type": "document",
       "source": {"type": "base64", "media_type": "application/pdf", "data": pdf_b64},
       "citations": {"enabled": True}}
```

Every answer comes back with a page_location pointer: the page number plus the quoted source text. The quote is free of output tokens, so it does not add to your bill. On my key, over a five-page agreement PDF with five questions, Claude answered all five and returned the correct page for all five (5 of 5), for $0.05 on Haiku 4.5.

Here is the run and the table: https://github.com/cfregly/claude-feature-hits/blob/main/pdf_citations/README.md

Run it in about a minute for roughly $0.02:

```
make pdf_citations
```

To try it on your own data, open pdf_citations/run.py, swap the sample PAGES and QUESTIONS for your document and the questions your users ask, then run python -m pdf_citations.run. Your PDF needs extractable text, since the page pointers come from the text Claude reads.

Happy building! 🚀
{your_name}
Building with Claude
