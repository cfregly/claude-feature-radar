# Product-team email: the Programmatic Tool Calling edge, the honest other direction

The sharpest founder edge, and the things that keep it from being a slam dunk.

---

**Subject:** Programmatic tool calling is our sharpest founder edge, with three honest qualifiers

To the Claude platform team,

Programmatic tool calling (`allowed_callers` plus the code execution tool) is the strongest edge the
engine found this month: it keeps a developer's own custom-tool outputs out of the model context, a
direct token-cost lever no competitor names. Measured on our key (4 tools of 60 rows, fan-out task),
it cut billed input tokens from 9,451 to 6,828, about 28%, and the sandbox code computed the answer
correctly where the in-context model failed. It is GA (no beta header on the live doc as of 2026-06-18).

Three qualifiers we should carry, not bury.

1. **The lead is absence-of-evidence, not a head-to-head loss for rivals.** No named OpenAI or Google
   equivalent keeps a developer's own custom-tool outputs out of context. But OpenAI ships both a code
   interpreter and tool search and could plausibly compose them, so state the unmatched piece
   precisely (`allowed_callers` output filtering) and recheck it.

2. **It excludes a chunk of customers.** Not available on Amazon Bedrock or Vertex AI, and not
   ZDR-eligible. A founder on Bedrock, Vertex, or a ZDR-bound stack cannot use it, lead with citations
   there instead.

3. **The win is workload-shaped, and the headline number is small-sample.** The doc itself notes a
   sequential single-call benchmark (tau2-bench) is flat to about 8% more expensive, so this only pays
   on genuine fan-out. Our 28% is one small task on our key, the doc's 24% is Anthropic's measurement.
   Reproduce before quoting either, per numbers-are-receipts. It also adds model round-trips, so on a
   fast tool it can be slower even while it bills fewer tokens.

To reproduce: `make setup`, paste your Anthropic key, `make ptc`, $0.08 on Sonnet 4.6
(it is not supported on Haiku). Receipt: `edges/programmatic-tool-calling/sample.txt`.

{your_name}
