# Real-Data, Artefact, and Number Checks

## Check 3 — Real scroll data (not synthetic)

**Source**: `CONTRIBUTING.md:20`

**CONTRIBUTING.md quote to include when flagging**:
> "Bugfixes or improvements must be run on real scroll data. Synthetic or
> toy examples are not accepted."

### Scope rule (Bug-3 prevention)

Apply this check **only** to the **One real example** and **Proof** sections
of the PR body. Do NOT scan the entire body.

Rationale: the `## Details` section may legitimately mention synthetic test
meshes or unit-test fixtures while the actual proof uses real data. Checking
the whole body generates false positives.

### Real-data signals (any one is sufficient to pass)

A real-data signal is any of:
- Named scroll: `Scroll 1`, `Scroll 2`, `PHerc`, `PHercParis`
- Named volpkg: contains `.volpkg`
- Named segment path: `paths/<8+ digits>`, `segments/<8+ digits>`
- Named mesh file: `<8+ digits>.obj`
- Named tifxyz file: `<8+ digits>...tifxyz`
- Specific dataset identifier: `20231007`, `20230503`, `20260310`
- Explicit "real scroll" / "scroll dataset" / "scroll spiral" / "published segment"
- Scroll spiral root with tracks (confirmed by "scroll spiral" phrase)

### Synthetic-data signals (trigger flag only if no real-data signal in scope)

- `synthetic`, `toy example`, `randomly generated`, `fake data`, `dummy`,
  `mock data`, `test data`
- "a 3D volume" (generic), "some volume" (generic), "sample input"
- Explicit `np.random` / `numpy array` with no real-data reference in same sections

### Severity: `blocker` (from CONTRIBUTING.md)

Always quote the CONTRIBUTING.md sentence in `rule.quote` when flagging.

---

## Check 4 — Proof artefact attached (not just claimed)

Look for a physical artefact in the **Proof** section:
- GitHub image attachment: `https://github.com/user-attachments/assets/...`
- Markdown image: `![alt](url)`
- HTML img tag: `<img ...`
- Fenced code block: ` ``` ` ... ` ``` ` (terminal output, benchmark)
- Indented code block: 4-space indented non-blank lines
- Benchmark table: `| col | col |`

**Note**: "I ran the tool and it worked" or "results improved" with no
attached evidence is a claim, not proof. Require at least one artefact.

**Severity**: `major` (the PR might still be valid with additional evidence).

**Section bug note**: the Proof section in `extract_section` stops too early
when `# before` comment lines inside a fenced code block are mistaken for
Markdown headings. Use the fixed extractor that stops only at `**Bold:**`
headings, not at `## ...` or `# ...` lines.

---

## Check 5 — Number consistency

Numbers stated in the PR body must be mutually consistent. This is a
heuristic check; flag only obvious contradictions. Confidence should be
moderate (0.65–0.80) because the checker reads text, not computed results.

### What to check

1. **Grid size cross-references**: a number stated as the output grid in One
   real example (e.g. `961 x 4113`) should match the same number if it
   appears in the Proof section's code block outputs.
2. **Valid-point counts**: if the example states `N valid points` and the
   proof terminal block shows `M / T`, then `M` should equal `N` (ignoring
   formatting: `3,532,144` == `3532144`).
3. **Scale cross-references**: a scale stated in the example (e.g. `0.0602,
   0.1244`) should be consistent with the same value in the proof block
   (e.g. `0.0601765, 0.124434`). Rounded values are consistent; use a 5%
   relative tolerance.

### What NOT to flag

- Numbers in different sub-experiments (the PR may show multiple comparisons).
- Numbers that are explained as belonging to different configurations.
- Approximations or averages vs. exact values (flagging would generate noise).

### Severity: `major` if a clear contradiction; `nit` otherwise.
