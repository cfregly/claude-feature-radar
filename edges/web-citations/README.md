# Edge: Web citations, a verifiable quote from the source

Part of [claude-feature-radar](../../README.md). This is a measured grounding-fidelity edge for live
web research: Claude hands back the verbatim source quote, not just a link.

## What It Is

Claude's web_search tool returns each web-grounded claim with a `web_search_result_location` citation:
the `url`, the `title`, and the verbatim `cited_text` (up to 150 characters of the actual source
passage), and the citation fields cost no input or output tokens. So a claim arrives self-verifying,
the quote is in the response, lifted from the page. The competitors cite a URL but make you re-fetch
the page to check the claim.

For a research, monitoring, or compliance agent over live web sources, this is the difference between
an auditable pipeline (every claim deep-links to the exact sentence) and a manual one.

## The Measured Proof

Run: `make web-citations`, 2026-06-19, the same 3 web-research questions on every vendor, each forced
to search the live web. The gate is how many returned citations carry a verbatim quote from the source.

| arm | answered | web citations | with a verbatim source quote |
|---|:---:|:---:|:---:|
| Claude Sonnet 4.6, web_search | 3/3 | 9 | 9 |
| OpenAI GPT-5.5, web_search | 3/3 | 3 | 0 |
| Gemini 3.1 Pro, Google Search | 3/3 | 6 | 0 |

All three answered and cited web URLs. Only Claude returned the verbatim source quote on every
citation. OpenAI's `url_citation` and Gemini's grounding segments index the model's own answer text
and carry only a URL and title, so a claim is not checkable without re-fetching the page. Machine
receipt: [`receipt.json`](receipt.json).

## Honest Scope

- The win is the verifiable source quote returned with the citation, not the presence of a citation
  (all three cite URLs).
- This uses the basic web_search tag, where the citation object is returned directly. The
  dynamic-filtering web tags route web content through code execution, which trades the citation for
  pre-context token filtering, a separate cost-axis tradeoff.
- `cited_text` is capped at about 150 characters of the source passage.

## Run It Yourself

```bash
git clone https://github.com/cfregly/claude-feature-radar && cd claude-feature-radar
make setup
make compare-deps
cp .env.example .env   # paste ANTHROPIC_API_KEY, OPENAI_API_KEY, and GEMINI_API_KEY
make web-citations     # cents-scale, searches the live web on every arm
```

`make web-citations` writes the latest local machine receipt to `data/last_web_citations.json`.

Sources, fetched 2026-06-19:

- Claude web search tool: https://platform.claude.com/docs/en/agents-and-tools/tool-use/web-search-tool
- OpenAI web search: https://developers.openai.com/api/docs/guides/tools-web-search
- Gemini Google Search grounding: https://ai.google.dev/gemini-api/docs/google-search
