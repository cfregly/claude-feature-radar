Subject: A Claude primitive for source-linked answers your users can verify

Hey {first_name},

Congrats on the batch. Quick note if your product answers questions over your users' own documents, a
contract, a policy, a clinical note, a financial filing.

The hard part is accuracy. A user needs to click from the answer straight to the sentence it came from,
with the source already attached to the claim.

Turn on citations per document and Claude returns each claim with a pointer into that document and the
verbatim quote, guaranteed by the API to resolve, free of output tokens, with no resolver code on your
side. The same one flag works on a PDF you hand it directly in the request, where the pointer is the
page.

```python
doc = {
    "type": "document",
    "source": {"type": "text", "media_type": "text/plain", "data": policy_text},
    "title": "Policy",
    "citations": {"enabled": True},   # the one change
}
# Claude's reply carries each claim with {start_char_index, end_char_index, cited_text}
```

I measured it over 8 questions on real documents: every claim came back with a pointer that resolves to
the source (8 of 8), and the quote costs no output tokens. The important part is that the API returns
the source span directly, so your app is not guessing where a quote came from.

Run it: `make citations` ($0.01 using your API key). Point it at your own documents to see your resolve
rate.

Full brief, demo GIF, code, and sample output: https://github.com/cfregly/claude-feature-hits/tree/main/citations

Docs: https://platform.claude.com/docs/en/build-with-claude/citations

If you reply with the bottleneck you are working through, I can point you to the closest Claude pattern.

Happy building,

--Chris Fregly
Building with Claude
