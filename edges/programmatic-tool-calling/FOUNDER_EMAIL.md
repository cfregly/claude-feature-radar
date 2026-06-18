# Founder email: the Programmatic Tool Calling edge

The sharpest edge: a cost lever no competitor names, measured on our own key.

---

**Subject:** One flag and Claude writes code that calls your tools in a loop, so the bulky results never touch your token bill

Hey {first_name},

If your agent calls a tool many times over data it then has to crunch (expense checks across a team,
rollups across regions or accounts, log or trace triage), every one of those tool results gets pulled
into the model's context and you pay input tokens for all of it, even the rows the model only needs to
sum and throw away.

Claude has a GA feature for this called programmatic tool calling. Add one field to a tool,
`allowed_callers: ["code_execution_20260120"]`, and instead of one model round-trip per call, Claude
writes a script in a sandbox that calls your tool in a loop, filters and aggregates the results there,
and returns only the answer. The bulky tool outputs go to the sandbox, not the model, so you are not
billed input tokens for data the model never reads.

I measured it on the same fan-out task two ways, on the same model (Sonnet 4.6), with an
identical-answer check: across 4 regions of 60 sales rows each (240 rows), find the highest-revenue
region.

- Plain tool use: every row flowed through the context, **9,451 billed input tokens**, and the model,
  summing 240 rows in its head, failed to produce a clean answer.
- Programmatic: the rows went to the sandbox, **6,828 billed input tokens (about 28% fewer)**, and the
  sandbox code computed the exact winner correctly. Anthropic's own docs report about 24% fewer input
  tokens on agentic-search benchmarks, so our 28% is in line, measured on our key.

Two honest things. The win is fan-out-shaped: on a task that is just one tool call the docs note it is
flat to about 8% more expensive, so this is for tool-heavy agents, not every agent. And it added model
round-trips here (the model called the tool serially from code), so on an instant mock tool it ran a
bit slower. The token saving is the win, and on a real slow tool you also save the per-call model
round-trip. It is GA, but not on Bedrock or Vertex and not ZDR-eligible, so check your stack.

What makes it an edge: no competitor exposes this. OpenAI ships a code interpreter and tool search,
but neither keeps your own custom-tool outputs out of the model's context the way `allowed_callers`
does.

{repo_link}

Run it yourself: `make setup`, then `cp .env.example .env` and paste your Anthropic key, then `make
ptc`. About six cents on Sonnet for the two runs, every token off the real API.

Go build,

{your_name}
Building with Claude
