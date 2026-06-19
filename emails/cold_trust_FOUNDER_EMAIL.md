Subject: A Claude primitive for grounded answers your users can verify

Hey {first_name},

Congrats on the batch. Quick note if your product answers questions over your users' own documents, a
contract, a policy, a clinical note, a financial filing.

The hard part is trust. A user needs to click from the answer straight to the sentence it came from,
and an answer with no checkable source is a support ticket, or in a regulated space, worse.

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
the source (8 of 8), and the quote costs no output tokens. The do-it-yourself path, asking the model
for a quote and locating it with str.find, breaks the moment the model answers in its own words.

Run it: `make citations` (about $0.06 on your key). Point it at your own documents to see your resolve
rate.

Docs: https://platform.claude.com/docs/en/build-with-claude/citations

Go build,
{your_name}
Building with Claude
