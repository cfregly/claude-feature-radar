# Product-team email (the honest other direction)

Honesty runs both ways. When a fair run shows a competitor ahead, or shows something Claude lacks,
the engine writes this. Same rigor as the founder email.

---

**Subject:** What OpenAI and Gemini ship that Claude does not, from a fair benchmark and audit

To the Claude platform team,

I ran a fair best-to-best benchmark and a skeptic-checked capability audit of Claude against OpenAI
and Gemini. The repo reproduces all of it. Here is the honest other direction, where they are ahead.

1. **Price.** On a fair 32-step agent benchmark, OpenAI gpt-5.4-mini was cheaper than Claude Haiku
   4.5 (about $0.05 versus $0.12 to $0.15), and a stronger OpenAI model answers correctly. We do not
   win the headline cost comparison, and a founder who ranks cost first will see that.

2. **Prompt-cache retention.** Gemini explicit caching takes an arbitrary TTL and OpenAI offers a
   24-hour retention tier, while Claude is fixed at 5 minutes or 1 hour.

3. **Secure MCP tunnel.** OpenAI's went GA on 2026-05-27, ahead of Claude's beta.

4. **Long-context billing.** GPT-5.5 has a larger context ceiling (with a surcharge band above about
   272k tokens), and Gemini's arbitrary-TTL caching over its 1M window is more flexible than ours.

To reproduce: clone the repo, run `make compare` and `make sweep` for the benchmark, and read
`briefs/2026-06-17-verified-picture.md` for the sourced audit. Every number is measured on real
calls, and the confounds we had to fix are in `docs/FINDINGS.md`.

The primitives we DO lead on (context editing, self-hosted sandboxes, the model-driven memory tool)
are in the same brief.

{your_name}

---

### Note

This is the committed example. `make alert` generates the benchmark-loss version of this email
automatically from the latest `data/last_compare.json` whenever a fair run shows a competitor ahead.
