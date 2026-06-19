# Edge: Citations, Claude vs the other models on grounding a user's own documents

Part of [claude-feature-radar](../../README.md). The headline test pits Claude's citation feature against OpenAI's `file_search` and Gemini's `File Search` over the same user documents. A secondary arm measures the do-it-yourself `str.find` baseline under a paraphrased answer.

## What It Is

A product that answers over a user's own documents (a contract, a report, the app's wiki) needs to deep-link each answer to the exact source so a person can verify before acting. With `citations: {"enabled": true}` on the supplied documents, Claude attaches a pointer whose `cited_text` is the verbatim source span the API extracted, guaranteed to resolve, with zero resolver code, the quote free of output tokens, and no copy of the user's data leaving the request. The competitors' citation tools cannot cite a directly-supplied document at all: they require uploading it to a hosted vector store first.

## The Measured Proof: Claude vs the other models

Run: `make citations-paraphrase`, 2026-06-19, 6 questions over 3 user documents. Every vendor answers the same questions over the same documents and must return a citation pointer INTO those documents with its real citation tool. Claude runs Sonnet, the competitors run their frontier tier (run the stronger competitor before a correctness claim).

| arm | citation tool | pointer granularity | resolves | cites right doc | hosted objects (copies of the user's data) | cost |
|---|---|:---:|:---:|:---:|:---:|---:|
| claude citations:sonnet | Claude Citations (inline) | char-span | 6/6 | 6/6 | 0 | $0.0237 |
| openai file_search:gpt-top | OpenAI file_search | file-level | 6/6 | 6/6 | 4 | $0.0670 |
| gemini File Search:gem-pro | Gemini File Search | chunk-level | 6/6 | 6/6 | 4 | $0.0230 |

Claude returns a structured, API-guaranteed-to-resolve **char-span** pointer into the user's directly-supplied documents with **zero hosted objects**, so the data never leaves the request. OpenAI `file_search` and Gemini `File Search` **cannot cite a directly-supplied document**: they require uploading it to a hosted vector store first (4/4 hosted objects, 8 in total, a third-party copy of the user's data), and even then the citation is file-level (OpenAI) or chunk-level (Gemini), never a guaranteed char span into the source. Verified against the vendors' live docs on 2026-06-19. Because this is an API-surface gap, it holds at the competitors' frontier tier, it is not a model contest.

Verdict: `promotable_edge: true`.

Full receipt: [`sample.txt`](sample.txt). Machine receipt: [`receipt.json`](receipt.json).

## The glue code the guarantee saves you

Reading the PDF natively, every arm is asked for a verbatim supporting quote. A model quotes the sentence as the PDF renders it (line-wrapped), so the developer's naive `str.find` in their stored canonical text can return -1, a silent drop. Here is the developer's naive `str.find`, the one-line whitespace-normalized `str.find`, and Claude's `page_location` guarantee, side by side.

| arm | naive str.find | + whitespace-normalized | Claude page_location guarantee |
|---|:---:|:---:|:---:|
| claude+citations:sonnet | - | - | 5/5 |
| claude DIY:sonnet | 5/5 | 5/5 | - |
| openai DIY:gpt-top | 4/5 | 5/5 | - |
| gemini DIY:gem-pro | 5/5 | 5/5 | - |

The developer's naive `str.find` silently dropped 1 of 5 PDF citation(s) on line-wrap whitespace, and the one-line `' '.join(quote.split())` recovered them. 

Live model output varies run to run, so here is the mechanism shown deterministically, grounded in the PDF's own line-wrapping (no model call). Take this real sentence:

> Overage seats beyond the 50 included seats are billed at 12 US dollars per seat per month.

Rendered the way the PDF wraps it (with an interior line break), then located three ways against the developer's stored canonical text:

| locate strategy | result |
|---|:---:|
| developer naive `str.find` | **DROP (-1, silent)** |
| + one-line `' '.join(quote.split())` | resolves |
| Claude `page_location` guarantee | resolves |

Claude's `page_location` resolved every quote by guarantee with zero resolver code. That normalization is exactly what the guarantee buys: the glue a founder would otherwise write and maintain, and the citations they silently lose until they do.

## Secondary: the do-it-yourself `str.find` baseline

Without any citation feature you would ask the model for a supporting quote and resolve it with `source.find(quote)`. Over 8 questions (with one inline PDF) where every arm answers in its own words:

| arm | mechanism | answered | resolves | silent drops | output tokens | cost |
|---|---|:---:|:---:|:---:|---:|---:|
| claude+citations:sonnet | API citations | 8/8 | 8/8 | 0 | 629 | $0.2397 |
| claude DIY:sonnet | DIY str.find | 8/8 | 8/8 | 0 | 655 | $0.0280 |
| openai DIY:gpt-top | DIY str.find | 8/8 | 8/8 | 0 | 966 | $0.0557 |
| gemini DIY:gem-pro | DIY str.find | 5/8 | 8/8 | 0 | 5,945 | $0.0823 |

Claude Citations resolved every answer's pointer by guarantee, on the lower Sonnet tier, with zero hosted or persisted objects, including a page pointer into the directly-supplied PDF. The frontier DIY arms also resolved: asked for a supporting sentence, they returned verbatim quotes even while paraphrasing the answer, and a whitespace-tolerant `str.find` resolves those. So on this workload, resolution is parity against a competent DIY resolver.

## Honest Scope

- The headline win is feature vs feature and is an API-surface gap (the competitors cannot return a structured, guaranteed-resolve pointer into a directly-supplied document without a hosted store), so it survives their frontier models.
- The secondary `str.find` baseline drop is NOT robust: a frontier model asked for a verbatim quote plus a whitespace-tolerant `str.find` resolves it, so the DIY path is parity with a competent resolver. The durable value there is the guarantee plus zero resolver code.
- The competitors CAN cite their own content through a hosted vector store. That hosted path, and its file/chunk granularity and persisted objects, is also measured in the [search-results](../search-results/README.md), [pdf-citations](../pdf-citations/README.md), and [grounding-stack](../grounding-stack/README.md) edges.
- Citations cannot be combined with Structured Outputs. The two return a 400 together, so a grounded answer here is free text.

## Run It Yourself

```bash
git clone https://github.com/cfregly/claude-feature-radar && cd claude-feature-radar
make setup
make compare-deps
cp .env.example .env   # paste ANTHROPIC_API_KEY, OPENAI_API_KEY, and GEMINI_API_KEY
make citations-paraphrase   # about $0.86, under a minute
```

Sources:

- Claude citations: https://platform.claude.com/docs/en/build-with-claude/citations
- Claude PDF support: https://platform.claude.com/docs/en/build-with-claude/pdf-support
- OpenAI file search: https://developers.openai.com/api/docs/guides/tools-file-search
- Gemini file search: https://ai.google.dev/gemini-api/docs/file-search
