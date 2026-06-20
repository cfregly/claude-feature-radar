Subject: Congrats on YC! A Claude web search trick for verifiable answers

Hey {first_name},

Congrats on the batch. If your product reads live web pages for users, one quick tip: pin the source quote to every claim from day one, before the support tickets asking "where did this come from?" pile up.

Here is the problem. Say your agent watches a regulator's rules page or a competitor's pricing page and flags changes. When a user asks where a flagged claim came from, a bare URL sends them back to re-read the whole page. That is slow, and it is the kind of thing that erodes trust in an agent fast.

Claude's web search tool fixes this. Every web-grounded claim comes back with the verbatim source quote already attached, so the reader checks the exact sentence in seconds. The one change is adding the tool to your request:

```python
tools=[{"type": "web_search_20250305", "name": "web_search", "max_uses": 4}]
# each text block's .citations carries web_search_result_location with .cited_text
```

The measured result, on my key: I ran 3 web-research questions on claude-sonnet-4-6 and all 9 returned web citations carried a verbatim quote from the source page, for $0.12. Those citation fields (the quote, the title, the URL) cost no input or output tokens either.

Run it yourself: clone the repo and run `make web_citations` (about $0.12, under a minute). To try your own questions, edit the `QUESTIONS` list in `web_citations/run.py` and run `python web_citations/run.py`.

The full brief, code, and a short demo:
https://github.com/cfregly/claude-feature-hits/blob/main/web_citations/README.md

Happy building! 🚀
{your_name}
Building with Claude
