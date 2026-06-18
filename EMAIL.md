# Founder email (Deliverable 2)

Paste into a Google Doc or your sending tool. Plain text, one link.

---

**Subject:** A 32-step tool agent carries ~35k tokens of context. On Claude, one flag (clear at 20k, keep 3) holds it near 15k.

Hey {first_name},

You get a long agent that stays bounded, with no eviction code to write.

Measured on the same 32-step agent across Claude Haiku 4.5, OpenAI gpt-5.4-mini, and Gemini
3.5-flash, all at full strength, with carried context counted the same way on every side (input plus
cached tokens, apples to apples). Turning on context editing (clear at a 20k threshold, keep the last
3 tool results) drops Claude's carried context from about 35k tokens to about 15k. It clears stale
tool results in place. OpenAI's server-side compaction also trims, to about 19k, but by summarizing
(lossy). OpenAI does ship real in-place tool-output trimming, but client-side, so you wire it into
your own process. Gemini's in-place trim is realtime-API only, so it carries about 33k, and it was
the priciest arm here, about $0.41 or 3x Claude. Claude is the only one that ships in-place clearing
as a managed feature on the standard tool-use path.

It is not free. On this run, editing on ran about 44% slower (63.5s vs 44.2s) and cost about 8% more
than leaving it off, because clearing invalidates the cache. You are buying bounded context, not a
cheaper or faster bill.

{repo_link}

Reproduce it: `make setup`, then `make compare-deps` (installs the OpenAI and Gemini SDKs into the
same venv), then `cp .env.example .env` and paste three keys (Anthropic, OpenAI, Gemini, the file
says where each goes), then `make compare`. About a dollar and a few minutes, every number measured.
The Gemini row needs a paid-tier Gemini key, or it is skipped on quota.

And honestly, Claude is not the cheapest: OpenAI's cheap model is cheaper here ($0.033 versus
Claude's $0.131 with editing on, $0.121 off). It also miscounted at the cheap tier, but its stronger
model answers correctly, so that is a model-tier gap, not a Claude win.

It is one flag on the Agent SDK or the API. Reply if you want a hand wiring it in.

Go build,

{your_name}
Building with Claude

---

### Why it is built this way (not part of the email)

- **The subject attributes 35k to the benchmark, not the reader's agent**, and ties the 15k to the
  actual trim config (clear at 20k, keep 3) in the subject line itself, because 15k is a tuned
  setting, not a property of the flag alone.
- **It states the real downside, measured.** Editing on ran about 44% slower and cost about 8% more
  (63.5s vs 44.2s, $0.131 vs $0.121). Calling that "about 40%" rounds the one honest-downside number
  toward zero, the nudge the panel caught, so we quote the real 44%.
- **The price and the miscount are separated**, with the model-tier caveat from FINDINGS #5: the
  cheap-tier miss disappears one tier up.
- **The reproduction is runnable from the email alone**, the exact commands and the three keys.
- **No overclaim.** Not cheaper, not faster, not "Claude Code is better" (parity with Codex), not
  "6x less context" (a metric confound). Just the in-place primitive only Claude ships.
