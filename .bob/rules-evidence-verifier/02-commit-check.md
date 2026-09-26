# Commit-ID and Symmetry Checks

## Check 1 — Named before/after commits that differ

The proof must name an exact commit SHA for the *before* state and an exact
commit SHA for the *after* state, and the two SHAs must differ.

### How to detect commit SHAs

A commit SHA is 7–40 lowercase hexadecimal characters appearing inside
backticks in context that identifies it as *before* or *after*.

**Before-context patterns** (any one is sufficient):
- `` "before" is `<sha>` ``
- `` upstream `<sha>` ``
- `` built from upstream `<sha>` ``
- `` upstream vs `<sha>` ``

**After-context patterns** (any one is sufficient):
- `` "after" is `<sha>` ``
- The SHA appears in *after* context without matching any before-context

**Detection algorithm:**
1. Scan the full body for `<sha>` tokens (7–40 hex chars in backticks).
2. For each, check whether it sits within 150 chars of a `before` or `after`
   keyword. Exclude SHAs that follow `assets/` (image attachment hashes) or
   that are pure decimal digits (timestamp IDs like `20231007`).
3. Collect `before_shas` and `after_shas`.
4. The check passes if `before_shas` and `after_shas` are both non-empty and
   at least one SHA appears exclusively in one set (i.e., the two sets differ).

**Severity**: `blocker` if no before SHA, no after SHA, or the two sets are
identical with only one distinct SHA.

### Minimal-reproduction exception

If the PR body explicitly states it cannot provide before/after on real data
(e.g. "no checkout", "no data", "minimal reproduction", "reproduce the
failure"), downgrade the severity to `major` and note the stated limitation.
Still flag it — a human reviewer must confirm the justification is valid.

---

## Check 2 — Symmetric comparison (same flags on both sides)

A comparison where before and after use different flags, different input files,
or different settings is not a valid before/after proof. This is a `blocker`.

### Explicit same-settings statement (sufficient to pass)

Look for any of these phrases anywhere in the body (scoped to the Proof, Before,
After, and One real example sections):
- "same data and commands on both sides"
- "same settings, before and after"
- "identical call" / "identical command" / "identical invocation"
- "same flags" / "same input" / "on both sides of each comparison"

If found: pass with high confidence.

### Code-block asymmetry analysis (secondary check)

If no explicit same-settings statement is found, look at fenced code blocks
that contain both `# before` and `# after` comments. Extract command-like lines
(non-comment, non-blank, non-pure-output) from each half and compare:

- If both halves show identical tool names and the same positional arguments
  (excluding output path and binary path differences): **pass**.
- If different flags (e.g. `--flag` on one side, absent on the other) or
  clearly different input files appear: **blocker** — quote both command lines
  side by side in the `evidence` field.
- If the before/after blocks contain only terminal output (no command lines):
  the symmetry is unverifiable; emit `major` asking the contributor to state
  explicitly that the same flags were used on both sides.

### Special case: explicit exception in body

If the PR explicitly says why asymmetry exists (e.g. "before uses the old
binary and after uses the fixed binary" or "OS-level bug; no data needed"), and
the asymmetry is limited to the binary/commit (not the flags or input file),
emit a `nit` rather than a blocker.
