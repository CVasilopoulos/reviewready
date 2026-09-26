## The problem, measured rather than asserted

`ScrollPrize/villa` is the open-source toolchain for reading the carbonised Herculaneum scrolls. Its contribution rules are written down carefully, in prose, across `CONTRIBUTING.md`, a pull-request template, and an `AGENTS.md` of per-subproject playbooks. Nothing enforces any of it.

We pulled ten real pull requests with public outcomes. Four of them — #1391, #1412, #1630 and #1724 — were working fixes that stayed open **17, 14, 16 and 14 days** and were then closed by a staleness bot **without any human ever reviewing them**. Sixty-one days of queued work, discarded unread.

Two of those four were fixed again later by different contributors who could not see the closed attempt: #1391 became #1683, #1630 became #1794. Both duplicates were withdrawn by their own authors once they found the earlier work.

The repository already runs two automated gates: one blocks pull requests touching more than twenty files, which none of these did, and the other is the staleness bot. On this corpus the existing automation fires four times, every time by closing a working fix nobody read. It catches neither duplicate.

## What we built

**A contract, compiled by IBM Bob from the repository's own documents.** `contract.yml` holds 27 enforceable rules: 25 quoted from a named file and line range, 2 marked `inferred` and each carrying its rationale. Every rule has a mechanical check, a severity justified by how the document phrases it, and a sentence to show a contributor who fails it.

**Three checkers, each packaged as a Bob custom mode** in `.bob/custom_modes.yaml`, with its own role definition, a `.bob/rules-<slug>/` folder of four rules files, a deliberately minimal tool grant — read, execute, todo, nothing that can write — and the script it drives. This is configuration a maintainer drops into their repository, not a program that happens to have been written with Bob.

- **Prior art.** Searches open *and closed* pull requests, because in this repository the closed ones are the trap, and reports overlap by file and function.
- **Contract compliance.** Iterates every rule in `contract.yml` and hard-codes none, so changing the contract changes the behaviour. It distinguishes a missing field from an empty one from one holding only the template's comment placeholder, and refuses to mark the verification checkbox satisfied merely because it is ticked.
- **Evidence.** Audits whether the proof a pull request offers is actually a proof: two distinct named commits, the same flags on both sides, real scroll data rather than toy input, and proof attached rather than described.

## Results, on pull requests we did not write

| | |
|---|---|
| Recall on the hold-out set | **5 of 5** |
| False blocks on the hold-out set | **0 of 2** |
| Whole corpus | 6 of 7 recall, 1 false block |

The control matters more than the recall. #1595 merged in a single day and #1724 was fully compliant; the gate returns REVISE on both, so it would not have stood in either contributor's way. #1724 is the whole point: a perfect submission, auto-closed after two weeks, never read.

Every verdict comes from running the three checkers over the cached corpus; nothing is mocked. `reports/SUMMARY.md` has the per-pull-request table, and the live demo opens any of the ten.

## Honest limits

Three of five planned checkers exist; interface-shape and subproject-router were cut when the forty Bobcoins ran out. One false positive remains, on a clean pull request that names its commit about eight hundred characters from the nearest before/after label — we left it failing rather than widen a window until the corpus passed. One miss, #1797, was closed purely on interface design and needs the checker we could not afford; that is precisely where a compiled contract stops and a human reviewer begins. Ten pull requests is a small corpus and these numbers carry wide error bars.

AI-assisted, human-directed.
