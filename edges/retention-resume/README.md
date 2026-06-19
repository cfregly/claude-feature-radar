# Edge: retention and resume, does the unattended loop survive a kill, and on what terms

Part of [claude-feature-radar](../../README.md). The question this answers for a founder running a
long, unattended agent: when the client dies mid-run, does the work survive, and how do the retention
terms compare across vendors. The honest read, grounded against the live vendor docs on 2026-06-18, is
**parity on the capability**: durable kill-and-resume is table stakes across Claude, OpenAI, and Gemini.
This bundle is built to never overclaim that, and to name the real, narrower win instead.

**The verdict is doc-grounded parity, and that is the finding.** Surviving a kill and re-attaching is
not a Claude-only capability. The genuine Claude edge, labeled beta, is two things: the fully managed
harness bundle (one product gives you the sandbox, the agent loop, a persistent filesystem,
conversation history, and built-in compaction, so you build none of it) and the strongest persistence
on the time axis (no 30-day TTL like OpenAI standalone responses, no roughly 2-hour handle cap like
Gemini Live).

## What it proves, and why the default spends nothing

A parity capability has no head-to-head arm worth running, because the run would only re-show parity.
So the proof for a parity edge is the grounding, not a benchmark. The default `make retention` is a
$0 dated comparison: it reads each vendor's strongest durable-resume surface off its own docs and
prints the retention table, the bundle win, and the beta caveat. No key, no network, no Managed Agents
spend. Full output in [`sample.txt`](sample.txt).

| vendor | strongest durable-resume surface | time axis | maturity |
|---|---|---|---|
| Claude | Managed Agents sessions, stateful by design, event history persisted server-side and fetchable in full | no 30-day TTL and no idle handle cap on the session | beta (`managed-agents-2026-04-01`) |
| OpenAI | Responses Conversations object across sessions, devices, and jobs, plus Agents SDK file-backed sessions that survive a process restart | conversation items have no 30-day TTL, standalone responses default to a 30-day TTL | GA |
| Gemini | Live API session resumption via `SessionResumptionConfig` | resumption handle valid for about 2 hours after the session ends | GA (Live API) |

Sources, all fetched 2026-06-18: Claude at
[platform.claude.com/docs/en/managed-agents/overview](https://platform.claude.com/docs/en/managed-agents/overview),
OpenAI at
[developers.openai.com/api/docs/guides/conversation-state](https://developers.openai.com/api/docs/guides/conversation-state),
Gemini at [ai.google.dev/gemini-api/docs/live-session](https://ai.google.dev/gemini-api/docs/live-session).

## The Claude win, stated honestly (beta)

The managed-harness bundle is the genuine edge. An Anthropic-hosted or self-hosted sandbox plus the
agent loop plus a persistent filesystem plus conversation history plus built-in compaction, in one
product, so the founder builds no agent loop, no sandbox, and no tool-execution layer. The capability
of surviving a kill is parity. The bundle and the time axis are the win. Two caveats ship with it:
Managed Agents is in beta (the `managed-agents-2026-04-01` header, which the SDK sets automatically,
enabled by default for all API accounts), and because state stays server-side it is not eligible for
Zero Data Retention or a HIPAA Business Associate Agreement.

## The live kill-and-resume (opt-in, never on a schedule)

The continuity engine can prove the bundle survives a real kill,
but it is an opt-in you trigger, never the default and never on a schedule. `make retention-live`
starts a live Managed Agents session that writes a small ledger to the sandbox, kills the client,
re-attaches off the server-side event log, replays the prior events, checks the ledger files are still
present, and reports the resume gap. It runs a wrong-session-id negative control (which must recover
nothing, so the clean resume is attributable to server-side persistence and not luck) and a mid-run
steer. The continuity gate passes only when events were replayed, the sandbox files survived, and the
negative control recovered nothing. Even when it passes, the verdict stays within-Claude (a continuity
and bundle proof, labeled beta), never a head-to-head capability win, because the capability is parity.
The scope is explicit: it proves the loop survives a kill and the retention terms, not eval quality.

## Run it yourself

```bash
git clone https://github.com/cfregly/claude-feature-radar && cd claude-feature-radar
make retention          # the $0 doc-grounded retention/bundle parity receipt (no key, no spend)
make setup              # only needed for the opt-in live run below
make retention-live     # OPT-IN: the live Managed Agents kill-and-resume (beta, spends a small amount)
```

`run.py` is not the entry point here. The demonstrator runs directly. `make retention` needs nothing
installed and spends nothing. `make retention-live` needs `ANTHROPIC_API_KEY` and a current `anthropic`
SDK (it sets the `managed-agents-2026-04-01` beta header automatically), and it spends a small, bounded
amount of Managed Agents sandbox time, a few minutes, well under the per-edge cap. The surface is beta
and moves monthly, so re-ground the header before quoting it.

See [`PRODUCT_EMAIL.md`](PRODUCT_EMAIL.md) for the internal parity read (the verdict this run ships):
the doc-grounded retention terms and the managed-harness bundle win, labeled beta.
