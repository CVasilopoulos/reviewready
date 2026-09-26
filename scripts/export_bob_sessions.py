#!/usr/bin/env python3
import datetime
import json
import os
import pathlib
import re
import shutil
import sqlite3
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parent.parent
OUT = ROOT / "bob_sessions"
DB = pathlib.Path(os.path.expanduser("~/.bob/db/bob.db"))
PROJECT = "/Users/A200270629/Desktop/projects/competitions/ibm-bob-2/"

SECRET = re.compile(
    r"BOB_API_KEY|BOBSHELL_API_KEY|IBM_CLOUD_API_KEY|IBMCLOUD_API_KEY"
    r"|gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{20,}|AKIA[0-9A-Z]{16}"
    r"|sk-[A-Za-z0-9]{20,}|-----BEGIN [A-Z ]*PRIVATE KEY|Bearer [A-Za-z0-9._-]{20,}",
    re.I)

SLUGS = {
    "67b6ce80a000444892a7d333faa96e63": "00-smoke-test",
    "89acdc64951c2e0e29cee6d94a1cc265": "01-init-project-context",
    "076440965cc9428fce914e69a8206d45": "02-prior-art-and-contract-checkers",
    "e0b909450634c08b701adfc8441427df": "03-evidence-verifier",
}


def ts(ms):
    return datetime.datetime.fromtimestamp(ms / 1000).strftime("%Y-%m-%d %H:%M:%S")


def scrub(s):
    return "[redacted]" if SECRET.search(s or "") else s


def rel(s):
    return (s or "").replace(PROJECT, "")


def snapshot():
    tmp = pathlib.Path(tempfile.mkdtemp()) / "bob.db"
    for suf in ("", "-shm", "-wal"):
        src = DB.parent / (DB.name + suf)
        if src.exists():
            shutil.copy2(src, str(tmp) + suf)
    return tmp


def target(name, args):
    for k in ("path", "file_path", "filePath"):
        if isinstance(args.get(k), str):
            return rel(args[k])
    if name == "execute_command":
        return "`" + scrub(str(args.get("command", ""))[:160]) + "`"
    if name == "new_task":
        return str(args.get("message", ""))[:110].replace("\n", " ")
    for k in ("query", "regex", "mode", "todos"):
        if isinstance(args.get(k), str):
            return args[k][:110].replace("\n", " ")
    return ""


def breakdown_table(costs):
    b = (costs.get("contextWindowBreakdown") or {}).get("breakdown") or {}
    if not b:
        return ""
    rows = "\n".join(f"| {k} | {v:,} |" for k, v in sorted(b.items(), key=lambda x: -x[1]))
    return f"\n| context component | tokens |\n|---|---|\n{rows}\n"


def export(conn, task, children):
    tid = task["id"]
    slug = SLUGS.get(tid, tid[:8])
    costs = json.loads(task["costs"] or "{}")
    msgs = list(conn.execute(
        "select role, data, created_at from messages where task_id=? order by created_at", (tid,)))
    dur = (task["updated_at"] - task["created_at"]) / 60000.0

    L = [f"# Bob session — {slug}", ""]
    L += [f"**Task id** `{tid}`  ",
          f"**Started** {ts(task['created_at'])} · **last activity** {ts(task['updated_at'])}"
          f" · **{dur:.0f} min**  ",
          f"**Status** {task['status']} · **type** {task['task_type']}", ""]
    L += ["## Session consumption summary", "",
          f"- **Bobcoins spent: {costs.get('cost', 0):.6f}**",
          f"- Context tokens: {costs.get('contextTokens', 0):,}",
          f"- Messages in this session: {len(msgs)}"]
    if children:
        L.append(f"- Subagents spawned: {len(children)}")
    L.append(breakdown_table(costs))

    prompts = [json.loads(d)["content"] for r, d, _ in msgs if r == "user"]
    if prompts:
        L += ["## The prompt", "", "```text", scrub(prompts[0].strip()), "```", ""]
        for p in prompts[1:]:
            L += ["**Follow-up prompt**", "", "```text", scrub(p.strip()), "```", ""]

    L += ["## What Bob did", "", "| time | tool | target |", "|---|---|---|"]
    n = 0
    for role, data, at in msgs:
        if role != "assistant":
            continue
        d = json.loads(data)
        when = (d.get("_meta") or {}).get("timestamp") or at
        for tc in d.get("toolCalls") or []:
            a = tc.get("arguments") or {}
            if not isinstance(a, dict):
                a = {}
            L.append(f"| {ts(when)[11:]} | `{tc.get('name')}` | {target(tc.get('name'), a)} |")
            n += 1
    L.append("")
    L.insert(L.index("## What Bob did") + 1, f"\n{n} tool calls.\n")

    says = [json.loads(d).get("content", "").strip() for r, d, _ in msgs if r == "assistant"]
    says = [s for s in says if len(s) > 200]
    if says:
        L += ["## Bob's own account, in its words", ""]
        for s in says[-2:]:
            L += ["> " + scrub(s)[:2400].replace("\n", "\n> "), ""]

    if children:
        L += ["## Subagents", "", "| started | cost | prompt |", "|---|---|---|"]
        for ch in children:
            cc = json.loads(ch["costs"] or "{}")
            L.append(f"| {ts(ch['created_at'])} | {cc.get('cost', 0):.6f} | "
                     f"{rel(ch['title'])[:120].splitlines()[0]} |")
        L.append("")

    text = "\n".join(L)
    if SECRET.search(text):
        raise SystemExit(f"refusing to write {slug}: secret pattern survived scrubbing")
    (OUT / f"{slug}.md").write_text(text)
    return slug, costs.get("cost", 0), n, len(children)


def attribution(conn):
    rows = list(conn.execute("""
        select replace(file_uri,'file://','') as f, repo_name, branch_name, tool_name,
               count(*) n, min(created_at) a, max(created_at) b
        from attribution_logs group by f, tool_name order by min(created_at)"""))
    L = ["# Bob's own file-attribution log", "",
         "IBM Bob records every edit it makes, per file and per line range, in its local database",
         "(`~/.bob/db/bob.db`, table `attribution_logs`). This is Bob's record, not ours.", "",
         "| file | tool | edits | first | last |", "|---|---|---|---|---|"]
    for f, repo, br, tool, n, a, b in rows:
        L.append(f"| `{rel(f)}` | {tool} | {n} | {ts(a)} | {ts(b)} |")
    L += ["", "Bob logged attribution only inside the git repository it had open at the time",
          "(`demo/villa`). The gate pack itself was written in a directory that was not yet a git",
          "repository, so those edits carry no attribution rows; the per-session tool-call tables in",
          "this folder are the record for them.", ""]
    (OUT / "ATTRIBUTION.md").write_text("\n".join(L))
    return len(rows)


def main():
    if not DB.exists():
        raise SystemExit(f"no Bob database at {DB}")
    snap = snapshot()
    conn = sqlite3.connect(f"file:{snap}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    OUT.mkdir(exist_ok=True)

    tasks = list(conn.execute("select * from tasks order by created_at"))
    kids = {}
    for t in tasks:
        if t["parent_id"]:
            kids.setdefault(t["parent_id"], []).append(t)

    total, index = 0.0, []
    for t in tasks:
        if t["task_type"] != "normal" or not (json.loads(t["costs"] or "{}").get("cost")):
            continue
        slug, cost, ncalls, nsub = export(conn, t, kids.get(t["id"], []))
        total += cost
        index.append((slug, t, cost, ncalls, nsub))
        print(f"  {slug}: {cost:.4f} Bobcoins, {ncalls} tool calls, {nsub} subagents")

    sub_total = sum(json.loads(t["costs"] or "{}").get("cost", 0)
                    for t in tasks if t["task_type"] == "subagent")
    nattr = attribution(conn)

    L = ["# Bob task ledger", "",
         "Generated from IBM Bob's own local database by `scripts/export_bob_sessions.py`.",
         "Every number here is Bob's, not ours.", "",
         "| # | task | started | duration | Bobcoins | tool calls | subagents |",
         "|---|---|---|---|---|---|---|"]
    for i, (slug, t, cost, ncalls, nsub) in enumerate(index):
        dur = (t["updated_at"] - t["created_at"]) / 60000.0
        L.append(f"| {i:02d} | [{slug}]({slug}.md) | {ts(t['created_at'])} | {dur:.0f} min "
                 f"| {cost:.4f} | {ncalls} | {nsub} |")
    L += ["", f"**Top-level tasks: {total:.4f} Bobcoins.** Subagents a further {sub_total:.4f}. "
              f"**Total {total + sub_total:.4f} of an allocation of 40**, which the IDE reports as 0% remaining.", "",
          "Two further sessions exist in the database with a cost of exactly 0 — an empty window opened",
          "on 2026-09-25 17:57 and another on 2026-09-26 12:20. They are not exported because nothing",
          "was run in them.", "",
          f"`ATTRIBUTION.md` holds Bob's own per-file edit log ({nattr} file/tool pairs).", "",
          "## What this ledger does not contain", "",
          "No screenshots. The session consumption figures above are read straight out of Bob's",
          "database, which is the same source the IDE's own summary panel displays. An earlier draft",
          "of this repository shipped six PNGs claiming to be those panels; they were copies of an",
          "unrelated screenshot and were removed. `PROVENANCE.md` records that in full.", ""]
    (OUT / "LEDGER.md").write_text("\n".join(L))
    print(f"wrote {len(index)} sessions + LEDGER.md + ATTRIBUTION.md ({nattr} rows)")
    shutil.rmtree(snap.parent, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
