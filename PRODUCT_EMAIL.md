# Product-team email (the honest other direction)

Honesty runs both ways. When a fair run shows a competitor ahead, or shows something Claude lacks,
the engine writes this. Same rigor as the founder email.

---

**Subject:** What OpenAI and Gemini ship that Claude does not, from a fair benchmark and audit

To the Claude platform team,

I ran a fair best-to-best benchmark and a skeptic-checked capability audit of Claude against OpenAI
and Gemini. The repo reproduces all of it. Here is the honest other direction, where they are ahead.

1. **Price.** On a fair 32-step agent benchmark, OpenAI gpt-5.4-mini was cheaper than Claude Haiku
   4.5 (about $0.033 with compaction and caching versus Claude's $0.131 with context editing on, or
   $0.121 with it off). That $0.033 config miscounted on this task (8 versus the true 11), and
   OpenAI's stronger model answers correctly at a higher price. We still do not win the headline
   cost comparison, and a founder who ranks cost first will see that.

2. **Prompt-cache retention.** Gemini explicit caching takes an arbitrary TTL and OpenAI offers a
   24-hour retention tier, while Claude is fixed at 5 minutes or 1 hour.

3. **Secure MCP tunnel.** OpenAI's went GA recently, ahead of Claude's beta. Verify the exact date
   against OpenAI's changelog before quoting it.

4. **Long-context billing.** GPT-5.5 has a larger context ceiling with a long-context surcharge band,
   and Gemini's arbitrary-TTL caching over its 1M window is more flexible than ours. GPT-5.5 is
   outside the benchmarked gpt-5.4 set, so this is a pricing-page claim. Verify the exact band against
   OpenAI's pricing page before quoting it.

To reproduce: clone, `make setup`, `make compare-deps` (the OpenAI and Gemini SDKs, into the same
venv), paste three keys (Anthropic, OpenAI, Gemini) into `.env`, then `make compare` and `make
sweep`, and read `briefs/2026-06-17-verified-picture.md` for the sourced audit. The Gemini row needs
a paid-tier key or it is skipped on quota. The benchmark numbers (price, carried context) are
measured on real calls. Items 3 and 4 above are competitor-doc claims to re-verify before quoting,
flagged inline. The confounds we had to fix are in `docs/FINDINGS.md`.

The primitives we DO lead on (context editing, self-hosted sandboxes, the model-driven memory tool)
are in the same brief.

{your_name}

---

### Note

This is the committed example. `make alert` generates the benchmark-loss version of this email
automatically from the latest `data/last_compare.json` whenever a fair run shows a competitor ahead.
