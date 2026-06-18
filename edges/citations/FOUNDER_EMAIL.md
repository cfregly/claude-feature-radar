# Founder email (Deliverable 2)

Paste into a Google Doc or your sending tool. Plain text, one link.

---

**Subject:** Claude hands you a guaranteed, per-character citation into your user's own doc in one field.

Hey {first_name},

If you are building over your users' own documents (contracts, charts, tickets, research, support docs), the thing that makes it shippable is a citation that links to the exact source sentence and is guaranteed to be real, not a quote the model might have paraphrased.

Claude ships a GA feature for this called Citations. Turn it on per document, and Claude returns each claim with a structured pointer (a character range for text, a page range for a PDF) plus the verbatim quote, extracted by the API. Two things you do not get anywhere else: the API extracts the quote from the source, so the quote it returns is guaranteed to be the real verbatim source text and not a paraphrase the model invented, and that quote is free of output tokens.

I measured it honestly, including the part that is not flattering. The realistic way to do this without the feature is to ask the model for the verbatim quote and resolve it yourself with `source.find(quote)`. Over 8 questions on a set of documents:

- Claude with Citations: 8 of 8 resolve, the API does the resolving and guarantees it, zero resolver code, and the quote costs zero output tokens (308 output tokens total).
- The DIY path on Claude, OpenAI, and Gemini: also 8 of 8, because on clean text the model quotes verbatim and `find` locates it. But you own that code, you pay output tokens for every quote (563 on Claude, 392 on OpenAI, 3,654 on Gemini), and `find` returns nothing the moment the model paraphrases instead of quoting verbatim. On this clean corpus it did not fail, so I am flagging that as the failure you inherit when you own the resolver, not as something I measured here.

So I am not going to tell you the competitors cannot cite. On clean text the DIY bolt-on works, and Google's Gemini File Search now returns a page-level pointer into your uploaded document (it shipped that in May 2026). The honest edge is narrower and precise: Claude is the only GA API that returns a per-character source pointer into your document with an API-extracted verbatim quote it guarantees is valid and free of output tokens, and no resolver code to write or maintain. OpenAI's file citations index the model's own output, not your source, and Gemini's pointer is page-level only.

{repo_link}

Run it yourself: `make setup`, then `make compare-deps`, then `cp .env.example .env` and paste three keys (Anthropic, OpenAI, Gemini, the file says where each goes), then `make citations`. $0.06 and a couple of minutes, every number read off the real API.

Two honest caveats I will not hide. Citations is not the cheapest arm in raw dollars (it adds input tokens for chunking, so on this small corpus it cost more than the OpenAI DIY path), and it cannot be combined with Structured Outputs on the same document (the API returns a 400). The win is the guarantee and zero code, not a cheaper bill.

If you are building long-running agents, a second reason: on METR's independent task time-horizon, the neutral referee rather than a vendor chart, Claude runs the longest autonomous jobs of any released model, about 1.9x the next best before reliability drops to half. On a short job every frontier model finishes, so that gap only shows on the long ones, but it is the one place an independent referee puts Claude first.

It is one field on the API: `citations: {"enabled": true}`. Reply if you want a hand wiring it in.

Go build,

{your_name}
Building with Claude

---

### Why it is built this way (not part of the email)

- **The hook does not overclaim.** An earlier version of this benchmark asked the competitor models
  to emit the character offset themselves, scored that 0/8, and called it a competitor failure. A
  scrutiny panel caught it: a tokenizer cannot count characters, and no founder would build it that
  way. The honest baseline is model-quote plus your own `str.find`, which resolves 8/8 on clean text.
  The email now states that plainly and rests on the edge that survives: the guaranteed in-API
  per-character pointer, free of output tokens, that no competitor matches at char granularity
  (Gemini File Search is page-level and still preview, OpenAI cites its own output).
- **It states the real cost.** Citations cost more than the OpenAI DIY path on this corpus, so the
  email says so rather than claiming "cheaper."
- **The numbers are receipts.** 8/8, the output-token counts, and the six-cent reproduction cost all
  come from `make citations` (`edges/citations/sample.txt`), not from memory.
- **The second pillar is independent and honestly scoped.** METR is the neutral referee, and the
  email says plainly that the gap only appears on long jobs, not short ones.
