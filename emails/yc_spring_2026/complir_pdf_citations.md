Subject: Congrats on YC! Page-linked answers over regulation PDFs

Hey Gustav,

First of all, congrats on the batch! Very exciting!!

My name is Chris Fregly, and I'm on the Applied AI team here at Anthropic. I focus on helping AI startups like Complir get past the bottlenecks that show up once agents move from demo to product.

I saw Complir is building AI agents for compliance and regulatory monitoring. From one former founder to an active founder, builder to builder, I wanted to share a Claude pattern for compliance agents that need every answer tied to a page a reviewer can check.

For compliance, the reviewer needs a one-click jump to the exact page behind the answer. Claude Citations can do that on the PDF you hand it directly in the request, with no hosted vector store and no page resolver to write.

```python
doc = {
    "type": "document",
    "source": {"type": "base64", "media_type": "application/pdf", "data": pdf_b64},
    "citations": {"enabled": True},  # page pointers plus quoted source text
}
```

Using my API key, over a five-page agreement PDF with five questions, Claude answered 5/5 and returned a page pointer that resolved to the correct page 5/5. That run cost $0.046.

Full brief, demo GIF, code, and sample output: https://github.com/cfregly/claude-feature-hits/tree/main/pdf_citations

Run it in about a minute for about $0.05:

```bash
git clone https://github.com/cfregly/claude-feature-hits && cd claude-feature-hits
# Starter credits if you need an API key: https://claude.com/offers?offer_code=bdfcc786-eb41-44f3-9190-e29e6e38209c&signup_code=3a6e0453a611a2c4bd79968fa98e3471
export ANTHROPIC_API_KEY=your-api-key
make pdf_citations
```

To try it on your own data, edit `pdf_citations/run.py` with a regulation PDF and the questions your agent needs to answer.

If I guessed the wrong bottleneck, reply with the real one and I can point you to the closest Claude pattern.

Happy building,

--Chris Fregly
Applied AI, Anthropic
fellow Claude builder and former AI startup founder
