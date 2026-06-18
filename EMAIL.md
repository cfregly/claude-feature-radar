# Founder email (Deliverable 2)

Paste into a Google Doc or your sending tool. Plain text, one link.

---

**Subject:** Your tool-heavy agent carries 35k tokens of context. On Claude, one flag drops it to 15k.

Hey {first_name},

You get a long agent that stays bounded, with no eviction code to write.

Measured on the same 32-step agent across Claude Haiku 4.5, OpenAI gpt-5.4-mini, and Gemini
3.5-flash, all at full strength, at a 20k trim threshold: turning context editing on drops Claude's
carried context from about 35k tokens to about 15k. It clears stale tool results in place. OpenAI's
server-side version summarizes them and loses detail, and its in-place trim is client-side, so you
wire it in yourself. Gemini's in-place trim is realtime-API only, so on this agent it carries about
33k. Claude is the only one that ships in-place clearing on the standard tool-use path.

It is not free. Clearing rewrites the cached prefix, so on this run it cost a few percent more and
ran a little slower than leaving editing off. You are buying bounded context, not a cheaper bill.

{repo_link}

Reproduce it on your own keys: `make setup`, install the compare deps, paste three keys (Anthropic,
OpenAI, Gemini) into `.env`, then `make compare`. About a dollar and a few minutes, every number
measured. And honestly, Claude is not the cheapest: OpenAI's cheap model costs less (it miscounted on
this run), and the README says where Claude loses.

It is one flag on the Agent SDK, or in Claude Code. Reply if you want a hand wiring it in.

Go build,

{your_name}
Building with Claude

---

### Why it is built this way (not part of the email)

- **It opens with the so-what, then the one number Claude wins.** A bounded agent with no eviction
  code, proved by about 35k down to about 15k of carried context (true context, cached tokens
  included, the metric we corrected mid-build, see docs/FINDINGS.md). The figure is tied to this
  agent and a 20k trim threshold, not sold as a fixed property of the flag.
- **It discloses the cost of the flag.** Context editing ran slower and cost a few percent more than
  leaving it off, because clearing invalidates the cache. We say so, because the panel checks it.
- **The workload, cost, and reproduction steps are up front**, including the three keys, so a cold
  clone does not hit a missing-key error.
- **No overclaim.** Not "Claude is cheaper" (false), not "Claude Code is better" (parity with Codex),
  not "fast" (editing on is slower), not "6x less context" (a metric confound). Just the in-place
  primitive only Claude ships, with the run-it-yourself proof.
