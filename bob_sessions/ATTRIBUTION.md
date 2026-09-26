# Bob's own file-attribution log

IBM Bob records every edit it makes, per file and per line range, in its local database
(`~/.bob/db/bob.db`, table `attribution_logs`). This is Bob's record, not ours.

| file | tool | edits | first | last |
|---|---|---|---|---|
| `demo/villa/AGENTS.md` | write_file | 22 | 2026-09-25 19:39:46 | 2026-09-25 19:39:46 |
| `demo/villa/.bob/rules-agent/AGENTS.md` | write_file | 1 | 2026-09-25 19:40:01 | 2026-09-25 19:40:01 |
| `demo/villa/.bob/rules-ask/AGENTS.md` | write_file | 1 | 2026-09-25 19:40:13 | 2026-09-25 19:40:13 |
| `demo/villa/.bob/rules-plan/AGENTS.md` | write_file | 1 | 2026-09-25 19:40:25 | 2026-09-25 19:40:25 |
| `demo/villa/contract.yml` | write_file | 94 | 2026-09-25 19:44:26 | 2026-09-25 19:51:15 |

Bob logged attribution only inside the git repository it had open at the time
(`demo/villa`). The gate pack itself was written in a directory that was not yet a git
repository, so those edits carry no attribution rows; the per-session tool-call tables in
this folder are the record for them.
