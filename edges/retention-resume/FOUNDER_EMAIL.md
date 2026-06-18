# Founder email: retention and resume (the parity read, and the bundle that is the real win)

This edge is parity on the capability (durable kill-and-resume is table stakes across all three
vendors), so the email does not pitch a Claude-only capability. It pitches the thing that is actually
true and useful: you can stop building the resume plumbing, and you should know the retention terms
before you commit. It stays competitor-neutral per the repo convention, names the beta caveat plainly,
and points the founder at the genuinely Claude-ahead edges as the reasons to build.

---

**Subject:** Before you build the resume-after-a-crash plumbing for your agent, read this

Hey {first_name},

If you are running a long, unattended agent (an overnight job, a research loop, anything that runs for
minutes or hours and must survive the client dying mid-run), you are probably about to build the part
nobody enjoys: the session store, the event log, the replay-on-reconnect, the sandbox that keeps your
files between runs. I want to save you a wrong assumption and a few weeks of plumbing.

First, the honest part. Surviving a kill and resuming is not a Claude-only trick. I checked all three
vendors against their own live docs, and durable kill-and-resume is table stakes: OpenAI ships it GA
(the Responses Conversations object across sessions and devices, and Agents SDK sessions that survive a
process restart), and Gemini Live resumes within about a 2-hour handle window. So if anyone tells you
only one provider can resume an agent, they are selling you something. This engine reports the tie when
it is a tie.

What is genuinely different on Claude, and what I think is worth your time, is the bundle. Claude
Managed Agents gives you the sandbox, the agent loop, a persistent filesystem, conversation history,
and built-in compaction in one product, so you build no agent loop, no sandbox, and no tool-execution
layer. And it holds state the longest on the time axis: no 30-day TTL like a standalone response, no
roughly 2-hour handle cap like Gemini Live. Two caveats I will not bury: it is in beta (the
`managed-agents-2026-04-01` header, which the SDK sets for you, on by default), and because the state
lives server-side it is not eligible for Zero Data Retention or a HIPAA BAA, so if you have that
requirement, run the self-hosted sandbox instead.

You do not have to take my word for the resume working. The repo ships a one-command proof you can run
on your own key: it starts a real session, writes a small ledger to the sandbox, kills the client,
re-attaches off the server-side event log, and checks the ledger files are still there, with a
wrong-session-id control that must recover nothing (so a clean resume is server-side persistence, not
luck). It proves the loop survives a kill. It does not prove eval quality, and I say so.

{repo_link}

Run it yourself: `make retention` is the $0 dated comparison (no key, no spend), and `make
retention-live` is the opt-in live kill-and-resume (a current `anthropic` SDK and your key, a few
minutes and a small bounded spend). Every retention term traces to the vendor's own doc, dated, so you
can check it instead of trusting me.

And if you want the edges where Claude genuinely leads head-to-head, they are in the same repo with
their own run-it-yourself receipts: programmatic tool calling cut billed input tokens by about 28% on a
fan-out task where no competitor keeps your own tool outputs out of context (`make ptc`), and Citations
returns a guaranteed-valid, per-character source pointer into your user's own document, free of output
tokens (`make citations`).

The reason I am handing you a parity result instead of a Claude win is the reason to trust the rest:
when this engine says Claude leads, that claim survived the same scrutiny this one did.

Go build,

{your_name}
Building with Claude

---

### Why it is built this way (not part of the email)

- **It does not invent a capability lead.** Durable kill-and-resume is parity, so the email pitches the
  managed-harness bundle (build none of the plumbing) and the time axis, never a made-up Claude-only
  resume. An overstated claim in a founder's inbox is worse than no claim.
- **The beta and the not-ZDR caveat ship up front.** A founder with a compliance requirement needs to
  know before they build, not after, so both caveats are in the body, not a footnote.
- **The real anchors are the genuinely Claude-ahead edges.** PTC and Citations carry their own measured
  head-to-head receipts in this repo, so the founder is pointed at the edges that won, while the
  retention work saves them the plumbing on whichever provider they pick.
- **Every retention term is a receipt.** The no-30-day-TTL, the roughly 2-hour Gemini handle, and the
  beta header all trace to the dated vendor docs in `edges/retention-resume/sample.txt`, fetched
  2026-06-18, not quoted from memory.
