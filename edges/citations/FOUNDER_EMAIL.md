# Founder email: the Citations edge

Paste into a Google Doc or your sending tool. Plain text, one link.

---

**Subject:** Congrats on YC! 🎉 A Claude pattern for answers over user docs

Hey {first_name},

Congrats on the YC batch. Quick builder note if your product answers questions over your users' own documents: contracts,
policies, tickets, research, support docs, or clinical notes.

The hard part is not writing an answer. The hard part is making the answer shippable. A user needs to
click through to the exact sentence behind the claim, and your product needs that pointer to be real.

Claude Citations gives you that pointer from the API. Turn it on per document and Claude returns the
answer with a structured source range plus the verbatim quote from that range. Your app can render the
click-through without writing a resolver.

```python
content = [
    {
        "type": "document",
        "source": {"type": "text", "media_type": "text/plain", "data": doc_text},
        "citations": {"enabled": True},
    },
    {"type": "text", "text": question},
]
```

I measured it on 8 questions over 3 documents, with every number read off the real API `usage`
object.

- Claude with Citations: 8 of 8 pointers resolve.
- The API does the resolving.
- The cited quote is free of output tokens.
- The run used 308 output tokens.

The edge is precise: Claude returns a per-character source pointer into your document, with an
API-extracted verbatim quote and no resolver code to own.

Run it yourself:

```bash
git clone https://github.com/cfregly/claude-feature-briefs && cd claude-feature-briefs
export ANTHROPIC_API_KEY=your-key
make citations
```

$0.06 and a couple of minutes, every number read off the real API. To run it on your own documents,
drop your `.txt` files into `citations/docs/`, edit the questions at the top of `citations/cite.py`,
and run `make citations` again.

Reply if you want a hand wiring it in.

Go build! 🚀

{your_name}
Building with Claude

---

### Why it is built this way

- **The hook does not overclaim.** An earlier version of this benchmark asked the competitor models
  to emit the character offset themselves, scored that 0/8, and called it a competitor failure. A
  scrutiny panel caught it: a tokenizer cannot count characters, and no founder would build it that
  way. The email now rests on the edge that survives: the guaranteed in-API per-character pointer,
  free of output tokens, returned by the API with no resolver code to own, no beta header.
- **The numbers are receipts.** 8/8, the output-token count, and the six-cent reproduction cost all
  come from `make citations` (`edges/citations/sample.txt`), not from memory.
