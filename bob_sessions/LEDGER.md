# Bob task ledger

Generated from IBM Bob's own local database by `scripts/export_bob_sessions.py`.
Every number here is Bob's, not ours.

| # | task | started | duration | Bobcoins | tool calls | subagents |
|---|---|---|---|---|---|---|
| 00 | [00-smoke-test](00-smoke-test.md) | 2026-09-25 19:21:34 | 1 min | 0.0281 | 0 | 0 |
| 01 | [01-init-project-context](01-init-project-context.md) | 2026-09-25 19:32:18 | 21 min | 3.6915 | 49 | 4 |
| 02 | [02-prior-art-and-contract-checkers](02-prior-art-and-contract-checkers.md) | 2026-09-25 23:38:10 | 319 min | 17.9104 | 112 | 0 |
| 03 | [03-evidence-verifier](03-evidence-verifier.md) | 2026-09-26 08:33:15 | 159 min | 17.6108 | 103 | 0 |

**Top-level tasks: 39.2409 Bobcoins.** Subagents a further 0.5508. **Total 39.7917 of an allocation of 40**, which the IDE reports as 0% remaining.

Two further sessions exist in the database with a cost of exactly 0 — an empty window opened
on 2026-09-25 17:57 and another on 2026-09-26 12:20. They are not exported because nothing
was run in them.

`ATTRIBUTION.md` holds Bob's own per-file edit log (5 file/tool pairs).

## What this ledger does not contain

No screenshots. The session consumption figures above are read straight out of Bob's
database, which is the same source the IDE's own summary panel displays. An earlier draft
of this repository shipped six PNGs claiming to be those panels; they were copies of an
unrelated screenshot and were removed. `PROVENANCE.md` records that in full.
