#!/usr/bin/env python3
"""
check_prior_art.py — Prior-art checker for ScrollPrize/villa pull requests.

Usage:
    python scripts/check_prior_art.py --pr <NUMBER> [options]

Options:
    --pr <N>          Candidate PR number (required)
    --corpus <dir>    Corpus cache directory (default: corpus/)
    --repo <slug>     GitHub repo slug (default: ScrollPrize/villa)
    --verbose         Include extra evidence lines in output
    --dry-run         Do not make any gh API calls; corpus-only mode

Output:
    A JSON array of finding objects conforming to schemas/finding.json,
    printed to stdout. Exit 0 always (errors are reported as findings).
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Schema constants
# ---------------------------------------------------------------------------

CHECKER = "prior-art"

SEVERITY_BLOCKER = "blocker"
SEVERITY_MAJOR = "major"
SEVERITY_NIT = "nit"

RULE_CLOSED_PR_SAME_ISSUE = "prior-art/closed-pr-same-issue"
RULE_OPEN_PR_SAME_ISSUE = "prior-art/open-pr-same-issue"
RULE_ADJACENT_FILE_OVERLAP = "prior-art/adjacent-file-overlap"
RULE_ALREADY_MERGED = "prior-art/already-merged"
RULE_NO_PRIOR_ART = "prior-art/no-prior-art"
RULE_SCRIPT_ERROR = "prior-art/script-error"


# ---------------------------------------------------------------------------
# Date parsing helpers
# ---------------------------------------------------------------------------

def parse_iso(s: str) -> datetime:
    """Parse an ISO-8601 datetime string (with optional Z suffix)."""
    s = s.rstrip("Z")
    return datetime.fromisoformat(s).replace(tzinfo=timezone.utc)


# ---------------------------------------------------------------------------
# Corpus helpers
# ---------------------------------------------------------------------------

def load_json(path: Path) -> Any:
    """Load a JSON file; return None if missing or unreadable."""
    try:
        return json.loads(path.read_text())
    except Exception:
        return None


def all_pr_dirs(corpus: Path) -> list[Path]:
    """Return every <corpus>/<N>/ directory that has a meta.json."""
    result = []
    for d in sorted(corpus.iterdir()):
        if d.is_dir() and (d / "meta.json").exists():
            try:
                int(d.name)          # only numeric PR directories
                result.append(d)
            except ValueError:
                pass
    return result


def load_meta(pr_dir: Path) -> dict | None:
    return load_json(pr_dir / "meta.json")


def pr_files(meta: dict) -> list[str]:
    """Return the list of changed file paths from a PR meta dict."""
    return [f["path"] for f in meta.get("files", [])]


def pr_issues(meta: dict) -> set[int]:
    """Return the set of issue numbers closed/referenced by this PR."""
    refs = meta.get("closingIssuesReferences", [])
    return {r["number"] for r in refs}


def pr_created_at(meta: dict) -> datetime | None:
    ca = meta.get("createdAt")
    return parse_iso(ca) if ca else None


# ---------------------------------------------------------------------------
# gh CLI wrapper (cache-first)
# ---------------------------------------------------------------------------

GH_CALLS = 0          # module-level counter for rate-limit spacing

def gh(args: list[str], cache_path: Path, dry_run: bool = False) -> Any:
    """
    Execute `gh <args>` and cache the JSON result to cache_path.
    If cache_path already exists, return the cached value without calling gh.
    Returns None on failure.
    """
    global GH_CALLS

    if cache_path.exists():
        return load_json(cache_path)

    if dry_run:
        return None

    if GH_CALLS >= 3:
        time.sleep(1)

    cmd = ["gh"] + args
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        GH_CALLS += 1
        if result.returncode != 0:
            return None
        data = json.loads(result.stdout)
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        cache_path.write_text(json.dumps(data, indent=2))
        return data
    except Exception:
        return None


def fetch_pr_meta(corpus: Path, repo: str, number: int, dry_run: bool) -> dict | None:
    """Ensure corpus/<number>/meta.json exists; fetch if needed."""
    cache = corpus / str(number) / "meta.json"
    if cache.exists():
        return load_json(cache)
    return gh(
        ["pr", "view", str(number), "--repo", repo, "--json",
         "number,title,state,createdAt,closedAt,mergedAt,author,baseRefOid,"
         "headRefOid,files,closingIssuesReferences,isDraft,labels,"
         "reviewDecision,additions,deletions,changedFiles,headRefName,"
         "baseRefName,url,updatedAt"],
        cache,
        dry_run,
    )


def fetch_pr_events(corpus: Path, repo: str, number: int, dry_run: bool) -> list | None:
    cache = corpus / str(number) / "events.json"
    if cache.exists():
        return load_json(cache)
    return gh(
        ["api", f"repos/{repo}/issues/{number}/events",
         "--paginate", "-q",
         '[.[] | {event:.event, actor:.actor.login, created_at:.created_at}]'],
        cache,
        dry_run,
    )


# ---------------------------------------------------------------------------
# Diff analysis helpers
# ---------------------------------------------------------------------------

# Noise tokens that appear in diffs of almost any C++ file — not meaningful
# for function overlap detection.
_NOISE_TOKENS = frozenset({
    "if", "for", "while", "do", "switch", "return", "else",
    "continue", "break", "delete", "new", "nullptr", "true", "false",
    "CHECK", "REQUIRE", "QVERIFY", "QCOMPARE",
    "add_dependencies", "vc_add_test", "fs::create_directories",
})


def extract_changed_functions(patch_text: str) -> set[str]:
    """
    Return the set of C++/Python function/method names that appear on
    +/- lines in a unified diff, using a simple heuristic:
    - C++: lines starting with + or - followed by a typed return + identifier(
    - Python: lines starting with + or - followed by "def " or "class "
    Noise tokens (control flow keywords, test macros) are excluded.
    """
    funcs: set[str] = set()
    # Only match named function definitions (typed return value required for C++)
    cpp_pat = re.compile(
        r'^[+-]\s+(?:bool|void|int|float|double|auto|unsigned|static|inline|'
        r'explicit|virtual|const|std::\w+|cv::\w+|QuadSurface\*?|'
        r'ObjToTifxyzConverter)\s+'
        r'(\w[\w:~<>]*)\s*\('
    )
    py_pat = re.compile(r'^[+-]\s+def\s+(\w+)\s*\(')
    class_pat = re.compile(r'^[+-]\s+class\s+(\w+)')

    for line in patch_text.splitlines():
        if not line.startswith(('+', '-')):
            continue
        if line.startswith('---') or line.startswith('+++'):
            continue
        for pat in (cpp_pat, py_pat, class_pat):
            m = pat.match(line)
            if m:
                name = m.group(1)
                if name not in _NOISE_TOKENS:
                    funcs.add(name)

    return funcs


def load_patch(pr_dir: Path) -> str:
    """Load diff.patch text; return empty string if missing."""
    p = pr_dir / "diff.patch"
    try:
        return p.read_text()
    except Exception:
        return ""


def patch_functions(pr_dir: Path) -> set[str]:
    return extract_changed_functions(load_patch(pr_dir))


def patch_files(pr_dir: Path) -> set[str]:
    """Extract file paths changed in a patch (from +++ b/ lines)."""
    files: set[str] = set()
    for line in load_patch(pr_dir).splitlines():
        if line.startswith("+++ b/"):
            files.add(line[6:].strip())
        elif line.startswith("--- a/"):
            files.add(line[6:].strip())
    return {f for f in files if f and f != "/dev/null"}


# ---------------------------------------------------------------------------
# Closed-by classification
# ---------------------------------------------------------------------------

BOT_SUFFIXES = ("[bot]", "-bot", "bot[bot]")
MAINTAINERS = {"bruniss", "pmh47", "hendrikschilling"}  # known from events


def classify_closer(events: list | None) -> str:
    """Return 'bot' | 'author' | 'maintainer' | 'unknown'."""
    if not events:
        return "unknown"
    author = None
    for ev in events:
        if ev.get("event") == "review_requested":
            # first actor is typically the author
            actor = ev.get("actor", "")
            if not actor.endswith("[bot]") and author is None:
                author = actor
    closer = None
    for ev in reversed(events):
        if ev.get("event") == "closed":
            closer = ev.get("actor", "")
            break
    if closer is None:
        return "unknown"
    if any(closer.endswith(s) or closer.endswith(s.replace("[", "")) for s in BOT_SUFFIXES):
        return "bot"
    if closer == author:
        return "author"
    if closer in MAINTAINERS:
        return "maintainer"
    return "unknown"


# ---------------------------------------------------------------------------
# Finding builders
# ---------------------------------------------------------------------------

def make_finding(
    severity: str,
    rule_id: str,
    rule_source: str,
    evidence: list[dict],
    suggested_fix: str,
    confidence: float,
    rule_quote: str | None = None,
) -> dict:
    rule: dict = {"id": rule_id, "source": rule_source}
    if rule_quote:
        rule["quote"] = rule_quote
    return {
        "checker": CHECKER,
        "severity": severity,
        "rule": rule,
        "evidence": evidence,
        "suggested_fix": suggested_fix,
        "confidence": round(confidence, 3),
    }


def no_prior_art_finding(examined: int, candidate_files: list[str]) -> dict:
    return make_finding(
        severity=SEVERITY_NIT,
        rule_id=RULE_NO_PRIOR_ART,
        rule_source="inferred",
        rule_quote="Thorough search of corpus found no overlapping prior work.",
        evidence=[{
            "what": f"Examined {examined} corpus PR(s); none overlap with candidate files or issues.",
            "where": "corpus/",
            "output": "candidate files: " + ", ".join(sorted(candidate_files)),
        }],
        suggested_fix="No prior art detected; proceed with submission.",
        confidence=0.92,
    )


def error_finding(msg: str) -> dict:
    return make_finding(
        severity=SEVERITY_BLOCKER,
        rule_id=RULE_SCRIPT_ERROR,
        rule_source="scripts/check_prior_art.py",
        evidence=[{"what": "script error", "output": msg}],
        suggested_fix="Fix the error in check_prior_art.py or supply missing corpus files.",
        confidence=0.0,
    )


# ---------------------------------------------------------------------------
# Core comparison logic
# ---------------------------------------------------------------------------

def compare_prs(
    candidate_number: int,
    candidate_meta: dict,
    candidate_dir: Path,
    prior_dir: Path,
    prior_meta: dict,
    corpus: Path,
    repo: str,
    dry_run: bool,
    verbose: bool,
) -> dict | None:
    """
    Compare candidate PR against one prior PR. Return a Finding dict if there
    is a meaningful overlap, or None if unrelated.
    """
    prior_number = prior_meta["number"]

    # --- Issue overlap ---
    candidate_issues = pr_issues(candidate_meta)
    prior_issues = pr_issues(prior_meta)
    shared_issues = candidate_issues & prior_issues

    # --- File overlap (from meta.json .files[]) ---
    candidate_files = set(pr_files(candidate_meta))
    prior_files_meta = set(pr_files(prior_meta))
    shared_files = candidate_files & prior_files_meta

    # Also check from the patches (catches cases where meta is incomplete)
    candidate_patch_files = patch_files(candidate_dir)
    prior_patch_files = patch_files(prior_dir)
    shared_patch_files = (candidate_files | candidate_patch_files) & \
                         (prior_files_meta | prior_patch_files)

    # If no issue overlap AND no file overlap → skip
    if not shared_issues and not shared_patch_files:
        return None

    # --- Function overlap (from diffs) ---
    candidate_funcs = patch_functions(candidate_dir)
    prior_funcs = patch_functions(prior_dir)
    shared_funcs = candidate_funcs & prior_funcs

    # If the only connection is file-level with no issue overlap and no
    # meaningful function overlap, this is incidental (two different fixes
    # to the same large file for unrelated reasons) — skip.
    if not shared_issues and shared_patch_files and not shared_funcs:
        return None

    # --- Load events for closer classification ---
    events = load_json(prior_dir / "events.json")
    if events is None:
        events = fetch_pr_events(corpus, repo, prior_number, dry_run)
    closer = classify_closer(events)

    # --- State and merge info ---
    prior_state = prior_meta.get("state", "UNKNOWN")
    merged_at = prior_meta.get("mergedAt")
    prior_author = prior_meta.get("author", {}).get("login", "unknown")

    # --- Confidence ---
    if shared_issues and len(shared_patch_files) >= 2 and shared_funcs:
        confidence = 0.95
    elif shared_issues and shared_patch_files:
        confidence = 0.85
    elif shared_patch_files and not shared_issues:
        confidence = 0.65
    else:
        confidence = 0.60

    # --- Severity and verdict ---
    if merged_at:
        severity = SEVERITY_BLOCKER
        rule_id = RULE_ALREADY_MERGED
        verdict = "same fix — already merged on main"
        suggested_fix = "this is already fixed on main, rebase and re-check"
        confidence = min(0.90, confidence + 0.05)
    elif prior_state == "OPEN":
        # Same issue + same file = same fix (function match raises confidence).
        # Different issues but same file + functions = adjacent fix.
        if shared_issues and shared_patch_files:
            severity = SEVERITY_BLOCKER
            rule_id = RULE_OPEN_PR_SAME_ISSUE
            verdict = "same fix — open PR exists"
            suggested_fix = (
                f"An open PR #{prior_number} by @{prior_author} already addresses "
                f"the same change. Coordinate or close this PR."
            )
        else:
            severity = SEVERITY_MAJOR
            rule_id = RULE_ADJACENT_FILE_OVERLAP
            verdict = "adjacent fix — same files, open PR"
            suggested_fix = (
                f"An open PR #{prior_number} by @{prior_author} touches the same files. "
                f"Coordinate to avoid divergence."
            )
    else:
        # CLOSED (not merged)
        # Same issue + same file = same fix regardless of function-name match.
        if shared_issues and shared_patch_files:
            severity = SEVERITY_BLOCKER
            rule_id = RULE_CLOSED_PR_SAME_ISSUE
            verdict = "same fix — closed (unmerged) prior PR"
            suggested_fix = (
                f"PR #{prior_number} by @{prior_author} was closed ({closer}) "
                f"without merge. Review it and either rebase on top or explain "
                f"the difference."
            )
        else:
            severity = SEVERITY_MAJOR
            rule_id = RULE_ADJACENT_FILE_OVERLAP
            verdict = "adjacent fix — overlapping files in closed PR"
            suggested_fix = (
                f"PR #{prior_number} by @{prior_author} was closed ({closer}) "
                f"and touches the same files. Check for overlap."
            )

    # --- Evidence ---
    evidence: list[dict] = []

    if shared_issues:
        evidence.append({
            "what": f"PR #{prior_number} references the same issue(s): "
                    + ", ".join(f"#{n}" for n in sorted(shared_issues)),
            "where": str(prior_dir / "meta.json"),
            "output": f"closingIssuesReferences: {sorted(shared_issues)}",
        })

    if shared_patch_files:
        evidence.append({
            "what": f"File overlap with PR #{prior_number}",
            "where": f"corpus/{prior_number}/diff.patch vs corpus/{candidate_number}/diff.patch",
            "output": "shared files: " + ", ".join(sorted(shared_patch_files)),
        })

    if shared_funcs:
        evidence.append({
            "what": f"Function-level overlap with PR #{prior_number}",
            "where": f"corpus/{prior_number}/diff.patch vs corpus/{candidate_number}/diff.patch",
            "output": "shared functions: " + ", ".join(sorted(shared_funcs)),
        })

    evidence.append({
        "what": f"PR #{prior_number} state and closure",
        "where": str(prior_dir / "meta.json"),
        "output": (
            f"number={prior_number} author={prior_author} "
            f"state={prior_state} mergedAt={merged_at} "
            f"closedAt={prior_meta.get('closedAt')} "
            f"closer={closer} "
            f"title={prior_meta.get('title', '')!r}"
        ),
    })

    if verbose:
        evidence.append({
            "what": "Verdict",
            "where": "check_prior_art.py",
            "output": verdict,
        })

    return make_finding(
        severity=severity,
        rule_id=rule_id,
        rule_source=str(prior_dir / "meta.json"),
        rule_quote=prior_meta.get("title", ""),
        evidence=evidence,
        suggested_fix=suggested_fix,
        confidence=confidence,
    )


# ---------------------------------------------------------------------------
# Main checker
# ---------------------------------------------------------------------------

def check(
    candidate_number: int,
    corpus: Path,
    repo: str,
    dry_run: bool,
    verbose: bool,
) -> list[dict]:
    """Run the full prior-art check. Return a list of findings."""

    # 1. Load or fetch candidate PR metadata
    candidate_dir = corpus / str(candidate_number)
    candidate_meta = load_meta(candidate_dir)
    if candidate_meta is None:
        candidate_meta = fetch_pr_meta(corpus, repo, candidate_number, dry_run)
    if candidate_meta is None:
        return [error_finding(
            f"Could not load meta.json for PR #{candidate_number}. "
            f"Run: gh pr view {candidate_number} --repo {repo} --json ... "
            f"and save to corpus/{candidate_number}/meta.json"
        )]

    candidate_created = pr_created_at(candidate_meta)
    if candidate_created is None:
        return [error_finding(
            f"meta.json for PR #{candidate_number} has no createdAt field."
        )]

    candidate_files = set(pr_files(candidate_meta))
    candidate_patch_files = patch_files(candidate_dir)
    all_candidate_files = candidate_files | candidate_patch_files

    # 2. Enumerate all prior corpus PRs (those that existed before candidate)
    prior_dirs = []
    for d in all_pr_dirs(corpus):
        if int(d.name) == candidate_number:
            continue
        meta = load_meta(d)
        if meta is None:
            continue
        created = pr_created_at(meta)
        if created is None:
            continue
        if created < candidate_created:
            prior_dirs.append((d, meta))

    # 3. Compare each prior PR
    findings: list[dict] = []
    examined = 0
    for prior_dir, prior_meta in prior_dirs:
        examined += 1
        finding = compare_prs(
            candidate_number=candidate_number,
            candidate_meta=candidate_meta,
            candidate_dir=candidate_dir,
            prior_dir=prior_dir,
            prior_meta=prior_meta,
            corpus=corpus,
            repo=repo,
            dry_run=dry_run,
            verbose=verbose,
        )
        if finding is not None:
            findings.append(finding)

    # 4. If no findings, emit a no-prior-art finding
    if not findings:
        findings.append(no_prior_art_finding(examined, sorted(all_candidate_files)))

    return findings


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pr", type=int, required=True,
                        help="Candidate PR number")
    parser.add_argument("--corpus", default="corpus",
                        help="Corpus cache directory (default: corpus/)")
    parser.add_argument("--repo", default="ScrollPrize/villa",
                        help="GitHub repo slug (default: ScrollPrize/villa)")
    parser.add_argument("--verbose", action="store_true",
                        help="Include extra evidence lines in output")
    parser.add_argument("--dry-run", action="store_true",
                        help="Never call gh; use corpus only")
    args = parser.parse_args()

    corpus = Path(args.corpus)
    if not corpus.exists():
        print(json.dumps([error_finding(
            f"Corpus directory '{corpus}' does not exist."
        )], indent=2))
        sys.exit(0)

    findings = check(
        candidate_number=args.pr,
        corpus=corpus,
        repo=args.repo,
        dry_run=args.dry_run,
        verbose=args.verbose,
    )

    print(json.dumps(findings, indent=2))


if __name__ == "__main__":
    main()
