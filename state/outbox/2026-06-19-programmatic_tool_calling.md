# Founder email draft (cadence, programmatic_tool_calling, cost)

Drafted by the unattended cadence into the inert outbox. No model call, no send. A deterministic template filled from the edge's measured fields and the Chris Fregly voice guide, for a human to review, edit, and decide whether to send.

---

**Subject:** A Claude edge you can test on your own key

Hey {first_name},

Quick builder note. If this workload looks like yours, the repo below lets you check the number on your own key before you trust the claim.

Programmatic tool calling - Claude API Docs Messages Managed Agents Admin Resources   API reference English   Console Log in    Search... ⌘K First steps Intro to Claude Quickstart Building with Claude Features overview Using the Mess

Here is the receipt path: It costs about $0.08 and a few minutes to check on your own key (about 1.5 minutes). Clone the repo and run one command:

```
make programmatic-tool-calling
```

The run prints its own receipt: the workload, the exact models on each side, the dollar cost off the real usage object, and the assumptions your own task would change. If your numbers move the result, that is the point, the repo is built for you to swap in your own workload. The gap can move as the platforms ship, so the repo re-runs the whole search instead of caching a winner.

Link: {repo_link}

Go build,
Chris

---

Provenance (not part of the email body):
- edge key: programmatic_tool_calling
- axis: cost
- verdict: claude-ahead
- reproduce: make programmatic-tool-calling (about $0.08)
- This draft is inert. The cadence never sends. A human reviews, runs the deslop and outbound-scrutiny panel, and decides.

