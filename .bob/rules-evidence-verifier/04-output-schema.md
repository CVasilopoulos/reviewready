# Output Schema and Confidence Calibration

## Required fields

Every finding from the Evidence Verifier must conform to `schemas/finding.json`:

```jsonc
{
  "checker": "evidence",          // always this value
  "severity": "blocker|major|nit",
  "rule": {
    "id": "evidence/<slug>",      // e.g. "evidence/no-before-commit"
    "source": "CONTRIBUTING.md:20" // or "inferred" for heuristic rules
    "quote": "..."                 // verbatim sentence from source document
  },
  "evidence": [                   // at least one item required
    {
      "what": "...",              // human-readable description
      "where": "corpus/<N>/body.md",
      "output": "..."             // raw excerpt proving the claim
    }
  ],
  "suggested_fix": "...",
  "confidence": 0.0               // 0.0–1.0, calibrated
}
```

## Rule IDs

| Check | Rule ID | Severity |
|---|---|---|
| Missing before commit | `evidence/no-before-commit` | blocker |
| Missing after commit | `evidence/no-after-commit` | blocker |
| Before = after (same SHA) | `evidence/commits-not-distinct` | blocker |
| Missing before/after (minimal repr) | `evidence/no-commits-minimal-repr` | major |
| Asymmetric flags | `evidence/asymmetric-flags` | blocker |
| Unverifiable symmetry | `evidence/symmetry-unverifiable` | major |
| Synthetic data in evidence | `evidence/synthetic-data` | blocker |
| No proof artefact | `evidence/no-proof-artefact` | major |
| Number inconsistency | `evidence/number-inconsistency` | major |
| All checks pass | `evidence/pass` | nit |

## Confidence calibration

| Situation | Confidence |
|---|---|
| Before/after SHAs clearly identified in backtick context | 0.95 |
| Before/after SHAs inferred from prose (no backticks) | 0.75 |
| Explicit same-settings statement in body | 0.92 |
| Symmetry inferred from identical code-block commands | 0.85 |
| Symmetry unverifiable (output-only blocks) | 0.65 |
| Synthetic data found, no real-data signal | 0.85 |
| Real-data signal confirmed in scoped sections | 0.90 |
| Image attachment or code block present | 0.95 |
| Only indented code block present | 0.85 |
| Number contradiction detected | 0.70 |
| All checks pass (positive result) | 0.88 |

Never assign 1.0. Never assign 0.0 unless the script errored.

## Pass finding

When all five checks pass, emit exactly one finding:

```json
{
  "checker": "evidence",
  "severity": "nit",
  "rule": {
    "id": "evidence/pass",
    "source": "inferred",
    "quote": "All five evidence checks passed."
  },
  "evidence": [
    {
      "what": "Checks performed",
      "where": "corpus/<N>/body.md",
      "output": "commits: PASS; symmetry: PASS; real-data: PASS; artefact: PASS; numbers: PASS"
    }
  ],
  "suggested_fix": "No action required.",
  "confidence": 0.88
}
```

## Output wrapper

The script prints a JSON array to stdout — one finding per issue detected,
or a single pass finding if all checks pass. The mode returns this array
verbatim. No wrapper object, no markdown, no prose.
