# Product-team email: retention and resume, the honest parity read (this run ships this one)

This edge is parity on the capability (durable kill-and-resume is table stakes across all three
vendors), so this internal note is what goes out, not a founder capability pitch. Same rigor as a
founder email. The engine writes the product-team note when a run is a tie, not a pitch built on a
claim that did not separate.

---

**Subject:** Durable kill-and-resume is parity across all three vendors, so we pitch the bundle, not a Claude-only resume

To the Claude platform team,

I built the retention/resume edge into the competitive engine and grounded it against the live vendor
docs on 2026-06-18. I want to flag the parity verdict and exactly what it does and does not let us
claim, because an earlier brief framed Managed Agents resumability as a Claude-only capability, and that
is an overclaim we should not ship.

The grounded reality. Durable kill-and-resume is table stakes:

- Claude Managed Agents (beta, `managed-agents-2026-04-01`) is stateful by design, sessions resume
  cleanly after pauses, and event history is persisted server-side and fetchable in full. Source:
  platform.claude.com/docs/en/managed-agents/overview.
- OpenAI ships durable state GA: the Responses Conversations object across sessions, devices, and jobs
  (items have no 30-day TTL), and Agents SDK file-backed sessions that survive a process restart and
  resume a paused run. Source: developers.openai.com/api/docs/guides/conversation-state.
- Gemini Live resumes via `SessionResumptionConfig` within about a 2-hour handle window. Source:
  ai.google.dev/gemini-api/docs/live-session.

So we must not say "only Claude can kill-and-resume" or "Managed Agents is Claude-only." All three ship
resumable hosted sessions.

What we CAN claim, and how I framed it. The genuine, defensible edge is the bundle and the time axis,
both labeled beta. The managed harness gives a founder the sandbox, the agent loop, a persistent
filesystem, conversation history, and built-in compaction in one product, so they build no agent loop,
no sandbox, and no tool layer. And Claude holds state the longest: no 30-day TTL like an OpenAI
standalone response, no roughly 2-hour handle cap like Gemini Live. The honest caveat ships with it:
because state stays server-side, Managed Agents is not ZDR- or HIPAA-BAA-eligible, so a compliance-bound
team should use the self-hosted sandbox.

Two doc gaps I am holding open, not papering over. The Gemini 7-day retention figure an earlier brief
carried is unverified (I confirmed the roughly 2-hour resumption handle and the audio-only session cap,
not a 7-day number), and a full Gemini managed-agent-runtime parity pass needs the Vertex AI Agent
Engine docs, which were not reachable, so any "Gemini has no managed agent runtime" line is held
never-evaluated.

How the demonstrator enforces this. The default `make retention` run spends nothing and emits a
doc-grounded parity receipt, never a head-to-head arm (a parity capability has no arm worth running).
The verdict can never be claude-ahead by construction: no competitor arm runs, so the honesty contract
holds the verdict at parity. The opt-in `make retention-live` runs a real kill-and-resume with a
negative control, but its verdict is within-Claude (a continuity and bundle proof), never a head-to-head
lead. Related correction in the same pass: context editing versus server-side compaction is also parity
(both vendors ship GA server-side compaction, Claude also ships beta in-place editing), so the
long-horizon LEADERSHIP claim should anchor on the independent METR time-horizon, not context editing.

To reproduce: `make retention` (no key, no spend, the dated comparison) or `make retention-live`
(opt-in, a current `anthropic` SDK and a key, a small bounded spend). The receipt is
`edges/retention-resume/sample.txt`, every term traced to a dated vendor doc.

{your_name}
