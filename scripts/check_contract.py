#!/usr/bin/env python3
"""
check_contract.py — Contract-compliance checker for pull requests.

Iterates every rule in contract.yml. Never hard-codes a rule.
Emits one finding per rule in schemas/finding.json format.

Usage:
    python scripts/check_contract.py --pr <NUMBER> [options]
    python scripts/check_contract.py --body <file> --diff <file> [options]

Options:
    --pr <N>            PR number; loads body from corpus/<N>/body.md,
                        diff from corpus/<N>/diff.patch,
                        meta from corpus/<N>/meta.json
    --body <file>       Path to PR body markdown file (alternative to --pr)
    --diff <file>       Path to PR diff patch file (alternative to --pr)
    --meta <file>       Path to PR meta JSON file (optional with --body/--diff)
    --contract <file>   Path to contract.yml (default: contract.yml)
    --corpus <dir>      Corpus cache directory (default: corpus/)
    --verbose           Include extra evidence details
    --eval-date <date>  ISO date to use as "today" for time-limit checks
                        (default: now; use PR's createdAt for reproducibility)

Output:
    A JSON array of finding objects (one per rule) to stdout.
    Exit 0 always; errors are surfaced as findings.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any

try:
    import yaml
except ImportError:
    print(json.dumps([{
        "checker": "contract-compliance",
        "severity": "blocker",
        "rule": {"id": "contract-compliance/script-error", "source": "scripts/check_contract.py"},
        "evidence": [{"what": "Missing dependency", "output": "PyYAML is not installed. Run: pip install pyyaml"}],
        "suggested_fix": "Install PyYAML: pip install pyyaml",
        "confidence": 0.0,
    }], indent=2))
    sys.exit(0)

# ---------------------------------------------------------------------------
# Schema constants
# ---------------------------------------------------------------------------

CHECKER = "contract-compliance"
SEV_BLOCKER = "blocker"
SEV_MAJOR = "major"
SEV_NIT = "nit"

# Template section headings (as they appear in the PR body)
TEMPLATE_HEADINGS = [
    "In one sentence",
    "One real example",
    "Before",
    "After this PR",
    "Proof",
    "Why / where this is useful",
]

# HTML placeholder pattern
_PLACEHOLDER_RE = re.compile(r'<!--.*?-->', re.DOTALL)

# ---------------------------------------------------------------------------
# Small helpers
# ---------------------------------------------------------------------------

def parse_iso(s: str) -> datetime:
    return datetime.fromisoformat(s.rstrip("Z")).replace(tzinfo=timezone.utc)


def fmt_source(source: Any) -> str:
    """Format a contract.yml source value as a string."""
    if isinstance(source, str):
        return source
    if isinstance(source, dict):
        f = source.get("file", "")
        lines = source.get("lines", "")
        return f"{f}:{lines}" if lines else f
    return str(source)


def make_finding(
    rule_id: str,
    severity: str,
    source: str,
    quote: str | None,
    evidence: list[dict],
    suggested_fix: str,
    confidence: float,
) -> dict:
    rule: dict[str, Any] = {"id": rule_id, "source": source}
    if quote:
        rule["quote"] = quote[:300]  # truncate very long quotes
    return {
        "checker": CHECKER,
        "severity": severity,
        "rule": rule,
        "evidence": evidence,
        "suggested_fix": suggested_fix,
        "confidence": round(min(1.0, max(0.0, confidence)), 3),
    }


def pass_finding(rule_id: str, source: str, quote: str | None, what: str,
                 confidence: float = 0.90) -> dict:
    return make_finding(
        rule_id=f"{rule_id}/pass",
        severity=SEV_NIT,
        source=source,
        quote=quote,
        evidence=[{"what": what}],
        suggested_fix="No action required.",
        confidence=confidence,
    )


def not_applicable_finding(rule_id: str, source: str, reason: str) -> dict:
    return make_finding(
        rule_id=f"{rule_id}/not-applicable",
        severity=SEV_NIT,
        source=source,
        quote=None,
        evidence=[{"what": reason}],
        suggested_fix="Rule does not apply to this PR type.",
        confidence=1.0,
    )


def error_finding(msg: str) -> dict:
    return make_finding(
        rule_id="contract-compliance/script-error",
        severity=SEV_BLOCKER,
        source="scripts/check_contract.py",
        quote=None,
        evidence=[{"what": "script error", "output": msg}],
        suggested_fix="Fix the error in check_contract.py or supply missing input files.",
        confidence=0.0,
    )


# ---------------------------------------------------------------------------
# Section extraction from PR body
# ---------------------------------------------------------------------------

def extract_section(body: str, heading: str) -> str | None:
    """
    Extract the text of a section identified by a bold heading like
    **Heading:** or **Heading**. Returns None if the heading is absent.
    Returns "" if the heading is present but the section is empty.
    """
    # Match **Heading:** or **Heading** at the start of a line
    pattern = re.compile(
        r'(?:^|\n)\*\*' + re.escape(heading) + r'(?:\:\*\*|\*\*:?)\s*',
        re.IGNORECASE,
    )
    m = pattern.search(body)
    if m is None:
        return None

    start = m.end()
    rest = body[start:]

    # Find the next **Bold:** heading or a ## heading or end of string
    next_heading = re.search(
        r'\n(?:\*\*[A-Z][^\n]*\*\*:?|\#{1,3} )',
        rest,
    )
    if next_heading:
        section = rest[:next_heading.start()]
    else:
        section = rest
    return section


def section_state(body: str, heading: str) -> tuple[str, str]:
    """
    Returns (state, raw_text) where state is one of:
      'absent'      — heading not present
      'blank'       — heading present, section empty
      'placeholder' — heading present, section contains only HTML comments
      'filled'      — heading present, section has real content
    """
    raw = extract_section(body, heading)
    if raw is None:
        return "absent", ""
    stripped = raw.strip()
    if not stripped:
        return "blank", raw
    # Remove HTML comments and check if anything real remains
    without_comments = _PLACEHOLDER_RE.sub("", stripped).strip()
    if not without_comments:
        return "placeholder", raw
    return "filled", raw


def count_words(text: str) -> int:
    return len(text.split())


def has_image_or_media(text: str) -> bool:
    """Check for images, videos, or fenced code blocks in text."""
    # GitHub image attachment
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
    # Indented code block (4 spaces)
    if re.search(r'\n    \S', text):
        return True
    # Benchmark table
    if re.search(r'\|.*\|.*\|', text):
        return True
    return False


# Exact template placeholder tokens from the PR template
_TEMPLATE_PLACEHOLDER_RE = re.compile(
    r'\[(?:real data/input|action|result|'
    r'[A-Z][a-z ]{5,}|'           # Title-Case phrase like [Explain what...]
    r'[a-z]{4,}(?:\s[a-z]{2,})+' # lowercase multi-word like [some description]
    r')\]'
)


def has_real_placeholders(text: str) -> bool:
    """Check for unfilled square-bracket template placeholders like [real data/input].
    Does NOT match numeric arrays like [0,1] or [0.06, 0.12] or [row, col]."""
    return bool(_TEMPLATE_PLACEHOLDER_RE.search(text))


def checkbox_state(body: str) -> str:
    """Return 'ticked', 'unticked', or 'absent'."""
    if re.search(r'- \[[xX]\]\s+I personally verified', body):
        return "ticked"
    if re.search(r'- \[ \]\s+I personally verified', body):
        return "unticked"
    return "absent"


# ---------------------------------------------------------------------------
# LLM detection
# ---------------------------------------------------------------------------

LLM_TOOL_NAMES = re.compile(
    r'\b(ChatGPT|GPT-?4|GPT-?3|Claude|Copilot|Cursor|Codex|Gemini|Bard|'
    r'LLM|AI[- ]assistant|AI[- ]tool|AI[- ]generated|AI[- ]assisted|'
    r'language model|large language model)\b',
    re.IGNORECASE,
)


def is_llm_assisted(body: str, diff: str, meta: dict | None) -> bool:
    """Return True if the PR appears to be LLM-assisted."""
    if LLM_TOOL_NAMES.search(body):
        return True
    # Check branch name
    if meta:
        branch = meta.get("headRefName", "")
        if LLM_TOOL_NAMES.search(branch):
            return True
    return False


def detect_pr_types(body: str, diff: str, meta: dict | None) -> set[str]:
    """
    Return the set of applicable type labels for a PR:
    'all' is always included.
    'bugfix', 'feature', 'llm-assisted' added as appropriate.
    """
    types = {"all"}
    title = ""
    branch = ""
    if meta:
        title = meta.get("title", "").lower()
        branch = meta.get("headRefName", "").lower()

    combined_low = (title + " " + branch + " " + body[:500]).lower()

    if re.search(r'\b(fix|bug|crash|error|issue|patch|repair)\b', combined_low):
        types.add("bugfix")

    if re.search(r'\b(feat|add|new|implement|support|introduce|enable)\b', combined_low):
        types.add("feature")

    if is_llm_assisted(body, diff, meta):
        types.add("llm-assisted")

    # If no specific type detected, default to feature
    if "bugfix" not in types and "feature" not in types:
        types.add("feature")

    return types


def rule_applies(rule: dict, pr_types: set[str]) -> bool:
    """Return True if the rule applies to this PR."""
    applies = rule.get("applies_to", "all")
    if isinstance(applies, str):
        applies = [applies]
    for a in applies:
        if a == "all" or a in pr_types:
            return True
    return False


# ---------------------------------------------------------------------------
# Human authorship heuristic
# ---------------------------------------------------------------------------

HUMAN_SIGNALS = [
    # First-person personal narrative
    (re.compile(r'\bI\s+(ran|tried|was|noticed|found|reproduced|tested|'
                r'checked|built|measured|converted|flattened|read)\b'),
     "first-person action verb"),
    # Personal uncertainty
    (re.compile(r'\bI\s+(haven\'t|have not|don\'t|did not|cannot|can\'t|'
                r'am not sure|think|believe)\b', re.IGNORECASE),
     "personal uncertainty expression"),
    # Specific named data
    (re.compile(r'(?:Scroll\s*\d|PHerc|\.volpkg|paths/\d{8,}|segment\s+id|'
                r'\d{8,}\.obj|scroll spiral)', re.IGNORECASE),
     "specific named scroll/dataset"),
    # Cross-references to prior work with personal observation
    (re.compile(r'#\d{3,4}.*?\b(by|from|of)\b', re.IGNORECASE),
     "cross-reference with personal observation"),
    # Idiosyncratic phrasing / personal opinion
    (re.compile(r'\b(my own machine|my machine|on my|I got|I see|I am|'
                r'I\'ve|I\'d|I\'ll|I noticed|I compared|I reproduced)\b',
                re.IGNORECASE),
     "personal possession/experience phrase"),
]

LLM_SIGNALS = [
    # Impersonal "This PR" framing
    (re.compile(r'\bThis (PR|change|commit|patch|fix|update)\b',
                re.IGNORECASE),
     "impersonal 'This PR/change' framing"),
    # Generic benefit framing
    (re.compile(r'\b(ensures?|guarantees?|allows? users? to|enables? users? to|'
                r'improves? (the )?performance|improves? (code )?quality)\b',
                re.IGNORECASE),
     "generic benefit/quality framing"),
    # Exhaustive symmetric list (many bullets of equal weight)
    (re.compile(r'(\n\s*[-*]\s+\w.{20,}\n){5,}'),
     "exhaustive symmetric bullet list"),
]


def score_human_authorship(body: str) -> tuple[int, int, list[str]]:
    """
    Returns (human_score, llm_score, reasoning_lines).
    """
    human = 0
    llm = 0
    reasons = []

    for pat, desc in HUMAN_SIGNALS:
        m = pat.search(body)
        if m:
            human += 1
            snippet = body[max(0, m.start()-20):m.end()+40].replace('\n', ' ').strip()
            reasons.append(f"HUMAN: {desc} — e.g. \"{snippet[:100]}\"")

    for pat, desc in LLM_SIGNALS:
        m = pat.search(body)
        if m:
            llm += 1
            snippet = body[max(0, m.start()-10):m.end()+30].replace('\n', ' ').strip()
            reasons.append(f"LLM: {desc} — e.g. \"{snippet[:100]}\"")

    return human, llm, reasons


# ---------------------------------------------------------------------------
# Individual rule checkers
# ---------------------------------------------------------------------------
# Each checker(rule, body, diff, meta, pr_types) -> dict (finding)
# ---------------------------------------------------------------------------


def _names_from_diff(diff: str) -> set:
    names = set()
    for m in re.finditer(r'^\+\+\+ b/(\S+)', diff or "", re.MULTILINE):
        p = m.group(1)
        stem = p.rsplit("/", 1)[-1]
        names.add(stem)
        if "." in stem:
            names.add(stem.rsplit(".", 1)[0])
        for part in p.split("/"):
            if len(part) > 3:
                names.add(part)
    for m in re.finditer(r'^[-+]\s*def\s+([A-Za-z_][A-Za-z0-9_]*)', diff or "", re.MULTILINE):
        names.add(m.group(1))
    return {n for n in names if len(n) > 3}


def _mentions_touched_code(body: str, diff: str) -> bool:
    for n in _names_from_diff(diff):
        if re.search(r'\b' + re.escape(n) + r'\b', body or ""):
            return True
    return False

def check_real_scroll_data_origin(rule: dict, body: str, diff: str,
                                   meta: dict | None) -> dict:
    src = fmt_source(rule.get("source"))
    quote = rule.get("quote", "")
    rule_id = rule["id"]

    # Look for: first-person verb + named tool + named data artifact
    has_first_person = bool(re.search(
        r'\bI\s+(ran|tried|tested|used|was running|was attempting|converted|'
        r'flattened|built|started|loaded|processed)\b', body, re.IGNORECASE))

    tool_names = re.compile(
        r'\b(vc_render|vc_obj2tifxyz|vc_flatten|vc_grow_seg|vc_tifxyz|'
        r'fit_spiral\.py|prefetch\.py|vesuvius\.predict|vesuvius\.tifxyz|'
        r'vc_segment|vc_cut|vc_vol|vc_ppm|vc_layers|vc_meshing|vc_texture|'
        r'lasagna|scroll[_ ]spiral|spiral.fitter|spiral_fitter)\b',
        re.IGNORECASE)
    has_tool = bool(tool_names.search(body)) or _mentions_touched_code(body, diff)

    scroll_data = re.compile(
        r'(?:Scroll\s*\d|PHerc\s*\d|\.volpkg|paths/\d{6,}|\d{8,}\.obj|'
        r'scroll spiral|scroll dataset|segment\s+\d|segments/\d{6,}|'
        r'PHercParis|20231007|20230503|Scroll 1)',
        re.IGNORECASE)
    has_data = bool(scroll_data.search(body))

    if has_first_person and has_tool and has_data:
        return pass_finding(rule_id, src, quote,
            "Body contains first-person account with named tool and real data artefact.")

    missing = []
    if not has_first_person:
        missing.append("no first-person account of running a tool")
    if not has_tool:
        missing.append("no named tool from this repository")
    if not has_data:
        missing.append("no named real scroll data artefact")

    return make_finding(
        rule_id=rule_id,
        severity=rule.get("severity", SEV_BLOCKER),
        source=src,
        quote=quote,
        evidence=[{
            "what": "Missing first-person real-scroll-data session",
            "output": f"Missing: {'; '.join(missing)}",
        }],
        suggested_fix=rule.get("failure_message", ""),
        confidence=0.80,
    )


def check_bugfix_error_screenshot(rule: dict, body: str, diff: str,
                                   meta: dict | None, pr_types: set[str]) -> dict:
    src = fmt_source(rule.get("source"))
    quote = rule.get("quote", "")
    rule_id = rule["id"]

    if "bugfix" not in pr_types:
        return not_applicable_finding(rule_id, src, "PR is not classified as a bugfix.")

    # Need artefact before (error) AND artefact after (success)
    before_section = extract_section(body, "Before") or ""
    proof_section = extract_section(body, "Proof") or ""
    after_section = extract_section(body, "After this PR") or ""

    before_has_artefact = has_image_or_media(before_section) or has_image_or_media(proof_section)
    after_has_artefact = (has_image_or_media(after_section) or has_image_or_media(proof_section))

    # Also accept if the proof section has both before and after content
    proof_has_before_after = (
        re.search(r'#\s*before\b', proof_section, re.IGNORECASE) and
        re.search(r'#\s*after\b', proof_section, re.IGNORECASE)
    )
    if proof_has_before_after:
        before_has_artefact = True
        after_has_artefact = True

    if before_has_artefact and after_has_artefact:
        return pass_finding(rule_id, src, quote,
            "PR body contains before-error and after-success artefacts (image, screenshot, or terminal block).")

    missing = []
    if not before_has_artefact:
        missing.append("no artefact showing the error before this PR")
    if not after_has_artefact:
        missing.append("no artefact showing success after this PR")

    return make_finding(
        rule_id=rule_id,
        severity=rule.get("severity", SEV_BLOCKER),
        source=src,
        quote=quote,
        evidence=[{
            "what": "Missing bugfix artefacts",
            "output": f"Missing: {'; '.join(missing)}",
        }],
        suggested_fix=rule.get("failure_message", ""),
        confidence=0.75,
    )


def check_no_synthetic_data(rule: dict, body: str, diff: str,
                              meta: dict | None) -> dict:
    src = fmt_source(rule.get("source"))
    quote = rule.get("quote", "")
    rule_id = rule["id"]

    synthetic_signals = re.compile(
        r'\b(synthetic|toy example|numpy array|randomly generated|'
        r'MNIST|CIFAR|ImageNet|fake data|test data|sample input|'
        r'a 3D volume|some volume|dummy|mock data)\b',
        re.IGNORECASE)

    real_signals = re.compile(
        r'(?:Scroll\s*\d|PHerc|\.volpkg|paths/\d{6,}|\d{8,}\.obj|'
        r'scroll spiral|scroll dataset|segment\s+\d|20231007|20230503|'
        r'PHercParis|Vesuvius|real scroll|published segment)',
        re.IGNORECASE)

    # Check specifically the example and proof sections (not the whole body,
    # which may legitimately mention synthetic test fixtures in ## Details).
    example_raw = extract_section(body, "One real example") or ""
    proof_raw = extract_section(body, "Proof") or ""
    evidence_text = example_raw + proof_raw

    has_synthetic_in_evidence = bool(synthetic_signals.search(evidence_text))
    has_real_in_body = bool(real_signals.search(body))
    has_real_in_evidence = bool(real_signals.search(evidence_text))

    if has_synthetic_in_evidence and not has_real_in_evidence:
        return make_finding(
            rule_id=rule_id,
            severity=rule.get("severity", SEV_BLOCKER),
            source=src,
            quote=quote,
            evidence=[{
                "what": "Example or proof section uses synthetic/toy data; no real scroll data",
                "output": evidence_text[:200],
            }],
            suggested_fix=rule.get("failure_message", ""),
            confidence=0.75,
        )

    # Special case: proof uses a minimal snippet with no real-data reference but body has real data
    proof_is_snippet = bool(re.search(r'```', proof_raw)) and not has_synthetic_in_evidence
    if proof_is_snippet and not has_real_in_evidence and not has_real_in_body:
        return make_finding(
            rule_id=rule_id,
            severity=rule.get("severity", SEV_BLOCKER),
            source=src,
            quote=quote,
            evidence=[{
                "what": "No real scroll data found in body",
                "output": "The example and proof sections do not reference real Vesuvius scroll data.",
            }],
            suggested_fix=rule.get("failure_message", ""),
            confidence=0.60,
        )

    return pass_finding(rule_id, src, quote,
        "Body references real Vesuvius scroll data with no synthetic-data signals in evidence sections.")


def check_motivation_section(rule: dict, body: str, diff: str,
                               meta: dict | None) -> dict:
    src = fmt_source(rule.get("source"))
    quote = rule.get("quote", "")
    rule_id = rule["id"]

    # Look for: first-person + named tool + task context anywhere in body
    first_person = re.compile(
        r'\bI\s+(was|am|ran|tried|was running|was attempting|wanted|'
        r'needed|found|noticed|discovered|used|started|converted|'
        r'flattened|loaded|reproduced)\b', re.IGNORECASE)
    tool_in_body = re.compile(
        r'\b(vc_render|vc_obj2tifxyz|vc_flatten|vc_grow_seg|vc_tifxyz|'
        r'fit_spiral\.py|vesuvius\.|vc_segment|vc_cut|vc_vol|vc_ppm|'
        r'vc_layers|vc_meshing|vc_texture|lasagna|scroll spiral|'
        r'spiral.fitter)\b', re.IGNORECASE)

    has_first = bool(first_person.search(body))
    has_tool = bool(tool_in_body.search(body)) or _mentions_touched_code(body, diff)

    if has_first and has_tool:
        return pass_finding(rule_id, src, quote,
            "Body contains first-person motivation with named tool context.")

    missing = []
    if not has_first:
        missing.append("no first-person account")
    if not has_tool:
        missing.append("no named tool or workflow step")

    return make_finding(
        rule_id=rule_id,
        severity=rule.get("severity", SEV_BLOCKER),
        source=src,
        quote=quote,
        evidence=[{
            "what": "Motivation section insufficient",
            "output": f"Missing: {'; '.join(missing)}",
        }],
        suggested_fix=rule.get("failure_message", ""),
        confidence=0.78,
    )


def check_before_after_comparison(rule: dict, body: str, diff: str,
                                   meta: dict | None, pr_types: set[str]) -> dict:
    src = fmt_source(rule.get("source"))
    quote = rule.get("quote", "")
    rule_id = rule["id"]

    if "bugfix" not in pr_types and "feature" not in pr_types:
        return not_applicable_finding(rule_id, src, "Rule only applies to bugfix and feature PRs.")

    # Check if any pipeline path is modified (paths appear in "diff --git a/<path>" lines)
    pipeline_dirs = re.compile(
        r'(?:^|\s)(vesuvius|ink-detection|volume-cartographer|segmentation|'
        r'lasagna|spiral-fitting)/')
    if not pipeline_dirs.search(diff):
        return pass_finding(rule_id, src, quote,
            "PR does not modify a comparable pipeline directory; comparison not required.",
            confidence=0.85)

    # Check for comparison evidence
    proof_raw = extract_section(body, "Proof") or ""
    before_raw = extract_section(body, "Before") or ""
    after_raw = extract_section(body, "After this PR") or ""

    all_sections = proof_raw + before_raw + after_raw

    has_media = has_image_or_media(all_sections)
    has_metric = bool(re.search(
        r'(?:before|after).{0,100}(?:\d+\s*(?:x|×)\s*\d+|\d+\.?\d*\s*%|'
        r'\d+\s+points|scale\s*[:\=]?\s*[\d\.]+)',
        all_sections, re.IGNORECASE))

    if has_media or has_metric:
        return pass_finding(rule_id, src, quote,
            "PR body contains before/after comparison evidence (image, video, or metric).")

    return make_finding(
        rule_id=rule_id,
        severity=rule.get("severity", SEV_MAJOR),
        source=src,
        quote=quote,
        evidence=[{
            "what": "Pipeline files modified but no before/after comparison found",
            "output": f"Pipeline dirs in diff: {bool(pipeline_dirs.search(diff))}; "
                      f"media in proof/before/after: {has_media}; metric found: {has_metric}",
        }],
        suggested_fix=rule.get("failure_message", ""),
        confidence=0.70,
    )


def check_llm_human_trigger(rule: dict, body: str, diff: str,
                              meta: dict | None) -> dict:
    src = fmt_source(rule.get("source"))
    quote = rule.get("quote", "")
    rule_id = rule["id"]

    # Must have first-person scroll-data session BEFORE/MOTIVATING the LLM use
    first_person_scroll = re.compile(
        r'\bI\s+(ran|tried|was running|was attempting|wanted|needed|'
        r'found|discovered|reproduced|noticed|started|loaded)\b.*?'
        r'(?:scroll|\.volpkg|paths/|\.obj|segment|spiral|volpkg)',
        re.IGNORECASE | re.DOTALL)

    has_personal_session = bool(first_person_scroll.search(body))

    # Also look for explicit statements of priority
    explicit_priority = bool(re.search(
        r'(?:crash|diagnosis|reproduction|bug|error|failure).{0,100}'
        r'(?:my own machine|my machine|from my|I reproduced|I diagnosed)',
        body, re.IGNORECASE | re.DOTALL))

    if has_personal_session or explicit_priority:
        return pass_finding(rule_id, src, quote,
            "Body describes a personal scroll-data session that preceded and motivated LLM use.")

    return make_finding(
        rule_id=rule_id,
        severity=rule.get("severity", SEV_BLOCKER),
        source=src,
        quote=quote,
        evidence=[{
            "what": "No first-person scroll-data session motivating LLM use",
            "output": "Body does not describe a personal scroll-data session that preceded the LLM involvement.",
        }],
        suggested_fix=rule.get("failure_message", ""),
        confidence=0.72,
    )


def check_llm_human_commentary(rule: dict, body: str, diff: str,
                                meta: dict | None) -> dict:
    """
    Key judgement rule. Uses explicit reasoning. Conservative: err toward pass.
    """
    src = fmt_source(rule.get("source"))
    quote = rule.get("quote", "")
    rule_id = rule["id"]

    human_score, llm_score, reasoning = score_human_authorship(body)

    # Decision matrix
    if human_score >= 3 and llm_score == 0:
        verdict = "pass"
        confidence = 0.85
    elif human_score >= 3 and llm_score == 1:
        verdict = "pass"
        confidence = 0.78
    elif human_score >= 2 and llm_score == 0:
        verdict = "pass"
        confidence = 0.75
    elif human_score >= 1 and llm_score == 0:
        verdict = "pass"
        confidence = 0.68
    elif human_score == 0 and llm_score >= 2:
        verdict = "fail"
        confidence = 0.70
    else:
        # Mixed signals: err toward pass
        verdict = "pass"
        confidence = 0.52

    evidence = [
        {
            "what": "Human authorship score",
            "output": f"human_signals={human_score}, llm_signals={llm_score}",
        },
        {
            "what": "Reasoning",
            "output": "\n".join(reasoning[:8]) if reasoning else "No strong signals detected.",
        },
    ]

    if verdict == "pass":
        return make_finding(
            rule_id=f"{rule_id}/pass",
            severity=SEV_NIT,
            source=src,
            quote=quote,
            evidence=evidence,
            suggested_fix="No action required.",
            confidence=confidence,
        )
    else:
        return make_finding(
            rule_id=rule_id,
            severity=rule.get("severity", SEV_BLOCKER),
            source=src,
            quote=quote,
            evidence=evidence,
            suggested_fix=rule.get("failure_message", ""),
            confidence=confidence,
        )


def check_llm_concise_description(rule: dict, body: str, diff: str,
                                   meta: dict | None) -> dict:
    src = fmt_source(rule.get("source"))
    quote = rule.get("quote", "")
    rule_id = rule["id"]

    # Count words above ## Details
    details_match = re.search(r'\n## Details', body, re.IGNORECASE)
    above_details = body[:details_match.start()] if details_match else body
    word_count = count_words(above_details)

    # Check for unexplained acronyms or dense notation.
    # Pattern: two or more separate all-caps words on the same line (not a single long word),
    # or a function call with an all-caps type parameter.
    # We require word-boundary separation to avoid matching long single words like PROGRESS.
    dense = bool(re.search(
        r'\b[A-Z]{3,}\b(?:\s+\b[A-Z]{3,}\b){1,}|'  # 2+ consecutive ALL_CAPS words
        r'\w+\s*\(\s*[A-Z]{2,}(?:\s*,\s*[A-Z]{2,}){1,}\s*\)',  # func(TYPE1, TYPE2)
        above_details))

    if word_count <= 300 and not dense:
        return pass_finding(rule_id, src, quote,
            f"Description above ## Details is {word_count} words; concise and clear.")

    issues = []
    if word_count > 500:
        issues.append(f"description is {word_count} words (> 500)")
    elif word_count > 300:
        issues.append(f"description is {word_count} words (300-500; only flagged if also unclear)")
    if dense:
        issues.append("uses unexplained acronyms or dense notation")

    # Only flag as major if > 500 words OR (> 300 AND dense)
    if word_count > 500 or (word_count > 300 and dense):
        return make_finding(
            rule_id=rule_id,
            severity=rule.get("severity", SEV_MAJOR),
            source=src,
            quote=quote,
            evidence=[{
                "what": "Description length and clarity check",
                "output": f"{'; '.join(issues)}",
            }],
            suggested_fix=rule.get("failure_message", ""),
            confidence=0.75,
        )

    return pass_finding(rule_id, src, quote,
        f"Description is {word_count} words; borderline but acceptable.")


def check_llm_real_scroll_validation(rule: dict, body: str, diff: str,
                                      meta: dict | None) -> dict:
    src = fmt_source(rule.get("source"))
    quote = rule.get("quote", "")
    rule_id = rule["id"]

    synthetic_signals = re.compile(
        r'\b(synthetic|toy example|numpy array|randomly generated|fake data|'
        r'test data|dummy|mock data)\b', re.IGNORECASE)

    real_signals = re.compile(
        r'(?:Scroll\s*\d|PHerc|\.volpkg|paths/\d{6,}|\d{8,}\.obj|'
        r'scroll spiral|scroll dataset|segment\s+\d|20231007|20230503|'
        r'PHercParis|real scroll|published segment)',
        re.IGNORECASE)

    # Check for synthetic data ONLY in the sections that describe the PR's
    # proof/example, NOT in the whole body (## Details may legitimately
    # mention synthetic test fixtures while the actual proof uses real data).
    example_raw = extract_section(body, "One real example") or ""
    proof_raw = extract_section(body, "Proof") or ""
    evidence_text = example_raw + proof_raw

    has_synthetic_in_evidence = bool(synthetic_signals.search(evidence_text))
    has_real_in_body = bool(real_signals.search(body))
    has_real_in_evidence = bool(real_signals.search(evidence_text))

    if has_synthetic_in_evidence and not has_real_in_evidence:
        return make_finding(
            rule_id=rule_id,
            severity=rule.get("severity", SEV_BLOCKER),
            source=src,
            quote=quote,
            evidence=[{"what": "Example or proof section uses synthetic data; no real scroll data evidence",
                        "output": evidence_text[:200]}],
            suggested_fix=rule.get("failure_message", ""),
            confidence=0.75,
        )

    # Check if the proof is a minimal snippet with justification
    is_minimal_snippet = (
        bool(re.search(r'```', proof_raw)) and
        not bool(real_signals.search(proof_raw)) and
        # Check for explicit justification that full proof is not possible
        bool(re.search(
            r'(?:only tested|have not run|cannot claim|I have not|'
            r'without (full|complete) data|two lines|minimal reproduction|'
            r'reproduce the failure|no data|no checkout)',
            body, re.IGNORECASE))
    )

    if is_minimal_snippet and has_real_in_body:
        # Accepted: OS-level bug, minimal reproduction is sufficient
        return pass_finding(rule_id, src, quote,
            "Minimal reproduction snippet accepted: PR explains why full scroll-data "
            "proof is not necessary for this platform-level bug; body references real data.",
            confidence=0.72)

    if has_real_in_body and not has_synthetic_in_evidence:
        return pass_finding(rule_id, src, quote,
            "Proof and example reference real Vesuvius scroll data with no synthetic signals "
            "in the evidence sections.",
            confidence=0.82)

    return make_finding(
        rule_id=rule_id,
        severity=rule.get("severity", SEV_BLOCKER),
        source=src,
        quote=quote,
        evidence=[{
            "what": "Cannot confirm proof was produced by this PR's code on real data",
            "output": f"real_in_body={has_real_in_body}, "
                      f"real_in_evidence={has_real_in_evidence}, "
                      f"synthetic_in_evidence={has_synthetic_in_evidence}, "
                      f"minimal_snippet={is_minimal_snippet}",
        }],
        suggested_fix=rule.get("failure_message", ""),
        confidence=0.58,
    )


def check_llm_human_review(rule: dict, body: str, diff: str,
                             meta: dict | None) -> dict:
    src = fmt_source(rule.get("source"))
    quote = rule.get("quote", "")
    rule_id = rule["id"]

    review_statements = re.compile(
        r'(?:I\s+(?:reviewed|read|checked|read through|inspected|went through)'
        r'|read through the diff|reviewed the.{0,30}(?:diff|code|change|PR)'
        r'|I\s+checked that)',
        re.IGNORECASE)

    has_review = bool(review_statements.search(body))

    if has_review:
        m = review_statements.search(body)
        snippet = body[max(0, m.start()-10):m.end()+60].replace('\n', ' ')
        return pass_finding(rule_id, src, quote,
            f"Body contains explicit code-review statement: \"{snippet[:120]}\"")

    return make_finding(
        rule_id=rule_id,
        severity=rule.get("severity", SEV_MAJOR),
        source=src,
        quote=quote,
        evidence=[{
            "what": "No explicit statement of having reviewed the generated diff",
            "output": "Body does not contain a sentence confirming personal review of the LLM-generated code.",
        }],
        suggested_fix=rule.get("failure_message", ""),
        confidence=0.68,
    )


def check_llm_no_fishing_expedition(rule: dict, body: str, diff: str,
                                     meta: dict | None) -> dict:
    src = fmt_source(rule.get("source"))
    quote = rule.get("quote", "")
    rule_id = rule["id"]

    signals = 0
    signal_reasons = []

    # (a) diff spans > 3 unrelated subproject directories
    subproject_dirs = set()
    for line in diff.splitlines():
        if line.startswith("diff --git"):
            m = re.match(r'diff --git a/([^/]+)/', line)
            if m:
                subproject_dirs.add(m.group(1))
    if len(subproject_dirs) > 3:
        signals += 1
        signal_reasons.append(
            f"(a) diff spans {len(subproject_dirs)} subproject dirs: "
            f"{', '.join(sorted(subproject_dirs))}")

    # (b) predominantly cosmetic changes
    total_lines = sum(1 for l in diff.splitlines()
                      if l.startswith('+') or l.startswith('-'))
    comment_lines = sum(1 for l in diff.splitlines()
                        if re.match(r'^[+-]\s*(?://|#|/\*|\*)', l))
    if total_lines > 0 and comment_lines / total_lines > 0.6:
        signals += 1
        signal_reasons.append(
            f"(b) {comment_lines}/{total_lines} changed lines are comments/docstrings")

    # (c) body reads as fishing expedition
    fishing_phrases = re.compile(
        r'\b(?:find bugs in|improve the codebase|improve code quality|'
        r'refactor|clean up|modernize|update to|upgrade to|best practices)\b',
        re.IGNORECASE)
    if fishing_phrases.search(body) and not re.search(
            r'\bI\s+(was|ran|tried|found|used)\b', body, re.IGNORECASE):
        signals += 1
        signal_reasons.append("(c) body uses fishing-expedition language without personal scroll session")

    if signals >= 2:
        return make_finding(
            rule_id=rule_id,
            severity=rule.get("severity", SEV_BLOCKER),
            source=src,
            quote=quote,
            evidence=[{
                "what": f"{signals} fishing-expedition signals found (need ≥2 to flag)",
                "output": "\n".join(signal_reasons),
            }],
            suggested_fix=rule.get("failure_message", ""),
            confidence=0.72,
        )

    return pass_finding(rule_id, src, quote,
        f"Focused PR: {signals} fishing-expedition signal(s) found (< 2 needed to flag). "
        f"{'; '.join(signal_reasons) if signal_reasons else 'No signals.'}")


def check_pr_template_structure(rule: dict, body: str, diff: str,
                                 meta: dict | None) -> dict:
    src = fmt_source(rule.get("source"))
    quote = rule.get("quote", "")
    rule_id = rule["id"]

    absent = [h for h in TEMPLATE_HEADINGS
              if not re.search(r'\*\*' + re.escape(h), body, re.IGNORECASE)]

    if len(absent) >= 2:
        return make_finding(
            rule_id=rule_id,
            severity=rule.get("severity", SEV_MAJOR),
            source=src,
            quote=quote,
            evidence=[{
                "what": "Two or more template headings absent",
                "output": f"Missing headings: {absent}",
            }],
            suggested_fix=rule.get("failure_message", ""),
            confidence=0.95,
        )
    if absent:
        return make_finding(
            rule_id=f"{rule_id}/partial",
            severity=SEV_MAJOR,
            source=src,
            quote=quote,
            evidence=[{
                "what": "One template heading absent",
                "output": f"Missing: {absent}",
            }],
            suggested_fix=rule.get("failure_message", ""),
            confidence=0.95,
        )
    return pass_finding(rule_id, src, quote,
        f"All {len(TEMPLATE_HEADINGS)} template headings present.")


def check_template_field(rule: dict, body: str, heading: str,
                          extra_check=None) -> dict:
    """Generic check for a template section field."""
    src = fmt_source(rule.get("source"))
    quote = rule.get("quote", "")
    rule_id = rule["id"]
    sev = rule.get("severity", SEV_MAJOR)

    state, raw = section_state(body, heading)

    if state == "absent":
        return make_finding(
            rule_id=f"{rule_id}/absent",
            severity=sev,
            source=src,
            quote=quote,
            evidence=[{"what": f"Section heading \"{heading}\" is absent from PR body.",
                        "output": "Heading not found anywhere in body."}],
            suggested_fix=rule.get("failure_message", ""),
            confidence=0.95,
        )
    if state == "blank":
        return make_finding(
            rule_id=f"{rule_id}/blank",
            severity=sev,
            source=src,
            quote=quote,
            evidence=[{"what": f"Section \"{heading}\" is present but empty (no content).",
                        "output": "Section content is whitespace only."}],
            suggested_fix=rule.get("failure_message", ""),
            confidence=0.97,
        )
    if state == "placeholder":
        return make_finding(
            rule_id=f"{rule_id}/placeholder-only",
            severity=sev,
            source=src,
            quote=quote,
            evidence=[{"what": f"Section \"{heading}\" contains only the template HTML "
                               f"comment placeholder; the field was not filled in.",
                        "output": raw.strip()[:200]}],
            suggested_fix=rule.get("failure_message", ""),
            confidence=0.98,
        )

    # Section is filled — apply extra checks if provided
    if extra_check:
        result = extra_check(raw, rule, src, quote)
        if result is not None:
            return result

    return pass_finding(rule_id, src, quote,
        f"Section \"{heading}\" is present and filled.")


def check_pr_one_sentence_summary(rule: dict, body: str, diff: str,
                                   meta: dict | None) -> dict:
    def extra(raw, rule, src, quote):
        # Check it's a single sentence (not a list, not 3+ sentences)
        sentences = [s.strip() for s in re.split(r'[.!?]', raw.strip()) if s.strip()]
        if len(sentences) >= 3:
            return make_finding(
                rule_id=f"{rule['id']}/too-many-sentences",
                severity=rule.get("severity", SEV_MAJOR),
                source=src,
                quote=quote,
                evidence=[{"what": f"Section contains {len(sentences)} sentences; at most 2 allowed.",
                            "output": raw.strip()[:200]}],
                suggested_fix=rule.get("failure_message", ""),
                confidence=0.80,
            )
        # Check it's not a bulleted list
        if re.search(r'^\s*[-*]', raw, re.MULTILINE):
            return make_finding(
                rule_id=f"{rule['id']}/is-list",
                severity=rule.get("severity", SEV_MAJOR),
                source=src,
                quote=quote,
                evidence=[{"what": "Section is a bulleted list, not a single sentence.",
                            "output": raw.strip()[:200]}],
                suggested_fix=rule.get("failure_message", ""),
                confidence=0.85,
            )
        return None
    return check_template_field(rule, body, "In one sentence", extra)


def check_pr_one_real_example(rule: dict, body: str, diff: str,
                               meta: dict | None) -> dict:
    def extra(raw, rule, src, quote):
        # Check for unfilled placeholders
        if has_real_placeholders(raw):
            return make_finding(
                rule_id=f"{rule['id']}/placeholder-remaining",
                severity=rule.get("severity", SEV_BLOCKER),
                source=src,
                quote=quote,
                evidence=[{"what": "Section still contains square-bracket placeholders.",
                            "output": raw.strip()[:200]}],
                suggested_fix=rule.get("failure_message", ""),
                confidence=0.95,
            )
        # Check for vague language
        vague = re.compile(
            r'\b(some data|a volume|an input file|a file|some input|'
            r'test data|sample input|a dataset)\b', re.IGNORECASE)
        if vague.search(raw):
            return make_finding(
                rule_id=f"{rule['id']}/vague-data",
                severity=rule.get("severity", SEV_BLOCKER),
                source=src,
                quote=quote,
                evidence=[{"what": "Section uses vague data description instead of named real dataset.",
                            "output": raw.strip()[:200]}],
                suggested_fix=rule.get("failure_message", ""),
                confidence=0.78,
            )
        return None
    return check_template_field(rule, body, "One real example", extra)


def check_pr_proof_attached(rule: dict, body: str, diff: str,
                              meta: dict | None) -> dict:
    def extra(raw, rule, src, quote):
        if not has_image_or_media(raw):
            return make_finding(
                rule_id=f"{rule['id']}/no-artefact",
                severity=rule.get("severity", SEV_BLOCKER),
                source=src,
                quote=quote,
                evidence=[{"what": "Proof section has text but no artefact "
                                   "(no image, no video link, no terminal output block, no table).",
                            "output": raw.strip()[:200]}],
                suggested_fix=rule.get("failure_message", ""),
                confidence=0.88,
            )
        return None
    return check_template_field(rule, body, "Proof", extra)


def check_proof_same_input(rule: dict, body: str, diff: str,
                            meta: dict | None) -> dict:
    src = fmt_source(rule.get("source"))
    quote = rule.get("quote", "")
    rule_id = rule["id"]

    example_raw = extract_section(body, "One real example") or ""
    proof_raw = extract_section(body, "Proof") or ""

    # Extract data references from each section
    data_re = re.compile(
        r'(?:Scroll\s*\d|PHerc[\w\s]*|paths/[\w/]+|[\w]{8,}\.(?:obj|volpkg|tifxyz)|'
        r'segment\s+[\w]+|[\w]{8,}\.obj)',
        re.IGNORECASE)

    example_refs = set(m.group(0).lower() for m in data_re.finditer(example_raw))
    proof_refs = set(m.group(0).lower() for m in data_re.finditer(proof_raw))

    # Check for "before/after" structure in proof
    has_before_after = (
        re.search(r'#\s*before\b', proof_raw, re.IGNORECASE) and
        re.search(r'#\s*after\b', proof_raw, re.IGNORECASE)
    )

    # Check if proof says what to look at
    look_at = bool(re.search(
        r'(?:look at|see the|compare|what we should|highlighted|scale|'
        r'output|result|exit code|grid size|valid points)',
        proof_raw, re.IGNORECASE))

    # If the proof uses a different input but explicitly explains why, accept
    different_inputs = example_refs and proof_refs and not example_refs.intersection(proof_refs)
    has_justification = bool(re.search(
        r'(?:without .{0,20}data|no data|no checkout|two lines|'
        r'minimal reproduction|reproduce the failure|OS-level|platform|'
        r'Windows|without full|cannot claim)',
        body, re.IGNORECASE))

    if different_inputs and not has_justification:
        return make_finding(
            rule_id=rule_id,
            severity=rule.get("severity", SEV_MAJOR),
            source=src,
            quote=quote,
            evidence=[{
                "what": "Proof and example may use different datasets without explanation",
                "output": f"example refs: {sorted(example_refs)[:3]}; "
                          f"proof refs: {sorted(proof_refs)[:3]}",
            }],
            suggested_fix=rule.get("failure_message", ""),
            confidence=0.62,
        )

    if not look_at:
        return make_finding(
            rule_id=f"{rule_id}/no-focus-indicator",
            severity=SEV_MAJOR,
            source=src,
            quote=quote,
            evidence=[{
                "what": "Proof does not clearly say what the reviewer should look at",
                "output": proof_raw.strip()[:200],
            }],
            suggested_fix=rule.get("failure_message", ""),
            confidence=0.65,
        )

    return pass_finding(rule_id, src, quote,
        "Proof and example appear to use consistent input; reviewer focus is identified.")


def check_verification_checkbox(rule: dict, body: str, diff: str,
                                 meta: dict | None) -> dict:
    """
    The verification checkbox is NEVER machine-verifiable.
    Always emit a major/unverifiable-by-machine finding regardless of state.
    """
    src = fmt_source(rule.get("source"))
    quote = rule.get("quote", "")

    state = checkbox_state(body)
    if state == "ticked":
        checkbox_desc = "- [x]  (ticked)"
    elif state == "unticked":
        checkbox_desc = "- [ ]  (unticked)"
    else:
        checkbox_desc = "absent"

    return make_finding(
        rule_id="pr-verification-checkbox/unverifiable-by-machine",
        severity=SEV_MAJOR,
        source=src,
        quote=quote,
        evidence=[
            {
                "what": "Checkbox state in raw Markdown",
                "output": checkbox_desc,
            },
            {
                "what": "Machine limitation",
                "output": (
                    "A ticked checkbox does not prove the contributor ran the code. "
                    "A human reviewer must confirm: (1) does the Before section describe "
                    "something this diff would actually change? (2) does the After section "
                    "describe a result that this diff would actually produce? "
                    "(3) do the screenshots/output blocks match the diff's changes?"
                ),
            },
        ],
        suggested_fix=(
            "Human reviewer: confirm the contributor personally ran this PR's code on the "
            "stated data and that the Before/After sections plausibly come from this diff."
        ),
        confidence=1.0,
    )


def check_time_limit(rule: dict, body: str, diff: str, meta: dict | None,
                     eval_date: datetime) -> dict:
    """
    Check pr-inactivity-14-days and pr-age-28-days from meta.json timestamps.
    """
    src = fmt_source(rule.get("source"))
    quote = rule.get("quote", "")
    rule_id = rule["id"]
    sev = rule.get("severity", SEV_BLOCKER)

    if meta is None:
        return not_applicable_finding(
            rule_id, src,
            "No meta.json available; cannot compute PR age from timestamps.")

    labels = [lbl.get("name", "") for lbl in meta.get("labels", [])]
    has_keep_open = "keep-open" in labels

    created_at_str = meta.get("createdAt")
    updated_at_str = meta.get("updatedAt")

    if not created_at_str:
        return not_applicable_finding(rule_id, src, "meta.json has no createdAt field.")

    created_at = parse_iso(created_at_str)
    updated_at = parse_iso(updated_at_str) if updated_at_str else created_at

    if rule_id == "pr-inactivity-14-days":
        days_inactive = (eval_date - updated_at).days
        if has_keep_open:
            return pass_finding(rule_id, src, quote,
                f"PR has 'keep-open' label; exempt from 14-day inactivity limit.",
                confidence=1.0)
        if days_inactive > 14:
            return make_finding(
                rule_id=rule_id,
                severity=sev,
                source=src,
                quote=quote,
                evidence=[{"what": f"PR has been inactive for {days_inactive} days",
                            "output": f"updatedAt={updated_at_str}, eval_date={eval_date.date()}"}],
                suggested_fix=rule.get("failure_message", ""),
                confidence=0.97,
            )
        return pass_finding(rule_id, src, quote,
            f"PR was updated {days_inactive} days ago (< 14-day limit).")

    elif rule_id == "pr-age-28-days":
        days_open = (eval_date - created_at).days
        days_inactive = (eval_date - updated_at).days
        if has_keep_open:
            return pass_finding(rule_id, src, quote,
                "PR has 'keep-open' label; exempt from 28-day age limit.",
                confidence=1.0)
        # The 28-day check is an elif branch (fires only if inactive < 14 days)
        if days_inactive <= 14 and days_open > 28:
            return make_finding(
                rule_id=rule_id,
                severity=sev,
                source=src,
                quote=quote,
                evidence=[{"what": f"PR is {days_open} days old and still open",
                            "output": f"createdAt={created_at_str}, eval_date={eval_date.date()}"}],
                suggested_fix=rule.get("failure_message", ""),
                confidence=0.97,
            )
        return pass_finding(rule_id, src, quote,
            f"PR is {days_open} days old (< 28-day limit or already caught by inactivity check).")

    return not_applicable_finding(rule_id, src, "Unknown time-limit rule.")


def check_keep_open_exemption(rule: dict, body: str, diff: str,
                               meta: dict | None) -> dict:
    src = fmt_source(rule.get("source"))
    quote = rule.get("quote", "")
    rule_id = rule["id"]

    if meta is None:
        return not_applicable_finding(rule_id, src, "No meta.json available.")

    labels = [lbl.get("name", "") for lbl in meta.get("labels", [])]
    if "keep-open" in labels:
        # Check the body documents why
        has_reason = bool(re.search(
            r'(?:keep.open|keep open|extension|reason|because|due to)',
            body, re.IGNORECASE))
        if not has_reason:
            return make_finding(
                rule_id=rule_id,
                severity=rule.get("severity", SEV_NIT),
                source=src,
                quote=quote,
                evidence=[{"what": "'keep-open' label applied but PR body does not "
                                   "document the reason for the extension."}],
                suggested_fix=rule.get("failure_message", ""),
                confidence=0.70,
            )
        return pass_finding(rule_id, src, quote,
            "'keep-open' label applied and PR body documents the reason.")
    return pass_finding(rule_id, src, quote,
        "PR does not use the 'keep-open' label; rule is informational only.")


def check_large_pr_needs_approval(rule: dict, body: str, diff: str,
                                   meta: dict | None,
                                   reviews: list | None) -> dict:
    src = fmt_source(rule.get("source"))
    quote = rule.get("quote", "")
    rule_id = rule["id"]
    THRESHOLD = 20

    if meta is None:
        return not_applicable_finding(rule_id, src, "No meta.json available.")

    changed_files = meta.get("changedFiles", 0)
    is_draft = meta.get("isDraft", False)

    if is_draft:
        return pass_finding(rule_id, src, quote,
            f"PR is a draft; large-PR gate is skipped.")

    if changed_files <= THRESHOLD:
        return pass_finding(rule_id, src, quote,
            f"PR changes {changed_files} files (<= {THRESHOLD} threshold); "
            f"large-PR review gate does not apply.")

    if reviews is None:
        return make_finding(
            rule_id=f"{rule_id}/unverifiable",
            severity=SEV_MAJOR,
            source=src,
            quote=quote,
            evidence=[{"what": f"PR changes {changed_files} files (> {THRESHOLD}); "
                               f"no review data in corpus to verify approvals.",
                        "output": "reviews.json absent or empty"}],
            suggested_fix=rule.get("failure_message", ""),
            confidence=0.0,
        )

    author = (meta.get("author") or {}).get("login", "")
    approvals = [r for r in reviews
                 if r.get("state") == "APPROVED" and r.get("author", {}).get("login", "") != author]

    if len(approvals) < 1:
        return make_finding(
            rule_id=rule_id,
            severity=rule.get("severity", SEV_BLOCKER),
            source=src,
            quote=quote,
            evidence=[{"what": f"PR changes {changed_files} files (> {THRESHOLD}) "
                               f"with 0 non-author approving reviews.",
                        "output": f"approvals={len(approvals)}, changedFiles={changed_files}"}],
            suggested_fix=rule.get("failure_message", ""),
            confidence=0.90,
        )

    return pass_finding(rule_id, src, quote,
        f"PR changes {changed_files} files (> {THRESHOLD}) with {len(approvals)} approving review(s).")


def check_large_pr_draft_exempt(rule: dict, body: str, diff: str,
                                 meta: dict | None) -> dict:
    src = fmt_source(rule.get("source"))
    quote = rule.get("quote", "")
    rule_id = rule["id"]

    if meta is None:
        return not_applicable_finding(rule_id, src, "No meta.json available.")

    is_draft = meta.get("isDraft", False)
    return pass_finding(rule_id, src, quote,
        f"PR draft status: {is_draft}. "
        f"{'Large-PR gate is skipped (draft).' if is_draft else 'Gate applies if > 20 files.'}")


def check_codeowners_review_required(rule: dict, body: str, diff: str,
                                      meta: dict | None,
                                      reviews: list | None) -> dict:
    src = fmt_source(rule.get("source"))
    quote = rule.get("quote", "")
    rule_id = rule["id"]

    # CODEOWNERS map from contract.yml
    CODEOWNERS = [
        (re.compile(r'^deprecated/crackle-viewer/'), ["jrudolph"]),
        (re.compile(r'^deprecated/vesuvius-c/'), ["jrudolph"]),
        (re.compile(r'^foundation/'), ["jrudolph"]),
        (re.compile(r'^ink-detection/'), ["erdpx"]),
        (re.compile(r'^lasagna/'), ["hendrikschilling"]),
        (re.compile(r'^scrollprize\.org/'), ["skyward7187", "giorgioangel", "pmh47"]),
        (re.compile(r'^vesuvius/'), ["jrudolph", "bruniss"]),
        (re.compile(r'^volume-cartographer/'), ["hendrikschilling"]),
        (re.compile(r'^spiral-fitting/'), ["pmh47"]),
    ]
    DEFAULT_OWNERS = ["giorgioangel", "pmh47"]

    if meta is None:
        return not_applicable_finding(rule_id, src, "No meta.json available.")

    # If the PR is already merged, CODEOWNER review was satisfied at merge time.
    # Emit informational nit rather than a blocker so merged PRs validate clean.
    if meta.get("mergedAt"):
        return pass_finding(
            rule_id, src, quote,
            f"PR is already merged (mergedAt={meta['mergedAt']}); CODEOWNER review "
            f"was satisfied at merge. This check applies to pre-submission review only.",
            confidence=0.90,
        )

    # Determine which owners are required
    changed_paths = [f["path"] for f in meta.get("files", [])]
    required_owners: set[str] = set()
    for path in changed_paths:
        matched = False
        for pat, owners in CODEOWNERS:
            if pat.match(path):
                required_owners.update(owners)
                matched = True
                break
        if not matched:
            required_owners.update(DEFAULT_OWNERS)

    if not reviews:
        return make_finding(
            rule_id=f"{rule_id}/unverifiable",
            severity=SEV_MAJOR,
            source=src,
            quote=quote,
            evidence=[{
                "what": "No review data available; cannot verify CODEOWNER approval",
                "output": f"Required owners: {sorted(required_owners)}",
            }],
            suggested_fix=rule.get("failure_message", ""),
            confidence=0.0,
        )

    approved_by = {
        r.get("author", {}).get("login", "")
        for r in reviews
        if r.get("state") == "APPROVED"
    }

    missing_owners = required_owners - approved_by
    if missing_owners:
        return make_finding(
            rule_id=rule_id,
            severity=rule.get("severity", SEV_BLOCKER),
            source=src,
            quote=quote,
            evidence=[{
                "what": "CODEOWNER approval missing",
                "output": f"Required: {sorted(required_owners)}; "
                          f"approved by: {sorted(approved_by)}; "
                          f"missing: {sorted(missing_owners)}",
            }],
            suggested_fix=rule.get("failure_message", ""),
            confidence=0.90,
        )

    return pass_finding(rule_id, src, quote,
        f"All required CODEOWNER approvals present: {sorted(approved_by & required_owners)}")


def check_llm_disclosure(rule: dict, body: str, diff: str,
                          meta: dict | None) -> dict:
    src = fmt_source(rule.get("source"))
    quote = rule.get("quote", "")
    rule_id = rule["id"]

    explicit_disclosure = bool(LLM_TOOL_NAMES.search(body))

    if explicit_disclosure:
        m = LLM_TOOL_NAMES.search(body)
        snippet = body[max(0, m.start()-20):m.end()+40].replace('\n', ' ')
        return pass_finding(rule_id, src, quote,
            f"LLM use explicitly disclosed: \"{snippet[:120]}\"")

    # Check for bulk-LLM diff signatures
    total_changed = sum(1 for l in diff.splitlines()
                        if l.startswith('+') or l.startswith('-'))
    comment_ratio = 0.0
    if total_changed > 0:
        comment_lines = sum(1 for l in diff.splitlines()
                            if re.match(r'^[+-]\s*(?://|#|/\*|\*)', l))
        comment_ratio = comment_lines / total_changed

    subprojects = set()
    for line in diff.splitlines():
        if line.startswith("diff --git"):
            m = re.match(r'diff --git a/([^/]+)/', line)
            if m:
                subprojects.add(m.group(1))

    suspicious_signals = []
    if comment_ratio > 0.5 and total_changed > 20:
        suspicious_signals.append(f"high comment-change ratio ({comment_ratio:.0%})")
    if len(subprojects) > 4:
        suspicious_signals.append(f"spans {len(subprojects)} subprojects")

    if suspicious_signals:
        return make_finding(
            rule_id=rule_id,
            severity=rule.get("severity", SEV_MAJOR),
            source=src,
            quote=quote,
            evidence=[{
                "what": "LLM involvement suspected but not disclosed",
                "output": f"Signals: {'; '.join(suspicious_signals)}",
            }],
            suggested_fix=rule.get("failure_message", ""),
            confidence=0.60,
        )

    return pass_finding(rule_id, src, quote,
        "No LLM involvement detected (no explicit mention, no bulk-LLM diff signatures).",
        confidence=0.80)


# ---------------------------------------------------------------------------
# Rule dispatch table
# ---------------------------------------------------------------------------

def dispatch_rule(rule: dict, body: str, diff: str, meta: dict | None,
                  reviews: list | None, pr_types: set[str],
                  eval_date: datetime) -> dict:
    """Route a contract rule to its checker function."""
    rule_id = rule["id"]
    src = fmt_source(rule.get("source"))

    if not rule_applies(rule, pr_types):
        applies = rule.get("applies_to", "all")
        return not_applicable_finding(
            rule_id, src,
            f"Rule applies_to={applies!r}; this PR types are {sorted(pr_types)}.")

    dispatch: dict = {
        "real-scroll-data-origin": lambda: check_real_scroll_data_origin(rule, body, diff, meta),
        "bugfix-error-screenshot": lambda: check_bugfix_error_screenshot(rule, body, diff, meta, pr_types),
        "no-synthetic-data": lambda: check_no_synthetic_data(rule, body, diff, meta),
        "motivation-section": lambda: check_motivation_section(rule, body, diff, meta),
        "before-after-comparison": lambda: check_before_after_comparison(rule, body, diff, meta, pr_types),
        "llm-human-trigger": lambda: check_llm_human_trigger(rule, body, diff, meta),
        "llm-human-commentary": lambda: check_llm_human_commentary(rule, body, diff, meta),
        "llm-concise-description": lambda: check_llm_concise_description(rule, body, diff, meta),
        "llm-real-scroll-validation": lambda: check_llm_real_scroll_validation(rule, body, diff, meta),
        "llm-human-review": lambda: check_llm_human_review(rule, body, diff, meta),
        "llm-no-fishing-expedition": lambda: check_llm_no_fishing_expedition(rule, body, diff, meta),
        "pr-template-structure": lambda: check_pr_template_structure(rule, body, diff, meta),
        "pr-one-sentence-summary": lambda: check_pr_one_sentence_summary(rule, body, diff, meta),
        "pr-one-real-example": lambda: check_pr_one_real_example(rule, body, diff, meta),
        "pr-before-section": lambda: check_template_field(rule, body, "Before"),
        "pr-after-section": lambda: check_template_field(rule, body, "After this PR"),
        "pr-proof-attached": lambda: check_pr_proof_attached(rule, body, diff, meta),
        "proof-same-input": lambda: check_proof_same_input(rule, body, diff, meta),
        "pr-usefulness-section": lambda: check_template_field(rule, body, "Why / where this is useful"),
        "pr-verification-checkbox": lambda: check_verification_checkbox(rule, body, diff, meta),
        "pr-inactivity-14-days": lambda: check_time_limit(rule, body, diff, meta, eval_date),
        "pr-age-28-days": lambda: check_time_limit(rule, body, diff, meta, eval_date),
        "pr-keep-open-exemption": lambda: check_keep_open_exemption(rule, body, diff, meta),
        "large-pr-needs-approval": lambda: check_large_pr_needs_approval(rule, body, diff, meta, reviews),
        "large-pr-draft-exempt": lambda: check_large_pr_draft_exempt(rule, body, diff, meta),
        "codeowners-review-required": lambda: check_codeowners_review_required(rule, body, diff, meta, reviews),
        "llm-disclosure": lambda: check_llm_disclosure(rule, body, diff, meta),
    }

    handler = dispatch.get(rule_id)
    if handler is None:
        # Unknown rule — emit nit noting it needs a handler
        return make_finding(
            rule_id=f"{rule_id}/no-handler",
            severity=SEV_NIT,
            source=src,
            quote=rule.get("quote", ""),
            evidence=[{"what": f"No handler implemented for rule '{rule_id}'; "
                               f"check contract.yml for new rules."}],
            suggested_fix="Add a handler for this rule in check_contract.py.",
            confidence=0.0,
        )

    try:
        return handler()
    except Exception as e:
        return make_finding(
            rule_id=f"{rule_id}/handler-error",
            severity=SEV_NIT,
            source=src,
            quote=None,
            evidence=[{"what": f"Handler for '{rule_id}' raised an exception.",
                        "output": str(e)}],
            suggested_fix="Fix the handler in check_contract.py.",
            confidence=0.0,
        )


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def run(body: str, diff: str, meta: dict | None, reviews: list | None,
        contract_path: Path, eval_date: datetime) -> list[dict]:
    """Run all contract rules against the PR. Return list of findings."""

    try:
        with open(contract_path) as f:
            contract_data = yaml.safe_load(f)
    except Exception as e:
        return [error_finding(f"Cannot load {contract_path}: {e}")]

    # contract.yml is a list of one object with a 'rules' key
    if isinstance(contract_data, list):
        rules = []
        for item in contract_data:
            if isinstance(item, dict) and "rules" in item:
                rules.extend(item["rules"])
    elif isinstance(contract_data, dict) and "rules" in contract_data:
        rules = contract_data["rules"]
    else:
        return [error_finding(f"Unexpected contract.yml structure: {type(contract_data)}")]

    if not rules:
        return [error_finding("contract.yml contains no rules.")]

    pr_types = detect_pr_types(body, diff, meta)
    findings = []

    for rule in rules:
        if not isinstance(rule, dict) or "id" not in rule:
            continue
        finding = dispatch_rule(rule, body, diff, meta, reviews, pr_types, eval_date)
        findings.append(finding)

    return findings


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--pr", type=int, help="PR number; loads from corpus/")
    parser.add_argument("--body", help="Path to PR body markdown file")
    parser.add_argument("--diff", help="Path to PR diff patch file")
    parser.add_argument("--meta", help="Path to PR meta JSON file")
    parser.add_argument("--contract", default="contract.yml",
                        help="Path to contract.yml (default: contract.yml)")
    parser.add_argument("--corpus", default="corpus",
                        help="Corpus directory (default: corpus/)")
    parser.add_argument("--verbose", action="store_true")
    parser.add_argument("--eval-date",
                        help="ISO date to use as today for time-limit checks (default: now)")
    args = parser.parse_args()

    corpus = Path(args.corpus)

    # Determine eval_date
    if args.eval_date:
        eval_date = datetime.fromisoformat(args.eval_date).replace(tzinfo=timezone.utc)
    else:
        eval_date = datetime.now(timezone.utc)

    # Load inputs
    body = ""
    diff = ""
    meta = None
    reviews = None

    if args.pr is not None:
        pr_dir = corpus / str(args.pr)
        body_path = pr_dir / "body.md"
        diff_path = pr_dir / "diff.patch"
        meta_path = pr_dir / "meta.json"
        reviews_path = pr_dir / "reviews.json"

        if not pr_dir.exists():
            print(json.dumps([error_finding(
                f"No corpus directory for PR #{args.pr}: {pr_dir}")], indent=2))
            sys.exit(0)

        try:
            body = body_path.read_text()
        except Exception:
            body = ""
        try:
            diff = diff_path.read_text()
        except Exception:
            diff = ""
        try:
            meta = json.loads(meta_path.read_text())
        except Exception:
            meta = None
        try:
            reviews_raw = json.loads(reviews_path.read_text())
            reviews = reviews_raw if isinstance(reviews_raw, list) else None
        except Exception:
            reviews = None

    else:
        if args.body:
            try:
                body = Path(args.body).read_text()
            except Exception as e:
                print(json.dumps([error_finding(f"Cannot read body file: {e}")], indent=2))
                sys.exit(0)
        if args.diff:
            try:
                diff = Path(args.diff).read_text()
            except Exception as e:
                print(json.dumps([error_finding(f"Cannot read diff file: {e}")], indent=2))
                sys.exit(0)
        if args.meta:
            try:
                meta = json.loads(Path(args.meta).read_text())
            except Exception as e:
                meta = None

    if not body:
        print(json.dumps([error_finding(
            "No PR body provided. Use --pr <N> or --body <file>.")], indent=2))
        sys.exit(0)

    contract_path = Path(args.contract)
    if not contract_path.exists():
        print(json.dumps([error_finding(
            f"contract.yml not found at {contract_path}")], indent=2))
        sys.exit(0)

    findings = run(body, diff, meta, reviews, contract_path, eval_date)
    print(json.dumps(findings, indent=2))


if __name__ == "__main__":
    main()
