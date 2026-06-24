Subject: Congrats on YC! A security route for prompt-injection defense

Hey Aum,

Congrats on YC.

I'm Chris Fregly on Anthropic's Applied AI team, focused on startups. I spend a lot of time with
teams moving agent demos into production, where the hard questions are cost, speed, reliability,
accuracy, and security at the same time.

I saw Silmaril is building prompt-injection defense that self-improves for AI-native applications and
agents. I made four small public security artifacts for exactly this boundary question: which tool
action is high risk, which injected instructions should block or ask, what evidence gets logged, how
MCP authorization is scoped, and which official source supports each security-control line.

The security surface I would map first is the exact boundary your product defends: model input,
retrieved content, tool call, action policy, operator review, and buyer evidence.

The prompt-injection preflight is here:

https://github.com/cfregly/claude-feature-hits/tree/main/tool_boundary_security

The audit-evidence check is here:

https://github.com/cfregly/claude-feature-hits/tree/main/audit_evidence_security

The MCP authorization check is here:

https://github.com/cfregly/claude-feature-hits/tree/main/mcp_authorization_security

The source-backed claims guard is here:

https://github.com/cfregly/claude-feature-hits/tree/main/security_claims_guard

Run all four with `make security`. The audit, MCP auth, and source-backed claim guards are $0.00 and
need no API key or network. The prompt-injection preflight makes twelve live Claude calls for $0.04
and passes 12/12 model decisions, with 0 unsafe tool executions.

The test I would build with you is not a generic demo. It is a prompt-injection eval
over an agent with real tool access:

```text
attacker input -> model/tool boundary -> allowed action?
expected: block, ask, or continue
evidence: tool call, refusal, source, and audit event
```

That gives you the security pillar in the same language buyers use: which attack chain was stopped,
which boundary stopped it, and what the operator does next.

Run it:

```shell
git clone https://github.com/cfregly/claude-feature-hits && cd claude-feature-hits
make security
```

If useful, reply with one prompt-injection workflow you use in demos. I can point you to the closest
Claude security pattern, the exact eval shape, and the source line I would map it to.

Happy building,

--Chris Fregly
Applied AI, Startups, Anthropic
