Subject: Congrats on YC! A Claude web search trick for sourced answers

Hey {first_name},

Congrats on the batch. Quick builder tip if your product reads live web pages for users: pin the exact source sentence to every claim from day one, before the "where did this come from?" tickets start piling up.

Here is the problem. Say you ship a competitor-pricing watcher or a market-research agent that reads live pages and reports back. A teammate sees a flagged number and asks where it came from. A bare URL sends them back to re-read the whole page, and a number nobody can trace in seconds is a number nobody trusts.

Claude's web search tool fixes this. Every web-grounded claim comes back with the verbatim source sentence already attached, so the reader checks the exact line in seconds. The one change is the tool you pass:

```python
tools=[{"type": "web_search_20260209", "name": "web_search"}]  # each claim returns its source quote
```

The measured result, on my key: on 3 live web-research questions, every Claude citation (9/9) came back with the verbatim source quote attached. Live cost $0.115. Those citation fields (the quote, the title, the URL) cost no input or output tokens either.

How it compares, on the same 3 questions:

| Model  | Citations with a source quote |
|--------|-------------------------------|
| Claude | 9 of 9                        |
| OpenAI | 0                             |
| Gemini | 0                             |

Run it yourself. About $0.12, under a minute:

```
git clone https://github.com/cfregly/claude-feature-hits && cd claude-feature-hits
make web_citations
```

Want the whole table, not just the Claude side? Set `OPENAI_API_KEY` and `GEMINI_API_KEY` too and run `make web_citations COMPARE=1`. It runs Claude, OpenAI, and Gemini side by side on the same questions, so you see the verbatim source quote come back from Claude and not the others, on your own keys for a few cents.

To try your own questions, edit the `QUESTIONS` list in `web_citations/run.py` and run it again.

Happy building!
{your_name}
Building with Claude
