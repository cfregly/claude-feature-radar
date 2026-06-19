# Edge: Context Editing, in-place clearing that keeps a long agent under the window

Part of [claude-feature-radar](../../README.md). A reliability lever for a long, tool-heavy agent,
labeled **beta**: it keeps a job that would otherwise hit the context window finishing instead of
erroring.

**What it is.** `context_management` with `clear_tool_uses_20250919` clears stale tool results out of
the context in place once a token trigger is crossed, keeping the most recent few. A long tool-heavy
agent's window stays bounded instead of climbing to the wall.

## The measured proof (isolated to one variable)

The same 8-report chain (each report about 40,000 tokens), run with the memory tool on in both arms
and the identical prompt, toggling only context editing, three times:

| run (only context editing differs) | outcome over 3 runs |
|---|---|
| context editing OFF | **3/3 failed** (2 crashed at the 200,000 window, 1 wrong answer), 0/3 correct |
| context editing ON | **3/3 finished correctly**, context held flat near 34,000 tokens, ~$0.35/run |

One captured editing-off run climbed from 1,816 to 187,471 carried tokens (per-turn cost up 24.7x),
then exceeded the window so the API rejected the request (`203,056 > 200,000`). Editing on held context
near 34k and finished. The reliability win is caused by context editing alone. Correctness is held
constant by the memory tool (on in both arms). Full receipt in [`sample.txt`](sample.txt).

## Where it pays off

The win is reliability on the long tail. A heavy tool agent (40,000-token-per-call payloads, many
steps) whose carried context would otherwise cross the window finishes the job instead of erroring. On
a job short enough to finish either way the feature changes nothing, so reach for it when the window is
the real constraint. It is beta (`context-management-2025-06-27`).

## Run it yourself

```bash
git clone https://github.com/cfregly/claude-feature-radar && cd claude-feature-radar
make setup
cp .env.example .env   # paste your Anthropic key
make longhorizon       # this edge, 3 runs for reliability, about two dollars on Haiku
# or one off+on pair ($0.65): python edges/context-editing/demo.py
```
