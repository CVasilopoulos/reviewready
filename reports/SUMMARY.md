# Gate results on the labelled corpus

Produced by running the three built checkers over every cached pull request.
Nothing here was tuned to improve these numbers; where the gate is wrong it is left wrong and said so.

## Headline

- **Hold-out recall: 5 of 5** — of the pull requests really rejected or sent back, how many the gate flagged for the right reason.
- **Hold-out false-block rate: 0 of 2** — of the ones really merged or fully compliant, how many the gate wrongly blocked.
- Whole corpus recall: 6 of 7. Whole corpus false-block: 1 of 3.

## Per pull request

| PR | Gate | Gate's top reason | Real outcome | Real reason | Agree | Incumbent automation |
|---|---|---|---|---|---|---|
| #1391 | BLOCK | `real-scroll-data-origin` | CLOSED unreviewed | stale-bot auto-close at 17d; body has 0/6 template fields, no proof | yes | pr-time-limits: auto-closed at 17d idle |
| #1412 | BLOCK | `real-scroll-data-origin` | CLOSED unreviewed | stale-bot auto-close at exactly 14d; 0/6 template fields, no attached output | yes | pr-time-limits: auto-closed at 14d idle |
| #1630 | BLOCK | `real-scroll-data-origin` | CLOSED unreviewed | stale-bot auto-close at 16d; 1/6 template fields, no checkbox | yes | pr-time-limits: auto-closed at 16d idle |
| #1683 | BLOCK | `prior-art/closed-pr-same-issue` | CLOSED by author | duplicate of #1391, which was bot-closed five days earlier | yes | nothing |
| #1724 | REVISE | `pr-verification-checkbox/unverifiable-by-machine (major)` | CLOSED unreviewed | fully compliant, never read by a human | yes | pr-time-limits: auto-closed at 15d idle |
| #1794 | BLOCK | `prior-art/closed-pr-same-issue` | CLOSED by author | superseded eight minutes later; duplicate of #1630 and #1781 | yes | nothing |
| #1595 | REVISE | `llm-human-review (major)` | MERGED in 1 day | clean, narrow, real bug | yes | nothing |
| #1781 | BLOCK | `prior-art/closed-pr-same-issue` | OPEN, change requested | argument documented as one thing, silently ignored | yes | nothing |
| #1797 | REVISE | `llm-concise-description (major)` | CLOSED on design | 'no good reason to add this mixture' | **no** | nothing |
| #1798 | BLOCK | `evidence/no-before-commit` | OPEN, positive | clean | **no** | nothing |

## Where the gate is wrong, stated plainly

- **#1798 is a false positive.** It is a clean pull request of our own. It names its before commit (`bcf631dd3`) in a Proof section about 800 characters away from the nearest before/after label, and the evidence checker's context window is 200 characters either side, so it reports both commits missing. Widening the window further would start fitting the checker to this corpus, so it is left failing.
- **#1797 is a miss.** It was closed purely on interface design, which is the job of the fourth checker. That checker was never built: the Bobcoin budget ran out after three. The gate returns REVISE where the truth is BLOCK, and it cannot do better without that checker.
- **#1724 is the one that matters most and the gate gets it right.** Fully compliant, real scroll data, before and after commits, proof attached, and it was still auto-closed after fifteen days without a human reading it. The gate returns REVISE, not BLOCK, so it would not have stood in this contributor's way.

## What the repository's existing automation would have caught

The repository already runs two gates. `large-pr-review-gate.yml` blocks pull requests touching more than twenty files; no pull request in this corpus does. `pr-time-limits.yml` closes anything idle fourteen days or open twenty-eight. On this corpus the incumbent fires on four entries, and in every case it fires by **closing a working fix nobody reviewed** rather than by telling its author anything.

**Neither incumbent gate catches either duplicate re-submission (#1683, #1794).** Both were written because the earlier fix had been closed and was invisible. That is the gap this project fills.

## Honest limits

- Ten pull requests is a small corpus, and seven of them are the hold-out. These numbers carry wide error bars.
- Three of five planned checkers exist. Interface-shape and subproject-router were cut when the budget ran out.
- Three false positives were fixed after the first corpus run, all on compliant pull requests, by making the checks derive names from the diff instead of a hard-coded list and by accepting commit hashes written in parentheses. Those fixes were made by Claude, not Bob, because the Bobcoins were exhausted; `PROVENANCE.md` records the split.
