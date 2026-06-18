# Founder email (Deliverable 2)

Paste into a Google Doc or your sending tool. Plain text, one link.

---

**Subject:** OpenAI was cheaper in my benchmark. I still build on Claude. Here is why.

Hey {first_name},

Straight up, because you have already tried all three: I ran the same agent on Claude and OpenAI, a
fair fight, both at full strength. OpenAI came out cheaper. The benchmark is in the repo so you can
run it on your own keys and check. We do not cheat, and the README says where we lose.

So why build on Claude? Not price. The reason is the agent primitives the others do not ship. The
sharpest one for anyone building tool-heavy agents is context editing. It clears stale tool results
out of your context server-side, in place, with one header. OpenAI either summarizes them and loses
detail, or makes you wire the eviction logic yourself. Gemini's version is realtime-only. Claude is
the only one that ships it as a managed API feature, so a long agent stays bounded and you build
nothing.

{repo_link}

`make compare` runs the fair benchmark on your keys. `make demo` shows context editing holding the
context flat (peak around 3k tokens instead of 36k) while the agent stays correct. Real numbers,
measured, not asserted by me.

Build it on Claude Code or the Agent SDK and it is one flag away. Reply if you want a hand wiring it
in.

Go build,

{your_name}
Building with Claude

---

### Why it is built this way (not part of the email)

- **It leads with the loss.** A founder who has tried all three deletes a "we are cheaper" email on
  sight, because they can check. Opening with "OpenAI was cheaper" buys the right to be believed on
  the next sentence.
- **One verified differentiator, reproducible.** Context editing survived a hard skeptic pass as the
  only managed-API in-place clearing primitive, and a founder turns it on in one line.
- **No overclaim.** Not "Claude is cheaper" (false), not "Claude Code is better" (it is parity with
  Codex). Just the one thing only we ship, with the run-it-yourself proof.
