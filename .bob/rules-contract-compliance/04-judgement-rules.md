# Judgement Rules for AI-Guidelines Checks

Some rules in contract.yml require human-level prose judgement. This file
defines exactly how to handle them.

## General principle

For any rule requiring qualitative judgement:
1. State your reasoning explicitly in the `evidence` field.
2. Set `confidence` honestly — not decoratively.
3. When uncertain, say so; a false accusation is worse than a miss.
4. Never guess 1.0 for a judgement call.

---

## `real-scroll-data-origin`

**What to look for:**
- First-person verb ("I ran", "I tried", "I was running")
- A named tool from this repository (vc_render, fit_spiral.py, vc_obj2tifxyz,
  vc_grow_seg_from_seed, vesuvius.predict, etc.)
- A real data artefact: named scroll ("Scroll 1", "PHerc 0332"), specific
  segment ID, `.volpkg` path, `paths/<id>/<id>.obj` URL

**Fail signals:**
- Abstract claims only: "this would help users who…", "users running this tool"
- No personal session described
- Data described as "a 3D volume", "some test data", "a synthetic mesh"

**Borderline:** The section may be implicit (e.g. spread across One real
example + Why / where sections). Look across the whole body.

---

## `llm-human-commentary` — key judgement rule

This requires deciding whether the PR body contains **genuine human-written**
commentary as opposed to generated prose.

**Indicators of human authorship (each raises confidence of passing):**
- First-person personal narrative ("I was", "I reproduced", "I noticed")
- Specific named scroll, segment, or dataset with a concrete action on it
- Idiosyncratic phrasing, abbreviation, or domain shorthand
- Personal opinion or uncertainty expressed authentically ("I haven't tested
  on Linux", "I'm not sure if…")
- Cross-references to other PRs with specific observations about their diffs

**Indicators of LLM prose (each lowers confidence of passing):**
- Impersonal register throughout: "This PR addresses", "The change ensures"
- Exhaustive, symmetric bullet lists with no personal grounding
- Generic benefit framing: "This improves X by doing Y" without a personal
  use-case
- No typos, no hedges, no personal voice anywhere
- Boilerplate "edge case handled", "tests added" phrasing

**Decision rule:**
- If the body has 3+ human indicators and 0 LLM indicators: **pass**, confidence ≥ 0.80
- If the body has 1-2 human indicators and 0-1 LLM indicators: **pass**, confidence 0.65-0.79
- If the body has 0 human indicators and 2+ LLM indicators: **fail**, confidence 0.65-0.75
- Mixed signals: **pass** (err toward pass; state the uncertainty explicitly)
  with confidence 0.45-0.60

**Always include in evidence:** at least two quoted sentences from the body
with your analysis of why they read as human or generated.

---

## `llm-concise-description`

Count words in the body above the `## Details` heading.
- ≤ 300 words: no flag on word count
- 301-500 words: flag only if ALSO poor clarity (unexplained acronyms, dense
  notation)
- > 500 words: flag as major regardless, but note whether clarity is also poor

"Conciseness" does not mean minimalism. A 250-word body with concrete specifics
is more concise than a 150-word body of vague generalities.

---

## `llm-real-scroll-validation`

Beyond `no-synthetic-data`, this rule asks whether the proof was produced by
**this PR's specific code** rather than being lifted from prior results.

Signals that the proof is genuine:
- The Before/After data in the Proof matches what this diff changes
- Terminal output shows version/commit information matching the PR's head SHA
- The contributor references specific file sizes, grid dimensions, or numbers
  that would change between the upstream and this PR

Signals the proof may be disconnected:
- Proof shows results for a feature not in this diff
- Proof screenshots are dated before the PR's opened date
- Numbers in the proof contradict what this diff changes

If the proof is a minimal reproduction (e.g. a 2-line Python snippet proving
an OS-level bug), accept it as sufficient if: (a) the snippet actually
demonstrates the root cause, and (b) the PR explains why full scroll-data
proof is not necessary or not possible on this platform.

---

## `llm-human-review`

Satisfied by any of:
- A sentence like "I reviewed the generated diff" or "I read through the diff"
- A checkbox ticked confirming review (separate from the verification checkbox)
- Inline review comments addressing specific code choices
- A blockquote or aside addressing the diff directly

Note: the verification checkbox (`pr-verification-checkbox`) is a separate
rule and is never machine-verifiable. This rule is about whether the contributor
read the *generated* code, which is a weaker claim verifiable by the presence
of specific commentary.

---

## `proof-same-input`

When the Proof section uses a different input than the One real example:
- If the PR explicitly explains the reason (e.g. "OS-level bug reproducible
  without full data", "minimal reproduction"), accept it if the explanation
  is convincing.
- If no explanation is given and the inputs are clearly different, flag as major.

---

## `pr-inactivity-14-days` and `pr-age-28-days`

These rules require comparing the PR's timestamps against the current date.
If running from a corpus with a fixed `createdAt` and `updatedAt`, compute
against the timestamp in `meta.json`. If the PR is not yet open (pre-submission
check), these rules do not apply — emit nit/not-applicable.

---

## `codeowners-review-required`

This rule requires review data that may not be in the corpus.
If `reviews.json` is empty or absent, emit:
```json
{
  "severity": "major",
  "rule.id": "codeowners-review-required/unverifiable",
  ...
  "evidence": [{ "what": "No review data in corpus; cannot verify CODEOWNER approval." }],
  "confidence": 0.0
}
```
Never fail a PR on this rule without review data.
