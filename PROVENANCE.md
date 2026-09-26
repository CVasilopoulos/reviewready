# Provenance

This project was built for the IBM Bob 2.0 Hackathon (September 2026). The submission rules require
that we include any code or files where IBM Bob 2.0 assisted. We go further and state, file by file,
what produced each one.

## Authored by IBM Bob 2.0

| Path | Bob task | Session artefacts |
|---|---|---|
| `contract.yml` | 01 compile the contract | `bob_sessions/01-compile-contract.{png,md}` |
| `checkers/prior_art.*` | 02 | `bob_sessions/02-*.{png,md}` |
| `checkers/contract_compliance.*` | 03 | `bob_sessions/03-*.{png,md}` |
| `checkers/evidence.*` | 04 | `bob_sessions/04-*.{png,md}` |
| `checkers/interface_shape.*` | 05 | `bob_sessions/05-*.{png,md}` |
| `checkers/subproject_router.*` | 06 | `bob_sessions/06-*.{png,md}` |
| `reports/*`, `reports/SUMMARY.md` | 07 parallel corpus run | `bob_sessions/07-*.{png,md}` |
| `ONBOARDING.md` | 08 (optional) | `bob_sessions/08-*.{png,md}` |

`bob_sessions/` holds the task session consumption summary screenshot and the exported task history
markdown for every one of these tasks.

## Written outside Bob

| Path | By |
|---|---|
| the runner, the report renderer, the dashboard | Claude Code (Anthropic), human-directed |
| `corpus/` cache and the ground-truth labels | `gh` CLI + hand labelling from maintainer comments |
| slides, video, cover image, this file | human + Claude Code |

Mixed-tool provenance is normal for this event — the May 2026 edition's own technology statistics
list Claude and Claude Code among participants' tools. We record the split so the "clear application
of IBM Bob 2.0" criterion can be judged on what Bob actually did.

## Third-party material

The target repository, `ScrollPrize/villa`, is MIT licensed (© 2024 Vesuvius Challenge) and is
referenced at pinned commit `d285029ab6b62bfacf12cdb41bd4653867db73c0`. Its source is **not**
vendored here. Quoted maintainer comments are public GitHub comments, attributed to their authors.

This project is released under the MIT licence.


## Correction, 2026-09-26

The table above was written before the event. What actually happened:

**Bob produced** `contract.yml`, all three custom modes in `.bob/custom_modes.yaml`, their
twelve rules files under `.bob/rules-*/`, and the three checker scripts
`scripts/check_prior_art.py`, `scripts/check_contract.py` and `scripts/check_evidence.py`.
Bob also debugged its own false positives during each build and found a bug in its second
checker while writing its third.

**Claude Code produced** the corpus runner and `reports/SUMMARY.md`, and three fixes to the
checkers after the first full corpus run: deriving tool names from the diff instead of a
hard-coded list, accepting commit hashes written in parentheses, and searching for them
either side of a before/after label. Those fixes were not made by Bob because the forty
Bobcoins were exhausted by then. They are ordinary bug fixes, not new capability.

**Two planned checkers do not exist.** Interface-shape and subproject-router were cut for the
same reason. The submission claims three checkers, not five.

The Bob session summary screenshot for every Bob task is in `bob_sessions/`.
