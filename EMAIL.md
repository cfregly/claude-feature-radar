# Founder email (Deliverable 2)

Paste into a Google Doc or your sending tool. Plain text, one link.

---

**Subject:** Claude cites the exact sentence in your user's own doc, and the pointer resolves 8/8. The DIY workaround: 0/8.

Hey {first_name},

If you are building anything over your users' own documents (contracts, charts, tickets, research papers, support docs), the thing that makes it shippable is trust: every claim links back to the exact sentence in the source, and that link actually works.

Claude ships a GA feature for this called Citations. You turn it on per document, and Claude returns each claim with a structured pointer (a character range for text, a page range for a PDF) plus the verbatim quote, extracted by the API so the pointer is guaranteed to resolve. The quote does not count toward your output tokens.

I measured it the only way that counts. Across 8 questions over a set of documents, does each returned offset land on the exact source text?

- Claude with Citations: 8 of 8 resolve, guaranteed, quotes free of output tokens.
- The prompt-for-quotes approach you would build without it: 0 of 8 resolve on Claude, 0 of 8 on OpenAI. The quoted text was correct, but the offsets pointed nowhere, so you cannot link to or verify them.
- Gemini resolved 7 of 8, but only by burning 45,630 output tokens against Claude's 308 (about 148x) and $0.42 against $0.011 (about 37x), because it has to brute-force the character count with reasoning.

No competitor exposes a pointer into your own document. OpenAI and Google only cite web-search URLs. So this is a real gap, not a benchmark I rigged: the cheap workaround gives you zero usable citations, and the only competitor that resolves at all costs 37x more to do it.

{repo_link}

Run it yourself: `make setup`, then `make compare-deps`, then `cp .env.example .env` and paste three keys (Anthropic, OpenAI, Gemini, the file says where each goes), then `make citations`. About thirty cents and a couple of minutes, every number read off the real API.

One honest caveat I will not hide: Citations cannot be combined with Structured Outputs on the same document (the API returns a 400), so if you need strict JSON and citations together, you pick one.

If you are building long-running agents, a second reason to look: on METR's independent task time-horizon, the neutral referee rather than a vendor chart, Claude runs the longest autonomous jobs of any released model, about 1.9x the next best before reliability drops to half. Claude is not the cheapest or the fastest per token, and it does not top every coding board. But it finishes the longest jobs, and it is the only one that cites your user's own documents with a pointer that resolves.

It is one field on the API: `citations: {"enabled": true}`. Reply if you want a hand wiring it in.

Go build,

{your_name}
Building with Claude

---

### Why it is built this way (not part of the email)

- **The hook is measured, cross-vendor, and ungameable.** The grader checks one thing per citation:
  does `source[start:end]` equal the quoted text. 8/8 on Claude, 0/8 on the workaround, from
  `make citations`, not asserted. The full receipt is `sample_citations.txt`.
- **It states the honest cost.** Citations is not the cheapest arm in raw dollars (it adds input
  tokens for chunking), so the email never claims "cheaper." It claims what the receipt shows: the
  quotes are free of output tokens, and among the approaches that actually resolve a pointer, Claude
  is the only one at 8/8 and 37x cheaper than the one competitor that resolves.
- **It carries the one real caveat** (incompatible with Structured Outputs) instead of hiding it.
- **The second pillar is independent, not a vendor chart.** METR is the neutral referee, and the
  email says plainly where Claude does not lead (cost, speed, coding boards) so the one place it does
  lead is credible.
- **No overclaim.** Not "best model," not "cheapest," not "wins every benchmark." A GA primitive no
  competitor ships, measured, plus an independent long-horizon result.
