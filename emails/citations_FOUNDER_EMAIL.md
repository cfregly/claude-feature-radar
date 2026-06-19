Subject: Congrats on YC! 🎉 A cool Claude feature to help you build

Hey {first_name},

Congrats on getting into YC! Quick tip if your app answers questions over your users' own documents.

When you answer over a contract, a policy, or a support doc, the answer is only as trustworthy as the
source behind it. [Citations](https://platform.claude.com/docs/en/build-with-claude/citations) gives you a source pointer for every answer that you can
check in your own code: the document, a character range, and the verbatim quote at that range. The
pointer is guaranteed to resolve, and the quote is free of output tokens.

Turn it on per document, then verify in your own code:

```python
content = [
    {"type": "document",
      "source": {"type": "text", "media_type": "text/plain", "data": doc_text},
      "citations": {"enabled": True}},          # add this
    {"type": "text", "text": question},
]
msg = client.messages.create(model="claude-haiku-4-5", max_tokens=400,
                            messages=[{"role": "user", "content": content}])
# every citation resolves: source[c.start_char_index:c.end_char_index] == c.cited_text
```

Want to watch it first, no clone needed? The brief opens with a gif of the run:
https://github.com/cfregly/claude-feature-briefs/blob/main/citations/README.md

See it run (about a minute):

```
git clone https://github.com/cfregly/claude-feature-briefs && cd claude-feature-briefs
export ANTHROPIC_API_KEY=your-key
make citations     # answer the questions and resolve every pointer, $0.01
```

To run it on your own documents, drop your `.txt` files into `citations/docs/`, edit the questions at
the top of `citations/cite.py`, and run `make citations` again.

Happy building! 🚀
{your_name}
Building with Claude
