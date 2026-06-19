# state/

The durable spine of the recurring engine. Everything here is committed, on purpose.

`data/` is gitignored transient scratch (benchmark receipts, the last run's JSON). It is
rewritten every run, so it cannot hold anything that must survive a clone. The diff
baseline and the coverage ledger must survive a clone, or the engine loses its memory of
what it already saw and what it already drafted. So they live here, not in `data/`.

| Path | What it holds | Written by |
| --- | --- | --- |
| `coverage.jsonl` | one row per (edge_key, variant, run_date, status) so the email stream never repeats an edge to the same reader | the draft stream |
| `runs/` | a per-run manifest, `runs/<date>.json`, pinned at the last finished phase for checkpoint and resume | the cadence |
| `outbox/` | the gated, human-released drafts the cadence produced but never sent. Inert files only. No send transport is wired in the unattended path | the draft stream |
| `managed_state.json` | the Managed Agents session, agent, and environment ids for the Tier-2 resumable monthly run | the managed runtime |

The landscape baseline (`landscape/landscape.json`) is the diff baseline and lives in the
sibling `landscape/` dir, committed for the same reason.

## The boundary, in one line

The cadence runs the sweep, the diff, the rank, the draft into `outbox/`, and the written
record on its own. It asks before it spends credits on a benchmark or scaffolds a new edge
bundle. It never sends mail, posts in public, pushes a remote, or spends past the cap on a
schedule. `engine/gate.py` states that boundary and `engine.gate.audit()` proves no
outward or non-always action ran unattended.
