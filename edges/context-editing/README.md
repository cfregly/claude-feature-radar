# Edge: Context Editing, in-place clearing that keeps a long agent under the window

Part of [claude-competitive-engine](../../README.md). This edge is **beta**, and it is the weakest of
the engine's edges competitively. We keep it because it is a real reliability mechanism, and because
honesty about a thin edge is the point.

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

## The honest scope

- **It is not a cheaper bill.** Clearing rewrites the cached prefix, so on a job short enough to finish
  either way it can cost more. The value is that a heavy job finishes at all.
- **A competitor is close.** OpenAI ships server-side compaction (an explicit `/responses/compact`
  endpoint) that bounds context too, by summarizing rather than clearing in place. At moderate scale
  all three vendors finish the same heavy task (`make longhorizon-compare` is a tie). The edge only
  appears on the long tail.
- **It is beta** (`context-management-2025-06-27`).

## Run it yourself

```bash
git clone <this-repo> && cd claude-competitive-engine
make setup
cp .env.example .env   # paste your Anthropic key
make longhorizon       # this edge, 3 runs for robustness, about two dollars on Haiku
# or one off+on pair (about 65 cents): python edges/context-editing/demo.py
```

See [`FOUNDER_EMAIL.md`](FOUNDER_EMAIL.md) and [`PRODUCT_EMAIL.md`](PRODUCT_EMAIL.md).
