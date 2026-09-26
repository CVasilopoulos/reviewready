# Rate Limiting and Cache Rules

This checker operates under a strict cache-first policy to avoid GitHub API
rate limits and to ensure deterministic, reproducible results.

## Cache directory layout

```
corpus/
  <PR_NUMBER>/
    meta.json          # gh pr view --json (all fields)
    diff.patch         # gh pr diff
    body.md            # PR description
    commits.json       # gh pr view --json commits
    events.json        # gh api /pulls/<N>/events
    comments.json      # gh pr view --json comments
    reviews.json       # gh pr view --json reviews
    review_comments.json
  issues/
    <N>.json           # gh issue view --json
  commits/
    <BASE>_<FILE>.json # commit list for a file since a base commit
    <SHA>.patch        # individual commit diff
```

## Rules

1. **Never re-fetch.** Before making any `gh` API call, check whether the
   target file exists under `corpus/`. If it does, read it. Do not make the
   API call.

2. **Always cache.** When a `gh` call is unavoidable (corpus miss), write the
   response to the appropriate path under `corpus/` before processing it.

3. **One call at a time.** Never issue parallel `gh` requests.

4. **Paginate carefully.** Use `--paginate` only when the initial response
   contains a `Link` header. Cache the full paginated result as one file.

5. **Respect secondary rate limits.** Insert a 1-second sleep between
   consecutive `gh api` calls if more than 3 calls are needed in a session.

6. **No authentication escalation.** Use only the ambient `gh auth` token. If
   `gh auth status` fails, emit a finding with `confidence: 0` instead of
   prompting for credentials.

## Offline mode

If `gh` is not installed or not authenticated, the checker runs in corpus-only
mode. It will examine every PR and issue already under `corpus/` and note in
the `evidence` field that the search was corpus-limited. Confidence for
negative results drops to 0.45 in this mode.
