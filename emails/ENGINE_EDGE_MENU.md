# Measured Claude edges for builders

An internal operator menu of the edges in this engine repo, not a founder handout. Each one is a real
Claude capability, measured on a real task against OpenAI and Gemini at their best, with the receipt
committed in `edges/<edge>/`. It clones the private engine for the full three-arm comparison, so it
stays internal. Do not trust the table, clone the repo and re-run the one command. If the number moves
on the workload, that is the point.

Every benchmark reads its numbers off a live API call. Costs are the actual run, not estimates.

## Pick by your bottleneck

Three questions cover most builders. Find yours, run those two or three commands first.

- Is the bottleneck **trust**, answers over your users' own documents that have to be verifiable? Start
  with the grounding edges.
- Is the bottleneck **the bill at scale**, an agent that fans out over data or carries a big context?
  Start with the cost edges.
- Is the bottleneck **a long-running or stateful agent** that has to finish and keep its state? Start
  with the reliability edges.

## Trust: answers your users can verify

A wrong, uncited answer over a contract or a clinical note is a churn event. These edges return a
pointer back to the exact source, guaranteed by the API, with no resolver code on your side.

| Edge | What you get | Receipt | Run |
|---|---|---|---|
| Citations | A per-character pointer into your user's own document, every claim, with the quote free of output tokens. | 8 of 8 claims resolved, zero resolver code | `make citations` |
| PDF citations | A page pointer into a PDF you hand the model directly in the request. | Claude 5 of 5 on the right page, the direct-file path on the others returned none | `make pdf-citations` |
| Search results | Cite the chunks your own retriever returned, inline, with no hosted vector store to stand up. | Block-level pointer, 0 stored objects, where the others needed a hosted store of 6 | `make search-results` |
| Grounding stack | A text doc, a PDF, and a retrieved chunk all cited in ONE request, each with its own pointer. | 3 of 3 source types cited in one call | `make grounding-stack` |
| Web citations | A verbatim quote from the live web source, not just a link you have to re-open. | 9 of 9 web citations carried the source quote | `make web-citations` |

## Cost: keep the bill down at scale

When an agent fans out over data or carries a long context, the tokens are the bill. These edges keep
the bytes the model does not need out of what you pay for.

| Edge | What you get | Receipt | Run |
|---|---|---|---|
| Programmatic tool calling | The model writes one sandbox script that calls your tool in a loop and returns only the answer, so the bulky rows never hit the context. | 9,451 to 6,828 billed input tokens, about 28% fewer, same answer | `make programmatic-tool-calling` |
| Cache diagnostics | When a prompt-cache hit silently turns into a miss, the API names which prefix changed. | Root cause named on all 4 documented miss reasons, where the others expose only counters | `make cache-diagnostics` |
| Bulk extended output | One batch turn writes a deliverable larger than the other models can produce in a single request. | 230,607 output tokens in one turn, past the 128k and 65k single-request caps | `make bulk-output` |

## Reliability: long-running, stateful agents

The agents a founder actually lives with run for a while and have to keep their state. These edges are
measured in the regime where that bites.

| Edge | What you get | Receipt | Run |
|---|---|---|---|
| Exact-list ledger | A long tool-heavy stream where the agent keeps a precise running list and the context stays bounded. | Exact list returned at $0.67 and 60.7s, cheaper and faster than the other exact runs | `make ledger` |
| Task budgets | An advisory budget across the whole agent loop, so the agent hands off cleanly near a cap instead of truncating mid-action. | Clean handoff with 0 tool calls when the budget said stop | `make task-budget` |
| Code-execution state | The sandbox keeps your files across separate requests, and keeps them when the user steps away. | Read the file back after a 31-minute idle, where the other container had expired | `make code-execution-state` then `make code-execution-state-verify` |

## Run it yourself

```bash
git clone https://github.com/cfregly/claude-feature-radar && cd claude-feature-radar
make setup
make compare-deps                  # the OpenAI and Gemini arms
cp .env.example .env               # paste ANTHROPIC_API_KEY, OPENAI_API_KEY, GEMINI_API_KEY
make programmatic-tool-calling                           # start with your bottleneck's edge, about $0.08
```

Most edges are cents to a couple of dollars and print their cost before they commit anything. Each one
states where it holds and where it does not in `edges/<edge>/README.md`, because a scoped claim you can
check is worth more than a broad one you cannot.

Go build.

Building with Claude
