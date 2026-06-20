# Verifiable source citations for every answer

![demo](demo.gif)

When your app answers over a user's own documents (contracts, policies, support tickets), the answer is only as good as the source behind it. Claude's Citations feature returns a structured pointer for every claim: the document, a character range, and the verbatim quote at that range. You verify each answer in your own code instead of trusting it.

## What you get

Set `citations.enabled` on each document and the API returns a `char_location` for every claim, a per-character pointer back into the source text. `source[start_char_index:end_char_index]` is exactly the `cited_text` the model handed back, and the quote does not count against your output tokens.

```python
content = [
    {"type": "document", "source": {...}, "citations": {"enabled": True}},  # one flag, per-character pointers back
    {"type": "text", "text": question},
]
msg = client.messages.create(model="claude-haiku-4-5", max_tokens=400,
                            messages=[{"role": "user", "content": content}])
# every citation resolves: source[c.start_char_index:c.end_char_index] == c.cited_text
```

Measured on Haiku 4.5: all 8 answers came back with a `char_location` pointer that resolves. `source[start:end]` equals the `cited_text`, with the quote free of output tokens. Live cost $0.011.

## Claude vs OpenAI vs Gemini

Claude returns a per-character pointer into the user's own document. Among the three, only Claude returns char-level: Gemini File Search resolves to a page, OpenAI file_search to a file (their docs, verified 2026-06-19). Char-level vs page-level vs file-level is the difference between checking the exact sentence and re-reading the file.

## Run it (about $0.01)

```
git clone https://github.com/cfregly/claude-feature-hits && cd claude-feature-hits
export ANTHROPIC_API_KEY=your-key   # https://console.anthropic.com/
make citations        # answer the questions and resolve every pointer, about a minute
```

## Run it on your own data

Drop your `.txt` files into `citations/docs/`, edit `QUESTIONS` at the top of `citations/cite.py`, and run `make citations` again.

## Learn more

- [Citations docs](https://platform.claude.com/docs/en/build-with-claude/citations)
