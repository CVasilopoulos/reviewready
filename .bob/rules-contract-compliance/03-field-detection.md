# Field Presence Detection

The PR template has six named sections. Detecting whether a section is
genuinely filled requires distinguishing three states, not two.

## The three states

### 1. Absent

The section heading is not present in the PR body at all. Detection:
```python
"**In one sentence:**" not in body
```
Emit: `severity` from contract rule, evidence: `"Heading absent from PR body."`

### 2. Present but blank

The heading is present but nothing follows it (or only whitespace) before the
next heading or end of document. Detection:
```python
section_text.strip() == ""
```
Emit: `severity` from contract rule, evidence: `"Heading present but section is empty."`

### 3. Present but placeholder only

The heading is present and the section contains content — but that content is
only the template's HTML comment placeholder, e.g.:
```
<!-- Explain what someone can do with this; don't list features. -->
```
Nothing else. Detection:
```python
import re
# Strip whitespace, check if only HTML comments remain
stripped = re.sub(r'<!--.*?-->', '', section_text, flags=re.DOTALL).strip()
stripped == ""  # True = placeholder-only
```
This is the **most misleading case**: it looks filled in at a glance, it
renders as invisible in GitHub's UI, and it could trick a fast reviewer.
Always call it out explicitly.
Emit: `severity` from contract rule, evidence: `"Section contains only the template HTML placeholder comment; the actual field was not filled in."`

### 4. Present and filled (genuine content)

The heading is present and the section contains non-empty text after removing
the placeholder comment.
Emit: pass finding (nit).

## The verification checkbox: a special case

The template line is:
```
- [ ] I personally verified that the example and proof above were produced by
  this PR on the stated data.
```

When a contributor ticks it (`- [x]` or `- [X]`), the raw Markdown changes.
**A ticked checkbox must NEVER be reported as passing this rule.**

Regardless of whether the checkbox is ticked or unticked, emit:
```json
{
  "checker": "contract-compliance",
  "severity": "major",
  "rule": {
    "id": "pr-verification-checkbox/unverifiable-by-machine",
    "source": ".github/pull_request_template.md:13",
    "quote": "- [ ] I personally verified that the example and proof above were produced by this PR on the stated data."
  },
  "evidence": [
    {
      "what": "Checkbox state in raw Markdown",
      "output": "- [x]  (ticked)" // or "- [ ]  (unticked)" or "absent"
    },
    {
      "what": "Machine limitation",
      "output": "A ticked box does not prove the contributor ran the code. A human reviewer must confirm this claim by reading the Before/After sections and asking whether the results plausibly come from this diff."
    }
  ],
  "suggested_fix": "Human reviewer: confirm the contributor personally ran this PR's code on the stated data and the Before/After sections match the results.",
  "confidence": 1.0
}
```

This is not a failure — it is a human-required confirmation. Emit it on every
PR regardless of checkbox state. Do not upgrade its severity to blocker.

## Bugfix artefact detection

For `bugfix-error-screenshot`: a "screenshot or terminal block" includes:
- An embedded image: `![alt](url)` or `<img ... />`
- A GitHub file attachment URL: `https://github.com/user-attachments/assets/...`
- A fenced code block immediately under the Before or Proof section

Two artefacts required: one showing the error before, one showing success after.

## Placeholder comment fingerprints

The villa PR template uses comments in this style:
```
<!-- Explain what someone can do with this; don't list features. -->
<!-- What happened without this PR? -->
<!-- What happens now? -->
<!-- Attach the image, video, output, or benchmark... -->
<!-- Who would use this result, and what can they do next? -->
```
Any section whose only non-whitespace content matches `^<!--.*-->$` (single
line) or is entirely enclosed in `<!-- ... -->` is placeholder-only.
