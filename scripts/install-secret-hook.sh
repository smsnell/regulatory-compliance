#!/bin/sh
set -eu
cd "$(git rev-parse --show-toplevel)"
command -v python3 >/dev/null
command -v gitleaks >/dev/null || { echo 'Install Gitleaks first; see docs/secret-safety.md.' >&2; exit 1; }
hook="$(git rev-parse --git-path hooks)/pre-commit"
if [ -n "$(git config --get core.hooksPath || true)" ]; then
    echo 'Existing core.hooksPath: add python3 scripts/secret_guard.py to your hook.' >&2
    exit 1
fi
if [ -e "$hook" ]; then
    if cmp -s scripts/pre-commit "$hook"; then exit 0; fi
    echo 'Existing pre-commit hook: add python3 scripts/secret_guard.py without replacing it.' >&2
    exit 1
fi
cp scripts/pre-commit "$hook"
chmod +x "$hook"
echo 'Secret guard installed; other Git/session-capture hooks preserved.'
