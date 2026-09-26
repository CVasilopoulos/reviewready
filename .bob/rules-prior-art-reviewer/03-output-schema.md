# Output Schema

Every response from the Prior Art Reviewer is a **JSON array** of finding
objects. Each object must validate against `schemas/finding.json`.

## Required fields

```jsonc
{
  "checker": "prior-art",          // always this value for this checker
  "severity": "blocker|major|nit",
  "rule": {
    "id": "prior-art/<slug>",      // e.g. "prior-art/closed-pr-same-issue"
    "source": "inferred",          // or a corpus file path
    "quote": "..."                 // optional: excerpt from diff or meta.json
  },
  "evidence": [                    // at least one item required
    {
      "what": "...",               // human-readable description
      "where": "corpus/1391/meta.json",  // file, PR number, or command
      "output": "..."              // raw excerpt proving the claim
    }
  ],
  "suggested_fix": "...",
  "confidence": 0.0                // 0.0-1.0; see calibration rules below
}
```

## Confidence calibration

| Situation | Confidence |
|---|---|
| Same issue number AND 2+ overlapping files AND overlapping function names in both diffs | 0.95 |
| Same issue number AND 1+ overlapping files | 0.85 |
| Overlapping files only, different issues | 0.65 |
| Merged commit touches same function | 0.90 |
| No prior art (negative result, thorough search) | 0.92 |
| No prior art (corpus incomplete, gh unavailable) | 0.45 |

Never assign 1.0. Never assign 0.0 unless the script errored.

## No-prior-art finding

When no matches are found, emit exactly one finding:

```json
{
  "checker": "prior-art",
  "severity": "nit",
  "rule": {
    "id": "prior-art/no-prior-art",
    "source": "inferred",
    "quote": "Thorough search of corpus found no overlapping prior work."
  },
  "evidence": [
    {
      "what": "PRs examined",
      "where": "corpus/",
      "output": "Checked N corpus entries; none overlap with candidate files or issues."
    }
  ],
  "suggested_fix": "No prior art detected; proceed with submission.",
  "confidence": 0.92
}
```

## Output wrapper

The script prints a JSON array to stdout — one finding per element. The mode
returns this array verbatim. No wrapper object, no markdown, no prose.

Example:

```json
[
  {
    "checker": "prior-art",
    "severity": "blocker",
    "rule": { "id": "prior-art/closed-pr-same-issue", "source": "corpus/1391/meta.json" },
    "evidence": [
      { "what": "PR #1391 references issue #1319, same as candidate #1683",
        "where": "corpus/1391/meta.json",
        "output": "closingIssuesReferences: [1319]" },
      { "what": "Both diffs modify vc_obj2tifxyz.cpp",
        "where": "corpus/1391/diff.patch vs corpus/1683/diff.patch",
        "output": "volume-cartographer/apps/src/vc_obj2tifxyz.cpp" }
    ],
    "suggested_fix": "Close this PR and continue work on #1391.",
    "confidence": 0.95
  }
]
```
