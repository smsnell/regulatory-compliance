#!/usr/bin/env python3
"""Scan Git's index, never the worktree or a binary-skipping patch."""
import argparse
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile


ROOT = Path(__file__).resolve().parents[1]
RAW_ROOTS = ('docs/verification/u05-anonymous-live/',
             'docs/verification/u05-live/', 'u07-verification/')


def git(*args):
    return subprocess.check_output(['git', *args])


def forbidden(path):
    parts = Path(path).parts
    return (path.startswith(RAW_ROOTS) or ('.staging' in parts
            and not path.startswith('tests/fixtures/sanitized/'))
            or any(p in {'.aws', '.ssh', '.evidence'} for p in parts)
            or any(p == '.env' or p.startswith('.env.') and p != '.env.example'
                   for p in parts))


def scan(data, scanner, config):
    # An empty private cwd prevents repository/global ignore files from hiding hits.
    # stdin scans every byte regardless of filename, MIME, NULs or Git attributes.
    with tempfile.TemporaryDirectory(prefix='rci-secret-scan-') as cwd:
        return subprocess.run(
            [scanner, 'stdin', '--config', str(config), '--redact=100',
             '--no-banner', '--no-color', '--log-level=error',
             '--ignore-gitleaks-allow', '--max-decode-depth=2'],
            input=data, cwd=cwd, stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL).returncode


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--all', action='store_true', help='scan every indexed file')
    args = parser.parse_args()
    scanner = shutil.which('gitleaks')
    if not scanner:
        sys.exit('Secret guard: install Gitleaks 8.24.2+ (see docs/secret-safety.md).')
    names = (git('ls-files', '-z') if args.all else
             git('diff', '--cached', '--name-only', '--diff-filter=ACMRT', '-z'))
    failed = False
    for raw in names.split(b'\0'):
        if not raw:
            continue
        path = raw.decode('utf-8', 'surrogateescape')
        if forbidden(path):
            print(f'Secret guard: prohibited raw evidence/credential path {path!r}', file=sys.stderr)
            failed = True
            continue
        data = git('show', ':' + path)
        code = scan(data, scanner, ROOT / '.gitleaks.toml')
        if code:
            reason = 'possible secret' if code == 1 else 'scanner failed'
            print(f'Secret guard: {reason} in staged file {path!r}; values suppressed.', file=sys.stderr)
            failed = True
    return int(failed)


if __name__ == '__main__':
    try:
        sys.exit(main())
    except (OSError, subprocess.CalledProcessError):
        sys.exit('Secret guard: Git/scanner error; commit blocked.')
