Subject: One flag, and Claude keeps your bulky tool results off your token bill (about 28% fewer input tokens, measured)

Hey {first_name},

If your agent calls a tool many times over data it then has to crunch (expense checks across a team, rollups across regions or accounts, log or trace triage), every one of those tool results gets pulled into the model's context and you pay input tokens for all of it, even the rows the model only sums and throws away.

Claude has a GA feature for this called programmatic tool calling. Add one field to a tool, allowed_callers: ["code_execution_20260120"], and instead of one model round-trip per call, Claude writes a script in a sandbox that calls your tool in a loop, filters and aggregates the results there, and returns only the answer. The bulky tool outputs go to the sandbox, not the model, so you are not billed input tokens for data the model never reads.

I measured it on the same fan-out task two ways, on the same model (Sonnet 4.6), with an identical-answer check: across 4 regions of 60 sales rows each (240 rows), find the highest-revenue region.

- Plain tool use: every row flows through the context, so you pay 9,451 billed input tokens.
- Programmatic: the rows go to the sandbox, so you pay 6,828 billed input tokens (about 28% fewer), and the sandbox returns the exact winner.

One scope line so the number holds when you run it: this pays off when your agent calls a tool many times over data it then crunches (the fan-out shape). On a real slow tool you also save the per-call model round-trip. It is GA today.

The reason I trust that number enough to send it: it comes out of an engine I re-run every week. The engine re-checks the live OpenAI, Gemini, and Claude docs, diffs what shipped against the last run, ranks the genuine differentiators, and only pitches the ones it can still prove with a fair head-to-head on real keys. A blocked doc fetch is logged as unknown, never as a competitor gap, so it cannot invent a Claude lead. So this is not a claim from a launch post. It is what survived this week's re-check.

The second edge it surfaced, if you are building over your users' own documents (contracts, clinical notes, filings, support docs): Claude Citations. Turn on citations: {"enabled": true} per document and Claude returns each claim with a character-level pointer into the source plus the verbatim quote, extracted and guaranteed to resolve by the API, free of output tokens, with zero resolver code on your side. The click-through to the exact sentence is the trust layer for that kind of product, and only Claude returns a per-character document pointer. The DIY path is to ask the model for the quote and resolve it yourself with str.find, which breaks the moment the model paraphrases, and you own and pay for that code.

You do not have to take the 28% on faith. The programmatic-tool-calling edge ships as a forkable app. Clone the repo, paste your own Messages-API tool dict and the Python that runs it into one file (app/yourtool.py), and run make app. It runs your own fan-out task twice, plain tool use vs programmatic, and prints your before/after input-token bill and the dollar delta at the model's price, with an upfront cost line before it spends anything. Out of the box it ships a worked example, so make app-check gives you a real number before you change a line. The whole thing costs $0.06 on Sonnet to reproduce.

{repo_url}
(The repository link resolves on publish.)

Run it yourself: make setup, then cp .env.example .env and paste your Anthropic key, then make ptc. $0.06 on Sonnet for the two runs, every token read off the real API.

Go build,

{your_name}
Building with Claude
