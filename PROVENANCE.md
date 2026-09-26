# Provenance

This project was built for the IBM Bob 2.0 Hackathon (September 2026). The submission rules require
that we include any code or files where IBM Bob 2.0 assisted. We go further and state, file by file,
what produced each one.

## Authored by IBM Bob 2.0

| Path | Bob task |
|---|---|
| `contract.yml` | 02 compile the contract |
| `.bob/custom_modes.yaml` and every `.bob/rules-*/` file | 03, 04, 05 |
| `scripts/check_prior_art.py` | 03 prior-art reviewer |
| `scripts/check_contract.py` | 04 contract compliance |
| `scripts/check_evidence.py` | 05 evidence verifier |

Two planned checkers, interface-shape and subproject-router, were cut when the Bobcoin
allocation ran out. See the correction at the end of this file for the full split and for
what happened to the session artefacts.

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

**There are no Bob session screenshots, but the sessions themselves are here.** An earlier draft
of this repository shipped six PNG files under `bob_sessions/` named as though each were the session
consumption summary of one Bob task. They were not: all six were byte-identical copies of an
unrelated screenshot, of a Codabench submission page from a different project. No screenshot of a Bob
session was ever captured. The files were removed on 2026-09-26 and this paragraph replaces them,
rather than quietly deleting them, because the earlier commit is public and a judge may have seen it.

In their place, `bob_sessions/` now holds the sessions exported from **IBM Bob's own local database**
(`~/.bob/db/bob.db`) by `scripts/export_bob_sessions.py`. That is the same store the IDE's summary
panel reads. Each file carries the task id, the exact prompt, the per-session Bobcoin spend and
context-window breakdown, and every tool call Bob made with its timestamp and target — the content a
screenshot would have shown, in a form a judge can check rather than squint at.

## What the database says, checked against the claims above

| | |
|---|---|
| Sessions with a non-zero cost | **4** |
| Bobcoins, top-level tasks | 39.2409 |
| Bobcoins, subagents | 0.5508 |
| **Total** | **39.7917 of an allocation of 40** — the IDE reports 0% remaining |

- **`contract.yml` was written by Bob**, in session `01-init-project-context`, in 94 logged edits
  between 19:44 and 19:51 on 2026-09-25. This one is corroborated twice: by that session's tool-call
  table and by Bob's own `attribution_logs` table, reproduced in `bob_sessions/ATTRIBUTION.md`.
- **Session 01 spawned four subagents in parallel** to survey villa's subprojects. They are listed
  with their individual costs at the foot of that session's file.
- **The three checker scripts, `custom_modes.yaml` and all twelve `.bob/rules-*/` files were written
  by Bob**, across sessions `02` and `03`. Session 02 is titled "build the first checker" but produced
  two of them, which is why the next session is titled "the third". Bob's attribution log does not
  cover these, because it only records edits inside the git repository it had open at the time
  (`demo/villa`) and the gate pack was not yet a repository; the tool-call tables are the record.
- **Bob found and fixed its own bugs.** The closing message of session 03 contains Bob's table of the
  three defects it was warned about and how each was avoided. It is quoted in that file.

## Still written outside Bob

Unchanged from the correction above: the corpus runner, `reports/SUMMARY.md`, the three post-budget
checker fixes, the demo page, the slides, the video and this file. Two planned checkers —
interface-shape and subproject-router — do not exist. The submission claims three, not five.
