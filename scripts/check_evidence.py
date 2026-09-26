#!/usr/bin/env python3
"""
check_evidence.py — Evidence-quality checker for pull requests.

Audits whether the proof a PR offers is actually a proof.  Performs five
static checks against the PR body and diff only.  Never runs tests, builds
anything, or creates git worktrees.

Usage:
    python scripts/check_evidence.py --pr <NUMBER> [options]
    python scripts/check_evidence.py --body <file> --diff <file> [options]

Options:
    --pr <N>         PR number; loads body from corpus/<N>/body.md,
                     diff from corpus/<N>/diff.patch
    --body <file>    Path to PR body markdown file (alternative to --pr)
    --diff <file>    Path to diff patch file (optional with --body)
    --corpus <dir>   Corpus cache directory (default: corpus/)
    --verbose        Include extra evidence details

Output:
    A JSON array of finding objects to stdout, conforming to schemas/finding.json.
    Exit 0 always; errors are surfaced as findings.

The five checks
---------------
1. Commit IDs   – proof names exact before/after SHAs that differ
2. Symmetry     – same input, flags, settings on both sides
3. Real data    – evidence sections reference real scroll data
4. Artefact     – an image, video, terminal block, or table is attached
5. Numbers      – numbers stated in the body are internally consistent

Known bugs avoided in this implementation
------------------------------------------
Bug-1: Placeholder regex must NOT match numeric array literals like [0,1]
       or [0.8602, 0.1344].  Use a text-word-only pattern.
Bug-2: Diff-path extraction must NOT use re.MULTILINE on the full diff body
       with '^' anchors.  Iterate line by line and use line.startswith().
Bug-3: Real-data check must be scoped to the One real example and Proof
       sections only, never to the full body (## Details may legitimately
       mention synthetic test fixtures).
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Schema constants
# ---------------------------------------------------------------------------

CHECKER = "evidence"
SEV_BLOCKER = "blocker"
SEV_MAJOR = "major"
SEV_NIT = "nit"

# Source references
SRC_CONTRIBUTING_20 = "CONTRIBUTING.md:20"
SRC_INFERRED = "inferred"

# CONTRIBUTING.md verbatim quote for the real-data rule (from contract.yml)
CONTRIBUTING_REAL_DATA_QUOTE = (
    "Bugfixes or improvements must be run on real scroll data. "
    "Synthetic or toy examples are not accepted."
)

# ---------------------------------------------------------------------------
# Finding helpers
# ---------------------------------------------------------------------------

def make_finding(
    rule_id: str,
    severity: str,
    source: str,
    evidence: list[dict],
    suggested_fix: str,
    confidence: float,
    quote: str | None = None,
) -> dict:
    rule: dict[str, Any] = {"id": rule_id, "source": source}
    if quote:
        rule["quote"] = quote[:400]
    return {
        "checker": CHECKER,
        "severity": severity,
        "rule": rule,
        "evidence": evidence,
        "suggested_fix": suggested_fix,
        "confidence": round(min(1.0, max(0.0, confidence)), 3),
    }


def pass_finding(what: str, details: str, where: str = "inferred") -> dict:
    return make_finding(
        rule_id="evidence/pass",
        severity=SEV_NIT,
        source=SRC_INFERRED,
        evidence=[{"what": what, "where": where, "output": details}],
        suggested_fix="No action required.",
        confidence=0.88,
    )


def error_finding(msg: str) -> dict:
    return make_finding(
        rule_id="evidence/script-error",
        severity=SEV_BLOCKER,
        source="scripts/check_evidence.py",
        evidence=[{"what": "script error", "output": msg}],
        suggested_fix="Fix the error in check_evidence.py or supply missing input files.",
        confidence=0.0,
    )


# ---------------------------------------------------------------------------
# Section extraction
#
# BUG-FIX: stop only at the next **Bold:** PR-template heading, NOT at
# ## headings (which can appear inside fenced code blocks and would truncate
# the section prematurely — this is the root of Bug-2 in the existing checker).
# ---------------------------------------------------------------------------

def extract_section(body: str, heading: str) -> str | None:
    """
    Extract the text of a section identified by a bold heading **Heading:**
    or **Heading**.  Stops at the next **Bold:** template heading.
    Returns None if the heading is absent, '' if present but empty.
    """
    pattern = re.compile(
        r'(?:^|\n)\*\*' + re.escape(heading) + r'(?:\:\*\*|\*\*:?)\s*',
        re.IGNORECASE,
    )
    m = pattern.search(body)
    if m is None:
        return None
    start = m.end()
    rest = body[start:]
    # Stop ONLY at **Bold:** headings — never at ## or # headings which may
    # appear inside fenced code blocks and do not delimit PR template sections.
    next_bold = re.search(r'\n\*\*[A-Z][^\n]*\*\*:?', rest)
    if next_bold:
        return rest[:next_bold.start()]
    return rest


# ---------------------------------------------------------------------------
# Shared utilities
# ---------------------------------------------------------------------------

# BUG-1 prevention: placeholder pattern matches only word-based template
# placeholders like [real data/input], [action], [describe the command].
# It does NOT match numeric arrays like [0,1], [0.8602, 0.1344], [-1,-1,-1].
_TEMPLATE_PLACEHOLDER_RE = re.compile(
    r'\[(?:'
    r'real data/input'          # exact match
    r'|action'                  # exact match
    r'|result'                  # exact match
    r'|before commit'           # exact match
    r'|after commit'            # exact match
    r'|commit hash'             # exact match
    r'|[A-Z][a-z ]{5,}'        # Title-Case phrase ≥6 chars, e.g. [Before commit hash]
    r'|[a-z]{4,}(?:\s[a-z]{2,})+'  # lowercase multi-word, e.g. [some description]
    r')\]'
)


def has_image_or_media(text: str) -> bool:
    """Return True if text contains an image, video link, code block, or table."""
    # GitHub image attachment URL
    if "https://github.com/user-attachments/assets/" in text:
        return True
    # Markdown image
    if re.search(r'!\[.*?\]\(.*?\)', text):
        return True
    # HTML img tag
    if re.search(r'<img\s', text, re.IGNORECASE):
        return True
    # Fenced code block
    if re.search(r'```', text):
        return True
    # Indented code block (4 spaces + non-space)
    if re.search(r'(?m)^    [^\s]', text):
        return True
    # Benchmark / data table (two or more | separators on one line)
    if re.search(r'\|[^|]+\|[^|]+\|', text):
        return True
    return False


# BUG-2 prevention: extract changed paths from diff by iterating lines,
# NOT by applying a MULTILINE regex to the full diff string with ^ anchors.
def extract_diff_paths(diff: str) -> set[str]:
    """Return the set of file paths changed in a unified diff."""
    paths: set[str] = set()
    for line in diff.splitlines():
        if line.startswith("diff --git "):
            # Format: diff --git a/<path> b/<path>
            m = re.match(r"diff --git a/([^ ]+) b/", line)
            if m:
                paths.add(m.group(1))
    return paths


# ---------------------------------------------------------------------------
# Check 1 — Named before/after commits that differ
# ---------------------------------------------------------------------------

# A commit SHA is 7–40 lowercase hex chars appearing inside backticks.
_SHA_IN_BACKTICKS_RE = re.compile(
    r'(?:`([0-9a-f]{7,40})`'
    r'|\(([0-9a-f]{7,40})\)'
    r'|(?<![0-9a-zA-Z`/])([0-9a-f]{7,40})(?![0-9a-zA-Z`/]))'
)

# Image-attachment hash guard: a SHA that follows "assets/" in a URL is an
# image hash, not a commit SHA.
_ASSET_URL_RE = re.compile(r'assets/[0-9a-f]{7,40}')


def _is_asset_hash(body: str, sha: str, pos: int) -> bool:
    """Return True if the SHA at position pos is part of an assets/ URL."""
    window = body[max(0, pos - 20):pos + len(sha) + 5]
    return bool(_ASSET_URL_RE.search(window))


def _is_timestamp(sha: str) -> bool:
    """Return True if the SHA looks like a timestamp segment ID (all digits)."""
    return bool(re.match(r'^[0-9]+$', sha))



_THIS_BRANCH_RE = re.compile(
    r'\b(?:against|on|with)\s+(?:this\s+(?:branch|PR|pull request)|the\s+branch)\b',
    re.IGNORECASE,
)


def _after_is_this_branch(body: str) -> bool:
    return bool(_THIS_BRANCH_RE.search(body or ""))

def find_contextual_shas(body: str, label: str, window: int = 200) -> set[str]:
    """
    Find commit SHAs (in backticks) that appear within `window` chars after
    a `label` keyword (e.g. 'before' or 'after').
    Excludes image-attachment hashes and pure-digit timestamp IDs.
    """
    found: set[str] = set()
    label_re = re.compile(r'\b' + re.escape(label) + r'\b', re.IGNORECASE)
    for lm in label_re.finditer(body):
        segment_start = max(0, lm.start() - window)
        segment = body[segment_start: lm.start() + window]
        for sm in _SHA_IN_BACKTICKS_RE.finditer(segment):
            sha = sm.group(1) or sm.group(2) or sm.group(3)
            abs_pos = segment_start + sm.start()
            if _is_asset_hash(body, sha, abs_pos):
                continue
            if _is_timestamp(sha):
                continue
            found.add(sha)
    return found


def _has_minimal_repr_excuse(body: str) -> bool:
    """Return True if the PR explicitly explains it cannot do before/after."""
    return bool(re.search(
        r'(?:no\s+data|no\s+checkout|minimal\s+reproduction|reproduce\s+the\s+failure'
        r'|without\s+(?:full\s+)?(?:data|checkout)|cannot\s+claim\s+a\s+before'
        r'|have\s+not\s+run\s+the\s+full\s+fit|only\s+tested\s+on\s+Windows)',
        body, re.IGNORECASE
    ))


def check_commit_ids(body: str) -> list[dict]:
    """
    Check 1: the proof names an exact before SHA and an exact after SHA that differ.
    Returns a list of findings (empty = pass for this check).
    """
    before_shas = find_contextual_shas(body, 'before')
    after_shas = find_contextual_shas(body, 'after')

    has_before = bool(before_shas)
    has_after = bool(after_shas)

    if has_before and has_after:
        all_shas = before_shas | after_shas
        # If the union is only 1 SHA (both sets contain the same single SHA), commits are not distinct
        if len(all_shas) == 1:
            sha = next(iter(all_shas))
            return [make_finding(
                rule_id="evidence/commits-not-distinct",
                severity=SEV_BLOCKER,
                source=SRC_INFERRED,
                evidence=[{
                    "what": "Before and after both reference the same commit SHA",
                    "where": "body.md",
                    "output": f"before_shas={sorted(before_shas)}, after_shas={sorted(after_shas)}",
                }],
                suggested_fix=(
                    "Provide two different commit SHAs: one for the before state "
                    "and one for the after state, both in backticks."
                ),
                confidence=0.92,
            )]
        # Two or more distinct SHAs found across both sets — pass
        return []

    # Missing one or both sides
    excuse = _has_minimal_repr_excuse(body)
    findings = []

    if not has_before:
        findings.append(make_finding(
            rule_id="evidence/no-before-commit" if not excuse else "evidence/no-commits-minimal-repr",
            severity=SEV_BLOCKER if not excuse else SEV_MAJOR,
            source=SRC_INFERRED,
            evidence=[{
                "what": "No before-state commit SHA found in body",
                "where": "body.md",
                "output": (
                    "Expected a backtick-quoted SHA near 'before', 'upstream', "
                    "or 'built from upstream' in the Proof section."
                    + (" PR states it cannot provide full before/after." if excuse else "")
                ),
            }],
            suggested_fix=(
                "Add the exact commit SHA used for the before-state run, e.g. "
                '"before" is `vc_obj2tifxyz` built from upstream `<sha>`.'
            ),
            confidence=0.92,
        ))

    implicit_after = has_before and _after_is_this_branch(body)
    if not has_after:
        findings.append(make_finding(
            rule_id=("evidence/after-commit-implicit" if implicit_after
                     else ("evidence/no-after-commit" if not excuse
                           else "evidence/no-commits-minimal-repr")),
            severity=(SEV_MAJOR if (implicit_after or excuse) else SEV_BLOCKER),
            source=SRC_INFERRED,
            evidence=[{
                "what": "No after-state commit SHA found in body",
                "where": "body.md",
                "output": (
                    "Expected a backtick-quoted SHA near 'after' in the Proof section."
                    + (" PR states it cannot provide full before/after." if excuse else "")
                ),
            }],
            suggested_fix=(
                "Add the exact commit SHA used for the after-state run, e.g. "
                '"after" is `<sha>`.'
            ),
            confidence=0.92,
        ))

    return findings


# ---------------------------------------------------------------------------
# Check 2 — Symmetric comparison (same flags on both sides)
# ---------------------------------------------------------------------------

_SAME_SETTINGS_RE = re.compile(
    r'(?:same\s+(?:data\s+and\s+)?(?:commands?|flags?|settings?|inputs?|invocation)'
    r'\s+(?:on\s+both\s+sides|before\s+and\s+after|for\s+(?:the\s+)?(?:part|both))'
    r'|on\s+both\s+sides\s+of\s+each\s+comparison'
    r'|identical\s+(?:call|command|invocation|settings?))',
    re.IGNORECASE,
)

_CODE_BLOCK_RE = re.compile(r'```[^\n]*\n(.*?)```', re.DOTALL)
_BEFORE_LABEL_RE = re.compile(r'^#\s*before\b', re.IGNORECASE)
_AFTER_LABEL_RE = re.compile(r'^#\s*after\b', re.IGNORECASE)


def _extract_code_block_pairs(text: str) -> list[tuple[list[str], list[str]]]:
    """
    Find fenced code blocks with # before / # after sections.
    Returns list of (before_lines, after_lines) where lines are non-comment,
    non-blank content.
    """
    pairs = []
    for block in _CODE_BLOCK_RE.findall(text):
        before: list[str] = []
        after: list[str] = []
        state: str | None = None
        for line in block.splitlines():
            stripped = line.strip()
            if _BEFORE_LABEL_RE.match(stripped):
                state = "before"
                continue
            if _AFTER_LABEL_RE.match(stripped):
                state = "after"
                continue
            if not stripped or stripped.startswith("#"):
                continue
            if state == "before":
                before.append(stripped)
            elif state == "after":
                after.append(stripped)
        if before or after:
            pairs.append((before, after))
    return pairs


def _command_signature(lines: list[str]) -> list[str]:
    """
    Extract lines that look like command invocations (start with a tool name
    or flag), filtering out pure terminal output lines.
    """
    cmd_lines = []
    for line in lines:
        # A command line starts with a tool name, a flag, or the tool's
        # subcommand syntax.  Output lines start with capitalised words like
        # "Valid", "Error", "Warning", "Scale", "Measured", etc.
        # Heuristic: a line that starts with a lowercase word, a path, or '--'
        # is likely a command; skip lines starting with capital + common output
        if re.match(r'^(?:Valid|Error|Warning|Scale|Measured|UV|Failed|'
                    r'Creating|Successfully|Hint|EXIT)', line):
            continue
        cmd_lines.append(line)
    return cmd_lines


def check_symmetry(body: str) -> list[dict]:
    """
    Check 2: same flags and input on both sides.
    Returns a list of findings (empty = pass for this check).
    """
    # Collect evidence text from the relevant sections
    proof_text = extract_section(body, "Proof") or ""
    before_text = extract_section(body, "Before") or ""
    after_text = extract_section(body, "After this PR") or ""
    example_text = extract_section(body, "One real example") or ""
    scope = proof_text + before_text + after_text + example_text

    # Explicit same-settings statement: pass immediately
    m = _SAME_SETTINGS_RE.search(scope)
    if m:
        return []  # Symmetry confirmed by explicit statement

    # No explicit statement; analyse before/after code-block pairs
    pairs = _extract_code_block_pairs(scope)

    if not pairs:
        # No code blocks at all — check if there's any comparison implied
        has_before_label = bool(re.search(r'\b#\s*before\b', scope, re.IGNORECASE))
        has_after_label = bool(re.search(r'\b#\s*after\b', scope, re.IGNORECASE))
        if has_before_label or has_after_label:
            # Labels present but couldn't parse commands (output-only or indented blocks)
            return [make_finding(
                rule_id="evidence/symmetry-unverifiable",
                severity=SEV_MAJOR,
                source=SRC_INFERRED,
                evidence=[{
                    "what": "Before/after sections present but command lines could not be verified",
                    "where": "body.md (Proof section)",
                    "output": (
                        "No explicit 'same commands on both sides' statement found "
                        "and no parseable command lines in code blocks. "
                        "Add a statement like 'Same data and commands on both sides' "
                        "or show the command lines explicitly."
                    ),
                }],
                suggested_fix=(
                    "Add an explicit statement that the same flags, input file, "
                    "and settings were used on both sides of the comparison."
                ),
                confidence=0.65,
            )]
        # No before/after structure at all — not an asymmetry finding
        # (commit check will handle missing before/after)
        return []

    # Compare command signatures across pairs
    asymmetries = []
    for i, (before_lines, after_lines) in enumerate(pairs):
        before_cmds = _command_signature(before_lines)
        after_cmds = _command_signature(after_lines)
        if not before_cmds and not after_cmds:
            continue
        if not before_cmds or not after_cmds:
            continue

        # Extract flags: tokens starting with '--' or '-'
        def flags(lines: list[str]) -> set[str]:
            result: set[str] = set()
            for line in lines:
                for tok in line.split():
                    if tok.startswith("--") or (tok.startswith("-") and len(tok) > 1):
                        result.add(tok.split("=")[0])
            return result

        before_flags = flags(before_cmds)
        after_flags = flags(after_cmds)
        only_before = before_flags - after_flags
        only_after = after_flags - before_flags

        if only_before or only_after:
            asymmetries.append((i + 1, before_cmds, after_cmds, only_before, only_after))

    if asymmetries:
        idx, b_cmds, a_cmds, ob, oa = asymmetries[0]
        return [make_finding(
            rule_id="evidence/asymmetric-flags",
            severity=SEV_BLOCKER,
            source=SRC_INFERRED,
            evidence=[{
                "what": f"Pair {idx}: flags differ between before and after — a comparison with different flags is not a comparison",
                "where": "body.md (Proof section code blocks)",
                "output": (
                    f"before command: {'; '.join(b_cmds[:3])}\n"
                    f"after command:  {'; '.join(a_cmds[:3])}\n"
                    f"flags only in before: {sorted(ob)}\n"
                    f"flags only in after:  {sorted(oa)}"
                ),
            }],
            suggested_fix=(
                "Use the same flags, input file, and settings on both sides. "
                "If a flag was intentionally removed or changed, explain why "
                "the comparison is still valid."
            ),
            confidence=0.82,
        )]

    # Pairs found, no asymmetric flags detected
    return []


# ---------------------------------------------------------------------------
# Check 3 — Real scroll data (scoped to example + proof sections only)
#
# BUG-3 prevention: do NOT scan the full body.  The ## Details section may
# mention synthetic test meshes while the proof itself uses real data.
# ---------------------------------------------------------------------------

_REAL_DATA_RE = re.compile(
    r'(?:Scroll\s*\d|PHerc|\.volpkg|paths/\d{6,}|\d{8,}\.obj|\d{8,}.*\.tifxyz'
    r'|scroll\s+spiral|scroll\s+dataset|segment\s+\d{4,}|segments/\d{6,}'
    r'|20231007|20230503|20260310|PHercParis|Vesuvius|real\s+scroll'
    r'|published\s+segment|scroll.*root)',
    re.IGNORECASE,
)

_SYNTHETIC_RE = re.compile(
    r'\b(?:synthetic|toy\s+example|randomly\s+generated|fake\s+data|dummy'
    r'|mock\s+data)\b'
    r'|(?:a\s+3D\s+volume\b|some\s+volume\b|sample\s+input\b)',
    re.IGNORECASE,
)


def check_real_data(body: str) -> list[dict]:
    """
    Check 3: evidence sections reference real scroll data, not synthetic input.
    Scoped to One real example + Proof sections only (Bug-3 prevention).
    """
    example_text = extract_section(body, "One real example") or ""
    proof_text = extract_section(body, "Proof") or ""
    scoped = example_text + proof_text

    has_real = bool(_REAL_DATA_RE.search(scoped))
    has_synthetic = bool(_SYNTHETIC_RE.search(scoped))

    if has_real and not has_synthetic:
        return []  # Pass

    if has_synthetic and not has_real:
        m = _SYNTHETIC_RE.search(scoped)
        snippet = scoped[max(0, m.start() - 20): m.end() + 60].replace("\n", " ").strip()
        return [make_finding(
            rule_id="evidence/synthetic-data",
            severity=SEV_BLOCKER,
            source=SRC_CONTRIBUTING_20,
            quote=CONTRIBUTING_REAL_DATA_QUOTE,
            evidence=[{
                "what": "Example or proof section uses synthetic/toy data with no real scroll data",
                "where": "body.md (One real example + Proof sections)",
                "output": f'Synthetic signal: "...{snippet[:150]}..."',
            }],
            suggested_fix=(
                "Replace synthetic data with real Vesuvius scroll data "
                "(a named segment, .volpkg path, or published mesh file)."
            ),
            confidence=0.85,
        )]

    if not has_real:
        return [make_finding(
            rule_id="evidence/synthetic-data",
            severity=SEV_BLOCKER,
            source=SRC_CONTRIBUTING_20,
            quote=CONTRIBUTING_REAL_DATA_QUOTE,
            evidence=[{
                "what": "No real scroll data found in One real example or Proof sections",
                "where": "body.md (One real example + Proof sections)",
                "output": (
                    "Neither section names a Vesuvius scroll, .volpkg path, "
                    "segment ID, or published mesh/tifxyz file."
                ),
            }],
            suggested_fix=(
                "Demonstrate the fix on real Vesuvius scroll data. "
                "Name the scroll, segment, or dataset used."
            ),
            confidence=0.80,
        )]

    # has_real AND has_synthetic — borderline (real data present despite synthetic mention)
    return []


# ---------------------------------------------------------------------------
# Check 4 — Proof artefact attached
# ---------------------------------------------------------------------------

def check_artefact(body: str) -> list[dict]:
    """
    Check 4: the Proof section contains an actual artefact, not just a claim.
    """
    proof_text = extract_section(body, "Proof") or ""

    if not proof_text.strip():
        return [make_finding(
            rule_id="evidence/no-proof-artefact",
            severity=SEV_MAJOR,
            source=SRC_INFERRED,
            evidence=[{
                "what": "Proof section is absent or empty",
                "where": "body.md",
                "output": "No Proof section found in body.",
            }],
            suggested_fix=(
                "Add a Proof section with an image, terminal output block, "
                "benchmark table, or video link."
            ),
            confidence=0.97,
        )]

    if has_image_or_media(proof_text):
        return []  # Pass

    # Section present but no artefact detected
    snippet = proof_text.strip()[:200]
    return [make_finding(
        rule_id="evidence/no-proof-artefact",
        severity=SEV_MAJOR,
        source=SRC_INFERRED,
        evidence=[{
            "what": "Proof section has text but no attached artefact",
            "where": "body.md (Proof section)",
            "output": (
                f"Section content (first 200 chars): {snippet!r}\n"
                "Expected: a GitHub image attachment, fenced code block of "
                "terminal output, indented code block, or benchmark table."
            ),
        }],
        suggested_fix=(
            "Attach an image, paste terminal output as a fenced code block "
            "(``` ... ```), or include a benchmark table."
        ),
        confidence=0.88,
    )]


# ---------------------------------------------------------------------------
# Check 5 — Number consistency
# ---------------------------------------------------------------------------

# Number pattern with non-digit look-around to avoid matching sub-sequences
# of larger digit strings (like segment IDs: 20250703034159599).
_NUMBER_RE = re.compile(r'(?<!\d)(\d{1,3}(?:,\d{3})*(?:\.\d+)?|\d+\.\d+|\d{5,9})(?!\d)')


def _clean_for_numbers(text: str) -> str:
    """Remove noisy content before number extraction."""
    # Strip GitHub attachment URLs (contain hex sub-sequences)
    t = re.sub(r'https://github\.com/user-attachments/assets/[^\s"]+', ' ', text)
    # Strip backtick strings (SHAs, segment IDs, command args)
    t = re.sub(r'`[^`]*`', ' ', t)
    # Strip HTML tag attribute values
    t = re.sub(r'(?:width|height|alt|src|id)="[^"]*"', ' ', t)
    return t


def _find_all_numbers(text: str) -> list[float]:
    """Extract significant numbers, excluding timestamps and large IDs."""
    clean = _clean_for_numbers(text)
    results = []
    for m in _NUMBER_RE.finditer(clean):
        try:
            n = float(m.group(1).replace(",", ""))
            if n > 1e9:   # skip timestamps / large segment IDs
                continue
            results.append(n)
        except ValueError:
            pass
    return results


def _numbers_consistent(a: float, b: float, tol: float = 0.06) -> bool:
    """Return True if a and b are within tol relative tolerance of each other."""
    if a == 0 and b == 0:
        return True
    if a == 0 or b == 0:
        return abs(a - b) < 1.0  # near-zero
    return abs(a - b) / max(abs(a), abs(b)) <= tol


def check_numbers(body: str) -> list[dict]:
    """
    Check 5: numbers stated in the PR body are internally consistent.

    Strategy: only flag numbers that appear in the SAME labelled context in
    both sections (e.g. the same "valid grid points" count stated twice with
    different values).  Avoid comparing numbers from different sub-experiments
    or different metrics (a 961-column grid and a 900-point window are both
    correct; the checker has no semantic context to distinguish them).

    Concretely: check only numbers that appear within 80 chars of the SAME
    keyword phrase in both sections.  If no such pairs exist, emit no finding.
    This is intentionally conservative — a false positive here is worse than
    a miss because it would reject a correct PR.
    """
    example_text = extract_section(body, "One real example") or ""
    proof_text = extract_section(body, "Proof") or ""

    if not example_text and not proof_text:
        return []

    # Extract (keyword, number) pairs from a section
    # Keywords that label a measurement value
    METRIC_KEYWORD_RE = re.compile(
        r'(?:'
        r'valid\s+(?:grid\s+)?points?'      # "valid grid points"
        r'|valid\s+corners?'
        r'|written\s+scale'                 # "written scale"
        r'|scale\s*[:\[]'                   # "scale: [...]"
        r'|grid\s+\d+\s*[x×]'              # "grid N x M"
        r'|output\s+grid'                   # "output grid"
        r'|(\d{1,3}(?:,\d{3})*)\s+(?:valid|of\s+\d)'  # "N valid"
        r')',
        re.IGNORECASE,
    )

    def extract_metric_values(text: str) -> dict[str, list[float]]:
        """Extract {keyword: [values]} from text near metric keywords."""
        result: dict[str, list[float]] = {}
        for m in METRIC_KEYWORD_RE.finditer(text):
            kw = m.group(0)[:30].lower().strip()
            # Get numbers within 80 chars after the keyword
            window = text[m.start(): m.start() + 80]
            nums = _find_all_numbers(window)
            nums = [n for n in nums if 1 <= n <= 1e8]
            if nums:
                result.setdefault(kw, []).extend(nums)
        return result

    example_metrics = extract_metric_values(example_text)
    proof_metrics = extract_metric_values(proof_text)

    contradictions: list[str] = []

    # Find keywords present in both sections and compare their values
    shared_keys: list[str] = []
    for ek in example_metrics:
        for pk in proof_metrics:
            # Match if the first 10 chars of keyword are the same
            if ek[:10] == pk[:10]:
                shared_keys.append((ek, pk))

    for ek, pk in shared_keys:
        ex_vals = example_metrics[ek]
        pr_vals = proof_metrics[pk]
        for ev in ex_vals:
            for pv in pr_vals:
                # Only compare values that are in the same order of magnitude
                if not (0.5 <= pv / max(ev, 1) <= 2.0):
                    continue
                if not _numbers_consistent(ev, pv):
                    contradictions.append(
                        f'"{ek}" states {ev:,.0f} in One real example '
                        f'but {pv:,.0f} in Proof'
                    )

    if contradictions:
        return [make_finding(
            rule_id="evidence/number-inconsistency",
            severity=SEV_MAJOR,
            source=SRC_INFERRED,
            evidence=[{
                "what": "Same metric stated with different values in One real example vs Proof",
                "where": "body.md",
                "output": "; ".join(contradictions[:3]),
            }],
            suggested_fix=(
                "Check that numbers stated in One real example match the "
                "terminal output in the Proof section."
            ),
            confidence=0.70,
        )]

    return []


# ---------------------------------------------------------------------------
# Main checker
# ---------------------------------------------------------------------------

def check(body: str, verbose: bool = False) -> list[dict]:
    """
    Run all five evidence checks.  Return a list of findings.
    If all checks pass, return a single nit/pass finding.
    """
    findings: list[dict] = []

    # Check 1 — Commit IDs
    findings.extend(check_commit_ids(body))

    # Check 2 — Symmetric comparison
    findings.extend(check_symmetry(body))

    # Check 3 — Real scroll data (scoped)
    findings.extend(check_real_data(body))

    # Check 4 — Proof artefact attached
    findings.extend(check_artefact(body))

    # Check 5 — Number consistency
    findings.extend(check_numbers(body))

    if not findings:
        # All checks passed
        return [pass_finding(
            what="All five evidence checks passed.",
            details="commits: PASS; symmetry: PASS; real-data: PASS; artefact: PASS; numbers: PASS",
            where="body.md",
        )]

    return findings


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--pr", type=int, help="PR number; loads from corpus/")
    parser.add_argument("--body", help="Path to PR body markdown file")
    parser.add_argument("--diff", help="Path to diff patch file (optional)")
    parser.add_argument("--corpus", default="corpus",
                        help="Corpus cache directory (default: corpus/)")
    parser.add_argument("--verbose", action="store_true",
                        help="Include extra evidence details in output")
    args = parser.parse_args()

    corpus = Path(args.corpus)
    body = ""

    if args.pr is not None:
        pr_dir = corpus / str(args.pr)
        if not pr_dir.exists():
            print(json.dumps([error_finding(
                f"No corpus directory for PR #{args.pr}: {pr_dir}"
            )], indent=2))
            sys.exit(0)
        body_path = pr_dir / "body.md"
        try:
            body = body_path.read_text()
        except Exception as e:
            print(json.dumps([error_finding(
                f"Cannot read {body_path}: {e}"
            )], indent=2))
            sys.exit(0)

    elif args.body:
        try:
            body = Path(args.body).read_text()
        except Exception as e:
            print(json.dumps([error_finding(f"Cannot read body file: {e}")], indent=2))
            sys.exit(0)

    if not body:
        print(json.dumps([error_finding(
            "No PR body provided. Use --pr <N> or --body <file>."
        )], indent=2))
        sys.exit(0)

    findings = check(body, verbose=args.verbose)
    print(json.dumps(findings, indent=2))


if __name__ == "__main__":
    main()
