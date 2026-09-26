#!/usr/bin/env bash
set -euo pipefail
cd "$(git rev-parse --show-toplevel)"
if command -v gitleaks >/dev/null 2>&1; then
  gitleaks detect --source . --no-banner --redact
  gitleaks git --no-banner --redact . 2>/dev/null || true
  exit 0
fi
echo "gitleaks not installed (brew install gitleaks); falling back to git grep"
pat='BOB_API_KEY|BOBSHELL_API_KEY|IBM_CLOUD_API_KEY|IBMCLOUD_API_KEY|ibm-coding-challenge|gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{20,}|AKIA[0-9A-Z]{16}|sk-[A-Za-z0-9]{20,}|-----BEGIN [A-Z ]*PRIVATE KEY|api[_-]?key["'"'"' ]*[:=]|Bearer [A-Za-z0-9._-]{20,}|password["'"'"' ]*[:=]'
status=0
git grep -nIE "$pat" -- . ':!scripts/secret-scan.sh' && status=1
git log -p --all | grep -nIE "$pat" | grep -v 'secret-scan.sh' | head -20 && status=1
if [ "$status" -ne 0 ]; then echo "SECRET SCAN: matches above must be reviewed before pushing"; exit 1; fi
echo "SECRET SCAN: clean"
