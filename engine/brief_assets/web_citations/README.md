# Verifiable web answers with Claude's web search citations

![demo](demo.gif)

Your agent watches live web sources, a regulator's rules page, a competitor's pricing page, a standards spec, and flags claims a human has to trust. When a teammate asks "where does it say that?", the agent hands back a URL and they go re-read the whole page. Claude's web search tool returns each web-grounded claim with the verbatim source quote attached, so the reader checks the exact sentence in seconds.

## What you get

Every web-grounded claim comes back as a `web_search_result_location` citation that carries the `url`, the `title`, and `cited_text`, up to 150 characters of the actual source passage. The claim arrives self-verifying: the quote is right there in the response, lifted from the page. In a measured run of 3 web-research questions on claude-sonnet-4-6, all 9 returned web citations carried a verbatim source quote, for $0.12. And those citation fields cost nothing: `cited_text`, `title`, and `url` do not count toward input or output tokens.

```python
response = client.messages.create(
    model="claude-sonnet-4-6",
    max_tokens=700,
    tools=[{"type": "web_search_20250305", "name": "web_search", "max_uses": 4}],  # add this
    messages=[{"role": "user", "content": "Search the web: how tall is the Burj Khalifa? Cite a source."}],
)
# each text block's .citations carries web_search_result_location with .cited_text  # add this
```

## Run it (about $0.12)

```
make web_citations
```

## Run it on your own questions

Edit the `QUESTIONS` list in `web_citations/run.py`, then run:

```
python web_citations/run.py
```

Or run the cheap self-test that asserts every web citation carries a source quote (about $0.05):

```
python web_citations/run.py --check
```

## Learn more

Web search tool: https://platform.claude.com/docs/en/agents-and-tools/tool-use/web-search-tool
