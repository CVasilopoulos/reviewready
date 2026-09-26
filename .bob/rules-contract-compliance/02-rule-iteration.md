# Rule Iteration Protocol

## Core invariant

Iterate over **every entry** in `contract.yml`'s `rules` array.
Never skip a rule. Never add checks that are not in `contract.yml`.
If `contract.yml` gains or loses rules, the checker's behaviour changes
automatically — no code change needed.

## `applies_to` filtering

Each rule has an `applies_to` field: `all`, `bugfix`, `feature`,
`llm-assisted`, or a YAML list combining these.

Before evaluating a rule, determine which categories the candidate PR falls
into:

| Category | Detection |
|---|---|
| `bugfix` | Title or branch name contains `fix`, `bug`, or `crash` (case-insensitive); OR `Before:` section describes an error/crash/failure |
| `feature` | Title/branch contains `feat`, `add`, `new`, `implement`; OR no bugfix signals present |
| `llm-assisted` | Body/commits/branch explicitly mention an LLM tool name (ChatGPT, Claude, Copilot, Cursor, Codex, Gemini); OR diff shows bulk-LLM signatures (mass reformatting, wholesale docstring/comment generation, changes spanning 4+ unrelated subproject directories with no single bug) |

Rules with `applies_to: all` run unconditionally.
Rules with `applies_to: llm-assisted` run only if the PR is detected as
llm-assisted. If LLM use is suspected but not explicitly disclosed, emit the
`llm-disclosure` finding (major) and still run the llm-* checks.

## Findings for inapplicable rules

When a rule does not apply (e.g. `applies_to: bugfix` but PR is not a bugfix),
emit a single **nit** finding with `rule.id` = `<contract-rule-id>/not-applicable`,
`suggested_fix` = "Rule does not apply to this PR type.", and `confidence` 1.0.

This ensures every rule produces exactly one finding, making the output
auditable: a reviewer can verify that no rule was silently skipped.

## Pass findings

When a rule applies and the PR satisfies it, emit a **nit** finding with
`rule.id` = `<contract-rule-id>/pass`, `evidence` describing what was checked,
and `confidence` reflecting certainty of the pass. This preserves the
one-finding-per-rule invariant and lets a reviewer see what passed.

## Ordering

Emit findings in the same order as the rules in `contract.yml`. Do not sort
by severity.

## Source citation

For every finding, populate `rule.source` with the exact value from the
`source` field in `contract.yml`. For rules with `source: inferred`, set
`rule.source` to `"inferred"` and include the `rationale` in `rule.quote`.
For rules with a `source.file` + `source.lines` object, format as
`"<file>:<lines>"` (e.g. `"CONTRIBUTING.md:17-18"`).
