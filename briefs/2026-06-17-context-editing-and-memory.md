# Gap brief: the long-running-agent cost gap

**Run date:** 2026-06-17
**Status of the gap:** holds, narrowly and specifically
**Anchor features:** context editing (`context-management-2025-06-27`) plus the memory tool
(`memory_20250818`), both on the Claude platform.

This is the sourced version of the claim the README and the founder email make. It names the
competitors and links each side to its own docs. It is dated because the platforms ship monthly
and this will need re-checking.

## The one-line claim that survives

Claude is the only one of the three big model platforms that exposes **memory as a tool the model
itself drives** *and* pairs it with **selective server-side context editing that clears stale tool
results in place rather than summarizing them**. That pair is what lets a long-running agent hold
its per-turn cost roughly flat while staying correct. The measured receipt is in
[`../sample_output.txt`](../sample_output.txt): on a 32-step audit, the managed agent cost 2.08x
less than the plain one for the same correct answer, with 76% smaller peak per-turn context.

## What got thrown out first

A careless version of this pitch overclaims and gets bounced in the first reply. Three framings
were checked and killed:

| Tempting claim | Why it is false |
|---|---|
| "Only Claude has a managed agent runtime." | Both competitors ship a hosted agent runtime. One has been generally available since early 2025. |
| "Only Claude has agent memory." | Google's Vertex AI **Memory Bank** has been generally available since 2025-12-16. |
| "Only Claude does server-side context management." | OpenAI shipped **server-side compaction** in early 2026. |

## The two dimensions where a real gap remains

### 1. Memory: a tool the model drives, versus a service you call

| Platform | What it offers | Shape |
|---|---|---|
| **Anthropic Claude** | A `memory` tool (`memory_20250818`) the model invokes to view, create, edit, and delete files in a memory store, plus hosted memory stores in Managed Agents. | Model-driven tool |
| **OpenAI** | Conversation-state persistence (raw history), plus an open-source Agents-SDK pattern where you distill notes to a `MEMORY.md` and re-load the directory yourself. No managed memory service, no model-driven memory tool. | Developer-managed, client-side |
| **Google Gemini** | Vertex AI **Memory Bank**, a managed service that extracts and consolidates memories from session history and retrieves them by user id. You trigger it. It is not a tool the model itself drives. | Managed service, developer-triggered |

Against OpenAI the memory gap is clean. Against Google it is a difference of shape, the model
driving its own memory versus a service the developer calls. State it as "a memory tool the model
drives," never as "they have no memory."

### 2. Context management: clearing in place, versus summarizing, versus rolling your own

| Platform | What it offers | Mechanism |
|---|---|---|
| **Anthropic Claude** | **Context editing** clears the oldest tool results server-side, in place, and reports what it cleared. Claude also offers server-side **compaction** (summarize). It is the only one offering both. | Clear in place (and summarize) |
| **OpenAI** | Server-side **compaction**: when the rendered context crosses a threshold, the server summarizes older turns. No in-place tool-result clearing found. | Summarize, server-side |
| **Google Gemini** | **ADK Context Compaction**, a client-side opt-in in the open-source SDK (you wire it into your runner). No managed server-side context shrinking on the platform itself. | Summarize, client-side, opt-in |

The defensible distinction is the **mechanism**: Claude clears stale tool results in place, which
is structurally different from summarize-and-replace, and Claude offers both server-side. Do not
claim a wholesale "context management" gap against OpenAI. The honest edge is the in-place clearing
plus the model-driven memory that makes the clearing safe.

## Caveats, stated plainly

- Both anchor features are **beta**. The beta header and parameter shapes are in
  [`../docs/VERIFIED_FACTS.md`](../docs/VERIFIED_FACTS.md), checked against a live call.
- A "roughly 84% context reduction" figure circulates for context editing. It was **not found on
  the current doc page**, so this repo does not quote it. The demo measures its own number instead.
- This is a snapshot. The competitors ship monthly. Re-run the scan before reusing this claim.

## Sources (gathered by the scan pass, 2026-06-17)

Claude:
- Memory tool: https://platform.claude.com/docs/en/agents-and-tools/tool-use/memory-tool
- Context editing: https://platform.claude.com/docs/en/build-with-claude/context-editing
- Compaction: https://platform.claude.com/docs/en/build-with-claude/compaction

OpenAI:
- Server-side compaction guide: https://developers.openai.com/api/docs/guides/compaction
- Conversation state (persistence, not memory): https://developers.openai.com/api/docs/guides/conversation-state
- Agents SDK sandbox memory (client-side): https://openai.github.io/openai-agents-python/sandbox/memory

Google:
- Vertex AI release notes (Memory Bank GA 2025-12-16): https://cloud.google.com/vertex-ai/generative-ai/docs/release-notes
- ADK Context Compaction (client-side SDK): https://adk.dev/context/compaction
- Gemini API managed agents: https://ai.google.dev/gemini-api/docs/managed-agents-quickstart
