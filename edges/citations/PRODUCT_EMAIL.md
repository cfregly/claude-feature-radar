# Product-team email: the Citations edge, the honest other direction

What competitors ship near this edge, and where Claude is weak on it. Same rigor as the founder email.

---

**Subject:** Citations is a real edge, but it is narrowing and it has one hard product gap

To the Claude platform team,

The Citations primitive (a guaranteed-valid char or page pointer into the user's own document, with
the verbatim quote extracted by the API and free of output tokens) is a genuine GA lead. Two things
the founder email does not lean on, because they are where we are exposed.

1. **The "no competitor" claim is already refuted, so the lead is narrow.** Google shipped Gemini
   File Search (2026-05), which returns a PAGE-level pointer into an uploaded document
   (`grounding_chunks.retrieved_context.page_number` plus verbatim text). Our surviving edge is
   specifically per-CHARACTER granularity plus the guaranteed-valid, output-token-free quote, not a
   capability nobody else has. Gemini File Search GA-versus-preview status is in flux. Recheck it
   before every send, because a char-level competitor pointer would erase this edge.
   Source: https://ai.google.dev/gemini-api/docs/file-search (checked 2026-06-17).

2. **Citations cannot be combined with Structured Outputs.** Enabling citations on a user document
   together with `output_config.format` returns a 400. A contract-review or clinical product that
   needs strict JSON output AND verifiable citations on the same call cannot have both today. This is
   the single thing that blunts the pitch for exactly the regulated, schema-driven customers who want
   citations most. Source:
   https://platform.claude.com/docs/en/build-with-claude/citations (re-fetched 2026-06-17).

3. **On clean text the DIY path matches us.** Measured (`make citations`): asking any model for the
   verbatim quote and resolving it with `str.find` resolves 8 of 8 on OpenAI and Gemini too. Our edge
   is the in-API resolve, the guarantee on messy input, the free quote, and zero resolver code, not a
   correctness gap on easy documents. We should say that plainly so a skeptic does not catch us.

To reproduce: `make setup`, `make compare-deps`, paste three keys into `.env`, then `make citations`,
$0.06. The receipt is `edges/citations/sample.txt`.

{your_name}
