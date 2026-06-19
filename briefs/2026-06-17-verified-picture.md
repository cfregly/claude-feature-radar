# Verified competitive picture (2026-06-17)

An audit of about 18 capabilities across Claude, OpenAI, and Google, each one skeptic-refuted, plus
a fair best-to-best benchmark. This is the sourced evidence behind the founder email and the
product email. It names the competitors because it is dated evidence, not a swipe. Re-run the engine
before quoting any of it, because this surface moves monthly.

## The honest headline

On a fair benchmark, Claude does not win on cost, speed, or correctness. OpenAI is cheaper, and the
cheap-tier correctness gap was a model-quality artifact (a stronger competitor model is correct).
Claude Code is strong but at parity with OpenAI Codex and Google Antigravity. The
managed-agent runtime is parity. So the reason to build on Claude is not price, and not the IDE. It
is a small set of agent primitives the others do not ship.

## The anchor: context editing (`clear_tool_uses_20250919`)

What it is: server-side, in-place clearing of the oldest tool results, each replaced with a
placeholder rather than summarized. The client keeps the full history. One beta header
(`context-management-2025-06-27`) and one edit object turn it on.

Why it survived the skeptic: OpenAI's tool-output trimmer is client-side (you wire it into your own
process). OpenAI's Responses-API compaction is server-side but summarizes into an opaque item.
Gemini's sliding window is server-side and non-summarizing but scoped to the realtime Live API, not
the standard tool-use path. ADK, Codex, and Antigravity summarize. Claude is the only one shipping
in-place clearing as a managed API feature on the standard tool-use path.

Honest framing, reconciled with our own benchmark: it cuts carried tokens and bounds context
(measured on the committed 8-report chain: editing-ON held context flat near 34k tokens while editing-OFF crashed at the 200k window, 203,056 tokens, receipt `../edges/context-editing/sample.txt`). It is NOT a raw dollar win when prompt
caching is on, because clearing rewrites the cached prefix (see `../docs/FINDINGS.md`). Pitch it as
context-bounding and no-build-eviction, never as "cheaper."

Source: https://platform.claude.com/docs/en/build-with-claude/context-editing

## Other verified Claude-ahead primitives

- **Self-hosted sandbox for the managed loop** (maintenance axis). Anthropic runs the loop, retry,
  and context management. Your infrastructure runs tool and code execution via a work queue. No
  competitor ships this exact hybrid: OpenAI hosts everything or you host everything, Google the
  same. Beta. Source: https://platform.claude.com/docs/en/managed-agents/self-hosted-sandboxes
- **The model-driven memory tool** (developer-experience axis). The model emits view/create/edit
  calls against durable `/memories` files with a client-side backend. Only Anthropic has
  model-driven plus read-and-write plus durable files plus cross-session as an API primitive. An
  architecture-shape lead, not a maturity lead, and it is beta.
  Source: https://platform.claude.com/docs/en/agents-and-tools/tool-use/memory-tool

## Where Claude is behind (the product email)

- **Raw price.** OpenAI is cheaper on the fair benchmark.
- **Prompt-cache retention.** Gemini explicit caching takes an arbitrary TTL, OpenAI offers a 24h
  retention tier, Claude is fixed at 5m or 1h.
- **Secure MCP tunnel.** OpenAI's went GA 2026-05-27, ahead of Claude's beta.
- **Long-context billing.** GPT-5.5 carries a surcharge band above ~272k tokens but a larger
  ceiling, and Gemini exposes arbitrary-TTL caching over its 1M window.

## Refuted or parity, do not pitch

- Claude Code as a product: parity with Codex and Antigravity (every core primitive came back
  parity: Agent SDK, subagents, Skills/SKILL.md, hooks).
- Managed-agent runtime: parity.
- Dreaming (async memory consolidation): parity (Codex Memories GA plus Vertex Memory Bank).
- Outcomes (rubric self-grade plus isolated grader plus retry): refuted (Google Jules' critic plus
  Vertex rubric metrics). Keep only with narrowed wording, never as "no competitor has it."

## Caveats

The whole context-management surface shipped in the last few months, the anchor lives there, so
re-check the beta header and competitor parity before sending. Self-hosted sandbox and the memory
tool are beta. Antigravity consolidated mid-June 2026. Re-run the engine before quoting.
