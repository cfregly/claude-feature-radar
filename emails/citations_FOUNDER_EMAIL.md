Subject: Congrats on YC! 🎉 A Claude pattern for answers over user docs

Hey {first_name},

Congrats on YC.

Quick builder note if your product answers questions over your users' own documents: contracts,
policies, tickets, research, support docs, or clinical notes.

The hard part is not writing an answer. The hard part is making the answer shippable. A user needs to
click through to the exact sentence behind the claim, and your product needs that pointer to be real.

[Citations](https://platform.claude.com/docs/en/build-with-claude/citations) gives you that pointer
from the API. Turn it on per document and Claude returns the answer with a structured source range
plus the verbatim quote from that range. Your app can render the click-through without writing a
resolver.

```python
content = [
    {
        "type": "document",
        "source": {"type": "text", "media_type": "text/plain", "data": doc_text},
        "citations": {"enabled": True},
    },
    {"type": "text", "text": question},
]
msg = client.messages.create(
    model="claude-haiku-4-5",
    max_tokens=400,
    messages=[{"role": "user", "content": content}],
)
```

Want to watch it first, no clone needed? The brief opens with a gif of the run:
https://github.com/cfregly/claude-feature-briefs/blob/main/citations/README.md

See it run:

```bash
git clone https://github.com/cfregly/claude-feature-briefs && cd claude-feature-briefs
export ANTHROPIC_API_KEY=your-key
make citations     # resolve every pointer, $0.06
```

To run it on your own documents, drop your `.txt` files into `citations/docs/`, edit the questions at
the top of `citations/cite.py`, and run `make citations` again.

Go build! 🚀
{your_name}
Building with Claude
