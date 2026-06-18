# Founder email: the Context Editing edge

The honest one. This is a real reliability mechanism, but it is the edge where a competitor is
closest, so the email says that plainly.

---

**Subject:** If your agent runs very long tool-heavy jobs, one flag keeps it from hitting the context wall

Hey {first_name},

If you build agents that read a lot before they answer (long document chains, big logs, deep tool
loops), the failure you eventually hit is the context window: the transcript grows until the model
either loses the thread or the API rejects the request.

Claude has a flag for this called context editing. It clears stale tool results out of the context in
place, so a long agent's window stays bounded instead of climbing. I measured it the honest way, with
everything held constant and only this one flag toggled (same model, same prompt, the memory tool on
in both arms), on a chain of 8 reports at about 40,000 tokens each, run three times:

- Context editing OFF: failed 3 of 3. Twice the context climbed past the 200,000 window (measured:
  `203,056 tokens > 200,000`) and the API rejected the request. Once it lost the count and answered
  wrong. Either way, the agent cannot finish the job.
- Context editing ON: finished 3 of 3 with the correct answer, context held flat near 34,000 tokens,
  $0.35 per run.

Two honest things. It is beta, and it is not a cheaper bill: clearing rewrites the cached prefix, so
on a job short enough to finish either way it can cost more. The value is that a heavy job finishes at
all.

And the part I will not hide: this is the one edge where a competitor is close. The other major
platforms ship server-side compaction that bounds context too (it compacts old turns server-side
rather than clearing them in place), and on a job at moderate scale all three big platforms finish, our
cross-vendor run is a
tie. So this is a reliability lever for the long tail of your hardest jobs, not a headline win.

{repo_link}

Run it yourself: `make setup`, then `cp .env.example .env` and paste your Anthropic key, then `python
edges/context-editing/demo.py` for one off+on pair, $0.65 on Haiku. The failure is
not deterministic, so the committed receipt runs it three times (`make longhorizon`, about two
dollars). Every number off the real API.

Go build,

{your_name}
Building with Claude
