Subject: Congrats on YC! Page-linked accuracy over regulation PDFs

Hey Gustav,

Congrats on YC.

I'm Chris Fregly on Anthropic's Applied AI team, focused on startups. I spend a lot of time working
through the practical bottlenecks that show up after the first useful agent demo.

I saw Complir is building AI agents for compliance and regulatory monitoring. The Claude pattern that
maps to that workload is page-linked PDF evidence for compliance agents whose answers need to survive
reviewer scrutiny.

For compliance, the reviewer needs a one-click jump to the exact page behind the answer. Claude
Citations can do that on the PDF you hand it directly in the request, with no hosted vector store and
no page resolver to write.

```python
doc = {
    "type": "document",
    "source": {"type": "base64", "media_type": "application/pdf", "data": pdf_b64},
    "citations": {"enabled": True},
}
```

Using my API key, over a five-page agreement PDF with five questions, Claude answered 5/5 and
returned a page pointer that resolved to the correct page 5/5. That run cost $0.05.

Full brief, demo GIF, code, and sample output: https://github.com/cfregly/claude-feature-hits/tree/main/pdf_citations

Run it in about a minute for $0.05:

```bash
git clone https://github.com/cfregly/claude-feature-hits && cd claude-feature-hits
# Get an API key: https://console.anthropic.com/
export ANTHROPIC_API_KEY=your-api-key
make pdf_citations
```

To try it on your own data, edit `pdf_citations/run.py` with a regulation PDF and the questions your
agent needs to answer.

The security follow-up for Complir is separate but connected: CMEK for eligible enterprise data
boundaries, the Compliance API for audit and monitoring workflows, and connector controls for the
systems your agent reads from. I would treat accuracy and security as one compliance story: answer
with source pointers, then prove who accessed what and where the data boundary sits.

If page-linked regulatory answers are not the sharpest Complir bottleneck right now, send me the one
that is and I can map it to the closest Claude pattern.

Happy building,

--Chris Fregly
Applied AI, Startups, Anthropic
