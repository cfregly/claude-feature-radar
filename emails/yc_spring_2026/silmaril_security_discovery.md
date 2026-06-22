Subject: Congrats on YC! A security route for prompt-injection defense

Hey Aum,

Congrats on YC.

I'm Chris Fregly on Anthropic's Applied AI team, focused on startups. I spend a lot of time with
teams moving agent demos into production, where the hard questions are cost, speed, reliability,
accuracy, and security at the same time.

I saw Silmaril is building prompt-injection defense that self-improves for AI-native applications and
agents. I would not force that into one of my public feature-hit briefs. The sharper route is a
security discovery conversation around the exact boundary your customers need to defend.

The Claude security surfaces I would map first:

| Security question | Claude pattern to test |
| --- | --- |
| Can we find vulnerable code paths before they ship? | Claude Code security review in the developer workflow |
| Can we review agent PRs before merge? | Claude Code security safeguards and PR-level review |
| Can we make tool boundaries explicit? | MCP/tool contract review: typed args, failure modes, destructive-action boundaries |
| Can enterprise buyers audit usage? | Compliance API, audit logs, connector controls |
| Can regulated customers own the encryption boundary? | CMEK for eligible Enterprise and Platform organizations |

The test I would build with you is not a generic "try Claude" demo. It is a prompt-injection eval
over an agent with real tool access:

```text
attacker input -> model/tool boundary -> allowed action?
expected: block, ask, or continue
evidence: tool call, refusal, source, and audit event
```

That gives you the security pillar in the same language buyers use: which attack chain was stopped,
which tool boundary caught it, what got logged, and what the operator does next.

If useful, reply with one prompt-injection workflow you use in demos. I can point you to the closest
Claude security pattern and the exact eval shape I would run.

Happy building,

--Chris Fregly
Applied AI, Startups, Anthropic
