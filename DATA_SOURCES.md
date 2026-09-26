# Data sources

The hackathon rules require that entrants bring their own data, use no client, company
confidential, personal or social-media data, use public web data only where the terms permit
commercial use, and keep a list of the sites used. This is that list.

## Sites used

| Source | What was taken | How | Terms |
|---|---|---|---|
| `github.com/ScrollPrize/villa` | Ten pull requests and their linked issues: title, body, diff, commits, review comments, reviews and timeline events | GitHub REST and GraphQL API through the `gh` CLI, authenticated as the entrant | Repository is MIT licensed, © 2024 Vesuvius Challenge. MIT permits commercial use, modification and redistribution with attribution. |
| `github.com` public issue and pull-request pages of the same repository | Maintainer outcomes used as ground-truth labels | Same API | Public content of an MIT-licensed repository, accessed under the GitHub Terms of Service, which permit viewing and forking public repositories |

Nothing else was scraped. No dataset was bought, no login-walled source was used, and no
site was accessed outside its published API.

## What the corpus contains

`gate-seed/corpus/` holds ten pull requests, identified by number, plus one issues file.
Each pull request directory holds `meta.json`, `body.md`, `diff.patch`, `commits.json`,
`comments.json`, `review_comments.json`, `reviews.json` and `events.json`. Total size is
about 500 KB. The repository source itself is **not** vendored; it is referenced at pinned
commit `d285029ab6b62bfacf12cdb41bd4653867db73c0`.

## Personal data: what was removed

The rules forbid personal information. Commit and author metadata returned by the API
carried some, so before publication the corpus was scrubbed:

- **7 email addresses** removed, including two personal mailbox addresses belonging to
  third-party contributors, replaced with `[email redacted]`.
- **9 real-name fields** on user objects blanked.

What remains is the public GitHub handle of each contributor, which is pseudonymous, is how
those people are addressed in the threads themselves, and is required to attribute their work
honestly. No email address, legal name, avatar, location or other profile field is retained.

The scrub is reproducible: it redacts anything matching an email pattern in every file, and
blanks the `name` field of any object that also carries a `login` or `is_bot` key, which is
how the API marks a user.

## Attribution

Every quoted maintainer or contributor comment is public, is attributed to its author's
handle, and is used to judge our own tool rather than to evaluate the people who wrote it.
The project's tooling split is recorded separately in `PROVENANCE.md`.
