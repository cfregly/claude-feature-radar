Subject: Congrats on YC! Verifiable answers over user docs

Hey {first_name},

Congrats on getting into YC. Quick tip if your app answers questions over your users' own documents.

When you answer over a contract, a policy, or a support ticket, users need the source behind each answer. [Citations](https://platform.claude.com/docs/en/build-with-claude/citations) gives you that: every answer comes back with a pointer into the source you can check in your own code, the document, a character range, and the verbatim quote at that range.

Turn it on per document, then verify in your own code:

```python
content = [
    {"type": "document", "source": {...}, "citations": {"enabled": True}},  # one flag, per-character pointers back
    {"type": "text", "text": question},
]
msg = client.messages.create(model="claude-haiku-4-5-20251001", max_tokens=400,
                            messages=[{"role": "user", "content": content}])
# every citation resolves: source[c.start_char_index:c.end_char_index] == c.cited_text
```

I ran it using my API key over a small doc set. On Haiku 4.5, all 8 answers came back with a pointer that resolves: the source text at that character range equals the quoted text, and the quote does not count against output tokens. Live cost about $0.01.

The operational win is simple: the API returns the structured pointer and the verbatim `cited_text` in the same response, so your app can verify the source span without writing a separate quote resolver or paying output tokens for the quote.

Reproduce it in about a minute for about $0.01. One clone, one file to edit:

```
git clone https://github.com/cfregly/claude-feature-hits && cd claude-feature-hits
export ANTHROPIC_API_KEY=your-api-key
make citations     # answer the questions and resolve every pointer, $0.01
```

Full brief, demo GIF, code, and sample output: https://github.com/cfregly/claude-feature-hits/tree/main/citations

Docs: https://platform.claude.com/docs/en/build-with-claude/citations

To run it on your own documents, drop your `.txt` files into `citations/docs/`, edit the questions at the top of `citations/cite.py`, and run `make citations` again.

Happy building,
{your_name}
Building with Claude
