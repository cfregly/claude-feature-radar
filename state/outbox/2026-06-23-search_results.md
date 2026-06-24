# Founder email draft (cadence, search_results, accuracy)

Drafted by the unattended cadence into the inert outbox. No model call, no send. A deterministic template filled from the edge's measured fields and the Chris Fregly voice guide, for a human to review, edit, and decide whether to send.

---

**Subject:** A Claude edge you can test using your own API key

Hey {first_name},

Quick builder note. If this workload looks like yours, the repo below lets you check the number using your own API key before you trust the claim.

Claude can cite developer-supplied RAG chunks inline with typed source pointers and zero hosted objects.

Here is the receipt path: Estimated check cost: $0.10 using your own API key (estimated 2.0 minutes). Clone the repo and run one command:

```
make search_results
```

The run prints its own receipt: the workload, the exact models on each side, the dollar cost off the real usage object, and the assumptions your own task would change. If your numbers move the result, that is the point, the repo is built for you to swap in your own workload. The gap can move as the platforms ship, so the repo re-runs the whole search instead of caching a winner.

Link: {repo_link}

Go build,
Chris

---

Provenance (not part of the email body):
- edge key: search_results
- axis: accuracy
- verdict: claude-ahead
- reproduce: make search_results (estimated $0.10)
- This draft is inert. The cadence never sends. A human reviews, runs the deslop and outbound-scrutiny panel, and decides.
