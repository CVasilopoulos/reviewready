# ReviewReady

Your repository's contribution rules, compiled into an agentic gate.

Built for the IBM Bob 2.0 Hackathon, September 2026, against the open-source
[ScrollPrize/villa](https://github.com/ScrollPrize/villa) toolchain (MIT), pinned at
`d285029ab6b62bfacf12cdb41bd4653867db73c0`.

## Why

That repository writes its contribution rules down carefully, in prose, and nothing enforces
them. On ten real pull requests with public outcomes, four working fixes waited 14 to 17 days
and were closed by a staleness bot with no human ever reviewing them. Two were later fixed
again by contributors who could not see the closed attempt.

## What this is

Bob configuration a maintainer drops into their repository:

```
.bob/custom_modes.yaml        three custom modes, each with a minimal tool grant
.bob/rules-<slug>/            role, protocol, output schema and limits per mode
scripts/check_*.py            the script each mode drives
contract.yml                  27 rules Bob compiled from the repo's own documents
schemas/finding.json          the finding format every checker emits
reports/                      per-PR reports and SUMMARY.md
bob_sessions/                 Bob task session summaries, one per task
corpus/                       ten cached pull requests, scrubbed of personal data
```

## Results

Measured on the seven pull requests we did not write:

| | |
|---|---|
| Recall | 5 of 5 |
| False blocks | 0 of 2 |

`reports/SUMMARY.md` has the per-pull-request table, the comparison against the repository's
existing automation, and a plain statement of where the gate is wrong.

## Run it

```bash
python3 scripts/check_prior_art.py --pr 1683 --dry-run
python3 scripts/check_contract.py  --pr 1595 --eval-date 2026-08-24
python3 scripts/check_evidence.py  --pr 1724
```

Each prints findings as JSON against `schemas/finding.json`.

## Provenance and data

`PROVENANCE.md` records file by file what Bob produced and what it did not.
`DATA_SOURCES.md` lists every site used, and what was removed from the corpus before
publication.

AI-assisted, human-directed.
