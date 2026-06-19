# Edge: Paraphrase resolution, the citation pointer that survives an own-words answer

Part of [claude-feature-radar](../../README.md). This is the paraphrase-robustness arm of the citations edge. It measures the case the clean-text test did not: when the model answers in its own words, does the source pointer still resolve?

## What It Is

A product that answers over a user's own documents usually wants readable, paraphrased prose, and a deep-link to the exact source so a person can verify before acting. With `citations: {"enabled": true}` on the supplied documents, Claude attaches a pointer whose `cited_text` is the verbatim source span the API extracted, so `source[start:end] == cited_text` resolves no matter how the answer is worded. The do-it-yourself path (ask the model for a supporting quote, then `source.find(quote)`) returns -1 the moment the quote is paraphrased, and the citation is silently dropped.

## The Measured Proof

Run: `make citations-paraphrase`, 2026-06-19, 8 questions over 3 text documents and one inline PDF. Every arm answers in its own words.

| arm | mechanism | answered | resolves | silent drops | output tokens | cost |
|---|---|:---:|:---:|:---:|---:|---:|
| claude+citations:sonnet | API citations | 8/8 | 8/8 | 0 | 594 | $0.2391 |
| claude DIY:sonnet | DIY str.find | 8/8 | 2/8 | 6 | 708 | $0.0281 |
| openai DIY:gpt-mid | DIY str.find | 7/8 | 0/8 | 8 | 453 | $0.0196 |
| gemini DIY:gem-flash | DIY str.find | 8/8 | 0/8 | 8 | 9,306 | $0.0916 |

Claude Citations resolved every answer's pointer by guarantee, with zero hosted or persisted objects, including a page pointer into the directly-supplied PDF. The DIY arms answered the same questions but dropped pointers under paraphrase, because the paraphrased supporting sentence is not a verbatim substring.

Full receipt: [`sample.txt`](sample.txt). Machine receipt: [`receipt.json`](receipt.json).

## Honest Scope

- On clean verbatim quotes the DIY path resolves about as well on every vendor. The citations edge measures that case. This arm measures the paraphrase regime, where the model answers in its own words.
- The grader is deterministic: `source[start:end] == cited_text` for Citations, `source.find(quote)` for the DIY arms, the same gate on every arm.
- Citations cannot be combined with Structured Outputs. The two return a 400 together, so a grounded answer here is free text.

## Run It Yourself

```bash
git clone https://github.com/cfregly/claude-feature-radar && cd claude-feature-radar
make setup
make compare-deps
cp .env.example .env   # paste ANTHROPIC_API_KEY, OPENAI_API_KEY, and GEMINI_API_KEY
make citations-paraphrase   # cents-scale
```

Sources:

- Claude citations: https://platform.claude.com/docs/en/build-with-claude/citations
- Claude PDF support: https://platform.claude.com/docs/en/build-with-claude/pdf-support
- OpenAI file search: https://developers.openai.com/api/docs/guides/tools-file-search
- Gemini file search: https://ai.google.dev/gemini-api/docs/file-search
