# Founder email (Deliverable 2)

Paste into a Google Doc or your sending tool. Plain text, one link.

---

**Subject:** Your tool-heavy agent carries 35k tokens of context. On Claude, one flag drops it to 15k.

Hey {first_name},

What you get: a long agent that stays bounded and fast, with zero eviction code to write.

The proof, measured on the same 32-step tool-using agent across Claude Haiku 4.5, OpenAI
gpt-5.4-mini, and Gemini 3.5-flash, all at full strength. With context editing off, Claude carries
about 35,000 tokens of context by the end of the run. Turn it on, one beta header, and the same
agent carries about 15,000. Context editing clears stale tool results in place. OpenAI's version
summarizes them and loses detail. Gemini has no in-place trim at all, so it carries about 33,000.
Claude is the only one that ships in-place clearing as a managed API feature.

{repo_link}

`make compare` runs the whole fair fight on your own keys, about a dollar and two minutes.
`make demo` shows the context dropping. Every number is measured, not asserted by me.

Honest, because you can check it: Claude is not the cheapest. OpenAI's cheap model costs less,
though it got the count wrong on this run, and the README shows exactly where Claude loses. The
reason to build on Claude is the bounded context with no eviction logic, not the price.

Build it on Claude Code or the Agent SDK. It is one flag. Reply if you want a hand wiring it in.

Go build,

{your_name}
Building with Claude

---

### Why it is built this way (not part of the email)

- **It opens with the so-what, then the one number Claude wins.** A bounded, fast agent with no
  eviction code, proved by 35k down to 15k of carried context (true context, cached tokens included,
  the metric we corrected mid-build, see docs/FINDINGS.md).
- **The workload, cost, and time are stated up front.** A 32-step agent, three named models, about a
  dollar and two minutes to reproduce, before the reader commits.
- **It is honest about price and correctness in the next breath.** OpenAI is cheaper, the trimmed run
  can miscount, and the repo says both. That honesty is what makes the context number believable.
- **No overclaim.** Not "Claude is cheaper" (false), not "Claude Code is better" (parity with Codex),
  not "6x less context" (that was a metric confound). Just the in-place primitive only Claude ships,
  with the run-it-yourself proof.
