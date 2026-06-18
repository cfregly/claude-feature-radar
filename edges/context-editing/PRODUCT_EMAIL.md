# Product-team email: the Context Editing edge, the honest other direction

This is the edge where Claude is weakest competitively. The note says so.

---

**Subject:** Context editing is a real mechanism but a thin competitive edge, and it is still beta

To the Claude platform team,

Context editing (`clear_tool_uses_20250919`) genuinely works: in an isolated test (same model, same
prompt, memory tool on in both arms, only the flag toggled, three runs), the editing-off agent failed
3 of 3 on a heavy 8-report chain (two window crashes at `203,056 > 200,000`, one wrong answer) and the
editing-on agent finished 3 of 3 correctly with context held near 34k. That is a real reliability win.

But as a competitive edge it is thin, and we should not oversell it.

1. **OpenAI is close or ahead.** OpenAI ships server-side compaction with an explicit
   `/responses/compact` endpoint that bounds context as well. Theirs compacts old turns server-side
   (their doc says "rather than traditional summarization") where ours clears stale tool results in
   place, so the honest distinction is the clearing semantics, not a capability they lack.

2. **It is beta.** Context editing rides the `context-management-2025-06-27` beta header. We cannot
   call it GA in an outbound email.

3. **At moderate scale it is a tie.** Our cross-vendor long-horizon run (`make longhorizon-compare`)
   has all three vendors finishing the same heavy task, Claude just carries the least context. The
   editing win only appears when the job is long enough to hit the window, which a cheap demo barely
   reaches.

So the right place to lead this is the long tail of very heavy tool agents, framed as a reliability
lever, with the OpenAI-compaction parity stated up front. Reproduce: `make longhorizon` and
`make longhorizon-compare`. Receipt: `edges/context-editing/sample.txt`.

{your_name}
