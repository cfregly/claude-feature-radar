---
name: claude-feature-hits
description: Run a short, public Claude feature artifact that prints the measured result and dollar cost. Use only artifacts listed in the root README as current wins. Triggers on "show me the Claude feature hit", "run a feature artifact", "prove the programmatic tool calling cost cliff", "prove the PDF citation hit", or "reproduce the public Claude proof".
---

# claude-feature-hits

Pick the promoted artifact from the root README, then run its `make` target.

1. Cost artifacts:
   - `make programmatic_tool_calling`
   - `make programmatic_tool_calling_cache_context`
2. Accuracy artifacts:
   - none promoted yet.
3. Speed artifacts:
   - none promoted yet.
4. Operations artifacts:
   - none promoted yet.
5. Reliability and Security artifacts:
   - none promoted yet.
6. Export `ANTHROPIC_API_KEY` for promoted default targets.
7. For every pillar, check the artifact README's `Best-available comparison` section before describing a win. A Claude receipt that beats OpenAI but not Gemini is not an all-provider win.
8. For every artifact, check the README's `Dimension matrix`. Do not imply a Cost, Speed, Accuracy, Reliability, Operations, or Security win when that row says `not measured` or `not claimed`.
9. Treat Managed Agents as an Operations candidate, not a promoted artifact, until it has a same-workload comparison against self-managed Claude, OpenAI, and Gemini agent stacks.
10. Run `make ci` before changing public copy.

Every number traces to the artifact's committed receipt. A public directory exists here only when it is a
current runnable win.
