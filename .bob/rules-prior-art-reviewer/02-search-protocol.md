# Search Protocol

The checker must perform the four searches below, **in order**, and short-circuit
to "blocker" if an exact match is found in step 1 or 2.

All searches are **time-gated**: only PRs, issues, and commits whose `createdAt`
(or `mergedAt` for commits) is **strictly before** the candidate PR's
`createdAt` are considered.

---

## Search 1 — Closed PRs that reference the same issues

1. Read `corpus/<CANDIDATE>/meta.json` to get `closingIssuesReferences`.
2. For each referenced issue number N, scan every `corpus/<PR>/meta.json` that
   predates the candidate and extract PRs whose `closingIssuesReferences`
   contains N.
3. For each such prior PR, compare the changed-file sets (from `meta.json`
   `.files[].path`). If any file overlaps, it is a candidate match.
4. To confirm, diff the two `diff.patch` files and look for identical or
   near-identical hunks touching the same C++/Python functions.

**Trap**: closed PRs are the primary source of duplicate work in this repo.
Do **not** skip them because `state == CLOSED`.

---

## Search 2 — Open PRs touching the same files

1. Enumerate all `corpus/<PR>/meta.json` files that predate the candidate and
   have `state == OPEN`.
2. Find those whose `files[].path` overlap with the candidate's changed files.
3. Apply the same diff-comparison heuristic as Search 1.

---

## Search 3 — Issues that reference the same files

1. For each candidate issue number, read `corpus/issues/<N>.json`.
2. Check whether any prior PR's body or comments (`corpus/<PR>/body.md`,
   `corpus/<PR>/comments.json`) mentions those issue numbers.
3. Record cross-references as evidence, not as a standalone finding — use these
   to raise or lower confidence on findings from Searches 1 and 2.

---

## Search 4 — Merged commits touching the same files since the base commit

1. Run (or read from cache):
   ```
   gh api repos/ScrollPrize/villa/commits \
     --field sha=<BASE_COMMIT> --field path=<FILE> \
     --paginate -q '.[].sha'
   ```
   Cache the result to `corpus/commits/<BASE_COMMIT>_<FILE_SLUG>.json`.
2. For each commit, fetch its patch (cache to `corpus/commits/<SHA>.patch`).
3. If a commit's patch overlaps with the candidate diff's hunks, emit a
   blocker: "this is already fixed on main, rebase and re-check".

---

## Match classification

For each candidate match, report all of the following:

| Field | How to determine it |
|---|---|
| PR / issue number | from `meta.json` `.number` |
| Author | from `meta.json` `.author.login` |
| State | from `meta.json` `.state` |
| Closed-by | last `closed` event actor in `events.json`; classify as bot / author / maintainer |
| File overlap | intersection of `meta.json` `.files[].path` |
| Function overlap | grep for `+` or `-` lines in both patches touching the same C++ function name |
| Verdict | same fix / adjacent fix / unrelated |

---

## Severity assignment

| Condition | Severity | suggested_fix |
|---|---|---|
| Unmerged prior PR makes the same change | `blocker` | "Close this PR and continue work on #<N>." |
| Adjacent fix by another contributor | `major` | "Coordinate with @<author> on #<N> to avoid divergence." |
| Merged fix already on main | `blocker` | "this is already fixed on main, rebase and re-check" |
| No prior art found | `nit` | "No prior art detected; proceed with submission." |
