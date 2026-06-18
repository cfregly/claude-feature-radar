# Founder email: the candidates we are NOT pitching yet (and why that should earn your trust)

This is the unusual email in the set. It pitches nothing. These three candidate edges are held because
the engine has not yet proven them against the competition, and the whole point of the engine is that
it tells you that plainly instead of dressing an unproven claim as a win. The hero stays
competitor-neutral per the repo convention. There is no measured receipt here, by design, because the
parity check has not run.

---

**Subject:** Three things I am NOT claiming yet, and the exact test each one has to pass first

Hey {first_name},

Most vendor outreach sends you a feature list and asks you to trust it. I want to do the opposite once,
so the claims I do make land harder.

Here are three Claude surfaces that look like they could be real edges for a founder, and that I am
holding back until I can prove them against the other platforms at their best:

1. A server-side fallback that recovers from a refusal inside a single call, with a credit applied. It
   could save you the client-side retry loop you would otherwise build. I have not yet confirmed that no
   competitor ships the same thing, so I am not claiming it.

2. A per-request reason for why a cache read missed, surfaced right in the usage object. It could turn a
   silent cost leak into a one-line debug. I have not yet confirmed the other usage objects stay silent
   where this one speaks, so I am not claiming it.

3. Claude Code as a build surface, the GitHub Action that opens pull requests following your repo
   conventions and runs headless in your CI. Codex and the Gemini CLI now ship equivalents for every
   headline piece, so this is likely parity, and I will say so if it is.

For each one the engine records the exact competitor surface to check it against and a machine-checkable
gate the proof has to pass. Until a skeptic fails to break the claim, the edge stays out of every email I
send you, including this one as a pitch.

If you want to see the held list and the test each candidate faces, it is one command and it spends
nothing:

```
make parity-gated
```

When one of these survives the check, you will get a separate email with the workload, the cost to
reproduce, and the number. If it does not survive, you will not hear about it as a win. That is the
trade I am offering: fewer claims, each one you can run yourself.

Link: {repo_link}

---

Provenance (not part of the email body): every candidate above is held `never-evaluated` in
`engine/demonstrators/other_parity_gated.py` until its parity check is recorded as surviving. No
measured number ships from this bundle, on purpose.
