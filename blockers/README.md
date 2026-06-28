# Production Blocker Intake

This directory is the field-signal layer for the production blocker loop. Radar still owns feature
classification. A blocker record adds the missing customer context that a receiving product or
engineering team needs before a miss becomes actionable.

Each `*.json` record must stay anonymized and must include:

- blocker id, date, category, severity, affected workload, consequence, workaround, evidence, privacy
  level, linked feature key, and misses slug
- recurrence count, value pillar, receiving owner, decision state, next action, learning-update target,
  and founder follow-up state
- replay command, fixture, receipt, expected result, and actual blocker

Run `make blockers` to render `GAP_PACKET.md` files into the product-owner misses checkout. Run
`make check-blockers` to verify that the committed misses packets still match these records.
