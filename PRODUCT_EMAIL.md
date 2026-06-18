# Product-team email (the honest other direction)

Honesty runs both ways. When a fair run or a live audit shows a competitor ahead, or shows something
Claude lacks, the engine writes this. Same rigor as the founder email.

---

**Subject:** Where OpenAI and Gemini are ahead of Claude in 2026, from a fair benchmark and a live-docs audit

To the Claude platform team,

I ran a fair best-to-best benchmark and a skeptic-checked, competitor-parity audit of the Claude
Developer Platform against OpenAI and Google. The repo reproduces all of it. Here is the honest other
direction, where they are ahead, so we know what to fix.

1. **Raw price and speed.** On a fair 32-step agent benchmark, both at full config, OpenAI
   gpt-5.4-mini ran cheaper than Claude Haiku 4.5 (about $0.046 versus $0.124) and finished faster. We
   do not win the headline cost-and-speed comparison, and a founder who ranks cost first sees it.

2. **Coding-agent leaderboards.** On the independent boards, GPT-5.5 leads or ties at the top of
   Terminal-Bench 2.0 and 2.1, and GPT-5.5 Pro leads BrowseComp at about 90 percent. SWE-bench
   Verified is a ceiling tie at 79.2 percent with no clean three-way. We lead the METR long-horizon
   time-horizon, but not the coding boards. Verify each against the boards before quoting.

3. **Citations cannot combine with Structured Outputs.** Our strongest document-grounding edge
   returns a 400 if both are set on a user document. A contract-review or clinical product that needs
   strict JSON output AND verifiable citations on the same call cannot have both today. This is the
   one caveat that blunts our best founder pitch.

4. **Cache retention.** Gemini offers an arbitrary cache TTL and OpenAI a 24-hour retention tier,
   while Claude is fixed at 5 minutes or 1 hour. For a founder with heavy repeated context, that is a
   real economics gap.

To reproduce: clone, `make setup`, `make compare-deps` (the OpenAI and Gemini SDKs, into the same
venv), paste three keys (Anthropic, OpenAI, Gemini) into `.env`, then `make compare`, `make sweep`,
and `make citations`, about $1 and ten minutes total. Read `briefs/2026-06-17-platform-edge.md` and
`briefs/2026-06-17-agentic-landscape.md` for the sourced audit. The benchmark numbers (price, speed,
citation resolution) are measured on real calls. The leaderboard standings in item 2 are independent
sources to re-verify before quoting, and the cache-retention figures are competitor-doc claims.

The primitives we DO lead on (document-grounded Citations, the longest independent task horizon, and
programmatic tool calling once it leaves beta) are in the same briefs.

{your_name}

---

### Note

This is the committed example. `make alert` generates the benchmark-loss version of this email
automatically from the latest `data/last_compare.json` whenever a fair run shows a competitor ahead.
