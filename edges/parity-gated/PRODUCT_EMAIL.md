# Internal note: three never-evaluated candidates and the parity check each one needs

To the product team. The engine surfaced three narrow candidate edges this run and is holding all three
as never-evaluated. None is pitched. This note records what each one is, the competitor surface it has to
be checked against, and the machine-checkable gate its proof would run, so the parity check can be
prioritized or the candidate can be retired.

## fallback_credit (correctness)

The claim under test is a server-side model fallback (Fable or Mythos) with a fallback credit that
recovers from a refusal inside a single call, against the client-side retry loop a founder would build on
a competitor. The gate the thin proof would run is: recovery happened in one call AND the credit was
applied. It is held because no skeptic pass has been run against a fetched competitor surface, and Fable
or Mythos may be access-gated on a given key (a dev key reaches Haiku, Sonnet, and Opus, not Fable
without Mythos access). An inaccessible tier is reported unavailable, never faked. Source:
platform.claude.com/docs/en/api/openai-sdk, fetched 2026-06-18.

## cache_diagnostics (observability)

The claim under test is a per-request cache_miss_reason in the usage object that explains why a cache read
missed (prefix below the minimum, changed prefix, expired TTL), against the OpenAI and Gemini usage
objects, which appear to surface no equivalent per-request miss reason to the caller. The gate is: the
miss reason is present on Claude AND absent on every fetched competitor. It is held pending the skeptic
pass, and the field name should be re-confirmed against the live usage schema before any quote. Source:
platform.claude.com/docs/en/build-with-claude/prompt-caching, fetched 2026-06-18.

## build_velocity (agentic-success)

The claim under test is Claude Code as a programmable build surface (the @claude GitHub Action that opens
pull requests following CLAUDE.md and runs headless in CI, plus plugins that bundle skills, agents, hooks,
and MCP), against Codex CLI with SKILL.md and the Gemini CLI. The gate is: a pull request merged following
CLAUDE.md AND fewer human-intervention steps than the competitor on the same repo and issue. It is the
weakest of the three: every headline primitive now has a shipping competitor equivalent, so parity is the
likely read, and it is best treated as supporting color rather than an anchored head-to-head. Source:
docs.claude.com/en/docs/claude-code/github-actions, fetched 2026-06-18.

## The ask

Run the skeptic pass (engine/verify.py) against a fetched competitor surface for each candidate and record
the verdict. Only a surviving check unblocks a candidate, and even then the verdict it can reach is
within-Claude, not a head-to-head lead. A killed check is the honest finding, and it ships here, not to a
founder. The honesty posture is the deliverable: an overstated edge in a founder inbox is worse than no
edge, so the engine holds these until a skeptic has been pointed at them.
