# Founder email (Deliverable 2)

Format note: paste into a Google Doc or your sending tool. Plain text, no tracking, one link.

---

**Subject:** Your agent gets pricier the longer it runs. A two-minute fix on Claude.

Hi {first_name},

Congrats on the batch. You have almost certainly wired up an agent on at least one of the big
three models by now, so you have probably felt this one: the longer an agent runs, the more each
step costs. The whole transcript gets re-sent and re-billed as input on every turn, so a 40-step
agent pays for its first step forty times. It is a quiet tax on exactly the thing you want more
of, which is the agent doing real work on its own.

I built a tiny repo that shows what Claude does about it, and lets you reproduce it on your own
key in about two minutes. It runs the same agent twice on the same model. The first run is plain.
The second turns on two Claude features: context editing, which clears stale tool output from the
context server-side, and a memory tool the model writes to itself so it does not lose the thread.
Same task, same correct answer. The plain run's cost climbs with every step. The managed run stays
roughly flat and comes in at less than half the cost on a 32-step task. The gap only widens the
longer the agent runs.

{repo_link}

`make setup`, paste your key, `make demo`. Every number it prints is measured from the API, not
asserted by me.

Two honest notes. Both features are in beta, and the other platforms are not standing still, so
the repo re-checks this claim against everyone's live docs and will tell you when the gap moves.
The point is not that Claude wins forever. It is that for a long-running agent today, this one
pairing, a memory tool the model drives plus in-place context editing, is something only Claude
gives you, and you can prove it on your own machine before you take my word for it.

If you are building something agentic and want a second set of eyes, just reply. Happy to get on
a call and help you get set up with credits.

Build something great,

{your_name}
Claude Evangelist for Startups, Anthropic

---

### Notes on the choices here (not part of the email)

- **One claim, one proof, one link.** A founder who has tried all three platforms deletes a
  feature-list email. They will run a two-minute thing that proves a number on their own key.
- **No competitor is named.** The email shows what Claude does and lets the absence speak. The
  named, dated, sourced comparison lives one click away in the repo's brief, for anyone who wants
  to check the receipts.
- **The honest caveat is in the email on purpose.** Saying the features are beta and the gap can
  move is what makes the rest of it believable to a technical reader.
