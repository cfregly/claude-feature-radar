# Founder email draft (cadence, citations, grounding)

Drafted by the unattended cadence into the inert outbox. No model call, no send. A deterministic template filled from the edge's measured fields and the Chris Fregly voice guide, for a human to review, edit, and decide whether to send.

---

**Subject:** A Claude edge you can test using your own API key

Hey {first_name},

Quick builder note. If this workload looks like yours, the repo below lets you check the number using your own API key before you trust the claim.

Claude Citations can return source pointers for user-supplied documents, so a founder can check the exact span behind an answer.

Here is the receipt path: Estimated check cost: $0.01 using your own API key (estimated 2.0 minutes). Clone the repo and run one command:

```
make citations
```

The run prints its own receipt: the workload, the exact models on each side, the dollar cost off the real usage object, and the assumptions your own task would change. If your numbers move the result, that is the point, the repo is built for you to swap in your own workload. The gap can move as the platforms ship, so the repo re-runs the whole search instead of caching a winner.

Link: {repo_link}

Go build,
Chris

---

Provenance (not part of the email body):
- edge key: citations
- axis: grounding
- verdict: claude-ahead
- reproduce: make citations (estimated $0.01)
- This draft is inert. The cadence never sends. A human reviews, runs the deslop and outbound-scrutiny panel, and decides.
