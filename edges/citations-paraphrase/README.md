# Edge: Paraphrase resolution, what the citation guarantee is worth

Part of [claude-feature-radar](../../README.md). This measures the case the clean-text citations test did not: when the model answers in its own words, does the source pointer still resolve, and is the do-it-yourself `str.find` drop a robust cross-vendor gap or a within-Claude convenience?

## What It Is

A product that answers over a user's own documents usually wants readable, paraphrased prose, and a deep-link to the exact source so a person can verify before acting. With `citations: {"enabled": true}` on the supplied documents, Claude attaches a pointer whose `cited_text` is the verbatim source span the API extracted, so `source[start:end] == cited_text` resolves no matter how the answer is worded, with zero resolver code and the quote free of output tokens. The do-it-yourself path (ask the model for a supporting quote, then `source.find(quote)`) can return -1 when the quote is paraphrased or re-wrapped, a silent drop with no signal.

## The Measured Proof

Run: `make citations-paraphrase`, 2026-06-19, 8 questions over 3 text documents and one inline PDF, every arm answering in its own words. Claude runs Sonnet, the competitors run their frontier tier (run the stronger competitor before a correctness claim).

| arm | mechanism | answered | resolves | silent drops | output tokens | cost |
|---|---|:---:|:---:|:---:|---:|---:|
| claude+citations:sonnet | API citations | 8/8 | 8/8 | 0 | 572 | $0.2388 |
| claude DIY:sonnet | DIY str.find | 8/8 | 8/8 | 0 | 692 | $0.0285 |
| openai DIY:gpt-top | DIY str.find | 8/8 | 8/8 | 0 | 881 | $0.0531 |
| gemini DIY:gem-pro | DIY str.find | 5/8 | 8/8 | 0 | 5,712 | $0.0795 |

Claude Citations resolved every answer's pointer by guarantee, on the lower Sonnet tier, with zero hosted or persisted objects, including a page pointer into the directly-supplied PDF. The frontier DIY arms also resolved: asked for a supporting sentence, they returned verbatim quotes even while paraphrasing the answer, and a whitespace-tolerant `str.find` resolves those. So on this workload, resolution is parity against a competent DIY resolver.

Verdict: `promotable_edge: false`. The durable value Claude Citations gives a founder here is the guarantee, the free `cited_text`, and zero resolver code, a within-Claude value-add, not a cross-vendor capability gap. The robust cross-vendor PDF win, where OpenAI and Gemini return no citation pointer at all for a directly-supplied inline PDF without a hosted vector store, is measured in the [pdf-citations](../pdf-citations/README.md) and [grounding-stack](../grounding-stack/README.md) edges.

Full receipt: [`sample.txt`](sample.txt). Machine receipt: [`receipt.json`](receipt.json).

## The glue code the guarantee saves you

Reading the PDF natively, every arm is asked for a verbatim supporting quote. A model quotes the sentence as the PDF renders it (line-wrapped), so the developer's naive `str.find` in their stored canonical text can return -1, a silent drop. Here is the developer's naive `str.find`, the one-line whitespace-normalized `str.find`, and Claude's `page_location` guarantee, side by side.

| arm | naive str.find | + whitespace-normalized | Claude page_location guarantee |
|---|:---:|:---:|:---:|
| claude+citations:sonnet | - | - | 5/5 |
| claude DIY:sonnet | 5/5 | 5/5 | - |
| openai DIY:gpt-top | 5/5 | 5/5 | - |
| gemini DIY:gem-pro | 5/5 | 5/5 | - |

The naive `str.find` happened to resolve every quote this run, but it is one PDF-rendering artifact (a line-wrap, a curly quote) away from a silent -1. 

Live model output varies run to run, so here is the mechanism shown deterministically, grounded in the PDF's own line-wrapping (no model call). Take this real sentence:

> Overage seats beyond the 50 included seats are billed at 12 US dollars per seat per month.

Rendered the way the PDF wraps it (with an interior line break), then located three ways against the developer's stored canonical text:

| locate strategy | result |
|---|:---:|
| developer naive `str.find` | **DROP (-1, silent)** |
| + one-line `' '.join(quote.split())` | resolves |
| Claude `page_location` guarantee | resolves |

Claude's `page_location` resolved every quote by guarantee with zero resolver code. That normalization is exactly what the guarantee buys: the glue a founder would otherwise write and maintain, and the citations they silently lose until they do.

## Honest Scope

- The `str.find` drop is not robust against the best competitor config. A frontier model returns a verbatim quote even while paraphrasing the answer, and a whitespace-tolerant `str.find` resolves it, so resolution is parity with a competent DIY resolver. The drop appears only with a weaker model or a naive resolver.
- The grader is deterministic: `source[start:end] == cited_text` for Citations, `source.find(quote)` for the DIY arms, the same gate on every arm.
- Citations cannot be combined with Structured Outputs. The two return a 400 together, so a grounded answer here is free text.

## Run It Yourself

```bash
git clone https://github.com/cfregly/claude-feature-radar && cd claude-feature-radar
make setup
make compare-deps
cp .env.example .env   # paste ANTHROPIC_API_KEY, OPENAI_API_KEY, and GEMINI_API_KEY
make citations-paraphrase   # about $0.74, under a minute
```

Sources:

- Claude citations: https://platform.claude.com/docs/en/build-with-claude/citations
- Claude PDF support: https://platform.claude.com/docs/en/build-with-claude/pdf-support
- OpenAI file search: https://developers.openai.com/api/docs/guides/tools-file-search
- Gemini file search: https://ai.google.dev/gemini-api/docs/file-search
