# Sourced web answers with Claude's web search citations

![demo](demo.gif)

Your agent reads live web pages and reports back, a competitor-pricing watcher, a market-research bot, a rules-page monitor. When a teammate asks "where does it say that?", a bare URL means re-reading the whole page. Claude's web search tool returns each web-grounded claim with the verbatim source sentence attached, so the reader checks the exact line in seconds.

## What you get

Every web-grounded claim arrives as a citation carrying the source `url`, the `title`, and `cited_text`, the actual passage lifted from the page. The claim is self-verifying: the quote is right there in the response. The citation fields cost nothing either, `cited_text`, `title`, and `url` do not count toward input or output tokens.

```python
tools=[{"type": "web_search_20260209", "name": "web_search"}]  # each claim returns its source quote
```

Measured: on 3 live web-research questions, every Claude citation (9 of 9) came back with the verbatim source quote attached. Live cost $0.115.

## Claude vs OpenAI vs Gemini

Same 3 live web-research questions, each platform on its best web-search setup:

| Model  | Citations with a source quote |
|--------|-------------------------------|
| Claude | 9 of 9                        |
| OpenAI | 0                             |
| Gemini | 0                             |

## Run it (about $0.12)

```
export ANTHROPIC_API_KEY=sk-ant-...   # https://console.anthropic.com/
make web_citations                    # build the venv, install anthropic, answer web questions with a source quote each
```

About a minute, $0.115 on my run. `make web_citations` is self-bootstrapping: it creates `.venv`, installs `anthropic`, and runs the self-test that asserts every web citation carries a verbatim source quote.

To reproduce the whole table on your own keys, not just the Claude side:

```
export ANTHROPIC_API_KEY=sk-ant-...
export OPENAI_API_KEY=your-key
export GEMINI_API_KEY=your-key
make web_citations COMPARE=1          # installs the optional OpenAI and Gemini SDKs, runs all three arms
```

`COMPARE=1` installs `requirements-compare.txt` (the OpenAI and Gemini SDKs) into the same `.venv` and runs the same questions over the live web on each platform, so you see the verbatim source quote come back from Claude and not from the others. Without it, the brief runs the Claude side alone on one dependency.

## Run it on your own data

Edit the `QUESTIONS` list in `web_citations/run.py`, then run `make web_citations` again.

## Learn more

Web search tool: https://platform.claude.com/docs/en/agents-and-tools/tool-use/web-search-tool
