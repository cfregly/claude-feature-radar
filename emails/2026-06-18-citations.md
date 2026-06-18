Subject: Congrats on YC! 🎉 A cool Claude feature for answering over your users' docs

Hey {first_name},

Congrats on getting into YC! Quick tip if your app answers questions over your users' own docs.

When someone asks a question and your app answers from their contracts, tickets, or research, the thing that builds trust is letting them click the answer and land on the exact sentence it came from. The usual way to build that is to have the model repeat the quote, then search the document for that text. The moment the model rewords the quote even slightly, the search finds nothing and the citation silently breaks, and now it is your code to maintain.

[Citations](https://platform.claude.com/docs/en/build-with-claude/citations) hands you the pointer instead. Turn it on, and every answer comes back with the document, the exact character range, and the verbatim quote, and Claude guarantees the pointer lands on real text. No matching code on your side.

It is one setting on the document you already pass:

```python
response = client.messages.create(
    model="claude-haiku-4-5",
    messages=[{"role": "user", "content": [
        { "type": "document",
          "source": {"type": "text", "media_type": "text/plain", "data": your_doc},
          "citations": {"enabled": True} },                  # add this line
        {"type": "text", "text": "What is the refund window?"},
    ]}],
)
```

Each answer block comes back with a `char_location` pointer (the document, a start and end character index, and the quote). You resolve it in one line: `source[start:end] == cited_text`. By the documented guarantee, it always holds.

The example asks 8 questions over 3 short docs and resolves every pointer the run returns in your own code, so you watch the guarantee hold instead of trusting it. The `cited_text` is free too, it does not count toward your output tokens.

See it run (about two minutes):

```
git clone {repo_url} && cd claude-feature-briefs
export ANTHROPIC_API_KEY=your-key
make citations        # the example, $0.06
```

To run it on your own docs, drop your `.txt` files into [citations/docs/]({repo_url}/tree/main/citations/docs) and edit the question list at the top of [cite.py]({repo_url}/blob/main/citations/cite.py), then run `make citations` again.

More: the [Citations cookbook](https://platform.claude.com/cookbook/misc-using-citations) is a runnable notebook over text, PDFs, and custom content.

Happy building! 🚀
Chris Fregly
Applied AI, Startups @ Anthropic
