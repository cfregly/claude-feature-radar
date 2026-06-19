# Edge: PDF citations, page pointers for directly supplied PDFs

Part of [claude-feature-radar](../../README.md). This is a measured grounding edge for directly supplied PDFs, not a claim about hosted vector-store search.

## What It Is

A user uploads a PDF and asks a question immediately. Claude Citations can return a `page_location` citation for the PDF supplied in the request, including the page number and quoted source text. The app does not need to persist the document in a hosted search store or write its own page resolver.

## The Measured Proof

Run: `make pdf-citations`, 2026-06-19, five questions over a five-page agreement PDF.

| arm | answered | direct-PDF pointer | right page | cost | wall time |
|---|:---:|:---:|:---:|---:|---:|
| claude:haiku | 5/5 | 5/5 | 5/5 | $0.0458 | 6.2s |
| openai:gpt-mid | 5/5 | 0/5 | 0/5 | $0.0064 | 15.9s |
| gemini:gem-flash | 5/5 | 0/5 | 0/5 | $0.0322 | 14.1s |

Claude answered every question and returned a correct-page citation for every answer. OpenAI and Gemini answered the same direct-PDF questions but returned no pointer into the supplied PDF on this direct-file path.

Full receipt: [`sample.txt`](sample.txt). Machine receipt: [`receipt.json`](receipt.json). Sample PDF: [`sample.pdf`](sample.pdf).

## Honest Scope

- This is a direct-PDF grounding edge for text-extractable PDFs.
- Scanned/image-only PDFs are outside this claim because Claude PDF citations require extractable text.
- OpenAI and Gemini have hosted file-search or vector-store paths. Those are different persisted workflows, not the direct PDF supplied inside the same request.

## Run It Yourself

```bash
git clone https://github.com/cfregly/claude-feature-radar && cd claude-feature-radar
make setup
make compare-deps
cp .env.example .env   # paste ANTHROPIC_API_KEY, OPENAI_API_KEY, and GEMINI_API_KEY
make pdf-citations     # cents-scale direct-PDF citation receipt
```

Sources:

- Claude citations: https://platform.claude.com/docs/en/build-with-claude/citations
- Claude PDF support: https://platform.claude.com/docs/en/build-with-claude/pdf-support
- OpenAI file inputs: https://developers.openai.com/api/docs/guides/file-inputs
- OpenAI file search: https://developers.openai.com/api/docs/guides/tools-file-search
- Gemini document processing: https://ai.google.dev/gemini-api/docs/document-processing
- Gemini file search: https://ai.google.dev/gemini-api/docs/file-search
